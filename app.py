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
        .health-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.8rem;
            margin: 0.9rem 0 1.1rem;
        }
        .health-card {
            border: 1px solid #D7DEE8;
            border-radius: 8px;
            background: linear-gradient(180deg, #FFFFFF 0%, #F7FAFC 100%);
            padding: 0.95rem 1rem;
            min-height: 112px;
        }
        .health-card.warning {border-top: 4px solid #E76F51;}
        .health-card.normal {border-top: 4px solid #2A9D8F;}
        .health-card.load {border-top: 4px solid #457B9D;}
        .health-card strong {
            color: #344054;
            display: block;
            font-size: 0.88rem;
            margin-bottom: 0.45rem;
        }
        .health-card .health-value {
            color: #101828;
            font-size: 1.65rem;
            font-weight: 760;
            line-height: 1.1;
        }
        .health-card span {
            color: #667085;
            display: block;
            font-size: 0.84rem;
            margin-top: 0.45rem;
        }
        .workflow-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.75rem;
            margin: 0.4rem 0 1.1rem;
        }
        .workflow-step {
            border: 1px solid #E6E8EC;
            border-radius: 8px;
            background: #FFFFFF;
            padding: 0.85rem 0.9rem;
            min-height: 112px;
        }
        .workflow-step strong {
            display: block;
            color: #1D6F67;
            margin-bottom: 0.35rem;
        }
        .workflow-step span {
            color: #475467;
            font-size: 0.9rem;
        }
        .funnel-row {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.55rem;
            margin: 0.4rem 0 1rem;
        }
        .funnel-step {
            border: 1px solid #D7DEE8;
            background: #F8FBFD;
            border-radius: 8px;
            padding: 0.8rem 0.85rem;
            min-height: 92px;
        }
        .funnel-step strong {
            color: #1F4E79;
            display: block;
            font-size: 0.9rem;
            margin-bottom: 0.4rem;
        }
        .funnel-step .funnel-value {
            color: #101828;
            font-size: 1.45rem;
            font-weight: 740;
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
        @media (max-width: 900px) {
            .workflow-grid {grid-template-columns: 1fr;}
            .health-strip {grid-template-columns: 1fr;}
            .funnel-row {grid-template-columns: 1fr;}
        }
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


def plot_workload_heatmap(fte: pd.DataFrame) -> None:
    """Render engineer workload by week as a heatmap."""
    if fte.empty:
        st.info("Workload Heatmap: no data in current selection.")
        return
    top_engineers = (
        fte.groupby("engineer", dropna=False)["workload_hours"]
        .sum()
        .sort_values(ascending=False)
        .head(12)
        .index
    )
    heatmap_data = (
        fte[fte["engineer"].isin(top_engineers)]
        .pivot_table(index="engineer", columns="week", values="workload_hours", aggfunc="sum", fill_value=0)
        .sort_index()
    )
    if heatmap_data.empty:
        st.info("Workload Heatmap: no data in current selection.")
        return
    fig = px.imshow(
        heatmap_data,
        aspect="auto",
        color_continuous_scale=["#EAF4F4", "#76B7B2", "#E76F51"],
        labels=dict(x="Week", y="Engineer", color="Hours"),
        title="Workload Heatmap by Engineer and Week",
    )
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=55, b=10), title_font_size=16)
    st.plotly_chart(fig, width="stretch")


def render_workflow() -> None:
    """Render the ITSM analytics workflow before KPI cards."""
    st.subheader("ITSM Service Delivery Analytics Workflow")
    st.markdown(
        """
        <div class="workflow-grid">
            <div class="workflow-step"><strong>Step 1<br>Load Jira Tickets</strong><span>导入 Ticket、FTE 和系统 Mapping 数据，复现 L2 Support 周报数据源。</span></div>
            <div class="workflow-step"><strong>Step 2<br>Monitor SLA</strong><span>按 P1/P2/P3/P4 目标时长识别 breach、long pending 和高风险工单。</span></div>
            <div class="workflow-step"><strong>Step 3<br>Review Workload</strong><span>分析工程师工时、系统负载和高负载系统，定位资源压力。</span></div>
            <div class="workflow-step"><strong>Step 4<br>Analyze Delivery</strong><span>按 entity、system、priority、status 复盘服务响应和解决效率。</span></div>
            <div class="workflow-step"><strong>Step 5<br>Export Support Pack</strong><span>输出 Excel 周报、HTML Summary 和风险工单 CSV，用于 ITSM 例会复盘。</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_service_health_snapshot(kpis: dict[str, float], tickets: pd.DataFrame, fte: pd.DataFrame) -> None:
    """Render IT service health indicators as the first operational section."""
    open_tickets = int(tickets["status"].isin(["Open", "In Progress", "Pending"]).sum()) if not tickets.empty else 0
    avg_fte = float(fte["fte_used"].mean()) if not fte.empty else 0
    utilization = min(avg_fte * 100, 100)
    st.subheader("Service Health Snapshot")
    st.markdown(
        f"""
        <div class="health-strip">
            <div class="health-card warning"><strong>SLA Breach Rate</strong><div class="health-value">{format_percent(kpis['sla_breach_rate'])}</div><span>{int(kpis['sla_breach_count']):,} tickets breached target response or resolution time.</span></div>
            <div class="health-card normal"><strong>Avg Resolution Time</strong><div class="health-value">{format_hours(kpis['avg_resolution_hours'])}</div><span>Resolved / closed ticket elapsed hours.</span></div>
            <div class="health-card load"><strong>Open Tickets</strong><div class="health-value">{open_tickets:,}</div><span>Open, In Progress and Pending workload in queue.</span></div>
            <div class="health-card load"><strong>Engineer Utilization</strong><div class="health-value">{utilization:.0f}%</div><span>Average FTE usage across filtered workload records.</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_ticket_flow(tickets: pd.DataFrame) -> None:
    """Render a ticket lifecycle funnel."""
    status_counts = tickets["status"].value_counts().to_dict() if not tickets.empty else {}
    flow = {
        "Created": len(tickets),
        "Assigned": int(tickets["assigned_to"].notna().sum()) if "assigned_to" in tickets else 0,
        "In Progress": status_counts.get("In Progress", 0),
        "Resolved": status_counts.get("Resolved", 0),
        "Closed": status_counts.get("Closed", 0),
    }
    st.subheader("Ticket Flow / SLA Funnel")
    st.markdown(
        "<div class=\"funnel-row\">"
        + "".join(
            f'<div class="funnel-step"><strong>{stage}</strong><div class="funnel-value">{value:,}</div></div>'
            for stage, value in flow.items()
        )
        + "</div>",
        unsafe_allow_html=True,
    )
    funnel_df = pd.DataFrame({"stage": list(flow.keys()), "tickets": list(flow.values())})
    fig = px.funnel(funnel_df, x="tickets", y="stage", title="Ticket Lifecycle Funnel")
    fig.update_traces(marker_color=["#1F4E79", "#457B9D", "#76B7B2", "#F4A261", "#2A9D8F"])
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=55, b=10), plot_bgcolor="white", paper_bgcolor="white")
    st.plotly_chart(fig, width="stretch")


def render_sla_and_workload(tickets: pd.DataFrame, fte: pd.DataFrame, summary_tables: dict[str, pd.DataFrame]) -> None:
    """Render the primary analysis workspace for IT service operations."""
    st.subheader("SLA Breach Analysis")
    left, right = st.columns([1.1, 0.9])
    with left:
        plot_bar(summary_tables["sla_breach_by_system"], "system_name", "sla_breach_count", "SLA Breach by System")
    with right:
        breach_by_priority = (
            tickets[tickets["is_sla_breached"]]
            .groupby("priority", dropna=False)
            .size()
            .reset_index(name="breach_count")
            .sort_values("priority")
        )
        plot_bar(breach_by_priority, "priority", "breach_count", "SLA Breach by Priority")

    st.subheader("Workload Heatmap")
    plot_workload_heatmap(fte)


def render_engineer_workload_board(tickets: pd.DataFrame, fte: pd.DataFrame) -> None:
    """Render engineer workload with ticket counts and overload flags."""
    st.subheader("Engineer Workload Board")
    workload = (
        fte.groupby("engineer", dropna=False)
        .agg(workload_hours=("workload_hours", "sum"), fte_used=("fte_used", "sum"))
        .reset_index()
        if not fte.empty
        else pd.DataFrame(columns=["engineer", "workload_hours", "fte_used"])
    )
    ticket_counts = (
        tickets.groupby("assigned_to", dropna=False)
        .size()
        .reset_index(name="ticket_count")
        .rename(columns={"assigned_to": "engineer"})
        if not tickets.empty
        else pd.DataFrame(columns=["engineer", "ticket_count"])
    )
    board = workload.merge(ticket_counts, on="engineer", how="left").fillna({"ticket_count": 0})
    board["load_status"] = board["workload_hours"].apply(lambda value: "OVERLOADED" if value > 45 else "NORMAL")
    board = board.sort_values(["load_status", "workload_hours"], ascending=[True, False])
    st.dataframe(
        board[["engineer", "ticket_count", "workload_hours", "fte_used", "load_status"]].head(15),
        width="stretch",
        hide_index=True,
        height=420,
    )


def main() -> None:
    """Run the Streamlit application."""
    ensure_sample_data()
    inject_styles()

    st.title("IT Support Analytics Hub")
    st.caption("IT 服务管理分析 | SLA 监控 | FTE 负载分析 | 运维效率复盘")

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
        This demo uses simulated Jira-style tickets and FTE workload data to reproduce an ITSM service delivery review:
        SLA monitoring, ticket risk identification, engineer workload analysis, system load review, and weekly support summary generation.
        It focuses on Ticket, SLA, FTE, ITSM, and service delivery efficiency, without using any real company or employee data.
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_service_health_snapshot(kpis, filtered_tickets, filtered_fte)
    render_workflow()
    render_sla_and_workload(filtered_tickets, filtered_fte, summary_tables)
    render_ticket_flow(filtered_tickets)
    render_engineer_workload_board(filtered_tickets, filtered_fte)

    st.subheader("Service Delivery Analytics")
    c1, c2 = st.columns(2)
    with c1:
        plot_bar(summary_tables["weekly_ticket_trend"], "week", "ticket_count", "SLA / Ticket Trend by Week")
        plot_bar(summary_tables["status_distribution"], "status", "ticket_count", "Ticket Status Distribution")
    with c2:
        plot_bar(summary_tables["pending_by_entity"], "entity", "pending_ticket_count", "Pending Tickets by Entity")
        plot_bar(
            summary_tables["workload_by_system"].sort_values("workload_hours"),
            "workload_hours",
            "system_name",
            "System Workload Distribution",
            orientation="h",
        )

    st.subheader("Ticket & Workload Review Tables")
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

    st.subheader("Support Report Export Center")
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
