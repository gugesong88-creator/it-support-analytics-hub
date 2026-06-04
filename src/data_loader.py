"""Load and validate ticket, FTE, and system mapping datasets."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

from src.utils import DATA_DIR


TICKET_COLUMNS = [
    "ticket_id",
    "created_at",
    "resolved_at",
    "week",
    "issue_type",
    "priority",
    "status",
    "system_name",
    "entity",
    "request_channel",
    "assigned_to",
    "resolution_owner",
    "time_spent_hours",
    "sla_target_hours",
    "change_type",
]

FTE_COLUMNS = ["week", "system_name", "entity", "engineer", "fte_used", "workload_hours"]

MAPPING_COLUMNS = ["system_name", "system_owner", "business_domain", "criticality", "support_level"]


def _read_file(uploaded_file, default_path: Path) -> pd.DataFrame:
    """Read a default or uploaded CSV/Excel file into a DataFrame."""
    if uploaded_file is None:
        return pd.read_csv(default_path)

    filename = uploaded_file.name.lower()
    if filename.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)

    st.error(f"Unsupported file type: {uploaded_file.name}. Please upload CSV, XLSX, or XLS.")
    st.stop()


def _validate_columns(df: pd.DataFrame, required_columns: Iterable[str], dataset_name: str) -> pd.DataFrame:
    """Validate required columns and stop the Streamlit app on schema errors."""
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        st.error(f"{dataset_name} is missing required fields: {', '.join(missing)}")
        st.stop()
    return df.copy()


def _coerce_tickets(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize ticket data types after loading."""
    for col in ["ticket_id", "week", "issue_type", "priority", "status", "system_name", "entity", "request_channel", "assigned_to", "resolution_owner", "change_type"]:
        df[col] = df[col].astype(str).str.strip()
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["resolved_at"] = pd.to_datetime(df["resolved_at"], errors="coerce")
    df["time_spent_hours"] = pd.to_numeric(df["time_spent_hours"], errors="coerce").fillna(0)
    df["sla_target_hours"] = pd.to_numeric(df["sla_target_hours"], errors="coerce").fillna(0)
    return df


def _coerce_fte(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize FTE data types after loading."""
    for col in ["week", "system_name", "entity", "engineer"]:
        df[col] = df[col].astype(str).str.strip()
    df["fte_used"] = pd.to_numeric(df["fte_used"], errors="coerce").fillna(0)
    df["workload_hours"] = pd.to_numeric(df["workload_hours"], errors="coerce").fillna(0)
    return df


def load_tickets(uploaded_file=None) -> pd.DataFrame:
    """Load support ticket data from upload or default sample CSV."""
    df = _read_file(uploaded_file, DATA_DIR / "sample_tickets.csv")
    df = _validate_columns(df, TICKET_COLUMNS, "Ticket data")
    return _coerce_tickets(df)


def load_fte(uploaded_file=None) -> pd.DataFrame:
    """Load FTE workload data from upload or default sample CSV."""
    df = _read_file(uploaded_file, DATA_DIR / "sample_fte.csv")
    df = _validate_columns(df, FTE_COLUMNS, "FTE data")
    return _coerce_fte(df)


def load_system_mapping(uploaded_file=None) -> pd.DataFrame:
    """Load system mapping data from upload or default sample CSV."""
    df = _read_file(uploaded_file, DATA_DIR / "sample_system_mapping.csv")
    df = _validate_columns(df, MAPPING_COLUMNS, "System mapping")
    for col in MAPPING_COLUMNS:
        df[col] = df[col].astype(str).str.strip()
    return df

