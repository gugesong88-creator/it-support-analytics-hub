"""Streamlit dashboard for IT support tickets, SLA, and FTE workload analytics."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from src.data_generator import generate_sample_data
from src.data_loader import load_fte, load_system_mapping, load_tickets
from src.metrics import build_summary_tables, calculate_kpis
from src.report_generator import generate_excel_report, generate_html_weekly_summary, generate_risk_ticket_csv
from src.sla_rules import add_workload_flags, apply_sla_rules, merge_system_mapping
from src.utils import DATA_DIR, format_hours, format_number, format_percent


st.set_page_config(
    page_title="IT Support Analytics Hub",
    page_icon="🛠️",
    layout="wide",
)


def ensure_sample_data() -> None:
    """Create default sample data when missing."""
    required_files = ["sample_tickets.csv", "sample_fte.csv", "sample_system_mapping.csv"]
    if not all((DATA_DIR / filename).exists() for filename in required_files):
        generate_sample_data(DATA_DIR)


def inject_styles() -> None:
    """Apply lightweight dashboard CSS."""
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.35rem; padding-bottom: 2rem;}
        .hero-note {
            border-left: 4px solid #2A9D8F;
            background: #F6FBFA;
            padding: 1rem 1.1rem;
            border-radius: 8px;
            color: #1C2B2A;
            margin-bottom: 1rem;
        }
        div[data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid #E6E8EC;
            border-radius: 8px;
            padding: 0.85rem 1rem;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
        }
        div[data-testid="stMetricLabel"] p {font-size: 0.86rem;}
        div[data-testid="stMetricValue"] {font-size: 1.35rem;}
        h1, h2, h3 {letter-spacing: 0;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def filter_options(df: pd.DataFrame, column: str) -> list[str]:
    """Return sorted options for a sidebar filter."""
    if column not in df.columns:
        return []
    values = df[column].dropna().astype(str)
    return sorted([value for value in values.unique().tolist() if value and value.lower() != "nan"])


def apply_filters(tickets: pd.DataFrame, fte: pd.DataFrame, filters: dict[str, list[str]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply sidebar filters to ticket and FTE datasets."""
    filtered_tickets = tickets.copy()
    filtered_fte = fte.copy()

    shared_columns = ["entity", "system_name", "week"]
    ticket_only = ["issue_type", "priority", "status", "assigned_to", "risk_level"]
    for column in shared_columns:
        selected = filters.get(column, [])
        if selected:
            filtered_tickets = filtered_tickets[filtered_tickets[column].astype(str).isin(selected)]
            filtered_fte = filtered_fte[filtered_fte[column].astype(str).isin(selected)]
    for column in ticket_only:
        selected = filters.get(column, [])
        if selected:
            filtered_tickets = filtered_tickets[filtered_tickets[column].astype(str).isin(selected)]
    return filtered_tickets, filtered_fte


def plot_bar(df: pd.DataFrame, x: str, y: str, title: str, orientation: str = "v") -> None:
    """Render a consistent Plotly bar chart or empty-state message."""
    if df.empty:
        st.info(f"{title}: no data in current selection.")
        return
    fig = px.bar(
        df,
        x=x,
        y=y,
        orientation=orientation,
        title=title,
        color=y if orientation == "v" else x,
        color_continuous_scale=["#2A9D8F", "#E9C46A", "#E76F51"],
    )
    fig.update_layout(
        height=350,
        margin=dict(l=10, r=10, t=55, b=10),
        title_font_size=16,
        coloraxis_showscale=False,
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    st.plotly_chart(fig, width="stretch")


def main() -> None:
    """Run the Streamlit application."""
    ensure_sample_data()
    inject_styles()

    st.title("IT Support Analytics Hub")
    st.caption("企业 IT 运维工单与 SLA 分析平台 | L2 Support Report Automation Demo")

    with st.sidebar:
        st.header("Data & Filters")
        ticket_file = st.file_uploader("Upload Ticket CSV / Excel", type=["csv", "xlsx", "xls"])
        fte_file = st.file_uploader("Upload FTE CSV / Excel", type=["csv", "xlsx", "xls"])
        mapping_file = st.file_uploader("Upload System Mapping CSV / Excel", type=["csv", "xlsx", "xls"])
        selected_today = st.date_input("Analysis date", value=date.today())

    tickets_raw = load_tickets(ticket_file)
    fte_raw = load_fte(fte_file)
    mapping_raw = load_system_mapping(mapping_file)

    tickets_processed = apply_sla_rules(tickets_raw, selected_today)
    tickets_processed = merge_system_mapping(tickets_processed, mapping_raw)
    fte_processed = add_workload_flags(fte_raw)

    with st.sidebar:
        st.divider()
        filters = {
            "entity": st.multiselect("entity", filter_options(tickets_processed, "entity")),
            "system_name": st.multiselect("system_name", filter_options(tickets_processed, "system_name")),
            "issue_type": st.multiselect("issue_type", filter_options(tickets_processed, "issue_type")),
            "priority": st.multiselect("priority", filter_options(tickets_processed, "priority")),
            "status": st.multiselect("status", filter_options(tickets_processed, "status")),
            "assigned_to": st.multiselect("assigned_to", filter_options(tickets_processed, "assigned_to")),
            "week": st.multiselect("week", filter_options(tickets_processed, "week")),
            "risk_level": st.multiselect("risk_level", ["HIGH", "MEDIUM", "LOW"]),
        }

    filtered_tickets, filtered_fte = apply_filters(tickets_processed, fte_processed, filters)
    summary_tables = build_summary_tables(filtered_tickets, filtered_fte)
    kpis = calculate_kpis(filtered_tickets, filtered_fte)

    st.markdown(
        """
        <div class="hero-note">
        This demo uses simulated Jira-style tickets and FTE workload data to reproduce the weekly L2 Support Report workflow:
        data cleaning, SLA monitoring, ticket risk identification, workload analysis, and weekly summary generation.
        It does not contain any real company, employee, customer, email, or system link information.
        </div>
        """,
        unsafe_allow_html=True,
    )

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("Reported Tickets", format_number(kpis["reported_tickets"]))
    kpi_cols[1].metric("Closed Tickets", format_number(kpis["closed_tickets"]))
    kpi_cols[2].metric("Pending Tickets", format_number(kpis["pending_tickets"]))
    kpi_cols[3].metric("SLA Breach Rate", format_percent(kpis["sla_breach_rate"]))
    kpi_cols_2 = st.columns(4)
    kpi_cols_2[0].metric("Released CR", format_number(kpis["released_cr"]))
    kpi_cols_2[1].metric("In Progress CR", format_number(kpis["in_progress_cr"]))
    kpi_cols_2[2].metric("Total Used FTEs", f"{kpis['total_used_ftes']:,.1f}")
    kpi_cols_2[3].metric("Avg Resolution Hours", format_hours(kpis["avg_resolution_hours"]))

    st.subheader("Support Analytics Charts")
    c1, c2 = st.columns(2)
    with c1:
        plot_bar(summary_tables["weekly_ticket_trend"], "week", "ticket_count", "Weekly Ticket Trend")
        plot_bar(summary_tables["sla_breach_by_system"], "system_name", "sla_breach_count", "SLA Breach by System")
        plot_bar(
            summary_tables["engineer_top10"].sort_values("workload_hours"),
            "workload_hours",
            "engineer",
            "Engineer Workload TOP10",
            orientation="h",
        )
    with c2:
        plot_bar(summary_tables["status_distribution"], "status", "ticket_count", "Ticket Status Distribution")
        plot_bar(summary_tables["pending_by_entity"], "entity", "pending_ticket_count", "Pending Tickets by Entity")
        plot_bar(
            summary_tables["workload_by_system"].sort_values("workload_hours"),
            "workload_hours",
            "system_name",
            "Workload by System",
            orientation="h",
        )

    st.subheader("Detail Tables")
    tabs = st.tabs(["Risk Tickets", "SLA Breach Tickets", "Pending Tickets", "CR Summary", "FTE Workload Summary"])
    with tabs[0]:
        st.dataframe(summary_tables["risk_tickets"], width="stretch", hide_index=True)
    with tabs[1]:
        st.dataframe(summary_tables["sla_breaches"], width="stretch", hide_index=True)
    with tabs[2]:
        st.dataframe(summary_tables["pending_tickets"], width="stretch", hide_index=True)
    with tabs[3]:
        st.dataframe(summary_tables["cr_summary"], width="stretch", hide_index=True)
    with tabs[4]:
        st.dataframe(summary_tables["fte_workload_summary"], width="stretch", hide_index=True)

    st.subheader("Downloads")
    excel_report = generate_excel_report(filtered_tickets, summary_tables["fte_workload_summary"], summary_tables)
    html_summary = generate_html_weekly_summary(kpis, summary_tables["risk_tickets"], summary_tables["fte_workload_summary"])
    risk_csv = generate_risk_ticket_csv(summary_tables["risk_tickets"])
    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button(
            "Download Excel Weekly Support Report",
            data=excel_report,
            file_name="weekly_support_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with d2:
        st.download_button(
            "Download HTML Weekly Summary",
            data=html_summary,
            file_name="weekly_support_summary.html",
            mime="text/html; charset=utf-8",
        )
    with d3:
        st.download_button(
            "Download Risk Ticket List CSV",
            data=risk_csv,
            file_name="risk_ticket_list.csv",
            mime="text/csv; charset=utf-8",
        )


if __name__ == "__main__":
    main()

