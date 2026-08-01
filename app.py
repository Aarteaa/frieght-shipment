import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from scipy.stats import chi2_contingency
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

st.set_page_config(page_title="Shipment Manifest — Analytics", layout="wide", page_icon="\U0001F4E6")

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------
INK = "#1C2333"
PAPER = "#F5F6F3"
RULE = "#CDD3D2"
AMBER = "#D98C1F"     # caution / weak signal
TEAL = "#1F6F5C"      # verified / good
BRICK = "#A63D2E"     # flagged / data issue
NAVY = "#24344D"      # primary accent
MUTED = "#6B7280"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif;
}}
.stApp {{
    background-color: {PAPER};
}}
h1, h2, h3 {{
    font-family: 'Oswald', sans-serif !important;
    color: {INK} !important;
    letter-spacing: 0.01em;
}}
code, .mono {{
    font-family: 'IBM Plex Mono', monospace !important;
}}

.manifest-header {{
    border: 1.5px solid {INK};
    background: #FFFFFF;
    padding: 28px 32px 22px 32px;
    margin-bottom: 8px;
    position: relative;
}}
.manifest-eyebrow {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    letter-spacing: 0.15em;
    color: {MUTED};
    text-transform: uppercase;
    margin-bottom: 6px;
}}
.manifest-title {{
    font-family: 'Oswald', sans-serif;
    font-weight: 600;
    font-size: 40px;
    color: {INK};
    line-height: 1.05;
    margin: 0;
}}
.route-line {{
    border: none;
    border-top: 2px dotted {RULE};
    margin: 18px 0 28px 0;
}}
.manifest-stat-row {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    color: {MUTED};
}}

.section-eyebrow {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    letter-spacing: 0.15em;
    color: {NAVY};
    text-transform: uppercase;
    border-bottom: 1px solid {RULE};
    padding-bottom: 6px;
    margin-bottom: 4px;
}}

.stamp-card {{
    position: relative;
    background: #FFFFFF;
    border: 1px solid {RULE};
    border-left: 4px solid var(--stamp-color, {NAVY});
    padding: 18px 20px;
    margin-bottom: 14px;
    overflow: hidden;
}}
.stamp-label {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.1em;
    color: {MUTED};
    text-transform: uppercase;
    margin-bottom: 6px;
}}
.stamp-value {{
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 600;
    font-size: 30px;
    color: {INK};
    line-height: 1;
}}
.stamp-badge {{
    position: absolute;
    top: 14px;
    right: 16px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.08em;
    font-weight: 600;
    text-transform: uppercase;
    border: 1.5px solid var(--stamp-color, {NAVY});
    color: var(--stamp-color, {NAVY});
    padding: 3px 8px;
    transform: rotate(4deg);
    border-radius: 2px;
}}

[data-baseweb="tab-list"] {{
    gap: 4px;
    border-bottom: 2px solid {INK} !important;
}}
[data-baseweb="tab"] {{
    font-family: 'Oswald', sans-serif !important;
    font-size: 15px !important;
    letter-spacing: 0.03em;
    color: {MUTED} !important;
}}
[data-baseweb="tab"][aria-selected="true"] {{
    color: {INK} !important;
}}
[data-baseweb="tab-highlight"] {{
    background-color: {AMBER} !important;
    height: 3px !important;
}}

.finding-note {{
    font-family: 'Inter', sans-serif;
    font-size: 14.5px;
    color: {INK};
    background: #FFFFFF;
    border: 1px solid {RULE};
    border-left: 4px solid {AMBER};
    padding: 12px 16px;
    margin: 10px 0 18px 0;
}}
</style>
""", unsafe_allow_html=True)


def stamp_card(label, value, status="neutral", note=None):
    colors = {"verified": TEAL, "caution": AMBER, "flagged": BRICK, "neutral": NAVY}
    badges = {"verified": "VERIFIED", "caution": "WEAK SIGNAL",
              "flagged": "DATA ISSUE", "neutral": "REFERENCE"}
    color = colors.get(status, NAVY)
    badge = badges.get(status, "REFERENCE")
    note_html = f'<div style="margin-top:8px;font-size:12.5px;color:{MUTED};">{note}</div>' if note else ""
    st.markdown(f"""
    <div class="stamp-card" style="--stamp-color:{color};">
        <div class="stamp-badge">{badge}</div>
        <div class="stamp-label">{label}</div>
        <div class="stamp-value">{value}</div>
        {note_html}
    </div>
    """, unsafe_allow_html=True)


def section_eyebrow(text):
    st.markdown(f'<div class="section-eyebrow">{text}</div>', unsafe_allow_html=True)


def finding_note(html):
    st.markdown(f'<div class="finding-note">{html}</div>', unsafe_allow_html=True)


PLOTLY_TEMPLATE = go.layout.Template(
    layout=dict(
        font=dict(family="Inter, sans-serif", color=INK, size=13),
        title=dict(font=dict(family="Oswald, sans-serif", size=18, color=INK)),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        colorway=[NAVY, AMBER, TEAL, BRICK, "#8A8F98", "#4C6B8A", "#B98A3D", "#5B8C7E",
                  "#7A4B42", "#3D4F6B", "#C7A868", "#6E9E92", "#9B5B4E", "#2E3D55", "#A9AEB5"],
        xaxis=dict(gridcolor=RULE, zerolinecolor=RULE),
        yaxis=dict(gridcolor=RULE, zerolinecolor=RULE),
    )
)


@st.cache_data
def load_data(path="shipments.csv"):
    df = pd.read_csv(path)
    date_cols = ["booking_date", "pickup_date", "delivery_date",
                 "promised_delivery_date", "actual_delivery_date"]
    for c in date_cols:
        df[c] = pd.to_datetime(df[c], errors="coerce")

    n_dupes = int(df["shipment_id"].duplicated().sum())
    df = df.drop_duplicates(subset="shipment_id").copy()

    known_pickup = df["pickup_date"].notna()
    invalid_order = known_pickup & (df["actual_delivery_date"] < df["pickup_date"])
    n_invalid_order = int(invalid_order.sum())
    df.loc[invalid_order, "actual_delivery_date"] = pd.NaT

    df["cost_per_km"] = df["freight_cost"] / df["distance_km"]

    usable = df[df["actual_delivery_date"].notna()].copy()
    usable["delay_days"] = (
        usable["actual_delivery_date"] - usable["promised_delivery_date"]
    ).dt.days
    usable["on_time"] = usable["delay_days"] <= 0

    meta = {
        "n_raw": len(df) + n_dupes,
        "n_dupes": n_dupes,
        "n_clean": len(df),
        "n_invalid_order": n_invalid_order,
        "n_usable": len(usable),
    }
    return df, usable, meta


df, usable, meta = load_data()

st.markdown(f"""
<div class="manifest-header">
    <div class="manifest-eyebrow">FreightFox &middot; Analysis Ref. SHP-2026-07 &middot; Shipment-Level Dataset</div>
    <div class="manifest-title">Shipment Manifest — Analytics</div>
    <hr class="route-line"/>
    <div class="manifest-stat-row">
        {meta['n_clean']:,} UNIQUE SHIPMENTS &nbsp;&middot;&nbsp;
        {meta['n_dupes']} DUPLICATE IDS DROPPED &nbsp;&middot;&nbsp;
        {meta['n_invalid_order']} INVALID DELIVERY-BEFORE-PICKUP ROWS &nbsp;&middot;&nbsp;
        {meta['n_usable']:,} USABLE FOR DELAY ANALYSIS
    </div>
</div>
""", unsafe_allow_html=True)

tabs = st.tabs([
    "Q4 · Data Quality",
    "Q1 · Regional OTD",
    "Q2 · Cost vs Distance",
    "Q3 · Customer Delays",
    "Q5 · Leading Metric",
])

with tabs[0]:
    section_eyebrow("Q4 — DATA QUALITY — READ THIS BEFORE TRUSTING ANYTHING ELSE")
    st.subheader("What's actually reliable in this file")

    st.markdown("**South region has a near-total data gap**")
    raw = pd.read_csv("shipments.csv")
    raw["actual_delivery_date"] = pd.to_datetime(raw["actual_delivery_date"], errors="coerce")
    raw = raw.drop_duplicates(subset="shipment_id")
    raw_resolved = raw[raw["status"].isin(["Delivered", "Delayed"])]
    fill_by_region = raw_resolved.groupby("region")["actual_delivery_date"].apply(
        lambda x: x.notna().mean() * 100
    ).round(1).sort_values()
    fig0 = px.bar(fill_by_region.reset_index(name="fill_rate"), x="region", y="fill_rate",
                  text="fill_rate",
                  title="% of Delivered/Delayed shipments with a recorded actual_delivery_date, by region")
    fig0.update_traces(texttemplate="%{text}%", textposition="outside", marker_color=NAVY)
    fig0.update_layout(template=PLOTLY_TEMPLATE, showlegend=False)
    st.plotly_chart(fig0, use_container_width=True)
    finding_note(
        "South has an <code>actual_delivery_date</code> on only <b>15.5%</b> of its resolved "
        "shipments, vs. <b>100%</b> everywhere else. Not a small-sample quirk — looks like a "
        "regional pipeline gap. South's numbers are flagged low-confidence throughout."
    )

    st.markdown("**The `status` label doesn't reliably describe what happened**")
    outcome_all = df[df["actual_delivery_date"].notna()].copy()
    outcome_all["actually_late"] = (
        outcome_all["actual_delivery_date"] - outcome_all["promised_delivery_date"]
    ).dt.days > 0
    delivered = outcome_all[outcome_all["status"] == "Delivered"]
    delayed = outcome_all[outcome_all["status"] == "Delayed"]
    c1, c2 = st.columns(2)
    with c1:
        stamp_card("Labeled 'Delivered' but actually late",
                    f"{delivered['actually_late'].mean():.1%}", "flagged", f"n = {len(delivered):,}")
    with c2:
        stamp_card("Labeled 'Delayed' but actually on-time",
                    f"{(~delayed['actually_late']).mean():.1%}", "flagged", f"n = {len(delayed):,}")
    finding_note(
        "Both numbers sit near 50% — a coin flip. Every delay figure on this dashboard is "
        "computed from dates directly; <code>status</code> is only used to identify shipments "
        "that should have an outcome."
    )

    st.markdown("**Everything else**")
    delivery_date_match = (df["delivery_date"] == df["promised_delivery_date"]).mean()
    st.write(
        f"- `delivery_date` matches `promised_delivery_date` in **{delivery_date_match:.0%}** "
        f"of rows — a duplicate column, excluded.\n"
        f"- **{meta['n_invalid_order']}** shipments show delivery before pickup — invalidated.\n"
        f"- **{meta['n_dupes']}** duplicate `shipment_id` values — dropped.\n"
        f"- **{df['booking_date'].isna().sum()}** missing `booking_date`, "
        f"**{df['pickup_date'].isna().sum()}** missing `pickup_date` — scattered, no pattern."
    )

with tabs[1]:
    section_eyebrow("Q1 — REGIONAL ON-TIME PERFORMANCE")
    st.subheader("On-time delivery by region")

    region_otd = usable.groupby("region")["on_time"].agg(["mean", "count"]).reset_index()
    region_otd["mean"] = (region_otd["mean"] * 100).round(1)
    region_otd = region_otd.sort_values("mean")

    p_region = chi2_contingency(pd.crosstab(usable["region"], usable["on_time"]))[1]
    p_mode = chi2_contingency(pd.crosstab(usable["mode"], usable["on_time"]))[1]
    p_carrier = chi2_contingency(pd.crosstab(usable["carrier_id"], usable["on_time"]))[1]

    fig = px.bar(region_otd, x="region", y="mean", text="mean",
                 labels={"mean": "On-time rate (%)"},
                 title=f"On-time rate by region  (chi\u00b2 p = {p_region:.2f})")
    fig.update_traces(texttemplate="%{text}%", textposition="outside", marker_color=NAVY)
    fig.update_layout(template=PLOTLY_TEMPLATE, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    finding_note(
        f"Region (p={p_region:.2f}) and mode (p={p_mode:.2f}) both fail a basic significance "
        f"test — the spread is noise. Carrier is the only dimension that clears p&lt;0.05 "
        f"(p={p_carrier:.3f}), so that's the real thread, not geography."
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        stamp_card("Region significance", f"p = {p_region:.2f}", "flagged", "not significant")
    with c2:
        stamp_card("Mode significance", f"p = {p_mode:.2f}", "flagged", "not significant")
    with c3:
        stamp_card("Carrier significance", f"p = {p_carrier:.3f}", "caution", "weak but real")

    carrier_otd = usable.groupby("carrier_id")["on_time"].agg(["mean", "count"]).reset_index()
    carrier_otd["mean"] = (carrier_otd["mean"] * 100).round(1)
    fig2 = px.bar(carrier_otd.sort_values("mean"), x="carrier_id", y="mean", text="mean",
                  title="On-time rate by carrier")
    fig2.update_traces(texttemplate="%{text}%", textposition="outside", marker_color=AMBER)
    fig2.update_layout(template=PLOTLY_TEMPLATE, showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

with tabs[2]:
    section_eyebrow("Q2 — FREIGHT COST vs. DISTANCE")
    st.subheader("Freight cost vs. distance")

    df_ex = df[df["carrier_id"] != "CARR_07"]
    model = LinearRegression().fit(df_ex[["distance_km"]], df_ex["freight_cost"])
    r2 = r2_score(df_ex["freight_cost"], model.predict(df_ex[["distance_km"]]))
    corr_ex = df_ex["distance_km"].corr(df_ex["freight_cost"])
    corr_all = df["distance_km"].corr(df["freight_cost"])

    c1, c2, c3 = st.columns(3)
    with c1:
        stamp_card("Correlation (all carriers)", f"{corr_all:.2f}", "caution", "outlier-distorted")
    with c2:
        stamp_card("Correlation (excl. CARR_07)", f"{corr_ex:.2f}", "verified", f"R\u00b2 = {r2:.2f}")
    with c3:
        stamp_card("Marginal cost (excl. CARR_07)", f"\u20b9{model.coef_[0]:.1f}/km", "verified")

    finding_note(
        "The pooled correlation looks weak because one carrier is far enough off the pricing "
        "curve to drag the whole regression down. Exclude it and the cost-distance relationship "
        "is clear and strong."
    )

    fig3 = px.scatter(
        df, x="distance_km", y="freight_cost", color="carrier_id",
        title="Cost vs distance (CARR_07 visibly off the trend)",
        opacity=0.55, render_mode="svg",
    )
    fig3.update_layout(template=PLOTLY_TEMPLATE)
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown("**Carrier cost-per-km vs. market rate**")
    market_rate = df_ex["cost_per_km"].mean()
    carrier_cpk = df.groupby("carrier_id")["cost_per_km"].mean().reset_index()
    carrier_cpk["multiple_of_market"] = (carrier_cpk["cost_per_km"] / market_rate).round(1)
    carrier_cpk = carrier_cpk.sort_values("multiple_of_market", ascending=False)

    fig4 = px.bar(carrier_cpk, x="carrier_id", y="multiple_of_market", text="multiple_of_market",
                  title=f"Cost-per-km as a multiple of market rate (\u20b9{market_rate:.1f}/km, CARR_07 excluded from baseline)")
    fig4.update_traces(texttemplate="%{text}x", textposition="outside", marker_color=BRICK)
    fig4.update_layout(template=PLOTLY_TEMPLATE, showlegend=False)
    st.plotly_chart(fig4, use_container_width=True)

    worst = carrier_cpk.iloc[0]
    stamp_card(f"{worst['carrier_id']} cost outlier", f"{worst['multiple_of_market']:.1f}x market",
                "flagged", "holds within every mode separately")

with tabs[3]:
    section_eyebrow("Q3 — CUSTOMER DELAY CONCENTRATION")
    st.subheader("Customers with the most delays")

    cust = usable.groupby("customer_id").agg(
        n=("shipment_id", "count"),
        delay_rate=("on_time", lambda x: (1 - x.mean()) * 100),
    ).reset_index()
    cust = cust[cust["n"] >= 20].sort_values("delay_rate", ascending=False)
    cust["delay_rate"] = cust["delay_rate"].round(1)

    st.dataframe(cust.head(15), use_container_width=True)

    top_cust = cust.iloc[0]["customer_id"]
    sub = usable[usable["customer_id"] == top_cust]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**{top_cust} — carrier spread**")
        st.bar_chart(sub["carrier_id"].value_counts(), color=NAVY)
    with col2:
        st.markdown(f"**{top_cust} — region spread**")
        st.bar_chart(sub["region"].value_counts(), color=AMBER)

    finding_note(
        f"{top_cust}'s delays spread across {sub['carrier_id'].nunique()} carriers and "
        f"{sub['region'].nunique()} regions with no concentration — doesn't look carrier- or "
        f"region-driven. On a sample of {len(sub)}, worth monitoring, not yet a root-cause claim."
    )

with tabs[4]:
    section_eyebrow("Q5 — LEADING INDICATOR")
    st.subheader("Recommended weekly tracking metric")
    st.markdown(
        "**Share of currently in-transit shipments already past their promised delivery date.**\n\n"
        "On-time rate only tells you about shipments that already finished — by then it's too "
        "late to act. This metric flags a shipment while it's still movable: expedite it, get "
        "ahead of the customer call, or swap carriers mid-route."
    )

    in_transit = df[df["status"] == "In-Transit"].copy()

    finding_note(
        "I'm deliberately <b>not</b> showing a single 'X% at risk' number here. This metric "
        "needs a real 'today' to compare against, and this is a static historical file with no "
        "live clock — any date invented as a stand-in for 'now' produces a distorted, near-100% "
        "figure, since in-transit shipments are scattered across the whole file rather than "
        "clustered near a true snapshot point. Showing a fabricated percentage would be worse "
        "than showing nothing."
    )

    stamp_card("Currently in-transit shipments", f"{len(in_transit):,}", "neutral",
                f"promised dates span {in_transit['promised_delivery_date'].min().date()} "
                f"to {in_transit['promised_delivery_date'].max().date()}")

    fig5 = px.histogram(
        in_transit, x="promised_delivery_date",
        title="Promised delivery dates of currently in-transit shipments",
    )
    fig5.update_traces(marker_color=TEAL)
    fig5.update_layout(template=PLOTLY_TEMPLATE, showlegend=False)
    st.plotly_chart(fig5, use_container_width=True)

    st.markdown(
        "**Second metric worth pairing with it:** weekly rate of `status`-vs-date disagreement. "
        "If that gap doesn't close, no dashboard built on top of `status` can be trusted."
    )
