import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(
    page_title="Water Consumption & Maintenance Dashboard",
    page_icon="💧",
    layout="wide",
)

st.markdown("""
<style>
    .main-title { font-size: 2.1rem; font-weight: 700; margin-bottom: 0.2rem; color: #F8FAFC; }
    .subtitle { font-size: 1rem; color: #94A3B8; margin-bottom: 1.5rem; }
    div[data-testid="stMetric"] {
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 12px;
        padding: 14px 18px;
        background: linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(30, 41, 59, 0.4));
    }
    div[data-testid="stMetricValue"] { font-size: 1.65rem; font-weight: 700; color: #38BDF8; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">💧 Water Consumption & Maintenance Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Real-time building usage analytics, automated anomaly detection, and maintenance prioritization</div>', unsafe_allow_html=True)

def find_column(df, candidates):
    if df is None or df.empty:
        return None
    cols_lower = {c.lower().strip(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
    for c in df.columns:
        c_low = c.lower()
        for cand in candidates:
            if cand.lower() in c_low:
                return c
    return None

@st.cache_data
def load_csv(path):
    try:
        return pd.read_csv(path)
    except Exception:
        return None

water = load_csv("final_water_consumption.csv")
priority = load_csv("maintenance_priority_report.csv")
anomalies = load_csv("water_anomaly_report.csv")

if water is None:
    st.error("final_water_consumption.csv not found. Please upload the file to the repository.")
    st.stop()

building_col = find_column(water, ["building", "building_name", "facility", "block", "site", "name"])
consumption_col = find_column(water, ["consumption", "water_consumption", "usage", "water_usage", "liters", "volume", "value", "meter_reading_liters"])
date_col = find_column(water, ["date", "timestamp", "datetime", "day"])
anomaly_col = find_column(water, ["anomaly", "is_anomaly", "outlier", "flag", "status"])

if building_col is None or consumption_col is None:
    st.error("Could not automatically detect building or consumption columns.")
    st.write("Available columns:", list(water.columns))
    st.stop()

raw_row_count = len(water)
numeric_consumption = pd.to_numeric(water[consumption_col], errors="coerce")
non_numeric_count = int(numeric_consumption.isna().sum())

water = water.copy()
water[consumption_col] = numeric_consumption
water = water.dropna(subset=[consumption_col]).copy()

negative_count = int((water[consumption_col] < 0).sum())
valid_water = water[water[consumption_col] >= 0].copy()
valid_water[building_col] = valid_water[building_col].astype(str).str.strip()

if date_col:
    valid_water[date_col] = pd.to_datetime(valid_water[date_col], errors="coerce")

# --- SIDEBAR FILTERS ---
st.sidebar.header("🎛️ Dashboard Filters")
buildings = sorted(valid_water[building_col].dropna().unique().tolist())

select_all = st.sidebar.checkbox("Select All Buildings", value=True)
if select_all:
    selected_buildings = st.sidebar.multiselect("Select Buildings", buildings, default=buildings)
else:
    selected_buildings = st.sidebar.multiselect("Select Buildings", buildings, default=buildings[:1] if buildings else [])

filtered = valid_water[valid_water[building_col].isin(selected_buildings)].copy()

if date_col and not filtered[date_col].isna().all():
    min_d = filtered[date_col].min().date()
    max_d = filtered[date_col].max().date()
    if min_d < max_d:
        date_range = st.sidebar.date_input("Date Range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
        if isinstance(date_range, tuple) and len(date_range) == 2:
            filtered = filtered[(filtered[date_col].dt.date >= date_range[0]) & (filtered[date_col].dt.date <= date_range[1])]

# --- KPI CALCULATIONS ---
total_consumption = filtered[consumption_col].sum() if not filtered.empty else 0
avg_consumption = filtered[consumption_col].mean() if not filtered.empty else 0

if anomaly_col:
    anomaly_count = int(filtered[anomaly_col].astype(str).str.lower().isin(["true", "1", "yes", "anomaly", "outlier"]).sum())
elif anomalies is not None and not anomalies.empty:
    anom_b_col = find_column(anomalies, ["building", "building_name", "facility", "block", "site", "name"])
    if anom_b_col:
        anomaly_count = len(anomalies[anomalies[anom_b_col].astype(str).str.strip().isin(selected_buildings)])
    else:
        anomaly_count = len(anomalies)
else:
    anomaly_count = 0

high_priority_count = 0
if priority is not None and not priority.empty:
    p_col = find_column(priority, ["priority", "maintenance_priority", "level", "status"])
    p_b_col = find_column(priority, ["building", "building_name", "facility", "block", "site", "name"])
    p_df = priority.copy()
    if p_b_col:
        p_df = p_df[p_df[p_b_col].astype(str).str.strip().isin(selected_buildings)]
    if p_col:
        high_priority_count = int(p_df[p_col].astype(str).str.lower().str.contains("high", na=False).sum())

top_building = "N/A"
top_share = 0.0
if not filtered.empty:
    b_totals = filtered.groupby(building_col)[consumption_col].sum().sort_values(ascending=False)
    top_building = b_totals.index[0]
    top_share = (b_totals.iloc[0] / total_consumption * 100) if total_consumption > 0 else 0

# --- KPI ROW ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Water Usage (L)", f"{total_consumption:,.0f}")
col2.metric("Avg Usage / Record (L)", f"{avg_consumption:,.1f}")
col3.metric("Top Consumer", f"{top_building}", f"{top_share:.1f}% of total" if top_building != "N/A" else None)
col4.metric("Anomalies / High Priority", f"{anomaly_count} / {high_priority_count}")

# --- AUTOMATED KEY INSIGHT BANNER ---
if not filtered.empty:
    st.info(
        f"**Key Takeaway:** **{top_building}** is the highest water consumer, accounting for **{top_share:.1f}%** "
        f"({b_totals.iloc[0]:,.0f} L) of the selected usage. Currently **{anomaly_count}** anomalies and "
        f"**{high_priority_count}** high-priority maintenance alerts are active."
    )
else:
    st.warning("No records match the current filter selection. Please select at least one building from the sidebar.")

# --- ORGANIZED TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Visual Analytics", "🚨 Maintenance & Anomalies", "🛡️ Data Health & Export"])

with tab1:
    if not filtered.empty:
        left_col, right_col = st.columns(2)
        with left_col:
            st.subheader("Building-wise Total Consumption")
            b_summary = (
                filtered.groupby(building_col)[consumption_col]
                .sum()
                .reset_index()
                .sort_values(by=consumption_col, ascending=True)
            )
            b_summary["Share (%)"] = (b_summary[consumption_col] / total_consumption * 100).round(1)
            fig_bar = px.bar(
                b_summary,
                x=consumption_col,
                y=building_col,
                orientation="h",
                text="Share (%)",
                color=consumption_col,
                color_continuous_scale="Blues",
                labels={consumption_col: "Total Consumption (Liters)", building_col: "Building"},
            )
            fig_bar.update_traces(texttemplate="%{text}%", textposition="outside")
            fig_bar.update_layout(showlegend=False, coloraxis_showscale=False, height=400, margin=dict(l=10, r=30, t=20, b=20))
            st.plotly_chart(fig_bar, use_container_width=True)

        with right_col:
            if date_col and not filtered[date_col].isna().all():
                st.subheader("Daily Consumption Trend & Average Threshold")
                daily_df = filtered.dropna(subset=[date_col]).copy()
                daily_df["Day"] = daily_df[date_col].dt.date
                daily_trend = daily_df.groupby("Day")[consumption_col].sum().reset_index()
                mean_daily = daily_trend[consumption_col].mean()

                fig_line = px.line(
                    daily_trend,
                    x="Day",
                    y=consumption_col,
                    markers=True,
                    labels={"Day": "Date", consumption_col: "Daily Usage (Liters)"},
                )
                fig_line.update_traces(line_color="#2DD4BF", line_width=2.5)
                fig_line.add_hline(
                    y=mean_daily,
                    line_dash="dash",
                    line_color="#F59E0B",
                    annotation_text=f"Daily Avg: {mean_daily:,.0f} L",
                    annotation_position="top left",
                )
                fig_line.update_layout(height=400, margin=dict(l=10, r=20, t=20, b=20))
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                st.subheader("Consumption Share Breakdown")
                fig_pie = px.pie(
                    b_summary,
                    values=consumption_col,
                    names=building_col,
                    hole=0.45,
                    color_discrete_sequence=px.colors.sequential.Tealgrn,
                )
                fig_pie.update_traces(textposition="inside", textinfo="percent+label")
                fig_pie.update_layout(height=400, margin=dict(l=10, r=10, t=20, b=20))
                st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("Building Performance Summary")
        summary_table = (
            filtered.groupby(building_col)[consumption_col]
            .agg(Records="count", Total_Liters="sum", Avg_Liters="mean", Max_Reading="max")
            .round(2)
            .sort_values(by="Total_Liters", ascending=False)
            .reset_index()
        )
        st.dataframe(summary_table, use_container_width=True, hide_index=True)

with tab2:
    rep_col1, rep_col2 = st.columns(2)
    with rep_col1:
        st.subheader("Maintenance Priority Report")
        if priority is not None and not priority.empty:
            st.dataframe(priority, use_container_width=True, hide_index=True)
        else:
            st.info("maintenance_priority_report.csv is not available or is empty.")

    with rep_col2:
        st.subheader("Detected Anomalies Report")
        if anomalies is not None and not anomalies.empty:
            st.dataframe(anomalies, use_container_width=True, hide_index=True)
        elif anomaly_col:
            anom_rows = filtered[filtered[anomaly_col].astype(str).str.lower().isin(["true", "1", "yes", "anomaly", "outlier"])]
            st.dataframe(anom_rows, use_container_width=True, hide_index=True)
        else:
            st.info("Anomaly report data is not available.")

with tab3:
    st.subheader("Data Validation & Quality Check")
    v_col1, v_col2, v_col3, v_col4 = st.columns(4)
    v_col1.metric("Raw Records", f"{raw_row_count:,}")
    v_col2.metric("Invalid / Missing", f"{non_numeric_count:,}")
    v_col3.metric("Negative Values", f"{negative_count:,}")
    v_col4.metric("Clean Valid Records", f"{len(valid_water):,}")

    if negative_count > 0 or non_numeric_count > 0:
        st.warning(f"Excluded {non_numeric_count} non-numeric/missing values and {negative_count} negative rows from active analytics.")
    else:
        st.success("All consumption records passed non-negative and numeric validation checks.")

    st.divider()
    st.download_button(
        label="⬇️ Download Filtered Dataset (CSV)",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name="filtered_water_consumption.csv",
        mime="text/csv",
    )
