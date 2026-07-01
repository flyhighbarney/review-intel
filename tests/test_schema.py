"""Tests for data schema validation."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date
from src.utils.schema import RawReview, ClassifiedReview, Source, Theme, Sentiment


def test_raw_review_creation():
    r = RawReview(
        review_id="test_001",
        product_id="B0C7C6QMLR",
        product_name="Shark Stratos",
        brand="Shark",
        category="vacuums",
        rating=4.0,
        title="Great vacuum",
        review_text="Really good suction power.",
        date=date(2024, 6, 15),
        verified_purchase=True,
        helpful_votes=5,
        source=Source.AMAZON,
    )
    assert r.review_id == "test_001"
    assert r.rating == 4.0


def test_raw_review_rating_bounds():
    import pytest
    with pytest.raises(Exception):
        RawReview(
            review_id="test",
            product_id="test",
            product_name="test",
            brand="test",
            category="test",
            rating=6.0,
            review_text="test",
            source=Source.AMAZON,
        )


def test_classified_review():
    r = ClassifiedReview(
        review_id="test_001",
        product_id="B0C7C6QMLR",
        product_name="Shark Stratos",
        brand="Shark",
        category="vacuums",
        rating=2.0,
        title="Broke quickly",
        review_text="Motor died after 3 months.",
        verified_purchase=True,
        helpful_votes=12,
        source=Source.AMAZON,
        primary_theme=Theme.DURABILITY,
        sentiment=Sentiment.NEGATIVE,
        sentiment_confidence=0.95,
        severity=4,
        features_mentioned=["motor"],
        failure_mode="Motor failure",
        failure_timeline="3 months",
        has_actionable_signal=True,
        actionable_detail="Improve motor durability",
        key_phrases=["motor died after 3 months"],
    )
    assert r.primary_theme == Theme.DURABILITY
    assert r.severity == 4


def test_severity_clamping():
    import pytest
    with pytest.raises(Exception):
        ClassifiedReview(
            review_id="test",
            product_id="test",
            product_name="test",
            brand="test",
            category="test",
            rating=1.0,
            title="",
            review_text="bad",
            verified_purchase=False,
            helpful_votes=0,
            source=Source.AMAZON,
            primary_theme=Theme.DURABILITY,
            sentiment=Sentiment.NEGATIVE,
            sentiment_confidence=0.9,
            severity=6,
        )
