"""SharkNinja Product Review Intelligence — Web Prototype Dashboard."""

import html
import json
import sys
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from config import CLASSIFIED_DIR, REPORTS_DIR

# ─── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="SharkNinja Review Intelligence",
    page_icon="🦈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Design tokens ─────────────────────────────────────────────────────────────

BG_PRIMARY = "#0e1117"
BG_CARD = "#1a1f2e"
BG_CARD_HOVER = "#222838"
BG_SURFACE = "#161b22"
BORDER = "#2d333b"
TEXT_PRIMARY = "#e6edf3"
TEXT_SECONDARY = "#8b949e"
TEXT_MUTED = "#6e7681"
ACCENT = "#0d7377"
ACCENT_LIGHT = "#14a3a8"
DANGER = "#f85149"
WARNING = "#d29922"
SUCCESS = "#3fb950"

BRAND_COLORS = {
    "Shark": "#14a3a8", "Ninja": "#e8863a",
    "Dyson": "#a371f7", "iRobot": "#58a6ff", "Bissell": "#3fb950",
    "Vitamix": "#f85149", "Nutribullet": "#39d353", "KitchenAid": "#ff7b72",
    "Cosori": "#bc8cff", "Breville": "#79c0ff", "Keurig": "#56d364",
    "Instant Pot": "#d29922", "De'Longhi": "#8b949e",
}

SENTIMENT_COLORS = {
    "positive": "#3fb950", "negative": "#f85149",
    "mixed": "#d29922", "neutral": "#8b949e",
}

THEME_LABELS = {
    "durability": "Durability", "noise": "Noise", "usability": "Usability",
    "cleaning": "Cleaning", "power": "Power/Suction", "size": "Size/Weight",
    "price_value": "Price/Value", "aesthetics": "Aesthetics",
    "packaging": "Packaging", "customer_service": "Customer Service",
    "battery": "Battery Life", "smell": "Smell/Odor",
    "accessories": "Accessories", "setup": "Setup", "safety": "Safety",
}

# ─── Chart helpers ─────────────────────────────────────────────────────────────

CHART_LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font_color=TEXT_PRIMARY,
    font_size=12,
    xaxis=dict(gridcolor="#2d333b", zerolinecolor="#2d333b"),
    yaxis=dict(gridcolor="#2d333b", zerolinecolor="#2d333b"),
    legend=dict(font_color=TEXT_PRIMARY),
    margin=dict(l=0, r=0, t=10, b=0),
)


def dark_layout(**overrides):
    layout = {**CHART_LAYOUT}
    for k, v in overrides.items():
        if isinstance(v, dict) and k in layout and isinstance(layout[k], dict):
            layout[k] = {**layout[k], **v}
        else:
            layout[k] = v
    return layout

# ─── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown(f"""
<style>
    .block-container {{ padding-top: 1.2rem; max-width: 1400px; }}

    /* ── Header ── */
    .header-bar {{
        background: linear-gradient(135deg, #0a1628 0%, #122a45 40%, {ACCENT} 100%);
        padding: 2rem 2.5rem;
        border-radius: 14px;
        margin-bottom: 1.8rem;
        border: 1px solid {BORDER};
    }}
    .header-bar h1 {{
        margin: 0; font-size: 1.8rem; font-weight: 700;
        color: #fff; letter-spacing: -0.5px;
    }}
    .header-bar p {{
        margin: 0.4rem 0 0 0; color: rgba(255,255,255,0.75);
        font-size: 0.9rem; line-height: 1.4;
    }}

    /* ── KPI cards ── */
    .kpi-row {{ display: flex; gap: 0.8rem; margin-bottom: 1.5rem; }}
    .kpi-card {{
        background: {BG_CARD};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 1.1rem 1rem;
        text-align: center;
        flex: 1;
        transition: border-color 0.2s;
    }}
    .kpi-card:hover {{ border-color: {ACCENT}; }}
    .kpi-value {{
        font-size: 1.9rem; font-weight: 700;
        color: {TEXT_PRIMARY}; line-height: 1.15;
    }}
    .kpi-label {{
        font-size: 0.7rem; text-transform: uppercase;
        letter-spacing: 1px; color: {TEXT_SECONDARY};
        margin-top: 0.25rem;
    }}
    .kpi-delta {{ font-size: 0.75rem; margin-top: 0.2rem; font-weight: 600; }}
    .kpi-delta.positive {{ color: {SUCCESS}; }}
    .kpi-delta.negative {{ color: {DANGER}; }}

    /* ── Section labels ── */
    .section-label {{
        font-size: 0.72rem; text-transform: uppercase;
        letter-spacing: 1.8px; font-weight: 600;
        color: {ACCENT_LIGHT};
        border-bottom: 1px solid {BORDER};
        padding-bottom: 0.5rem;
        margin: 2rem 0 1rem 0;
    }}

    /* ── Review quotes ── */
    .review-quote {{
        background: {BG_CARD};
        border-left: 3px solid {ACCENT};
        padding: 0.8rem 1.1rem;
        margin: 0.6rem 0;
        font-size: 0.88rem;
        color: {TEXT_PRIMARY};
        border-radius: 0 8px 8px 0;
        line-height: 1.5;
    }}
    .review-quote strong {{ color: {TEXT_PRIMARY}; }}

    /* ── Score circles ── */
    .score-circle {{
        display: inline-flex; align-items: center; justify-content: center;
        width: 110px; height: 110px; border-radius: 50%;
        font-size: 2.2rem; font-weight: 700; color: #fff;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }}
    .score-good {{ background: linear-gradient(135deg, {ACCENT}, {SUCCESS}); }}
    .score-ok {{ background: linear-gradient(135deg, {WARNING}, #e67e22); }}
    .score-bad {{ background: linear-gradient(135deg, {DANGER}, #c0392b); }}
    .brand-stat-text {{
        font-size: 0.88rem; color: {TEXT_SECONDARY};
        margin-top: 0.5rem; line-height: 1.6;
    }}
    .brand-stat-text strong {{ color: {TEXT_PRIMARY}; }}

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {{
        background: {BG_SURFACE} !important;
        border-right: 1px solid {BORDER} !important;
    }}
    [data-testid="stSidebar"] * {{
        color: {TEXT_PRIMARY} !important;
    }}
    [data-testid="stSidebar"] [data-baseweb="tag"] {{
        background-color: {ACCENT} !important;
        color: #fff !important;
        border: none !important;
    }}
    [data-testid="stSidebar"] [data-baseweb="tag"] span {{
        color: #fff !important;
    }}
    [data-testid="stSidebar"] [data-baseweb="select"],
    [data-testid="stSidebar"] [data-baseweb="input"] {{
        background-color: {BG_CARD} !important;
        border-color: {BORDER} !important;
    }}
    [data-testid="stSidebar"] button {{
        background: {ACCENT} !important;
        color: #fff !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }}
    [data-testid="stSidebar"] button:hover {{
        background: {ACCENT_LIGHT} !important;
    }}
    [data-testid="stSidebar"] hr {{
        border-color: {BORDER} !important;
    }}
    [data-testid="stSidebar"] .stCaption, [data-testid="stSidebar"] small {{
        color: {TEXT_MUTED} !important;
    }}
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {{
        color: {TEXT_PRIMARY} !important;
        font-size: 1.5rem !important;
    }}
    [data-testid="stSidebar"] [data-testid="stMetricLabel"] {{
        color: {TEXT_SECONDARY} !important;
    }}

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0; border-bottom: 1px solid {BORDER};
    }}
    .stTabs [data-baseweb="tab"] {{
        padding: 0.7rem 1.3rem;
        font-size: 0.85rem; font-weight: 500;
        color: {TEXT_SECONDARY} !important;
    }}
    .stTabs [data-baseweb="tab"][aria-selected="true"] {{
        color: {ACCENT_LIGHT} !important;
        border-bottom-color: {ACCENT_LIGHT} !important;
    }}

    /* ── Expanders ── */
    .streamlit-expanderHeader {{
        background: {BG_CARD} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 8px !important;
        color: {TEXT_PRIMARY} !important;
    }}

    /* ── Metrics ── */
    [data-testid="stMetricValue"] {{ color: {TEXT_PRIMARY} !important; }}
    [data-testid="stMetricLabel"] {{ color: {TEXT_SECONDARY} !important; }}

    /* ── Data table ── */
    .stDataFrame {{ border: 1px solid {BORDER}; border-radius: 8px; }}

    /* ── Download buttons ── */
    .stDownloadButton > button {{
        background: {BG_CARD} !important;
        color: {TEXT_PRIMARY} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 8px !important;
    }}
    .stDownloadButton > button:hover {{
        border-color: {ACCENT} !important;
        color: {ACCENT_LIGHT} !important;
    }}
</style>
""", unsafe_allow_html=True)

# ─── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data
def load_data():
    path = CLASSIFIED_DIR / "reviews_classified.jsonl"
    if not path.exists():
        return pd.DataFrame()
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


@st.cache_data
def load_results():
    path = REPORTS_DIR / "analysis_results.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


@st.cache_data
def load_recommendations():
    path = REPORTS_DIR / "recommendations.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def safe(text: str, max_len: int = 300) -> str:
    return html.escape(str(text)[:max_len])

# ─── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar(df: pd.DataFrame) -> pd.DataFrame:
    with st.sidebar:
        st.markdown("### 🦈 Review Intel")
        st.markdown("---")

        categories = st.multiselect(
            "Category",
            options=sorted(df["category"].unique()),
            default=sorted(df["category"].unique()),
        )

        all_brands = sorted(df["brand"].unique())
        shark_ninja = [b for b in all_brands if b in ("Shark", "Ninja")]

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Our Brands", use_container_width=True):
                st.session_state["brand_filter"] = shark_ninja
        with col2:
            if st.button("All Brands", use_container_width=True):
                st.session_state["brand_filter"] = all_brands

        default_brands = st.session_state.get("brand_filter", all_brands)
        brands = st.multiselect("Brand", options=all_brands, default=default_brands)

        sentiments = st.multiselect(
            "Sentiment",
            options=["positive", "negative", "mixed", "neutral"],
            default=["positive", "negative", "mixed", "neutral"],
        )

        min_severity = st.slider("Min Severity", 1, 5, 1)
        verified_only = st.checkbox("Verified purchases only")

        st.markdown("---")

        mask = (
            df["category"].isin(categories)
            & df["brand"].isin(brands)
            & df["sentiment"].isin(sentiments)
            & (df["severity"] >= min_severity)
        )
        if verified_only:
            mask &= df["verified_purchase"] == True

        filtered = df[mask]

        st.metric("Showing", f"{len(filtered):,} / {len(df):,}")

        if len(filtered) > 0:
            neg_pct = (filtered["sentiment"] == "negative").mean() * 100
            st.metric("Negative Rate", f"{neg_pct:.1f}%")

        st.markdown("---")
        st.caption("SharkNinja Review Intelligence v0.1")

    return filtered

# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    df = load_data()
    results = load_results()
    recs = load_recommendations()

    if df.empty:
        st.info("No data found — generating demo dataset (one-time, takes ~30 seconds)...")
        try:
            import subprocess
            subprocess.run(
                [sys.executable, str(ROOT / "run_demo.py")],
                cwd=str(ROOT),
                check=True,
                capture_output=True,
                text=True,
            )
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Auto-generation failed: {e}. Run `python run_demo.py` manually.")
            return

    filtered = render_sidebar(df)

    st.markdown("""
    <div class="header-bar">
        <h1>Product Review Intelligence</h1>
        <p>AI-powered consumer insights across Shark, Ninja &amp; top competitors &mdash;
        {total:,} reviews across {cats} categories and {brands} brands</p>
    </div>
    """.format(
        total=len(df),
        cats=df["category"].nunique(),
        brands=df["brand"].nunique(),
    ), unsafe_allow_html=True)

    tab_exec, tab_issues, tab_compete, tab_products, tab_trends, tab_data = st.tabs([
        "  Executive Overview  ",
        "  Issue Deep-Dive  ",
        "  Competitive Intel  ",
        "  Product Explorer  ",
        "  Trends & Signals  ",
        "  Data & Export  ",
    ])

    with tab_exec:
        render_executive(filtered, df, results)
    with tab_issues:
        render_issues(filtered, results)
    with tab_compete:
        render_competitive(filtered, results)
    with tab_products:
        render_products(filtered, results)
    with tab_trends:
        render_trends(filtered, results)
    with tab_data:
        render_data(filtered)

# ─── Executive Overview ───────────────────────────────────────────────────────

def render_executive(filtered: pd.DataFrame, full_df: pd.DataFrame, results: dict):
    if len(filtered) == 0:
        st.info("No reviews match the current filters.")
        return

    avg_rating = filtered["rating"].mean()
    neg_rate = (filtered["sentiment"] == "negative").mean()
    avg_sev = filtered["severity"].mean()
    ver_pct = filtered["verified_purchase"].mean() * 100

    kpis = [
        ("Reviews", f"{len(filtered):,}", None),
        ("Avg Rating", f"{avg_rating:.2f}", "positive" if avg_rating >= 3.5 else "negative"),
        ("Negative", f"{neg_rate * 100:.1f}%", "negative" if neg_rate > 0.3 else "positive"),
        ("Severity", f"{avg_sev:.1f}/5", "negative" if avg_sev > 3 else "positive"),
        ("Verified", f"{ver_pct:.0f}%", None),
        ("Products", f"{filtered['product_name'].nunique()}", None),
    ]

    cols = st.columns(6)
    for col, (label, value, delta_class) in zip(cols, kpis):
        with col:
            delta = ""
            if delta_class:
                word = "Good" if delta_class == "positive" else "Watch"
                delta = f'<div class="kpi-delta {delta_class}">{word}</div>'
            st.markdown(
                f'<div class="kpi-card">'
                f'<div class="kpi-value">{value}</div>'
                f'<div class="kpi-label">{label}</div>'
                f'{delta}</div>',
                unsafe_allow_html=True,
            )

    col1, col2 = st.columns([1.3, 1])

    with col1:
        st.markdown('<p class="section-label">Brand Health Scorecard</p>', unsafe_allow_html=True)

        brand_stats = filtered.groupby("brand").agg(
            avg_rating=("rating", "mean"),
            review_count=("review_id", "count"),
            neg_pct=("sentiment", lambda x: (x == "negative").mean() * 100),
            avg_severity=("severity", "mean"),
        ).round(2)

        brand_stats["health_score"] = (
            brand_stats["avg_rating"] / 5 * 40 +
            (100 - brand_stats["neg_pct"]) / 100 * 30 +
            (5 - brand_stats["avg_severity"]) / 4 * 30
        ).round(0).astype(int)

        brand_stats = brand_stats.sort_values("health_score", ascending=False)

        colors = [BRAND_COLORS.get(b, "#8b949e") for b in brand_stats.index]
        is_ours = [b in ("Shark", "Ninja") for b in brand_stats.index]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=brand_stats.index,
            x=brand_stats["health_score"],
            orientation="h",
            marker_color=colors,
            marker_line_width=[2.5 if o else 0 for o in is_ours],
            marker_line_color=["#ffd700" if o else "rgba(0,0,0,0)" for o in is_ours],
            text=[f"  {s}  ({n:,})" for s, n in zip(brand_stats["health_score"], brand_stats["review_count"])],
            textposition="outside",
            textfont=dict(size=11, color=TEXT_SECONDARY),
        ))
        fig.update_layout(**dark_layout(
            height=max(300, len(brand_stats) * 42),
            margin=dict(l=0, r=100, t=10, b=0),
            xaxis=dict(range=[0, 115], title="Health Score (0-100)", gridcolor=BORDER, zerolinecolor=BORDER),
            yaxis=dict(categoryorder="total ascending", automargin=True, gridcolor=BORDER),
        ))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown('<p class="section-label">Issue Theme Breakdown</p>', unsafe_allow_html=True)

        neg_df = filtered[filtered["sentiment"].isin(["negative", "mixed"])]
        if len(neg_df) > 0:
            theme_counts = neg_df["primary_theme"].value_counts().head(8)
            labels = [THEME_LABELS.get(t, t) for t in theme_counts.index]

            chart_colors = ["#14a3a8", "#e8863a", "#a371f7", "#58a6ff",
                            "#3fb950", "#f85149", "#d29922", "#bc8cff"]

            fig = go.Figure(data=[go.Pie(
                labels=labels,
                values=theme_counts.values,
                hole=0.6,
                marker_colors=chart_colors[:len(labels)],
                textinfo="label+percent",
                textfont=dict(size=11, color=TEXT_PRIMARY),
                insidetextorientation="radial",
            )])
            fig.update_layout(**dark_layout(
                height=380,
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=False,
                annotations=[dict(
                    text=f"<b>{len(neg_df):,}</b><br><span style='font-size:12px'>Issues</span>",
                    x=0.5, y=0.5, font=dict(size=18, color=TEXT_PRIMARY), showarrow=False
                )],
            ))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("No negative reviews in current filter!")

    # Shark vs Ninja
    st.markdown('<p class="section-label">Shark vs Ninja</p>', unsafe_allow_html=True)

    shark_ninja = filtered[filtered["brand"].isin(["Shark", "Ninja"])]
    if len(shark_ninja) > 0:
        col1, col2 = st.columns(2)
        for col, brand, color in [(col1, "Shark", BRAND_COLORS["Shark"]), (col2, "Ninja", BRAND_COLORS["Ninja"])]:
            with col:
                bdf = shark_ninja[shark_ninja["brand"] == brand]
                if len(bdf) == 0:
                    st.info(f"No {brand} reviews in current filter")
                    continue

                avg_r = bdf["rating"].mean()
                neg = (bdf["sentiment"] == "negative").mean() * 100
                top_issue = bdf[bdf["sentiment"].isin(["negative", "mixed"])]["primary_theme"].mode()
                top_issue_name = THEME_LABELS.get(top_issue.iloc[0], "N/A") if len(top_issue) > 0 else "N/A"

                score = int(avg_r / 5 * 40 + (100 - neg) / 100 * 30 + (5 - bdf["severity"].mean()) / 4 * 30)
                score_class = "score-good" if score >= 65 else "score-ok" if score >= 45 else "score-bad"

                st.markdown(f"""
                <div style="text-align:center; padding: 1rem 0;">
                    <div class="score-circle {score_class}">{score}</div>
                    <div style="margin-top:0.8rem;">
                        <strong style="font-size:1.2rem; color:{TEXT_PRIMARY};">{brand}</strong>
                        <div class="brand-stat-text">
                            {len(bdf):,} reviews &bull; {avg_r:.2f} avg &bull; {neg:.0f}% negative<br>
                            Top issue: <strong>{top_issue_name}</strong>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                fig = px.histogram(bdf, x="rating", nbins=5, color_discrete_sequence=[color])
                fig.update_layout(**dark_layout(
                    height=140,
                    margin=dict(l=0, r=0, t=5, b=0),
                    xaxis=dict(title="", dtick=1, gridcolor=BORDER, zerolinecolor=BORDER),
                    yaxis=dict(title="", showticklabels=False, gridcolor=BORDER),
                    showlegend=False,
                    bargap=0.15,
                ))
                st.plotly_chart(fig, use_container_width=True)


# ─── Issue Deep-Dive ──────────────────────────────────────────────────────────

def render_issues(df: pd.DataFrame, results: dict):
    st.markdown('<p class="section-label">Top Issues by Impact Score</p>', unsafe_allow_html=True)

    top_issues = results.get("top_issues", {})

    if not top_issues:
        st.info("No pre-computed issues. Showing live analysis from filtered data.")
        _render_live_issues(df)
        return

    selected_cat = st.selectbox(
        "Category",
        options=list(top_issues.keys()),
        format_func=lambda x: x.replace("_", " ").title(),
    )

    issues = top_issues.get(selected_cat, [])
    if not issues:
        st.info("No issues found for this category")
        return

    issue_df = pd.DataFrame(issues)

    fig = go.Figure()
    for brand in issue_df["brand"].unique():
        bdf = issue_df[issue_df["brand"] == brand]
        fig.add_trace(go.Bar(
            y=[THEME_LABELS.get(t, t) for t in bdf["theme"]],
            x=bdf["impact_score"],
            name=brand,
            orientation="h",
            marker_color=BRAND_COLORS.get(brand, "#8b949e"),
            text=[f'{s:.0f}' for s in bdf["impact_score"]],
            textposition="outside",
            textfont=dict(color=TEXT_SECONDARY),
        ))

    fig.update_layout(**dark_layout(
        height=max(300, len(issues) * 38),
        barmode="group",
        margin=dict(l=0, r=60, t=10, b=0),
        xaxis=dict(title="Impact Score", gridcolor=BORDER, zerolinecolor=BORDER),
        yaxis=dict(categoryorder="total ascending", automargin=True, gridcolor=BORDER),
        legend=dict(orientation="h", y=1.08, font_color=TEXT_PRIMARY),
    ))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<p class="section-label">Issue Details</p>', unsafe_allow_html=True)

    for i, issue in enumerate(issues[:8]):
        brand = issue["brand"]
        with st.expander(
            f"#{i+1}  {THEME_LABELS.get(issue['theme'], issue['theme'])} — {brand}  "
            f"(impact: {issue['impact_score']:.0f}, freq: {issue['frequency']})",
            expanded=(i < 2),
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Impact", f"{issue['impact_score']:.0f}")
            c2.metric("Frequency", issue["frequency"])
            c3.metric("Avg Severity", f"{issue['avg_severity']:.1f}/5")
            c4.metric("Recency", f"{issue['recency_weight']:.2f}")

            if issue.get("top_failure_mode"):
                st.markdown(f"**Failure Mode:** {safe(issue['top_failure_mode'])}")

            if issue.get("affected_products"):
                st.markdown(f"**Affected Products:** {', '.join(safe(p) for p in issue['affected_products'])}")

            if issue.get("sample_quotes"):
                st.markdown("**Customer Voices:**")
                for q in issue["sample_quotes"][:3]:
                    st.markdown(f'<div class="review-quote">{safe(q, 400)}</div>', unsafe_allow_html=True)


def _render_live_issues(df: pd.DataFrame):
    neg = df[df["sentiment"].isin(["negative", "mixed"])]
    if len(neg) == 0:
        st.info("No negative/mixed reviews in current filter")
        return

    issue_df = neg.groupby(["brand", "primary_theme", "category"]).agg(
        count=("review_id", "size"),
        avg_severity=("severity", "mean"),
    ).reset_index()
    issue_df["impact"] = issue_df["count"] * issue_df["avg_severity"]
    issue_df = issue_df.sort_values("impact", ascending=False).head(15)
    issue_df["theme_label"] = issue_df["primary_theme"].map(lambda t: THEME_LABELS.get(t, t))

    fig = px.bar(
        issue_df, x="impact", y="theme_label", color="brand",
        orientation="h", color_discrete_map=BRAND_COLORS,
    )
    fig.update_layout(**dark_layout(
        yaxis=dict(categoryorder="total ascending", automargin=True, gridcolor=BORDER),
        xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
    ))
    st.plotly_chart(fig, use_container_width=True)

# ─── Competitive Intel ────────────────────────────────────────────────────────

def render_competitive(df: pd.DataFrame, results: dict):
    comparisons = results.get("competitor_comparison", [])

    if not comparisons:
        st.info("Run the full pipeline to generate competitor comparisons.")
        _render_live_competitive(df)
        return

    comp_df = pd.DataFrame(comparisons)

    st.markdown('<p class="section-label">Competitive Positioning</p>', unsafe_allow_html=True)

    selected_cat = st.selectbox(
        "Category",
        options=sorted(comp_df["category"].unique()),
        format_func=lambda x: x.replace("_", " ").title(),
        key="comp_cat",
    )

    cat_comps = comp_df[comp_df["category"] == selected_cat]

    if len(cat_comps) == 0:
        st.info("No comparisons for this category")
        return

    pivot = cat_comps.pivot_table(
        index="competitor", columns="theme", values="delta", aggfunc="mean"
    ).fillna(0)

    theme_labels = [THEME_LABELS.get(t, t) for t in pivot.columns]

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=theme_labels,
        y=pivot.index.tolist(),
        colorscale=[
            [0, "#f85149"],
            [0.35, "#6e2b28"],
            [0.5, BG_CARD],
            [0.65, "#1a4d2e"],
            [1, "#3fb950"],
        ],
        zmid=0,
        text=[[f"{v:+.2f}" for v in row] for row in pivot.values],
        texttemplate="%{text}",
        textfont=dict(size=12, color=TEXT_PRIMARY),
        colorbar=dict(title=dict(text="Delta", side="right"), tickfont=dict(color=TEXT_SECONDARY)),
    ))
    fig.update_layout(**dark_layout(
        height=max(280, len(pivot) * 55 + 80),
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(side="top", tickfont=dict(color=TEXT_SECONDARY)),
        yaxis=dict(tickfont=dict(color=TEXT_SECONDARY)),
    ))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("🟢 Green = Shark/Ninja advantage  ·  🔴 Red = competitor advantage")

    st.markdown('<p class="section-label">Biggest Competitive Gaps</p>', unsafe_allow_html=True)

    weaknesses = cat_comps[cat_comps["delta"] < -0.1].sort_values("delta").head(5)
    strengths = cat_comps[cat_comps["delta"] > 0.1].sort_values("delta", ascending=False).head(5)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Where We Lag** 🔻")
        if len(weaknesses) == 0:
            st.caption("No significant gaps found.")
        for _, row in weaknesses.iterrows():
            st.markdown(
                f"- **{THEME_LABELS.get(row['theme'], row['theme'])}** vs {row['competitor']}: "
                f"`{row['delta']:+.2f}`"
            )
    with col2:
        st.markdown("**Where We Lead** 🔺")
        if len(strengths) == 0:
            st.caption("No significant leads found.")
        for _, row in strengths.iterrows():
            st.markdown(
                f"- **{THEME_LABELS.get(row['theme'], row['theme'])}** vs {row['competitor']}: "
                f"`{row['delta']:+.2f}`"
            )

    gaps = results.get("feature_gaps", [])
    if gaps:
        st.markdown('<p class="section-label">Feature Gaps</p>', unsafe_allow_html=True)
        gap_df = pd.DataFrame(gaps)
        gap_df["theme"] = gap_df["theme"].map(lambda t: THEME_LABELS.get(t, t))
        st.dataframe(gap_df, use_container_width=True, hide_index=True)


def _render_live_competitive(df: pd.DataFrame):
    st.markdown('<p class="section-label">Rating Comparison</p>', unsafe_allow_html=True)

    brand_ratings = df.groupby("brand").agg(
        avg_rating=("rating", "mean"),
        count=("review_id", "size"),
    ).round(2).sort_values("avg_rating", ascending=False)

    colors = [BRAND_COLORS.get(b, "#8b949e") for b in brand_ratings.index]
    fig = go.Figure(go.Bar(
        x=brand_ratings.index, y=brand_ratings["avg_rating"],
        marker_color=colors,
        text=[f"{r:.2f}" for r in brand_ratings["avg_rating"]],
        textposition="outside",
        textfont=dict(color=TEXT_SECONDARY),
    ))
    fig.update_layout(**dark_layout(
        height=350,
        yaxis=dict(range=[0, 5.5], title="Avg Rating", gridcolor=BORDER),
        xaxis=dict(gridcolor=BORDER),
    ))
    st.plotly_chart(fig, use_container_width=True)

# ─── Product Explorer ─────────────────────────────────────────────────────────

def render_products(df: pd.DataFrame, results: dict):
    st.markdown('<p class="section-label">Product Deep Dive</p>', unsafe_allow_html=True)

    product_stats = df.groupby(["product_name", "brand", "category"]).agg(
        reviews=("review_id", "size"),
        avg_rating=("rating", "mean"),
        neg_pct=("sentiment", lambda x: (x == "negative").mean() * 100),
        avg_severity=("severity", "mean"),
        pos_pct=("sentiment", lambda x: (x == "positive").mean() * 100),
    ).round(2).reset_index().sort_values("reviews", ascending=False)

    selected_product = st.selectbox(
        "Select Product",
        options=product_stats["product_name"].tolist(),
        key="product_selector",
    )

    prod_df = df[df["product_name"] == selected_product]
    prod_info = product_stats[product_stats["product_name"] == selected_product].iloc[0]

    brand = prod_info["brand"]

    cols = st.columns(5)
    cols[0].metric("Reviews", f"{int(prod_info['reviews']):,}")
    cols[1].metric("Avg Rating", f"{prod_info['avg_rating']:.2f}")
    cols[2].metric("Positive", f"{prod_info['pos_pct']:.0f}%")
    cols[3].metric("Negative", f"{prod_info['neg_pct']:.0f}%")
    cols[4].metric("Severity", f"{prod_info['avg_severity']:.1f}")

    col1, col2 = st.columns(2)

    with col1:
        fig = px.histogram(
            prod_df, x="rating", nbins=5,
            color_discrete_sequence=[BRAND_COLORS.get(brand, "#8b949e")],
            title="Rating Distribution",
        )
        fig.update_layout(**dark_layout(
            height=280, margin=dict(l=0, r=0, t=35, b=0),
            xaxis=dict(dtick=1, gridcolor=BORDER, zerolinecolor=BORDER),
            yaxis=dict(gridcolor=BORDER),
            bargap=0.15,
            title_font=dict(size=14, color=TEXT_SECONDARY),
        ))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        neg_prod = prod_df[prod_df["sentiment"].isin(["negative", "mixed"])]
        if len(neg_prod) > 0:
            theme_counts = neg_prod["primary_theme"].value_counts().head(8)
            labels = [THEME_LABELS.get(t, t) for t in theme_counts.index]
            fig = px.bar(
                x=theme_counts.values, y=labels,
                orientation="h", title="Top Complaint Themes",
                color_discrete_sequence=[DANGER],
            )
            fig.update_layout(**dark_layout(
                height=280, margin=dict(l=0, r=0, t=35, b=0),
                yaxis=dict(categoryorder="total ascending", automargin=True, gridcolor=BORDER),
                xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
                showlegend=False,
                title_font=dict(size=14, color=TEXT_SECONDARY),
            ))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("No negative reviews for this product!")

    failures = prod_df["failure_mode"].dropna()
    if len(failures) > 0:
        st.markdown('<p class="section-label">Failure Modes</p>', unsafe_allow_html=True)
        failure_counts = failures.value_counts().head(5)
        for mode, count in failure_counts.items():
            st.markdown(f"- **{safe(mode)}** ({count} reports)")

    st.markdown('<p class="section-label">Sample Reviews</p>', unsafe_allow_html=True)

    review_filter = st.radio(
        "Show", ["All", "Positive", "Negative", "Mixed"],
        horizontal=True, key="prod_review_filter",
    )

    show_df = prod_df
    if review_filter != "All":
        show_df = prod_df[prod_df["sentiment"] == review_filter.lower()]

    if len(show_df) == 0:
        st.caption("No reviews match this filter.")

    for _, r in show_df.head(8).iterrows():
        rating_int = int(r["rating"]) if pd.notna(r["rating"]) else 0
        stars = "★" * rating_int + "☆" * (5 - rating_int)
        sent_color = SENTIMENT_COLORS.get(r["sentiment"], "#8b949e")
        title_text = safe(r.get("title", ""), 100)
        st.markdown(
            f'<div class="review-quote">'
            f'<span style="color:{sent_color}; font-weight:600;">{stars}</span> '
            f'<strong>{title_text}</strong><br>'
            f'{safe(r["review_text"], 500)}'
            f'</div>',
            unsafe_allow_html=True,
        )

# ─── Trends & Signals ────────────────────────────────────────────────────────

def render_trends(df: pd.DataFrame, results: dict):
    st.markdown('<p class="section-label">Monthly Sentiment Trends</p>', unsafe_allow_html=True)

    if df["date"].notna().any():
        df_dated = df[df["date"].notna()].copy()
        df_dated["month"] = df_dated["date"].dt.to_period("M").astype(str)

        monthly = df_dated.groupby(["month", "sentiment"]).size().reset_index(name="count")

        fig = px.area(
            monthly, x="month", y="count", color="sentiment",
            color_discrete_map=SENTIMENT_COLORS,
            line_shape="spline",
        )
        fig.update_layout(**dark_layout(
            height=350,
            xaxis=dict(title="", gridcolor=BORDER, zerolinecolor=BORDER),
            yaxis=dict(title="Review Count", gridcolor=BORDER, zerolinecolor=BORDER),
            legend=dict(orientation="h", y=1.05, font_color=TEXT_PRIMARY),
        ))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown('<p class="section-label">Monthly Rating Trend by Brand</p>', unsafe_allow_html=True)

        monthly_brand = df_dated.groupby(["month", "brand"]).agg(
            avg_rating=("rating", "mean"),
        ).reset_index()

        fig = px.line(
            monthly_brand, x="month", y="avg_rating", color="brand",
            color_discrete_map=BRAND_COLORS,
            line_shape="spline",
        )
        fig.update_layout(**dark_layout(
            height=350,
            xaxis=dict(title="", gridcolor=BORDER, zerolinecolor=BORDER),
            yaxis=dict(title="Avg Rating", range=[1, 5], gridcolor=BORDER, zerolinecolor=BORDER),
            legend=dict(orientation="h", y=1.08, font_color=TEXT_PRIMARY),
        ))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No date data available for trend analysis")

    emerging = results.get("emerging_issues", [])
    if emerging:
        st.markdown('<p class="section-label">Emerging Issues</p>', unsafe_allow_html=True)

        em_df = pd.DataFrame(emerging)
        em_df["theme_label"] = em_df["theme"].map(lambda t: THEME_LABELS.get(t, t))

        fig = px.bar(
            em_df, x="growth_factor", y="theme_label", color="category",
            orientation="h",
            text=[f"{g:.1f}x" for g in em_df["growth_factor"]],
        )
        fig.update_layout(**dark_layout(
            height=max(200, len(em_df) * 45),
            xaxis=dict(title="Growth Factor", gridcolor=BORDER, zerolinecolor=BORDER),
            yaxis=dict(categoryorder="total ascending", automargin=True, gridcolor=BORDER),
        ))
        st.plotly_chart(fig, use_container_width=True)

    return_risks = results.get("return_risk", [])
    if return_risks:
        st.markdown('<p class="section-label">Return Risk Products</p>', unsafe_allow_html=True)

        risk_df = pd.DataFrame(return_risks)
        fig = px.scatter(
            risk_df, x="return_risk_count", y="avg_severity",
            size="return_risk_count", color="avg_severity",
            hover_name="product",
            color_continuous_scale=[WARNING, DANGER, "#8b0000"],
            size_max=40,
        )
        fig.update_layout(**dark_layout(
            height=350,
            xaxis=dict(title="Return-Risk Review Count", gridcolor=BORDER, zerolinecolor=BORDER),
            yaxis=dict(title="Avg Severity", gridcolor=BORDER, zerolinecolor=BORDER),
        ))
        st.plotly_chart(fig, use_container_width=True)

    verified_stats = results.get("verified_vs_unverified", {})
    if verified_stats:
        st.markdown('<p class="section-label">Verified vs Unverified</p>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Verified Avg Rating", verified_stats.get("verified_avg_rating", "N/A"))
            st.metric("Verified Count", f"{verified_stats.get('verified_count', 0):,}")
        with col2:
            st.metric("Unverified Avg Rating", verified_stats.get("unverified_avg_rating", "N/A"))
            st.metric("Unverified Count", f"{verified_stats.get('unverified_count', 0):,}")

# ─── Data & Export ────────────────────────────────────────────────────────────

def render_data(df: pd.DataFrame):
    st.markdown('<p class="section-label">Review Data Explorer</p>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search = st.text_input("Search reviews", "", placeholder="Type to search review text...")
    with col2:
        sort_by = st.selectbox("Sort by", ["rating", "severity", "date", "helpful_votes"])
    with col3:
        sort_order = st.radio("Order", ["Desc", "Asc"], horizontal=True)

    show_df = df.copy()
    if search:
        show_df = show_df[show_df["review_text"].str.contains(search, case=False, na=False, regex=False)]

    ascending = sort_order == "Asc"
    show_df = show_df.sort_values(sort_by, ascending=ascending, na_position="last")

    st.caption(f"Showing {min(len(show_df), 500):,} of {len(show_df):,} reviews")

    display_cols = [
        "brand", "product_name", "category", "rating", "sentiment",
        "primary_theme", "severity", "verified_purchase", "title", "review_text",
    ]
    available_cols = [c for c in display_cols if c in show_df.columns]

    st.dataframe(
        show_df[available_cols].head(500),
        use_container_width=True,
        hide_index=True,
        column_config={
            "rating": st.column_config.NumberColumn("Rating", format="%.0f ★"),
            "severity": st.column_config.NumberColumn("Severity", format="%d / 5"),
            "verified_purchase": st.column_config.CheckboxColumn("Verified"),
            "review_text": st.column_config.TextColumn("Review", width="large"),
        },
    )

    st.markdown('<p class="section-label">Export</p>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        csv = show_df.to_csv(index=False)
        st.download_button(
            "📥  Download CSV",
            csv, "sharkninja_review_data.csv", "text/csv",
            use_container_width=True,
        )
    with col2:
        neg_only = show_df[show_df["sentiment"] == "negative"].to_csv(index=False)
        st.download_button(
            "📥  Negative Only",
            neg_only, "negative_reviews.csv", "text/csv",
            use_container_width=True,
        )
    with col3:
        summary = show_df.groupby(["brand", "category", "primary_theme"]).agg(
            count=("review_id", "size"),
            avg_rating=("rating", "mean"),
            avg_severity=("severity", "mean"),
        ).round(2).reset_index().to_csv(index=False)
        st.download_button(
            "📥  Summary Pivot",
            summary, "review_summary.csv", "text/csv",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
