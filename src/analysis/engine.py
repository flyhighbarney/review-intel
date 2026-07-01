"""Phase 3: Analysis engine — issue ranking, competitor comparison, trend detection, feature gaps."""

from __future__ import annotations
import hashlib
from collections import defaultdict
from datetime import date, timedelta

import pandas as pd
import numpy as np

from src.utils.schema import ClassifiedReview, Theme, Sentiment, CompetitorComparison
from src.utils import logging as log
from config import settings


class AnalysisEngine:
    def __init__(self, reviews: list[ClassifiedReview]):
        self.reviews = reviews
        self.df = self._to_dataframe()

    def _to_dataframe(self) -> pd.DataFrame:
        records = [r.model_dump() for r in self.reviews]
        df = pd.DataFrame(records)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    def run_all(self) -> dict:
        """Run all analyses and return a complete results dictionary."""
        log.section("Analysis Engine")
        results = {}

        results["top_issues"] = self.top_issues_by_category()
        results["competitor_comparison"] = self.competitor_comparison()
        results["emerging_issues"] = self.emerging_issues(days=90)
        results["feature_gaps"] = self.feature_gap_analysis()
        results["language_patterns"] = self.language_patterns()
        results["return_risk"] = self.return_risk_indicators()
        results["summary_stats"] = self.summary_stats()
        results["verified_vs_unverified"] = self.verified_purchase_analysis()

        return results

    def summary_stats(self) -> dict:
        stats = {
            "total_reviews": len(self.df),
            "categories": self.df["category"].nunique(),
            "brands": self.df["brand"].nunique(),
            "date_range": {
                "min": str(self.df["date"].min()) if self.df["date"].notna().any() else None,
                "max": str(self.df["date"].max()) if self.df["date"].notna().any() else None,
            },
            "avg_rating_by_brand": self.df.groupby("brand")["rating"].mean().round(2).to_dict(),
            "review_count_by_category": self.df["category"].value_counts().to_dict(),
            "review_count_by_brand": self.df["brand"].value_counts().to_dict(),
            "sentiment_distribution": self.df["sentiment"].value_counts().to_dict(),
            "verified_purchase_rate": float(self.df["verified_purchase"].mean()),
        }
        log.info(f"Total reviews: {stats['total_reviews']}")
        log.info(f"Categories: {stats['categories']}, Brands: {stats['brands']}")
        return stats

    def top_issues_by_category(self, top_n: int = 10) -> dict[str, list[dict]]:
        """Top issues weighted by severity x frequency x recency."""
        log.info("Computing top issues by category...")
        results = {}
        neg = self.df[self.df["sentiment"].isin(["negative", "mixed"])]
        today = pd.Timestamp.now()

        for cat in neg["category"].unique():
            cat_df = neg[neg["category"] == cat]
            issue_groups = cat_df.groupby(["brand", "primary_theme"])

            issues = []
            for (brand, theme), group in issue_groups:
                frequency = len(group)
                avg_severity = group["severity"].mean()

                if group["date"].notna().any():
                    days_since = (today - group["date"].dropna()).dt.days
                    recency = np.exp(-days_since.mean() / 180).item()
                else:
                    recency = 0.5

                impact = frequency * avg_severity * recency
                sample_quotes = group["review_text"].head(3).tolist()
                products = group["product_name"].unique().tolist()

                failure_modes = group["failure_mode"].dropna().value_counts()
                top_failure = failure_modes.index[0] if len(failure_modes) > 0 else None

                issues.append({
                    "brand": brand,
                    "theme": theme,
                    "frequency": frequency,
                    "avg_severity": round(avg_severity, 2),
                    "recency_weight": round(recency, 3),
                    "impact_score": round(impact, 2),
                    "top_failure_mode": top_failure,
                    "sample_quotes": sample_quotes[:3],
                    "affected_products": products,
                })

            issues.sort(key=lambda x: x["impact_score"], reverse=True)
            results[cat] = issues[:top_n]

        return results

    def competitor_comparison(self) -> list[dict]:
        """Theme-by-theme comparison of Shark/Ninja vs each competitor."""
        log.info("Running competitor comparison...")
        comparisons = []

        for cat in self.df["category"].unique():
            cat_df = self.df[self.df["category"] == cat]
            our_brands = [b for b in settings.shark_ninja_brands if b in cat_df["brand"].values]

            for our_brand in our_brands:
                our_df = cat_df[cat_df["brand"] == our_brand]
                competitors = [b for b in cat_df["brand"].unique() if b not in settings.shark_ninja_brands]

                for comp in competitors:
                    comp_df = cat_df[cat_df["brand"] == comp]

                    for theme in Theme:
                        our_theme = our_df[our_df["primary_theme"] == theme.value]
                        comp_theme = comp_df[comp_df["primary_theme"] == theme.value]

                        if len(our_theme) < 3 and len(comp_theme) < 3:
                            continue

                        our_score = self._theme_score(our_theme) if len(our_theme) >= 3 else None
                        comp_score = self._theme_score(comp_theme) if len(comp_theme) >= 3 else None

                        if our_score is not None and comp_score is not None:
                            delta = our_score - comp_score
                            insight = self._generate_insight(our_brand, comp, theme.value, delta)
                            opportunity = self._generate_opportunity(our_brand, comp, theme.value, delta)

                            comparisons.append({
                                "category": cat,
                                "our_brand": our_brand,
                                "competitor": comp,
                                "theme": theme.value,
                                "our_score": round(our_score, 2),
                                "competitor_score": round(comp_score, 2),
                                "delta": round(delta, 2),
                                "our_sample_size": len(our_theme),
                                "competitor_sample_size": len(comp_theme),
                                "insight": insight,
                                "opportunity": opportunity,
                            })

        return comparisons

    def _theme_score(self, theme_df: pd.DataFrame) -> float:
        """Score a theme: higher = better. Based on sentiment ratio and severity."""
        if len(theme_df) == 0:
            return 0.0
        pos = (theme_df["sentiment"] == "positive").sum()
        neg = (theme_df["sentiment"] == "negative").sum()
        total = len(theme_df)
        sentiment_ratio = (pos - neg) / total
        avg_rating = theme_df["rating"].mean()
        return (sentiment_ratio + avg_rating / 5) / 2

    def _generate_insight(self, our: str, comp: str, theme: str, delta: float) -> str:
        if delta > 0.2:
            return f"{our} significantly outperforms {comp} on {theme}"
        elif delta > 0:
            return f"{our} slightly ahead of {comp} on {theme}"
        elif delta > -0.2:
            return f"{our} slightly behind {comp} on {theme}"
        else:
            return f"{our} significantly underperforms {comp} on {theme}"

    def _generate_opportunity(self, our: str, comp: str, theme: str, delta: float) -> str:
        if delta < -0.1:
            return f"Improve {theme} to close gap with {comp}"
        elif delta > 0.2:
            return f"Leverage {theme} advantage in marketing vs {comp}"
        return ""

    def emerging_issues(self, days: int = 90) -> list[dict]:
        """Themes rising in frequency over the last N days."""
        log.info(f"Detecting emerging issues (last {days} days)...")
        if not self.df["date"].notna().any():
            return []

        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        recent = self.df[self.df["date"] >= cutoff]
        older = self.df[self.df["date"] < cutoff]

        if len(recent) == 0 or len(older) == 0:
            return []

        emerging = []
        for cat in self.df["category"].unique():
            for theme in Theme:
                recent_count = len(recent[(recent["category"] == cat) & (recent["primary_theme"] == theme.value)])
                older_count = len(older[(older["category"] == cat) & (older["primary_theme"] == theme.value)])

                recent_rate = recent_count / max(len(recent[recent["category"] == cat]), 1)
                older_rate = older_count / max(len(older[older["category"] == cat]), 1)

                if recent_rate > older_rate * 1.5 and recent_count >= 5:
                    emerging.append({
                        "category": cat,
                        "theme": theme.value,
                        "recent_count": recent_count,
                        "older_count": older_count,
                        "growth_factor": round(recent_rate / max(older_rate, 0.001), 2),
                        "recent_severity_avg": round(
                            recent[(recent["category"] == cat) & (recent["primary_theme"] == theme.value)]["severity"].mean(), 2
                        ),
                    })

        emerging.sort(key=lambda x: x["growth_factor"], reverse=True)
        return emerging

    def feature_gap_analysis(self) -> list[dict]:
        """What competitors are praised for that Shark/Ninja isn't."""
        log.info("Running feature gap analysis...")
        gaps = []
        pos = self.df[self.df["sentiment"] == "positive"]

        for cat in pos["category"].unique():
            cat_pos = pos[pos["category"] == cat]
            our_brands = [b for b in settings.shark_ninja_brands if b in cat_pos["brand"].values]
            comps = [b for b in cat_pos["brand"].unique() if b not in settings.shark_ninja_brands]

            our_themes = set()
            for b in our_brands:
                our_themes.update(cat_pos[cat_pos["brand"] == b]["primary_theme"].unique())

            for comp in comps:
                comp_pos = cat_pos[cat_pos["brand"] == comp]
                comp_themes = comp_pos["primary_theme"].value_counts()

                for theme, count in comp_themes.items():
                    if theme not in our_themes and count >= 3:
                        gaps.append({
                            "category": cat,
                            "competitor": comp,
                            "theme": theme,
                            "competitor_positive_count": int(count),
                            "gap_description": f"{comp} praised for {theme} — Shark/Ninja has no positive mentions",
                        })

        return gaps

    def language_patterns(self, top_n: int = 20) -> dict:
        """Extract exact phrases customers use — feeds copywriting."""
        log.info("Extracting language patterns...")
        all_phrases = []
        for r in self.reviews:
            all_phrases.extend(r.key_phrases)

        phrase_counts = defaultdict(int)
        for p in all_phrases:
            phrase_counts[p.lower().strip()] += 1

        sorted_phrases = sorted(phrase_counts.items(), key=lambda x: x[1], reverse=True)

        positive_phrases = []
        negative_phrases = []
        for r in self.reviews:
            for phrase in r.key_phrases:
                if r.sentiment == Sentiment.POSITIVE:
                    positive_phrases.append(phrase)
                elif r.sentiment == Sentiment.NEGATIVE:
                    negative_phrases.append(phrase)

        pos_counts = defaultdict(int)
        neg_counts = defaultdict(int)
        for p in positive_phrases:
            pos_counts[p.lower()] += 1
        for p in negative_phrases:
            neg_counts[p.lower()] += 1

        return {
            "top_phrases": sorted_phrases[:top_n],
            "top_positive": sorted(pos_counts.items(), key=lambda x: x[1], reverse=True)[:top_n],
            "top_negative": sorted(neg_counts.items(), key=lambda x: x[1], reverse=True)[:top_n],
        }

    def return_risk_indicators(self) -> list[dict]:
        """Reviews that predict return or negative word-of-mouth."""
        log.info("Identifying return-risk indicators...")
        risk_signals = [
            "return", "returned", "returning", "refund", "money back",
            "waste of money", "don't buy", "do not buy", "avoid",
            "worst purchase", "throwing it away", "threw it out",
            "never again", "stay away", "garbage", "junk",
        ]

        at_risk = []
        for r in self.reviews:
            text_lower = r.review_text.lower()
            matches = [s for s in risk_signals if s in text_lower]
            if matches and r.rating <= 2:
                at_risk.append({
                    "review_id": r.review_id,
                    "brand": r.brand,
                    "product": r.product_name,
                    "category": r.category,
                    "rating": r.rating,
                    "risk_signals": matches,
                    "severity": r.severity,
                    "theme": r.primary_theme.value if isinstance(r.primary_theme, Theme) else r.primary_theme,
                    "snippet": r.review_text[:200],
                })

        by_product = defaultdict(list)
        for r in at_risk:
            by_product[r["product"]].append(r)

        summary = []
        for product, risks in by_product.items():
            summary.append({
                "product": product,
                "return_risk_count": len(risks),
                "avg_severity": round(sum(r["severity"] for r in risks) / len(risks), 2),
                "top_themes": list(set(r["theme"] for r in risks)),
                "sample_reviews": risks[:3],
            })

        summary.sort(key=lambda x: x["return_risk_count"], reverse=True)
        return summary

    def verified_purchase_analysis(self) -> dict:
        """Compare verified vs unverified purchase patterns."""
        log.info("Analyzing verified vs unverified purchase segments...")
        verified = self.df[self.df["verified_purchase"] == True]
        unverified = self.df[self.df["verified_purchase"] == False]

        return {
            "verified_count": len(verified),
            "unverified_count": len(unverified),
            "verified_avg_rating": round(verified["rating"].mean(), 2) if len(verified) > 0 else None,
            "unverified_avg_rating": round(unverified["rating"].mean(), 2) if len(unverified) > 0 else None,
            "verified_sentiment": verified["sentiment"].value_counts().to_dict() if len(verified) > 0 else {},
            "unverified_sentiment": unverified["sentiment"].value_counts().to_dict() if len(unverified) > 0 else {},
            "verified_severity_avg": round(verified["severity"].mean(), 2) if len(verified) > 0 else None,
            "unverified_severity_avg": round(unverified["severity"].mean(), 2) if len(unverified) > 0 else None,
        }
