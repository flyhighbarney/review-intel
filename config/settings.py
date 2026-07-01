"""Central configuration — all knobs in one place."""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CLEANED_DIR = DATA_DIR / "cleaned"
CLASSIFIED_DIR = DATA_DIR / "classified"
CACHE_DIR = DATA_DIR / "cache"
REPORTS_DIR = ROOT / "reports"
PROMPTS_DIR = ROOT / "prompts"


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    apify_api_token: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "ReviewIntel/0.1 by SharkNinja"

    # LLM config
    classification_model: str = "claude-haiku-4-5-20251001"
    edge_case_model: str = "claude-sonnet-5"
    recommendation_model: str = "claude-sonnet-5"
    max_concurrent_llm: int = 10
    llm_budget_usd: float = 50.0

    # Scraping targets
    target_review_count: int = 5000
    categories: list[str] = Field(default=["vacuums", "blenders", "air_fryers", "coffee_makers"])
    shark_ninja_brands: list[str] = Field(default=["Shark", "Ninja"])
    competitor_brands: dict[str, list[str]] = Field(default={
        "vacuums": ["Dyson", "iRobot", "Bissell"],
        "blenders": ["Vitamix", "Nutribullet", "KitchenAid"],
        "air_fryers": ["Instant Pot", "Cosori", "Breville"],
        "coffee_makers": ["Keurig", "Breville", "De'Longhi"],
    })

    model_config = {"env_file": str(ROOT / ".env"), "env_file_encoding": "utf-8"}


settings = Settings()


# Product catalog — maps ASIN/product IDs to canonical names
PRODUCT_CATALOG = {
    "vacuums": {
        "Shark": [
            {"asin": "B0C7C6QMLR", "name": "Shark Stratos Cordless"},
            {"asin": "B0BQMMRQ7S", "name": "Shark Navigator Lift-Away"},
            {"asin": "B09JFR2V85", "name": "Shark AI Ultra Robot"},
        ],
        "Dyson": [
            {"asin": "B0CTP45GH8", "name": "Dyson V15 Detect"},
            {"asin": "B0BVM4MLNJ", "name": "Dyson Gen5detect"},
        ],
        "iRobot": [
            {"asin": "B0C415HQBX", "name": "iRobot Roomba j9+"},
        ],
        "Bissell": [
            {"asin": "B0CHJ6DJMS", "name": "Bissell CrossWave HydroSteam"},
        ],
    },
    "blenders": {
        "Ninja": [
            {"asin": "B0CJ7GQHP2", "name": "Ninja Professional Plus"},
            {"asin": "B0CT8LBMHJ", "name": "Ninja Detect Duo"},
        ],
        "Vitamix": [
            {"asin": "B0B2HNTMYP", "name": "Vitamix A3500"},
        ],
        "Nutribullet": [
            {"asin": "B0CSGK4G6Q", "name": "Nutribullet Ultra"},
        ],
    },
    "air_fryers": {
        "Ninja": [
            {"asin": "B0BF74XLBS", "name": "Ninja Foodi DualZone"},
            {"asin": "B0CJDHG6S4", "name": "Ninja Combi"},
        ],
        "Cosori": [
            {"asin": "B0843L6VP1", "name": "Cosori Pro II"},
        ],
        "Breville": [
            {"asin": "B085L1GPZP", "name": "Breville Joule Oven Air Fryer"},
        ],
        "Instant Pot": [
            {"asin": "B0B2SDZFVY", "name": "Instant Vortex Plus"},
        ],
    },
    "coffee_makers": {
        "Ninja": [
            {"asin": "B0CXBW2LJZ", "name": "Ninja DualBrew Pro"},
            {"asin": "B0D1BWTLHY", "name": "Ninja Luxe Cafe"},
        ],
        "Keurig": [
            {"asin": "B0CXBB7C3F", "name": "Keurig K-Supreme SMART"},
        ],
        "Breville": [
            {"asin": "B0DBBNJPTS", "name": "Breville Barista Express Impress"},
        ],
    },
}
