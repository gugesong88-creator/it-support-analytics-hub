"""Generate simulated Jira-style ticket, FTE, and system mapping data."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import random

import numpy as np
import pandas as pd

try:
    from src.utils import DATA_DIR
except ModuleNotFoundError:
    DATA_DIR = Path(__file__).resolve().parents[1] / "data"


RANDOM_SEED = 20260604
SYSTEMS = [
    "SAP",
    "MES",
    "WMS",
    "AP Portal",
    "HR System",
    "Finance System",
    "Quality System",
    "API Gateway",
]
ENTITIES = ["ATJ", "ATD", "AC", "ATD II"]
ENGINEERS = [f"Engineer {idx:02d}" for idx in range(1, 19)]
SLA_TARGETS = {"P1": 8, "P2": 24, "P3": 72, "P4": 120}


def build_system_mapping() -> pd.DataFrame:
    """Create system ownership mapping with fictional owners and domains."""
    domains = {
        "SAP": ("ERP Operations", "Critical", "L2"),
        "MES": ("Manufacturing Execution", "Critical", "L2"),
        "WMS": ("Warehouse Operations", "High", "L2"),
        "AP Portal": ("Supplier Collaboration", "Medium", "L2"),
        "HR System": ("People Operations", "Medium", "L2"),
        "Finance System": ("Finance Operations", "High", "L2"),
        "Quality System": ("Quality Management", "High", "L2"),
        "API Gateway": ("Integration Platform", "Critical", "L2/L3"),
    }
    rows = []
    for idx, system_name in enumerate(SYSTEMS, start=1):
        business_domain, criticality, support_level = domains[system_name]
        rows.append(
            {
                "system_name": system_name,
                "system_owner": f"System Owner {idx:02d}",
                "business_domain": business_domain,
                "criticality": criticality,
                "support_level": support_level,
            }
        )
    return pd.DataFrame(rows)


def _random_week_start(today: date, rng: np.random.Generator) -> date:
    """Return a random week start within the latest 12 weeks."""
    current_monday = today - timedelta(days=today.weekday())
    week_offset = int(rng.integers(0, 12))
    return current_monday - timedelta(weeks=week_offset)


def build_tickets(n_tickets: int = 880, today: date | None = None) -> pd.DataFrame:
    """Create simulated support ticket data with SLA and pending-risk samples."""
    today = today or date.today()
    rng = np.random.default_rng(RANDOM_SEED)
    random.seed(RANDOM_SEED)
    now = datetime.combine(today, datetime.min.time()) + timedelta(hours=15)

    rows = []
    status_choices = ["Open", "In Progress", "Pending", "Resolved", "Closed", "Cancelled"]
    issue_types = ["Incident", "Service Request", "Change Request", "Hot Fix"]
    priority_probs = [0.08, 0.22, 0.45, 0.25]
    high_load_engineers = ["Engineer 03", "Engineer 07", "Engineer 11"]
    high_load_systems = ["SAP", "MES", "API Gateway"]

    for idx in range(1, n_tickets + 1):
        week_start = _random_week_start(today, rng)
        created_at = datetime.combine(week_start, datetime.min.time()) + timedelta(
            days=int(rng.integers(0, 7)),
            hours=int(rng.integers(8, 20)),
            minutes=int(rng.integers(0, 60)),
        )
        created_at = min(created_at, now - timedelta(hours=2))

        priority = str(rng.choice(["P1", "P2", "P3", "P4"], p=priority_probs))
        issue_type = str(rng.choice(issue_types, p=[0.42, 0.30, 0.20, 0.08]))
        status = str(rng.choice(status_choices, p=[0.12, 0.18, 0.14, 0.25, 0.27, 0.04]))
        system_name = str(rng.choice(SYSTEMS, p=[0.18, 0.16, 0.12, 0.10, 0.08, 0.12, 0.10, 0.14]))
        if idx % 31 == 0:
            system_name = random.choice(high_load_systems)

        target = SLA_TARGETS[priority]
        force_breach = idx % 9 == 0 or priority == "P1" and idx % 5 == 0
        force_long_pending = idx % 23 == 0
        if force_long_pending:
            status = "Pending"
            elapsed_hours = int(rng.integers(80, 190))
        elif force_breach:
            elapsed_hours = int(target + rng.integers(1, max(12, target + 72)))
        else:
            elapsed_hours = int(rng.integers(1, max(2, target + 36)))

        if status in ["Resolved", "Closed", "Cancelled"]:
            resolved_at = created_at + timedelta(hours=elapsed_hours)
            if resolved_at > now:
                resolved_at = None
                status = str(rng.choice(["Open", "In Progress", "Pending"], p=[0.30, 0.45, 0.25]))
        else:
            resolved_at = None
            created_at = now - timedelta(hours=elapsed_hours)

        if issue_type == "Change Request":
            change_type = str(rng.choice(["Normal Change", "Emergency Change", "Standard Change"], p=[0.55, 0.18, 0.27]))
            if idx % 37 == 0:
                status = "Pending"
                change_type = "Emergency Change"
                resolved_at = None
                created_at = now - timedelta(hours=int(rng.integers(40, 110)))
        else:
            change_type = "NA"

        assigned_to = random.choice(high_load_engineers) if idx % 17 == 0 else random.choice(ENGINEERS)
        resolution_owner = assigned_to if status in ["Resolved", "Closed"] else random.choice(ENGINEERS)
        time_spent = float(max(0.25, rng.normal(loc=target / 7, scale=target / 16)))

        rows.append(
            {
                "ticket_id": f"TCK-{idx:05d}",
                "created_at": created_at,
                "resolved_at": resolved_at,
                "week": created_at.strftime("%Y-W%U"),
                "issue_type": issue_type,
                "priority": priority,
                "status": status,
                "system_name": system_name,
                "entity": str(rng.choice(ENTITIES, p=[0.28, 0.27, 0.25, 0.20])),
                "request_channel": str(rng.choice(["Service Portal", "Email", "Teams", "Phone", "Monitoring"])),
                "assigned_to": assigned_to,
                "resolution_owner": resolution_owner,
                "time_spent_hours": round(time_spent, 2),
                "sla_target_hours": target,
                "change_type": change_type,
            }
        )
    return pd.DataFrame(rows)


def build_fte(n_rows: int = 360, today: date | None = None) -> pd.DataFrame:
    """Create simulated weekly FTE workload records."""
    today = today or date.today()
    rng = np.random.default_rng(RANDOM_SEED + 11)
    rows = []
    high_load_engineers = ["Engineer 03", "Engineer 07", "Engineer 11"]
    high_load_systems = ["SAP", "MES", "API Gateway"]

    current_monday = today - timedelta(days=today.weekday())
    weeks = [(current_monday - timedelta(weeks=idx)).strftime("%Y-W%U") for idx in range(12)]

    for idx in range(n_rows):
        week = weeks[idx % len(weeks)]
        system_name = str(rng.choice(SYSTEMS, p=[0.18, 0.16, 0.12, 0.10, 0.08, 0.12, 0.10, 0.14]))
        engineer = random.choice(ENGINEERS)
        if idx % 14 == 0:
            engineer = random.choice(high_load_engineers)
        if idx % 19 == 0:
            system_name = random.choice(high_load_systems)

        workload = float(rng.uniform(8, 38))
        if engineer in high_load_engineers and idx % 4 == 0:
            workload += float(rng.uniform(18, 30))
        if system_name in high_load_systems and idx % 5 == 0:
            workload += float(rng.uniform(15, 28))

        rows.append(
            {
                "week": week,
                "system_name": system_name,
                "entity": str(rng.choice(ENTITIES)),
                "engineer": engineer,
                "fte_used": round(workload / 40, 2),
                "workload_hours": round(workload, 2),
            }
        )
    return pd.DataFrame(rows)


def generate_sample_data(output_dir: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate all sample datasets and save them under data/."""
    output_dir = output_dir or DATA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    tickets = build_tickets()
    fte = build_fte()
    mapping = build_system_mapping()
    tickets.to_csv(output_dir / "sample_tickets.csv", index=False)
    fte.to_csv(output_dir / "sample_fte.csv", index=False)
    mapping.to_csv(output_dir / "sample_system_mapping.csv", index=False)
    return tickets, fte, mapping


if __name__ == "__main__":
    generated = generate_sample_data()
    print(
        "Generated sample data:",
        f"tickets={len(generated[0])}",
        f"fte={len(generated[1])}",
        f"mapping={len(generated[2])}",
    )

