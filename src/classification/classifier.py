"""LLM-based review classification with batching, retries, and self-consistency checks."""

from __future__ import annotations
import asyncio
import json
from pathlib import Path

from config import CLEANED_DIR, CLASSIFIED_DIR, PROMPTS_DIR, settings
from src.utils.schema import RawReview, ClassifiedReview, Theme, Sentiment
from src.utils.llm import classify_review, get_cost_breakdown
from src.utils import logging as log


def _load_prompt() -> str:
    prompt_file = PROMPTS_DIR / "classification_v1.txt"
    return prompt_file.read_text(encoding="utf-8")


def _build_user_prompt(review: RawReview) -> str:
    return (
        f"Product: {review.product_name}\n"
        f"Brand: {review.brand}\n"
        f"Category: {review.category}\n"
        f"Rating: {review.rating}/5\n"
        f"Title: {review.title}\n"
        f"Review:\n{review.review_text}"
    )


def _parse_classification(raw: dict, review: RawReview) -> ClassifiedReview | None:
    try:
        if raw.get("parse_error"):
            return None

        primary = raw.get("primary_theme", "usability")
        if primary not in [t.value for t in Theme]:
            primary = "usability"

        sentiment = raw.get("sentiment", "neutral")
        if sentiment not in [s.value for s in Sentiment]:
            sentiment = "neutral"

        return ClassifiedReview(
            review_id=review.review_id,
            product_id=review.product_id,
            product_name=review.product_name,
            brand=review.brand,
            category=review.category,
            rating=review.rating,
            title=review.title,
            review_text=review.review_text,
            date=review.date,
            verified_purchase=review.verified_purchase,
            helpful_votes=review.helpful_votes,
            source=review.source,
            primary_theme=Theme(primary),
            secondary_themes=[Theme(t) for t in raw.get("secondary_themes", []) if t in [x.value for x in Theme]],
            sentiment=Sentiment(sentiment),
            sentiment_confidence=float(raw.get("sentiment_confidence", 0.5)),
            severity=max(1, min(5, int(raw.get("severity", 3)))),
            features_mentioned=raw.get("features_mentioned", []),
            failure_mode=raw.get("failure_mode"),
            failure_timeline=raw.get("failure_timeline"),
            competitor_mentions=raw.get("competitor_mentions", []),
            has_actionable_signal=bool(raw.get("has_actionable_signal", False)),
            actionable_detail=raw.get("actionable_detail", ""),
            is_shipping_complaint=bool(raw.get("is_shipping_complaint", False)),
            key_phrases=raw.get("key_phrases", []),
        )
    except Exception as e:
        log.warn(f"Failed to parse classification for {review.review_id}: {e}")
        return None


async def classify_batch(
    reviews: list[RawReview],
    batch_size: int = 50,
    use_edge_case_model: bool = True,
) -> list[ClassifiedReview]:
    """Classify reviews in batches with progress tracking."""

    log.section("LLM Classification")
    system_prompt = _load_prompt()
    classified: list[ClassifiedReview] = []
    failed: list[str] = []

    total = len(reviews)
    with log.make_progress() as progress:
        task = progress.add_task("Classifying reviews", total=total)

        for batch_start in range(0, total, batch_size):
            batch = reviews[batch_start:batch_start + batch_size]

            tasks = [
                _classify_single(r, system_prompt, use_edge_case_model)
                for r in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for r, result in zip(batch, results):
                if isinstance(result, Exception):
                    log.warn(f"Error classifying {r.review_id}: {result}")
                    failed.append(r.review_id)
                elif result is not None:
                    classified.append(result)
                else:
                    failed.append(r.review_id)
                progress.advance(task)

    _save_classified(classified)

    cost = get_cost_breakdown()
    log.section("Classification Results")
    log.info(f"Classified: {len(classified)}/{total}")
    log.info(f"Failed: {len(failed)}")
    log.info(f"LLM cost: ${cost['total_usd']:.2f}")
    log.info(f"Cost breakdown: {json.dumps(cost['by_model'], indent=2)}")

    return classified


async def _classify_single(
    review: RawReview,
    system_prompt: str,
    use_edge_case: bool,
) -> ClassifiedReview | None:
    user_prompt = _build_user_prompt(review)

    model = None
    if use_edge_case and _is_edge_case(review):
        model = settings.edge_case_model

    raw = await classify_review(
        review_text=review.review_text,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
    )

    return _parse_classification(raw, review)


def _is_edge_case(review: RawReview) -> bool:
    """Route ambiguous reviews to the stronger model."""
    if review.rating == 3:
        return True
    if len(review.review_text) > 1000:
        return True
    text_lower = review.review_text.lower()
    if any(w in text_lower for w in ["however", "but", "although", "on the other hand"]):
        if review.rating in (2, 4):
            return True
    return False


async def run_consistency_check(
    reviews: list[RawReview],
    sample_size: int = 100,
) -> dict:
    """Run 100 reviews through classification twice and measure agreement."""

    log.section("Self-Consistency Check")
    import random
    random.seed(42)
    sample = random.sample(reviews, min(sample_size, len(reviews)))

    system_prompt = _load_prompt()

    run1_results = []
    run2_results = []

    for r in sample:
        user_prompt = _build_user_prompt(r)
        r1 = await classify_review(r.review_text, system_prompt, user_prompt, temperature=0.0)
        r2 = await classify_review(r.review_text, system_prompt, user_prompt + "\n\n(Second pass — classify independently)", temperature=0.1)
        run1_results.append(r1)
        run2_results.append(r2)

    agreements = {
        "primary_theme": 0,
        "sentiment": 0,
        "severity_exact": 0,
        "severity_within_1": 0,
    }

    for r1, r2 in zip(run1_results, run2_results):
        if r1.get("primary_theme") == r2.get("primary_theme"):
            agreements["primary_theme"] += 1
        if r1.get("sentiment") == r2.get("sentiment"):
            agreements["sentiment"] += 1
        s1 = r1.get("severity", 3)
        s2 = r2.get("severity", 3)
        if s1 == s2:
            agreements["severity_exact"] += 1
        if abs(s1 - s2) <= 1:
            agreements["severity_within_1"] += 1

    n = len(sample)
    rates = {k: v / n for k, v in agreements.items()}

    log.section("Consistency Results")
    for k, v in rates.items():
        status = "PASS" if v >= 0.8 else "WARN" if v >= 0.7 else "FAIL"
        log.info(f"  {k}: {v:.1%} [{status}]")

    return {"sample_size": n, "agreement_rates": rates, "raw_counts": agreements}


def _save_classified(reviews: list[ClassifiedReview]):
    out = CLASSIFIED_DIR / "reviews_classified.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in reviews:
            f.write(r.model_dump_json() + "\n")
    log.success(f"Saved {len(reviews)} classified reviews to {out}")


def load_classified() -> list[ClassifiedReview]:
    path = CLASSIFIED_DIR / "reviews_classified.jsonl"
    if not path.exists():
        return []
    reviews = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                reviews.append(ClassifiedReview.model_validate_json(line))
    return reviews
