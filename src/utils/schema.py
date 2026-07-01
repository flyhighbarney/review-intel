"""Canonical review schema — single source of truth for all data shapes."""

import datetime
from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class Source(str, Enum):
    AMAZON = "amazon"
    REDDIT = "reddit"
    BESTBUY = "bestbuy"
    TRUSTPILOT = "trustpilot"


class Theme(str, Enum):
    DURABILITY = "durability"
    NOISE = "noise"
    USABILITY = "usability"
    CLEANING = "cleaning"
    POWER = "power"
    SIZE = "size"
    PRICE_VALUE = "price_value"
    AESTHETICS = "aesthetics"
    PACKAGING = "packaging"
    CUSTOMER_SERVICE = "customer_service"
    BATTERY = "battery"
    SMELL = "smell"
    ACCESSORIES = "accessories"
    SETUP = "setup"
    SAFETY = "safety"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    NEUTRAL = "neutral"


class FixCategory(str, Enum):
    DESIGN_CHANGE = "design_change"
    MATERIALS = "materials"
    FIRMWARE = "firmware"
    DOCUMENTATION = "documentation"
    PACKAGING = "packaging"
    MARKETING_REFRAME = "marketing_reframe"
    QUALITY_CONTROL = "quality_control"
    CUSTOMER_SUPPORT = "customer_support"


class RawReview(BaseModel):
    review_id: str
    product_id: str
    product_name: str
    brand: str
    category: str
    rating: float = Field(ge=1, le=5)
    title: str = ""
    review_text: str
    date: Optional[datetime.date] = None
    verified_purchase: bool = False
    helpful_votes: int = 0
    source: Source
    reviewer_name: str = ""
    source_url: str = ""


class ClassifiedReview(BaseModel):
    review_id: str
    product_id: str
    product_name: str
    brand: str
    category: str
    rating: float
    title: str
    review_text: str
    date: Optional[datetime.date] = None
    verified_purchase: bool
    helpful_votes: int
    source: Source

    primary_theme: Theme
    secondary_themes: List[Theme] = []
    sentiment: Sentiment
    sentiment_confidence: float = Field(ge=0, le=1)
    severity: int = Field(ge=1, le=5)
    features_mentioned: List[str] = []
    failure_mode: Optional[str] = None
    failure_timeline: Optional[str] = None
    competitor_mentions: List[Dict] = []
    has_actionable_signal: bool = False
    actionable_detail: str = ""
    is_shipping_complaint: bool = False
    is_spam: bool = False
    key_phrases: List[str] = []


class IssueReport(BaseModel):
    issue_id: str
    category: str
    brand: str
    theme: Theme
    problem_statement: str
    root_cause_hypothesis: str
    fix_category: FixCategory
    severity_score: float
    frequency: int
    recency_weight: float
    impact_score: float
    sample_quotes: List[str]
    affected_products: List[str]
    evidence_review_ids: List[str]


class CompetitorComparison(BaseModel):
    category: str
    our_brand: str
    competitor: str
    theme: Theme
    our_score: float
    competitor_score: float
    delta: float
    our_sample_size: int
    competitor_sample_size: int
    insight: str
    opportunity: str
