"""SLA, change request, and workload risk rules."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd


SLA_TARGETS = {"P1": 8, "P2": 24, "P3": 72, "P4": 120}


def apply_sla_rules(tickets: pd.DataFrame, today: date) -> pd.DataFrame:
    """Apply SLA breach, long pending, CR status, and risk-level rules."""
    df = tickets.copy()
    today_ts = pd.Timestamp(today) + pd.Timedelta(hours=23, minutes=59)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["resolved_at"] = pd.to_datetime(df["resolved_at"], errors="coerce")
    df["sla_target_hours"] = df["priority"].map(SLA_TARGETS).fillna(df["sla_target_hours"]).fillna(72).astype(float)

    end_time = df["resolved_at"].fillna(today_ts)
    df["elapsed_hours"] = ((end_time - df["created_at"]).dt.total_seconds() / 3600).clip(lower=0).round(1)
    df["is_sla_breached"] = df["elapsed_hours"] > df["sla_target_hours"]

    long_pending = df["status"].eq("Pending") & (df["elapsed_hours"] > 72)
    sla_breach = df["is_sla_breached"]
    df["risk_type"] = np.select([long_pending, sla_breach], ["LONG_PENDING", "SLA_BREACH"], default="NORMAL")

    is_cr = df["issue_type"].eq("Change Request")
    df["cr_status"] = np.select(
        [
            is_cr & df["status"].isin(["Resolved", "Closed"]),
            is_cr & df["status"].isin(["Open", "In Progress", "Pending"]),
        ],
        ["Released CR", "In Progress CR"],
        default="NA",
    )

    high = (
        df["priority"].eq("P1") & df["is_sla_breached"]
    ) | (long_pending & (df["elapsed_hours"] > 120)) | (
        df["change_type"].eq("Emergency Change") & df["status"].eq("Pending")
    )
    medium = (
        df["priority"].isin(["P2", "P3"]) & df["is_sla_breached"]
    ) | long_pending | df["cr_status"].eq("In Progress CR")
    df["risk_level"] = np.select([high, medium], ["HIGH", "MEDIUM"], default="LOW")

    df["age_bucket"] = pd.cut(
        df["elapsed_hours"],
        bins=[-0.1, 8, 24, 72, 168, float("inf")],
        labels=["0-8h", "8-24h", "1-3d", "3-7d", "7d+"],
    ).astype(str)
    return df


def merge_system_mapping(tickets: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    """Merge processed ticket data with system ownership mapping."""
    mapping_clean = mapping.drop_duplicates("system_name")
    return tickets.merge(mapping_clean, on="system_name", how="left")


def add_workload_flags(fte: pd.DataFrame) -> pd.DataFrame:
    """Add engineer and system high-load flags to FTE records."""
    df = fte.copy()
    engineer_week = (
        df.groupby(["week", "engineer"], dropna=False)["workload_hours"]
        .sum()
        .reset_index(name="engineer_weekly_hours")
    )
    system_week = (
        df.groupby(["week", "system_name"], dropna=False)["workload_hours"]
        .sum()
        .reset_index(name="system_weekly_hours")
    )
    df = df.merge(engineer_week, on=["week", "engineer"], how="left")
    df = df.merge(system_week, on=["week", "system_name"], how="left")
    df["workload_risk"] = np.select(
        [
            df["engineer_weekly_hours"] > 45,
            df["system_weekly_hours"] > 120,
        ],
        ["HIGH_LOAD", "HIGH_SYSTEM_LOAD"],
        default="NORMAL",
    )
    return df

