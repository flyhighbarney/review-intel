"""Tests for synthetic data generation."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.synthetic import generate_synthetic_reviews


def test_generates_correct_count():
    reviews = generate_synthetic_reviews(count=100, seed=99)
    assert 80 <= len(reviews) <= 120


def test_rating_distribution():
    reviews = generate_synthetic_reviews(count=1000, seed=42)
    ratings = [r.rating for r in reviews]
    avg = sum(ratings) / len(ratings)
    assert 2.5 <= avg <= 4.0


def test_all_categories_present():
    reviews = generate_synthetic_reviews(count=500, seed=42)
    categories = set(r.category for r in reviews)
    assert "vacuums" in categories
    assert "blenders" in categories


def test_brands_present():
    reviews = generate_synthetic_reviews(count=500, seed=42)
    brands = set(r.brand for r in reviews)
    assert "Shark" in brands or "Ninja" in brands
    assert len(brands) >= 4


def test_review_text_not_empty():
    reviews = generate_synthetic_reviews(count=100, seed=42)
    for r in reviews:
        assert len(r.review_text) > 20
