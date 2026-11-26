import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Page Setup
st.set_page_config(page_title="Water Consumption & Maintenance Dashboard", layout="wide")

st.markdown("""
<style>
    .main-title { font-size: 2rem; font-weight: 700; margin-bottom: 0.2rem; }
    .subtitle { font-size: 1rem; color: #94A3B8; margin-bottom: 1.5rem; }
    div[data-testid="stMetric"] {
        border: 1px solid rgba(56, 189, 248, 0.3);
        border-radius: 10px;
        padding: 12px 16px;
        background-color: rgba(30, 41, 59, 0.4);
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">Water Consumption & Maintenance Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Building water usage overview, spike detection, and maintenance tracking</div>', unsafe_allow_html=True)

# 2. Load Datasets
@st.cache_data
def load_data():
    water = pd.read_csv("final_water_consumption.csv")
    try:
        priority = pd.read_csv("maintenance_priority_report.csv")
    except Exception:
        priority = pd.DataFrame()
    try:
        anomalies = pd.read_csv("water_anomaly_report.csv")
    except Exception:
        anomalies = pd.DataFrame()
    return water, priority, anomalies

water_df, priority_df, anomalies_df = load_data()

# Standardize column names cleanly
water_df["building"] = water_df["building"].astype(str).str.strip()
water_df["meter_reading_liters"] = pd.to_numeric(water_df["meter_reading_liters"], errors="coerce")
raw_rows = len(water_df)
invalid_rows = int(water_df["meter_reading_liters"].isna().sum())
negative_rows = int((water_df["meter_reading_liters"] < 0).sum())

# Keep only valid, non-negative readings
clean_df = water_df[water_df["meter_reading_liters"] >= 0].copy()
if "date" in clean_df.columns:
    clean_df["date"] = pd.to_datetime(clean_df["date"], errors="coerce")

# 3. Sidebar Filters
st.sidebar.header("Dashboard Filters")
all_buildings = sorted(clean_df["building"].unique())

select_all = st.sidebar.checkbox("Select All Buildings", value=True)
if select_all:
    selected_buildings = st.sidebar.multiselect("Select Buildings", all_buildings, default=all_buildings, key="all_b")
else:
    selected_buildings = st.sidebar.multiselect("Select Buildings", all_buildings, default=all_buildings[:1], key="sub_b")

filtered_df = clean_df[clean_df["building"].isin(selected_buildings)].copy()

if "date" in filtered_df.columns and not filtered_df["date"].isna().all():
    min_date, max_date = filtered_df["date"].min().date(), filtered_df["date"].max().date()
    if min_date < max_date:
        date_range = st.sidebar.date_input("Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
        if isinstance(date_range, tuple) and len(date_range) == 2:
            filtered_df = filtered_df[(filtered_df["date"].dt.date >= date_range[0]) & (filtered_df["date"].dt.date <= date_range[1])]

# 4. Top Summary Metrics (KPIs)
total_usage = filtered_df["meter_reading_liters"].sum()
avg_usage = filtered_df["meter_reading_liters"].mean() if not filtered_df.empty else 0

anom_count = len(anomalies_df[anomalies_df["building"].isin(selected_buildings)]) if not anomalies_df.empty and "building" in anomalies_df.columns else len(anomalies_df)
high_prio = len(priority_df[(priority_df["building"].isin(selected_buildings)) & (priority_df["priority"].astype(str).str.contains("High", case=False, na=False))]) if not priority_df.empty and "building" in priority_df.columns and "priority" in priority_df.columns else 0

if not filtered_df.empty:
    building_totals = filtered_df.groupby("building")["meter_reading_liters"].sum().sort_values(ascending=False)
    top_building = building_totals.index[0]
    top_share = (building_totals.iloc[0] / total_usage) * 100
else:
    top_building, top_share = "N/A", 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Water Used", f"{total_usage:,.0f} L")
c2.metric("Average per Reading", f"{avg_usage:,.0f} L")
c3.metric("Highest Consumer", top_building, f"{top_share:.1f}% of total")
c4.metric("Anomalies / High Priority", f"{anom_count} / {high_prio}")

if filtered_df.empty:
    st.warning("Please select at least one building from the left sidebar.")
    st.stop()

# 5. Organized Tabs
tab1, tab2, tab3 = st.tabs(["Easy Visual Charts", "Maintenance & Anomalies", "Data Quality & Download"])

with tab1:
    col_left, c_right = st.columns(2)

    # Chart 1: Simple Color-Coded Bar Chart
    with col_left:
        st.subheader("1. Which Building Uses the Most Water?")
        bar_data = filtered_df.groupby("building")["meter_reading_liters"].sum().reset_index().sort_values("meter_reading_liters")
        bar_data["Share"] = (bar_data["meter_reading_liters"] / total_usage * 100).round(1).astype(str) + "%"
        bar_data["Category"] = bar_data["building"].apply(lambda b: "Highest Consumer" if b == top_building else "Normal Usage")

        fig_bar = px.bar(
            bar_data,
            x="meter_reading_liters",
            y="building",
            orientation="h",
            text="Share",
            color="Category",
            color_discrete_map={"Highest Consumer": "#EF4444", "Normal Usage": "#38BDF8"},
            labels={"meter_reading_liters": "Total Water Used (Liters)", "building": ""},
        )
        fig_bar.update_traces(textposition="outside")
        fig_bar.update_layout(height=380, legend_title_text="", margin=dict(l=10, r=40, t=10, b=10))
        st.plotly_chart(fig_bar, use_container_width=True)
        st.caption(f"How to read: The red bar shows that **{top_building}** uses the most water ({top_share:.1f}% of total usage).")

    # Chart 2: Daily Trend with Highlighted Spike Dots
    with c_right:
        st.subheader("2. Daily Water Usage & High-Usage Spikes")
        daily_df = filtered_df.groupby(filtered_df["date"].dt.date)["meter_reading_liters"].sum().reset_index()
        daily_df.columns = ["Date", "Liters"]
        daily_avg = daily_df["Liters"].mean()
        spikes_df = daily_df[daily_df["Liters"] > daily_avg]

        fig_line = px.line(daily_df, x="Date", y="Liters", labels={"Liters": "Daily Water Used (Liters)", "Date": ""})
        fig_line.update_traces(line_color="#38BDF8", line_width=2.5)
        fig_line.add_scatter(
            x=spikes_df["Date"], y=spikes_df["Liters"],
            mode="markers", name="Above Average (Spike)",
            marker=dict(color="#EF4444", size=8)
        )
        fig_line.add_hline(y=daily_avg, line_dash="dash", line_color="#FACC15", annotation_text=f"Daily Average: {daily_avg:,.0f} L")
        fig_line.update_layout(height=380, legend_title_text="", margin=dict(l=10, r=20, t=10, b=10))
        st.plotly_chart(fig_line, use_container_width=True)
        st.caption(f"How to read: The yellow dashed line is the daily average ({daily_avg:,.0f} L). Red dots show {len(spikes_df)} days with above-average usage.")

    # Simple Summary Table
    st.subheader("3. Building-by-Building Summary Table")
    summary = filtered_df.groupby("building")["meter_reading_liters"].agg(
        Total_Readings="count",
        Total_Liters="sum",
        Average_Liters="mean",
        Peak_Liters="max"
    ).round(0).sort_values("Total_Liters", ascending=False).reset_index()
    st.dataframe(summary, use_container_width=True, hide_index=True)

with tab2:
    c_left, c_right = st.columns(2)
    with c_left:
        st.subheader("Maintenance Priority List")
        st.dataframe(priority_df, use_container_width=True, hide_index=True)
    with c_right:
        st.subheader("Detected Water Anomalies")
        st.dataframe(anomalies_df, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("Data Cleaning & Validation Summary")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Raw Rows", raw_rows)
    m2.metric("Missing / Invalid", invalid_rows)
    m3.metric("Negative Values", negative_rows)
    m4.metric("Clean Rows Used", len(clean_df))
    st.download_button("Download Filtered Data (CSV)", filtered_df.to_csv(index=False), "filtered_water_data.csv", "text/csv")
