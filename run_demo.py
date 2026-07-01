"""Quick demo runner — generates synthetic data and runs analysis without LLM calls.

This produces a working dashboard with synthetic classified data,
no API keys required. Use this to validate the pipeline and dashboard
before connecting real data and LLM classification.
"""

from __future__ import annotations
import asyncio
import hashlib
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import CLASSIFIED_DIR, REPORTS_DIR, RAW_DIR, CLEANED_DIR
from src.ingestion.synthetic import generate_synthetic_reviews
from src.cleaning.pipeline import CleaningPipeline
from src.utils.schema import ClassifiedReview, Theme, Sentiment, Source
from src.utils import logging as log


def _simulate_classification(reviews) -> list[ClassifiedReview]:
    """Deterministic classification without LLM — for demo and testing."""
    log.section("Simulated Classification (no LLM)")
    random.seed(42)
    classified = []

    theme_map = {
        "power": Theme.POWER,
        "suction": Theme.POWER,
        "usability": Theme.USABILITY,
        "easy": Theme.USABILITY,
        "noise": Theme.NOISE,
        "loud": Theme.NOISE,
        "quiet": Theme.NOISE,
        "battery": Theme.BATTERY,
        "broke": Theme.DURABILITY,
        "broken": Theme.DURABILITY,
        "stopped working": Theme.DURABILITY,
        "cracked": Theme.DURABILITY,
        "peeling": Theme.DURABILITY,
        "clean": Theme.CLEANING,
        "price": Theme.PRICE_VALUE,
        "worth": Theme.PRICE_VALUE,
        "expensive": Theme.PRICE_VALUE,
        "size": Theme.SIZE,
        "small": Theme.SIZE,
        "large": Theme.SIZE,
        "heavy": Theme.SIZE,
        "smell": Theme.SMELL,
        "plastic smell": Theme.SMELL,
        "setup": Theme.SETUP,
        "customer service": Theme.CUSTOMER_SERVICE,
    }

    failure_modes = {
        Theme.DURABILITY: [
            "Motor failure", "Plastic component cracked", "Coating peeled",
            "Stopped powering on", "Battery won't hold charge", "Brush roll broke",
        ],
        Theme.NOISE: ["Excessive motor noise", "Grinding sound developed"],
        Theme.CLEANING: ["Filter clogging", "Difficult to disassemble"],
    }

    for r in reviews:
        text_lower = r.review_text.lower()

        theme = Theme.USABILITY
        for keyword, t in theme_map.items():
            if keyword in text_lower:
                theme = t
                break

        if r.rating >= 4:
            sentiment = Sentiment.POSITIVE
            confidence = 0.85 + random.random() * 0.15
        elif r.rating <= 2:
            sentiment = Sentiment.NEGATIVE
            confidence = 0.80 + random.random() * 0.20
        elif r.rating == 3:
            sentiment = Sentiment.MIXED
            confidence = 0.60 + random.random() * 0.30
        else:
            sentiment = Sentiment.NEUTRAL
            confidence = 0.70

        severity = max(1, min(5, 6 - int(r.rating)))
        if "safety" in text_lower or "dangerous" in text_lower:
            severity = 5

        failure = None
        timeline = None
        if sentiment == Sentiment.NEGATIVE and theme in failure_modes:
            failure = random.choice(failure_modes[theme])
            import re
            m = re.search(r"(\d+)\s*months?", text_lower)
            if m:
                timeline = f"{m.group(1)} months"

        competitor_mentions = []
        for brand_name in ["Dyson", "iRobot", "Vitamix", "Keurig", "Cosori", "Breville"]:
            if brand_name.lower() in text_lower and brand_name != r.brand:
                ctx = "favorable" if r.rating >= 4 else "unfavorable"
                competitor_mentions.append({"brand": brand_name, "context": ctx})

        words = r.review_text.split()
        phrases = []
        if len(words) > 5:
            start = random.randint(0, min(len(words) - 5, 10))
            phrases.append(" ".join(words[start:start+5]))

        features = []
        feature_keywords = [
            "dust cup", "brush roll", "filter", "motor", "battery", "handle",
            "basket", "blade", "grinder", "water tank", "screen", "nozzle",
            "hose", "cord", "charger", "app", "sensor", "suction",
        ]
        for fk in feature_keywords:
            if fk in text_lower:
                features.append(fk)

        classified.append(ClassifiedReview(
            review_id=r.review_id,
            product_id=r.product_id,
            product_name=r.product_name,
            brand=r.brand,
            category=r.category,
            rating=r.rating,
            title=r.title,
            review_text=r.review_text,
            date=r.date,
            verified_purchase=r.verified_purchase,
            helpful_votes=r.helpful_votes,
            source=r.source,
            primary_theme=theme,
            sentiment=sentiment,
            sentiment_confidence=round(confidence, 3),
            severity=severity,
            features_mentioned=features,
            failure_mode=failure,
            failure_timeline=timeline,
            competitor_mentions=competitor_mentions,
            has_actionable_signal=sentiment == Sentiment.NEGATIVE and severity >= 3,
            actionable_detail="Address reported failure mode" if failure else "",
            is_shipping_complaint=False,
            key_phrases=phrases,
        ))

    out = CLASSIFIED_DIR / "reviews_classified.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for c in classified:
            f.write(c.model_dump_json() + "\n")

    log.success(f"Classified {len(classified)} reviews (simulated)")
    return classified


def main():
    log.section("SharkNinja Review Intel — Demo Mode")
    log.info("Generating synthetic data + simulated classification (no API keys needed)")

    for d in [RAW_DIR, CLEANED_DIR, CLASSIFIED_DIR, REPORTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    # Phase 1
    reviews = generate_synthetic_reviews(count=5500)

    # Phase 2a
    pipeline = CleaningPipeline()
    cleaned = pipeline.run(reviews)

    # Phase 2b (simulated)
    classified = _simulate_classification(cleaned)

    # Phase 3
    from src.analysis.engine import AnalysisEngine
    engine = AnalysisEngine(classified)
    results = engine.run_all()

    REPORTS_DIR.mkdir(exist_ok=True)
    with open(REPORTS_DIR / "analysis_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    # Phase 2c
    from src.classification.evaluator import ClassificationEvaluator
    evaluator = ClassificationEvaluator(classified)
    eval_results = evaluator.run_all_checks()
    with open(REPORTS_DIR / "eval_results.json", "w", encoding="utf-8") as f:
        json.dump(eval_results, f, indent=2, default=str)

    log.section("Demo Complete")
    log.success(f"Reviews: {len(classified)}")
    log.success(f"Reports saved to: {REPORTS_DIR}")
    log.success("Launch dashboard: streamlit run src/dashboard/app.py")


if __name__ == "__main__":
    main()
