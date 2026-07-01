"""Tests for the cleaning pipeline."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date
from src.utils.schema import RawReview, Source
from src.cleaning.pipeline import CleaningPipeline


def _make_review(text: str, review_id: str = "test", **kwargs) -> RawReview:
    defaults = dict(
        review_id=review_id,
        product_id="B0TEST",
        product_name="Test Product",
        brand="Shark",
        category="vacuums",
        rating=3.0,
        title="Test",
        review_text=text,
        date=date(2024, 6, 1),
        verified_purchase=True,
        helpful_votes=0,
        source=Source.AMAZON,
    )
    defaults.update(kwargs)
    return RawReview(**defaults)


def test_removes_empty_reviews():
    pipeline = CleaningPipeline()
    reviews = [
        _make_review("This is a legitimate review with enough text to pass", review_id="r1"),
        _make_review("Too short", review_id="r2"),
        _make_review("", review_id="r3"),
    ]
    result = pipeline._remove_empty(reviews)
    assert len(result) == 1


def test_deduplicates_exact():
    pipeline = CleaningPipeline()
    reviews = [
        _make_review("This is the exact same review text repeated here", review_id="r1"),
        _make_review("This is the exact same review text repeated here", review_id="r2"),
        _make_review("This is a completely different review about something else", review_id="r3"),
    ]
    result = pipeline._deduplicate(reviews)
    assert len(result) == 2


def test_spam_detection():
    pipeline = CleaningPipeline()
    reviews = [
        _make_review("Great product, works well for cleaning my house daily", review_id="r1"),
        _make_review("Buy now at our website for 50% discount code SAVE50 click here", review_id="r2"),
        _make_review("Visit my website for free trial of this amazing product guaranteed", review_id="r3"),
    ]
    result = pipeline._remove_spam(reviews)
    assert len(result) == 1


def test_normalize_text():
    pipeline = CleaningPipeline()
    reviews = [
        _make_review("This   has   extra    spaces   and \n newlines throughout the text", review_id="r1"),
    ]
    result = pipeline._normalize_text(reviews)
    assert "   " not in result[0].review_text
