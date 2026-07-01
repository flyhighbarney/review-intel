"""Review cleaning pipeline — dedup, spam detection, language filtering, shipping-only removal."""

from __future__ import annotations
import hashlib
import re
from collections import defaultdict

import pandas as pd
from langdetect import detect, LangDetectException
from rapidfuzz import fuzz

from config import RAW_DIR, CLEANED_DIR
from src.utils.schema import RawReview
from src.utils import logging as log


class CleaningPipeline:
    def __init__(self):
        self.stats = defaultdict(int)

    def run(self, reviews: list[RawReview] | None = None) -> list[RawReview]:
        """Full cleaning pipeline. Reads from raw dir if no reviews passed."""
        log.section("Cleaning Pipeline")

        if reviews is None:
            reviews = self._load_raw()

        self.stats["input"] = len(reviews)
        log.info(f"Starting with {len(reviews)} raw reviews")

        reviews = self._remove_empty(reviews)
        reviews = self._deduplicate(reviews)
        reviews = self._filter_language(reviews)
        reviews = self._remove_spam(reviews)
        reviews = self._flag_shipping_only(reviews)
        reviews = self._normalize_text(reviews)

        self.stats["output"] = len(reviews)
        self._save_cleaned(reviews)
        self._print_stats()
        return reviews

    def _load_raw(self) -> list[RawReview]:
        reviews = []
        for f in RAW_DIR.glob("*.jsonl"):
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        reviews.append(RawReview.model_validate_json(line))
        return reviews

    def _remove_empty(self, reviews: list[RawReview]) -> list[RawReview]:
        out = [r for r in reviews if len(r.review_text.strip()) >= 20]
        self.stats["removed_empty"] = len(reviews) - len(out)
        return out

    def _deduplicate(self, reviews: list[RawReview]) -> list[RawReview]:
        seen_exact: set[str] = set()
        seen_fuzzy: list[str] = []
        unique: list[RawReview] = []

        for r in reviews:
            text_hash = hashlib.md5(r.review_text.lower().strip().encode()).hexdigest()
            if text_hash in seen_exact:
                self.stats["removed_exact_dup"] += 1
                continue
            seen_exact.add(text_hash)

            is_fuzzy_dup = False
            normalized = r.review_text.lower().strip()[:200]
            for prev in seen_fuzzy[-500:]:
                if fuzz.ratio(normalized, prev) > 95:
                    is_fuzzy_dup = True
                    self.stats["removed_fuzzy_dup"] += 1
                    break

            if not is_fuzzy_dup:
                seen_fuzzy.append(normalized)
                unique.append(r)

        return unique

    def _filter_language(self, reviews: list[RawReview]) -> list[RawReview]:
        english: list[RawReview] = []
        for r in reviews:
            try:
                lang = detect(r.review_text[:500])
                if lang == "en":
                    english.append(r)
                else:
                    self.stats["removed_non_english"] += 1
            except LangDetectException:
                english.append(r)
        return english

    def _remove_spam(self, reviews: list[RawReview]) -> list[RawReview]:
        clean: list[RawReview] = []
        spam_patterns = [
            r"(?i)buy\s+now\s+at",
            r"(?i)visit\s+(my|our)\s+(website|site|link)",
            r"(?i)(discount|coupon)\s+code",
            r"(?i)click\s+here",
            r"(?i)free\s+trial",
            r"(?i)100%\s+guaranteed",
        ]
        compiled = [re.compile(p) for p in spam_patterns]

        for r in reviews:
            is_spam = False
            for pattern in compiled:
                if pattern.search(r.review_text):
                    is_spam = True
                    break

            if not is_spam and self._is_bot_pattern(r):
                is_spam = True

            if is_spam:
                self.stats["removed_spam"] += 1
            else:
                clean.append(r)
        return clean

    def _is_bot_pattern(self, r: RawReview) -> bool:
        text = r.review_text
        if len(text) < 30 and r.rating == 5.0 and text.count("!") > 3:
            return True
        words = text.split()
        if len(words) > 10:
            unique_ratio = len(set(w.lower() for w in words)) / len(words)
            if unique_ratio < 0.3:
                return True
        return False

    def _flag_shipping_only(self, reviews: list[RawReview]) -> list[RawReview]:
        """Don't remove shipping reviews — flag them so the classifier can skip."""
        shipping_patterns = [
            r"(?i)^(arrived|delivered|shipping|package|box)\b",
            r"(?i)\b(ups|fedex|usps|delivery driver)\b",
        ]
        product_patterns = [
            r"(?i)\b(suction|power|noise|battery|clean|brush|blend|cook|brew|fry|heat)\b",
        ]
        compiled_ship = [re.compile(p) for p in shipping_patterns]
        compiled_prod = [re.compile(p) for p in product_patterns]

        for r in reviews:
            has_shipping = any(p.search(r.review_text) for p in compiled_ship)
            has_product = any(p.search(r.review_text) for p in compiled_prod)
            if has_shipping and not has_product:
                self.stats["flagged_shipping"] += 1

        return reviews

    def _normalize_text(self, reviews: list[RawReview]) -> list[RawReview]:
        for r in reviews:
            text = r.review_text
            text = re.sub(r"\s+", " ", text).strip()
            text = re.sub(r"[^\x20-\x7E\n]", "", text)
            r.review_text = text
            r.title = re.sub(r"\s+", " ", r.title).strip()
        return reviews

    def _save_cleaned(self, reviews: list[RawReview]):
        out = CLEANED_DIR / "reviews_cleaned.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for r in reviews:
                f.write(r.model_dump_json() + "\n")
        log.success(f"Saved {len(reviews)} cleaned reviews to {out}")

    def _print_stats(self):
        log.section("Cleaning Stats")
        for k, v in sorted(self.stats.items()):
            log.info(f"  {k}: {v}")
        retained = self.stats.get("output", 0)
        total = self.stats.get("input", 1)
        log.info(f"  retention_rate: {retained/total*100:.1f}%")
