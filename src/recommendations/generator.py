"""Phase 4: LLM-powered recommendation engine — turns analysis into PM-ready action items."""

from __future__ import annotations
import asyncio
import json
from datetime import date

from src.utils.schema import ClassifiedReview, IssueReport, FixCategory, Theme
from src.utils.llm import generate_text, get_cost_breakdown
from src.utils import logging as log


RECOMMENDATION_SYSTEM = """You are a senior product strategist at SharkNinja.
You translate consumer review data into concrete, actionable recommendations
for engineering, marketing, customer service, and executive leadership.

Be specific. Name parts, features, and competitor models.
Every recommendation must trace back to real review evidence.
Think like a builder: what can a PM or engineer act on Monday morning?"""


async def generate_recommendations(
    analysis_results: dict,
    reviews: list[ClassifiedReview],
) -> dict:
    """Generate all recommendation types from analysis results."""

    log.section("Recommendation Engine")

    engineering, marketing, cs, executive = await asyncio.gather(
        _engineering_recommendations(analysis_results, reviews),
        _marketing_recommendations(analysis_results, reviews),
        _customer_service_recommendations(analysis_results, reviews),
        _executive_scorecard(analysis_results, reviews),
    )

    brief = await _generate_pm_brief(analysis_results, reviews)

    cost = get_cost_breakdown()
    log.info(f"Recommendation generation cost: ${cost['total_usd']:.2f}")

    return {
        "engineering": engineering,
        "marketing": marketing,
        "customer_service": cs,
        "executive_scorecard": executive,
        "pm_brief": brief,
    }


async def _engineering_recommendations(results: dict, reviews: list[ClassifiedReview]) -> list[dict]:
    top_issues = results.get("top_issues", {})

    issues_text = ""
    for cat, issues in top_issues.items():
        issues_text += f"\n## {cat.upper()}\n"
        for issue in issues[:5]:
            issues_text += (
                f"- [{issue['brand']}] {issue['theme']}: "
                f"impact={issue['impact_score']}, freq={issue['frequency']}, "
                f"severity={issue['avg_severity']}\n"
                f"  Failure mode: {issue.get('top_failure_mode', 'N/A')}\n"
                f"  Quote: \"{issue['sample_quotes'][0][:150]}...\"\n"
            )

    prompt = f"""Based on these top consumer issues from product reviews, generate
engineering recommendations. For each issue, provide:

1. One-sentence problem statement
2. Root cause hypothesis
3. Fix category (design_change, materials, firmware, documentation, packaging, quality_control)
4. Estimated impact (HIGH/MEDIUM/LOW based on volume x severity)
5. Specific technical recommendation

Return as a JSON array of objects with fields: problem_statement, root_cause,
fix_category, impact, recommendation, category, brand, theme.

Top issues data:
{issues_text}

Return ONLY the JSON array."""

    text = await generate_text(prompt, system=RECOMMENDATION_SYSTEM)
    try:
        return json.loads(text) if text.strip().startswith("[") else json.loads(text[text.find("["):text.rfind("]")+1])
    except (json.JSONDecodeError, ValueError):
        return [{"raw_response": text, "parse_error": True}]


async def _marketing_recommendations(results: dict, reviews: list[ClassifiedReview]) -> list[dict]:
    comparisons = results.get("competitor_comparison", [])
    gaps = results.get("feature_gaps", [])

    advantages = [c for c in comparisons if c.get("delta", 0) > 0.15]
    weaknesses = [c for c in comparisons if c.get("delta", 0) < -0.15]

    prompt = f"""Based on competitive review analysis, generate marketing recommendations.

OUR ADVANTAGES (where Shark/Ninja beats competitors):
{json.dumps(advantages[:10], indent=2)}

COMPETITOR WEAKNESSES (where they underperform):
{json.dumps(weaknesses[:10], indent=2)}

FEATURE GAPS (what competitors are praised for that we're not):
{json.dumps(gaps[:10], indent=2)}

For each opportunity, provide:
1. Messaging angle (one sentence)
2. Target competitor
3. Evidence strength (HIGH/MEDIUM/LOW)
4. Suggested copy direction
5. Channel recommendation (packaging, Amazon listing, social, ads, PR)

Return as a JSON array of objects with fields: messaging_angle, target_competitor,
evidence_strength, copy_direction, channel, category.

Return ONLY the JSON array."""

    text = await generate_text(prompt, system=RECOMMENDATION_SYSTEM)
    try:
        return json.loads(text) if text.strip().startswith("[") else json.loads(text[text.find("["):text.rfind("]")+1])
    except (json.JSONDecodeError, ValueError):
        return [{"raw_response": text, "parse_error": True}]


async def _customer_service_recommendations(results: dict, reviews: list[ClassifiedReview]) -> list[dict]:
    return_risks = results.get("return_risk", [])
    top_issues = results.get("top_issues", {})

    prompt = f"""Based on review analysis, generate customer service recommendations.

HIGH RETURN-RISK PRODUCTS:
{json.dumps(return_risks[:5], indent=2, default=str)}

TOP COMPLAINT THEMES (across categories):
{json.dumps({cat: issues[:3] for cat, issues in top_issues.items()}, indent=2, default=str)}

For each recommendation, provide:
1. Issue summary
2. Proactive content to create (FAQ, video, email template)
3. Escalation trigger (what customer says that means this issue)
4. Resolution script suggestion
5. Priority (P1/P2/P3)

Return as a JSON array with fields: issue_summary, content_recommendation,
escalation_trigger, resolution_script, priority, affected_products.

Return ONLY the JSON array."""

    text = await generate_text(prompt, system=RECOMMENDATION_SYSTEM)
    try:
        return json.loads(text) if text.strip().startswith("[") else json.loads(text[text.find("["):text.rfind("]")+1])
    except (json.JSONDecodeError, ValueError):
        return [{"raw_response": text, "parse_error": True}]


async def _executive_scorecard(results: dict, reviews: list[ClassifiedReview]) -> dict:
    stats = results.get("summary_stats", {})
    comparisons = results.get("competitor_comparison", [])
    emerging = results.get("emerging_issues", [])

    prompt = f"""Create an executive scorecard from this review intelligence data.

SUMMARY STATS:
{json.dumps(stats, indent=2, default=str)}

KEY COMPETITIVE POSITIONS:
{json.dumps(comparisons[:15], indent=2, default=str)}

EMERGING ISSUES:
{json.dumps(emerging[:10], indent=2, default=str)}

Generate a scorecard with:
1. Overall brand health score (1-100) for each Shark/Ninja brand
2. Category-level scores vs top competitor
3. Top 3 risks requiring executive attention
4. Top 3 opportunities for competitive advantage
5. 90-day trend summary

Return as a JSON object with fields: brand_scores, category_scores,
top_risks, top_opportunities, trend_summary.

Return ONLY the JSON object."""

    text = await generate_text(prompt, system=RECOMMENDATION_SYSTEM)
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError):
        return {"raw_response": text, "parse_error": True}


async def _generate_pm_brief(results: dict, reviews: list[ClassifiedReview]) -> str:
    """Generate the '5 things to fix' PM-ready brief."""

    vacuum_issues = results.get("top_issues", {}).get("vacuums", [])
    shark_issues = [i for i in vacuum_issues if i["brand"] == "Shark"][:5]

    if not shark_issues:
        shark_issues = vacuum_issues[:5]

    prompt = f"""Write a concise 2-page executive brief titled:
"Top 5 Things to Fix in the Next Shark Vacuum"

Based on analysis of consumer reviews:

TOP ISSUES:
{json.dumps(shark_issues, indent=2, default=str)}

COMPETITIVE CONTEXT:
{json.dumps([c for c in results.get('competitor_comparison', []) if c.get('category') == 'vacuums'][:10], indent=2, default=str)}

Format:
- Title
- One-paragraph executive summary
- 5 numbered issues, each with:
  - Problem statement (1 sentence)
  - Evidence (2-3 verbatim customer quotes)
  - Root cause hypothesis
  - Recommended fix
  - Expected impact on ratings
- Closing paragraph with timeline recommendation

Write in a direct, professional tone. No fluff. Every sentence should drive a decision.
Use markdown formatting."""

    return await generate_text(prompt, system=RECOMMENDATION_SYSTEM, max_tokens=3000)
