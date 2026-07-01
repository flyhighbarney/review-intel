"""Classification evaluation — hallucination detection and quality checks."""

from __future__ import annotations
import json
import re
from collections import defaultdict

from src.utils.schema import ClassifiedReview, Theme
from src.utils import logging as log


class ClassificationEvaluator:
    """Catches LLM hallucinations and measures classification quality."""

    def __init__(self, reviews: list[ClassifiedReview]):
        self.reviews = reviews
        self.issues: list[dict] = []

    def run_all_checks(self) -> dict:
        log.section("Classification Quality Evaluation")

        results = {
            "hallucination_check": self.hallucination_check(),
            "feature_grounding": self.feature_grounding_check(),
            "sentiment_rating_alignment": self.sentiment_rating_alignment(),
            "severity_distribution": self.severity_distribution_check(),
            "coverage_stats": self.coverage_stats(),
        }

        log.info(f"Total quality issues found: {len(self.issues)}")
        return results

    def hallucination_check(self) -> dict:
        """Check if extracted key_phrases actually appear in review text."""
        total_phrases = 0
        grounded = 0
        hallucinated = 0
        hallucination_examples = []

        for r in self.reviews:
            for phrase in r.key_phrases:
                total_phrases += 1
                if phrase.lower() in r.review_text.lower():
                    grounded += 1
                else:
                    words = phrase.lower().split()
                    text_lower = r.review_text.lower()
                    word_matches = sum(1 for w in words if w in text_lower)
                    if word_matches / max(len(words), 1) >= 0.7:
                        grounded += 1
                    else:
                        hallucinated += 1
                        if len(hallucination_examples) < 10:
                            hallucination_examples.append({
                                "review_id": r.review_id,
                                "phrase": phrase,
                                "text_snippet": r.review_text[:200],
                            })

        rate = grounded / max(total_phrases, 1)
        status = "PASS" if rate >= 0.90 else "WARN" if rate >= 0.80 else "FAIL"
        log.info(f"Key phrase grounding: {rate:.1%} [{status}]")

        if status != "PASS":
            self.issues.append({
                "type": "hallucination",
                "grounding_rate": rate,
                "examples": hallucination_examples,
            })

        return {
            "total_phrases": total_phrases,
            "grounded": grounded,
            "hallucinated": hallucinated,
            "grounding_rate": round(rate, 4),
            "examples": hallucination_examples,
        }

    def feature_grounding_check(self) -> dict:
        """Check if features_mentioned are actually in the review text."""
        total = 0
        grounded = 0

        for r in self.reviews:
            for feature in r.features_mentioned:
                total += 1
                if feature.lower() in r.review_text.lower():
                    grounded += 1
                else:
                    parts = feature.lower().split()
                    if any(p in r.review_text.lower() for p in parts):
                        grounded += 1

        rate = grounded / max(total, 1)
        status = "PASS" if rate >= 0.85 else "WARN"
        log.info(f"Feature grounding: {rate:.1%} [{status}]")

        return {"total": total, "grounded": grounded, "rate": round(rate, 4)}

    def sentiment_rating_alignment(self) -> dict:
        """Check if sentiment aligns with star rating."""
        aligned = 0
        misaligned = 0
        misaligned_examples = []

        for r in self.reviews:
            if r.rating >= 4 and r.sentiment.value == "positive":
                aligned += 1
            elif r.rating <= 2 and r.sentiment.value == "negative":
                aligned += 1
            elif r.rating == 3 and r.sentiment.value in ("mixed", "neutral"):
                aligned += 1
            elif r.rating >= 4 and r.sentiment.value in ("mixed", "neutral"):
                aligned += 1
            elif r.rating <= 2 and r.sentiment.value == "mixed":
                aligned += 1
            else:
                misaligned += 1
                if len(misaligned_examples) < 5:
                    misaligned_examples.append({
                        "review_id": r.review_id,
                        "rating": r.rating,
                        "sentiment": r.sentiment.value,
                        "snippet": r.review_text[:100],
                    })

        total = aligned + misaligned
        rate = aligned / max(total, 1)
        status = "PASS" if rate >= 0.75 else "WARN"
        log.info(f"Sentiment-rating alignment: {rate:.1%} [{status}]")

        return {
            "aligned": aligned,
            "misaligned": misaligned,
            "rate": round(rate, 4),
            "examples": misaligned_examples,
        }

    def severity_distribution_check(self) -> dict:
        """Verify severity isn't all clustered at one level."""
        counts = defaultdict(int)
        for r in self.reviews:
            counts[r.severity] += 1

        total = len(self.reviews)
        dist = {k: round(v / total, 3) for k, v in sorted(counts.items())}

        max_concentration = max(dist.values()) if dist else 0
        status = "PASS" if max_concentration < 0.6 else "WARN"
        log.info(f"Severity distribution max concentration: {max_concentration:.1%} [{status}]")

        return {"distribution": dist, "max_concentration": max_concentration}

    def coverage_stats(self) -> dict:
        """What percentage of reviews got each field populated."""
        total = len(self.reviews)
        if total == 0:
            return {}

        stats = {
            "has_primary_theme": sum(1 for r in self.reviews if r.primary_theme) / total,
            "has_features": sum(1 for r in self.reviews if r.features_mentioned) / total,
            "has_failure_mode": sum(1 for r in self.reviews if r.failure_mode) / total,
            "has_key_phrases": sum(1 for r in self.reviews if r.key_phrases) / total,
            "has_actionable": sum(1 for r in self.reviews if r.has_actionable_signal) / total,
            "has_competitor_mention": sum(1 for r in self.reviews if r.competitor_mentions) / total,
            "shipping_complaints": sum(1 for r in self.reviews if r.is_shipping_complaint) / total,
        }

        for field, rate in stats.items():
            log.info(f"  {field}: {rate:.1%}")

        return {k: round(v, 4) for k, v in stats.items()}
