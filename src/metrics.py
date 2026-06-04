"""Dashboard KPI and summary table calculations."""

from __future__ import annotations

import pandas as pd


def calculate_kpis(tickets: pd.DataFrame, fte: pd.DataFrame) -> dict[str, float]:
    """Calculate headline KPIs for support analytics."""
    total = int(len(tickets))
    closed = int(tickets["status"].isin(["Resolved", "Closed"]).sum())
    pending = int(tickets["status"].eq("Pending").sum())
    breach_count = int(tickets["is_sla_breached"].sum())
    resolved = tickets[tickets["status"].isin(["Resolved", "Closed"])]
    return {
        "reported_tickets": total,
        "closed_tickets": closed,
        "pending_tickets": pending,
        "sla_breach_count": breach_count,
        "sla_breach_rate": breach_count / total if total else 0,
        "released_cr": int(tickets["cr_status"].eq("Released CR").sum()),
        "in_progress_cr": int(tickets["cr_status"].eq("In Progress CR").sum()),
        "total_used_ftes": float(fte["fte_used"].sum()) if not fte.empty else 0,
        "avg_resolution_hours": float(resolved["elapsed_hours"].mean()) if not resolved.empty else 0,
    }


def build_summary_tables(tickets: pd.DataFrame, fte: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build all summary tables used by charts, reports, and exports."""
    risk_tickets = tickets[(tickets["risk_type"].ne("NORMAL")) | tickets["risk_level"].isin(["HIGH", "MEDIUM"])].copy()
    sla_breaches = tickets[tickets["is_sla_breached"]].copy()
    pending_tickets = tickets[tickets["status"].eq("Pending")].copy()

    weekly_ticket_trend = (
        tickets.groupby("week", dropna=False)
        .size()
        .reset_index(name="ticket_count")
        .sort_values("week")
    )
    status_distribution = (
        tickets.groupby("status", dropna=False)
        .size()
        .reset_index(name="ticket_count")
        .sort_values("ticket_count", ascending=False)
    )
    sla_breach_by_system = (
        sla_breaches.groupby("system_name", dropna=False)
        .size()
        .reset_index(name="sla_breach_count")
        .sort_values("sla_breach_count", ascending=False)
    )
    pending_by_entity = (
        pending_tickets.groupby("entity", dropna=False)
        .size()
        .reset_index(name="pending_ticket_count")
        .sort_values("pending_ticket_count", ascending=False)
    )
    workload_by_system = (
        fte.groupby("system_name", dropna=False)["workload_hours"]
        .sum()
        .reset_index(name="workload_hours")
        .sort_values("workload_hours", ascending=False)
    )
    engineer_top10 = (
        fte.groupby("engineer", dropna=False)
        .agg(workload_hours=("workload_hours", "sum"), fte_used=("fte_used", "sum"))
        .reset_index()
        .sort_values("workload_hours", ascending=False)
        .head(10)
    )
    cr_summary = (
        tickets[tickets["issue_type"].eq("Change Request")]
        .groupby(["cr_status", "change_type"], dropna=False)
        .size()
        .reset_index(name="ticket_count")
        .sort_values("ticket_count", ascending=False)
    )
    fte_workload_summary = (
        fte.groupby(["week", "system_name", "entity"], dropna=False)
        .agg(workload_hours=("workload_hours", "sum"), fte_used=("fte_used", "sum"))
        .reset_index()
        .sort_values(["week", "workload_hours"], ascending=[False, False])
    )
    high_load_system_top10 = workload_by_system.head(10)

    return {
        "weekly_ticket_trend": weekly_ticket_trend,
        "status_distribution": status_distribution,
        "sla_breach_by_system": sla_breach_by_system,
        "pending_by_entity": pending_by_entity,
        "workload_by_system": workload_by_system,
        "engineer_top10": engineer_top10,
        "risk_tickets": risk_tickets,
        "sla_breaches": sla_breaches,
        "pending_tickets": pending_tickets,
        "cr_summary": cr_summary,
        "fte_workload_summary": fte_workload_summary,
        "high_load_system_top10": high_load_system_top10,
    }

