import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Water Consumption Dashboard", layout="wide")
st.title("💧 Water Consumption & Maintenance Dashboard")


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
  st.error(
      "final_water_consumption.csv nahi mili. Kripya file repository mein"
      " upload karein."
  )
  st.stop()

building_col = find_column(
    water, ["building", "building_name", "facility", "block", "site", "name"]
)
consumption_col = find_column(water, [
    "consumption",
    "water_consumption",
    "usage",
    "water_usage",
    "liters",
    "volume",
    "value",
])
date_col = find_column(water, ["date", "timestamp", "datetime", "day"])
anomaly_col = find_column(
    water, ["anomaly", "is_anomaly", "outlier", "flag", "status"]
)

if building_col is None or consumption_col is None:
  st.error("Building ya consumption column automatically nahi mil paya.")
  st.write("Available columns:", list(water.columns))
  st.stop()

water[consumption_col] = pd.to_numeric(
    water[consumption_col], errors="coerce"
)
water = water.dropna(subset=[consumption_col]).copy()
water[building_col] = water[building_col].astype(str)

if date_col:
  water[date_col] = pd.to_datetime(water[date_col], errors="coerce")

# Sidebar filters
st.sidebar.header("Filters")
buildings = sorted(water[building_col].dropna().unique().tolist())
selected_buildings = st.sidebar.multiselect(
    "Select Buildings", buildings, default=buildings
)

filtered = water[water[building_col].isin(selected_buildings)].copy()

# KPIs
total_consumption = filtered[consumption_col].sum()
avg_consumption = filtered[consumption_col].mean() if not filtered.empty else 0

if anomaly_col:
  anomaly_count = (
      filtered[anomaly_col]
      .astype(str)
      .str.lower()
      .isin(["true", "1", "yes", "anomaly", "outlier"])
      .sum()
  )
elif anomalies is not None and not anomalies.empty:
  anom_b_col = find_column(anomalies, [
      "building",
      "building_name",
      "facility",
      "block",
      "site",
      "name",
  ])
  if anom_b_col:
    anomaly_count = len(
        anomalies[anomalies[anom_b_col].astype(str).isin(selected_buildings)]
    )
  else:
    anomaly_count = len(anomalies)
else:
  anomaly_count = 0

high_priority_count = 0
if priority is not None and not priority.empty:
  p_col = find_column(
      priority, ["priority", "maintenance_priority", "level", "status"]
  )
  p_b_col = find_column(priority, [
      "building",
      "building_name",
      "facility",
      "block",
      "site",
      "name",
  ])
  p_df = priority.copy()
  if p_b_col:
    p_df = p_df[p_df[p_b_col].astype(str).isin(selected_buildings)]
  if p_col:
    high_priority_count = (
        p_df[p_col]
        .astype(str)
        .str.lower()
        .str.contains("high", na=False)
        .sum()
    )

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Consumption", f"{total_consumption:,.2f}")
col2.metric("Average Consumption", f"{avg_consumption:,.2f}")
col3.metric("Anomalies Detected", f"{int(anomaly_count):,}")
col4.metric("High Priority Buildings", f"{int(high_priority_count):,}")

st.divider()

# Building-wise consumption bar chart
st.subheader("Building-wise Water Consumption")
if not filtered.empty:
  b_summary = (
      filtered.groupby(building_col)[consumption_col]
      .sum()
      .sort_values(ascending=False)
  )
  st.bar_chart(b_summary)
else:
  st.info("Selected buildings ke liye koi data nahi hai.")

# Daily consumption trend
if date_col:
  st.subheader("Daily Consumption Trend")
  daily_df = filtered.dropna(subset=[date_col]).copy()
  if not daily_df.empty:
    daily_df["Day"] = daily_df[date_col].dt.date
    daily_trend = daily_df.groupby("Day")[consumption_col].sum()
    st.line_chart(daily_trend)

# Maintenance priority report
st.subheader("Maintenance Priority Report")
if priority is not None and not priority.empty:
  st.dataframe(priority, use_container_width=True)
else:
  st.info("maintenance_priority_report.csv available nahi hai ya khali hai.")

# Anomaly report
st.subheader("Anomaly Report")
if anomalies is not None and not anomalies.empty:
  st.dataframe(anomalies, use_container_width=True)
elif anomaly_col:
  anom_rows = filtered[
      filtered[anomaly_col]
      .astype(str)
      .str.lower()
      .isin(["true", "1", "yes", "anomaly", "outlier"])
  ]
  st.dataframe(anom_rows, use_container_width=True)
else:
  st.info("Anomaly report data available nahi hai.")

# Download filtered data
st.download_button(
    label="Download Filtered Data (CSV)",
    data=filtered.to_csv(index=False).encode("utf-8"),
    file_name="filtered_water_consumption.csv",
    mime="text/csv",
)
