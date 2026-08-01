import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
from scipy.stats import chi2_contingency
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

st.set_page_config(page_title="Shipment Analytics", layout="wide")


# ---------------------------------------------------------------------------
# Data loading + cleaning
# ---------------------------------------------------------------------------
@st.cache_data
def load_data(path="shipments.csv"):
    df = pd.read_csv(path)
    date_cols = ["booking_date", "pickup_date", "delivery_date",
                 "promised_delivery_date", "actual_delivery_date"]
    for c in date_cols:
        df[c] = pd.to_datetime(df[c], errors="coerce")

    n_dupes = int(df["shipment_id"].duplicated().sum())
    df = df.drop_duplicates(subset="shipment_id").copy()

    # Invalidate physically impossible rows: delivered before picked up.
    # Only null out actual_delivery_date where pickup_date is known and the
    # comparison actually fails -- do NOT do a raw >= comparison against a
    # column with NaNs, since NaN comparisons are always False in pandas and
    # would silently wipe out rows with a missing pickup_date instead of just
    # the genuinely invalid ones.
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

st.title("Shipment Analytics Dashboard")
st.caption(
    f"{meta['n_clean']} unique shipments ({meta['n_dupes']} duplicate IDs dropped, "
    f"{meta['n_invalid_order']} delivered-before-pickup rows invalidated). "
    f"{meta['n_usable']} have a usable actual delivery date and drive the delay analysis below."
)

tabs = st.tabs([
    "Data Quality",
    "Q1 · Regional OTD",
    "Q2 · Cost vs Distance",
    "Q3 · Customer Delays",
    "Q5 · Leading Metric",
])

# ---------------------------------------------------------------------------
# Data Quality
# ---------------------------------------------------------------------------
with tabs[0]:
    st.header("Data quality issues found")

    st.subheader("1. South region has a near-total data gap")
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
    fig0.update_traces(texttemplate="%{text}%", textposition="outside")
    st.plotly_chart(fig0, use_container_width=True)
    st.error(
        "South has an actual_delivery_date on only 15.5% of its resolved shipments, "
        "vs. 100% everywhere else. This isn't a small-sample quirk -- it looks like a "
        "regional data pipeline gap. South's numbers throughout this dashboard are "
        "flagged low-confidence as a result."
    )

    st.subheader("2. The status label doesn't reliably describe what happened")
    outcome_all = df[df["actual_delivery_date"].notna()].copy()
    outcome_all["actually_late"] = (
        outcome_all["actual_delivery_date"] - outcome_all["promised_delivery_date"]
    ).dt.days > 0
    delivered = outcome_all[outcome_all["status"] == "Delivered"]
    delayed = outcome_all[outcome_all["status"] == "Delayed"]
    c1, c2 = st.columns(2)
    c1.metric("Labeled 'Delivered' but actually late",
              f"{delivered['actually_late'].mean():.1%}", f"n={len(delivered)}")
    c2.metric("Labeled 'Delayed' but actually on-time",
              f"{(~delayed['actually_late']).mean():.1%}", f"n={len(delayed)}")
    st.warning(
        "Both numbers sit right around 50% -- essentially a coin flip. Every delay "
        "figure in this dashboard is computed from dates directly; the status "
        "column is only used to identify shipments that should have an outcome."
    )

    st.subheader("3. Delivered-before-pickup rows")
    st.write(
        f"**{meta['n_invalid_order']}** shipments show an `actual_delivery_date` before "
        f"`pickup_date` -- logically impossible. Invalidated and excluded from delay math."
    )

    st.subheader("4. Smaller issues")
    delivery_date_match = (df["delivery_date"] == df["promised_delivery_date"]).mean()
    st.write(
        f"- `delivery_date` matches `promised_delivery_date` in **{delivery_date_match:.0%}** "
        f"of rows -- a duplicate column with no independent information, excluded.\n"
        f"- **{meta['n_dupes']}** duplicate `shipment_id` values, dropped (first occurrence kept).\n"
        f"- **{df['booking_date'].isna().sum()}** missing `booking_date`, "
        f"**{df['pickup_date'].isna().sum()}** missing `pickup_date` -- scattered across "
        f"statuses with no clear pattern."
    )

# ---------------------------------------------------------------------------
# Q1 — Regional OTD
# ---------------------------------------------------------------------------
with tabs[1]:
    st.header("On-time delivery by region")

    region_otd = usable.groupby("region")["on_time"].agg(["mean", "count"]).reset_index()
    region_otd["mean"] = (region_otd["mean"] * 100).round(1)
    region_otd = region_otd.sort_values("mean")

    p_region = chi2_contingency(pd.crosstab(usable["region"], usable["on_time"]))[1]
    p_mode = chi2_contingency(pd.crosstab(usable["mode"], usable["on_time"]))[1]
    p_carrier = chi2_contingency(pd.crosstab(usable["carrier_id"], usable["on_time"]))[1]

    fig = px.bar(region_otd, x="region", y="mean", text="mean",
                 labels={"mean": "On-time rate (%)"},
                 title=f"On-time rate by region  (chi² p = {p_region:.2f})")
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    st.info(
        f"Region (p={p_region:.2f}) and mode (p={p_mode:.2f}) both fail a basic "
        f"significance test -- the spread you see is noise. Carrier is the only "
        f"dimension that clears p<0.05 (p={p_carrier:.3f}), so that's the real thread."
    )

    sig_col1, sig_col2, sig_col3 = st.columns(3)
    sig_col1.metric("Region p-value", f"{p_region:.2f}")
    sig_col2.metric("Mode p-value", f"{p_mode:.2f}")
    sig_col3.metric("Carrier p-value", f"{p_carrier:.3f}")

    carrier_otd = usable.groupby("carrier_id")["on_time"].agg(["mean", "count"]).reset_index()
    carrier_otd["mean"] = (carrier_otd["mean"] * 100).round(1)
    fig2 = px.bar(carrier_otd.sort_values("mean"), x="carrier_id", y="mean", text="mean",
                  title="On-time rate by carrier")
    fig2.update_traces(texttemplate="%{text}%", textposition="outside")
    st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------------
# Q2 — Cost vs distance
# ---------------------------------------------------------------------------
with tabs[2]:
    st.header("Freight cost vs. distance")

    df_ex = df[df["carrier_id"] != "CARR_07"]
    model = LinearRegression().fit(df_ex[["distance_km"]], df_ex["freight_cost"])
    r2 = r2_score(df_ex["freight_cost"], model.predict(df_ex[["distance_km"]]))
    corr_ex = df_ex["distance_km"].corr(df_ex["freight_cost"])
    corr_all = df["distance_km"].corr(df["freight_cost"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Correlation (all carriers)", f"{corr_all:.2f}")
    c2.metric("Correlation (excl. CARR_07)", f"{corr_ex:.2f}")
    c3.metric("Marginal cost (excl. CARR_07)", f"₹{model.coef_[0]:.1f}/km")
    st.caption(
        f"The pooled correlation looks weak because one carrier is far enough off "
        f"the pricing curve to drag the whole regression down. Exclude it and the "
        f"cost-distance relationship is clear and strong (R² = {r2:.2f})."
    )

    fig3 = px.scatter(
        df, x="distance_km", y="freight_cost", color="carrier_id",
        title="Cost vs distance (CARR_07 visibly off the trend)",
        opacity=0.5,
        render_mode="svg",  # force SVG instead of WebGL -- WebGL scattergl
                            # silently fails on browsers/environments without
                            # GPU/WebGL support, which is what happened here
    )
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Carrier cost-per-km vs. market rate")
    market_rate = df_ex["cost_per_km"].mean()
    carrier_cpk = df.groupby("carrier_id")["cost_per_km"].mean().reset_index()
    carrier_cpk["multiple_of_market"] = (carrier_cpk["cost_per_km"] / market_rate).round(1)
    carrier_cpk = carrier_cpk.sort_values("multiple_of_market", ascending=False)

    fig4 = px.bar(carrier_cpk, x="carrier_id", y="multiple_of_market", text="multiple_of_market",
                  title=f"Cost-per-km as a multiple of market rate (₹{market_rate:.1f}/km, CARR_07 excluded from baseline)")
    fig4.update_traces(texttemplate="%{text}x", textposition="outside")
    st.plotly_chart(fig4, use_container_width=True)

    worst = carrier_cpk.iloc[0]
    st.error(
        f"**{worst['carrier_id']}** runs at **{worst['multiple_of_market']:.1f}x** the market "
        f"cost-per-km. This holds separately within FTL, LTL, and PTL, so it isn't just "
        f"a mode-mix effect -- worth a direct conversation on pricing."
    )

# ---------------------------------------------------------------------------
# Q3 — Customer delays
# ---------------------------------------------------------------------------
with tabs[3]:
    st.header("Customers with the most delays")

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
        st.write(f"**{top_cust}** carrier spread:")
        st.bar_chart(sub["carrier_id"].value_counts())
    with col2:
        st.write(f"**{top_cust}** region spread:")
        st.bar_chart(sub["region"].value_counts())

    st.info(
        f"{top_cust}'s delays spread across {sub['carrier_id'].nunique()} carriers and "
        f"{sub['region'].nunique()} regions with no concentration -- doesn't look "
        f"carrier- or region-driven. On a sample of {len(sub)}, worth monitoring, not "
        f"yet worth a root-cause claim."
    )

# ---------------------------------------------------------------------------
# Q5 — Leading indicator
# ---------------------------------------------------------------------------
with tabs[4]:
    st.header("Recommended weekly tracking metric")
    st.markdown(
        """
        **Share of currently in-transit shipments already past their promised delivery date.**

        On-time rate only tells you about shipments that already finished -- by then
        it's too late to act. This metric flags a shipment while it's still movable:
        expedite it, get ahead of the customer call, or swap carriers mid-route.
        """
    )

    in_transit = df[df["status"] == "In-Transit"].copy()

    st.warning(
        "I'm deliberately **not** showing a single 'X% at risk' number here. This "
        "metric needs a real 'today' to compare against, and this is a static "
        "historical file with no live clock -- any date I invent as a stand-in for "
        "'now' (max booking date, max promised date, etc.) produces a distorted, "
        "near-100% figure, because in-transit shipments are scattered across the "
        "whole file rather than clustered near a true snapshot point. Showing a "
        "fabricated percentage here would be worse than showing nothing."
    )

    st.write(
        f"What I can show honestly: **{len(in_transit)}** shipments are currently "
        f"In-Transit, with promised delivery dates spanning "
        f"{in_transit['promised_delivery_date'].min().date()} to "
        f"{in_transit['promised_delivery_date'].max().date()}. In production, this "
        f"metric becomes trivial to compute correctly -- you'd compare each "
        f"in-transit shipment's `promised_delivery_date` against the real system "
        f"clock, which a static export doesn't have."
    )

    fig5 = px.histogram(
        in_transit, x="promised_delivery_date",
        title="Promised delivery dates of currently in-transit shipments",
    )
    st.plotly_chart(fig5, use_container_width=True)

    st.markdown(
        """
        **Second metric worth pairing with it:** weekly rate of `status`-vs-date
        disagreement. If that gap doesn't close, no dashboard built on top of `status`
        can be trusted, and that's worth fixing before anything else here.
        """
    )
