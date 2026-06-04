"""Generate downloadable Excel, HTML, and CSV reports."""

from __future__ import annotations

from html import escape
from io import BytesIO, StringIO

import pandas as pd

from src.utils import format_percent


def _safe_text(value) -> str:
    """Escape values for HTML output."""
    if pd.isna(value):
        return "-"
    return escape(str(value))


def generate_excel_report(processed_tickets: pd.DataFrame, fte_summary: pd.DataFrame, summary_tables: dict[str, pd.DataFrame]) -> BytesIO:
    """Generate a formatted Excel weekly support report."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        processed_tickets.to_excel(writer, sheet_name="Ticket Summary", index=False)
        summary_tables["sla_breaches"].to_excel(writer, sheet_name="SLA Breaches", index=False)
        summary_tables["pending_tickets"].to_excel(writer, sheet_name="Pending Tickets", index=False)
        summary_tables["cr_summary"].to_excel(writer, sheet_name="CR Summary", index=False)
        fte_summary.to_excel(writer, sheet_name="FTE Workload", index=False)
        summary_tables["engineer_top10"].to_excel(writer, sheet_name="Engineer TOP10", index=False)

        workbook = writer.book
        header_format = workbook.add_format({"bold": True, "bg_color": "#17324D", "font_color": "white", "border": 1})
        number_format = workbook.add_format({"num_format": "0.0"})

        for sheet_name, worksheet in writer.sheets.items():
            df = {
                "Ticket Summary": processed_tickets,
                "SLA Breaches": summary_tables["sla_breaches"],
                "Pending Tickets": summary_tables["pending_tickets"],
                "CR Summary": summary_tables["cr_summary"],
                "FTE Workload": fte_summary,
                "Engineer TOP10": summary_tables["engineer_top10"],
            }[sheet_name]
            for col_num, col in enumerate(df.columns):
                worksheet.write(0, col_num, col, header_format)
                worksheet.set_column(col_num, col_num, min(max(len(str(col)) + 4, 14), 32))
                if "hours" in str(col).lower() or "fte" in str(col).lower():
                    worksheet.set_column(col_num, col_num, 16, number_format)
            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, max(len(df), 1), max(len(df.columns) - 1, 0))

    output.seek(0)
    return output


def generate_html_weekly_summary(metrics: dict[str, float], risk_tickets: pd.DataFrame, fte_summary: pd.DataFrame) -> str:
    """Generate a UTF-8 HTML weekly summary for IT support teams."""
    risk_top10 = risk_tickets.sort_values(["risk_level", "elapsed_hours"], ascending=[True, False]).head(10)
    system_top10 = (
        fte_summary.groupby("system_name", dropna=False)["workload_hours"]
        .sum()
        .reset_index()
        .sort_values("workload_hours", ascending=False)
        .head(10)
    )

    risk_rows = "\n".join(
        "<tr>"
        f"<td>{_safe_text(row.ticket_id)}</td>"
        f"<td>{_safe_text(row.priority)}</td>"
        f"<td>{_safe_text(row.system_name)}</td>"
        f"<td>{_safe_text(row.entity)}</td>"
        f"<td>{_safe_text(row.status)}</td>"
        f"<td>{_safe_text(row.risk_type)}</td>"
        f"<td class=\"number\">{float(row.elapsed_hours):,.1f}</td>"
        "</tr>"
        for row in risk_top10.itertuples(index=False)
    )
    if not risk_rows:
        risk_rows = "<tr><td colspan=\"7\" class=\"empty\">No risk tickets in the current selection.</td></tr>"

    system_rows = "\n".join(
        "<tr>"
        f"<td>{_safe_text(row.system_name)}</td>"
        f"<td class=\"number\">{float(row.workload_hours):,.1f}</td>"
        "</tr>"
        for row in system_top10.itertuples(index=False)
    )
    if not system_rows:
        system_rows = "<tr><td colspan=\"2\" class=\"empty\">No FTE workload records in the current selection.</td></tr>"

    return f"""\ufeff<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>L2 Support Weekly Summary</title>
<style>
body {{
    margin: 0;
    padding: 24px;
    background: #f5f7fb;
    color: #1f2937;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
    font-size: 14px;
    line-height: 1.6;
}}
.container {{
    max-width: 980px;
    margin: 0 auto;
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}}
.header {{
    padding: 24px 28px;
    background: #17324d;
    color: white;
}}
.header h1 {{ margin: 0 0 8px; font-size: 24px; }}
.header p {{ margin: 0; color: #d8e6f3; }}
.content {{ padding: 24px 28px 30px; }}
.summary-grid {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
    margin: 18px 0 22px;
}}
.card {{
    border: 1px solid #e5e7eb;
    border-left: 4px solid #2a9d8f;
    border-radius: 8px;
    padding: 12px 14px;
    background: #fbfdff;
}}
.card.warning {{ border-left-color: #e76f51; }}
.label {{ color: #6b7280; font-size: 12px; }}
.value {{ font-size: 20px; font-weight: 700; color: #111827; }}
h2 {{
    margin: 24px 0 10px;
    font-size: 17px;
    color: #17324d;
    border-bottom: 2px solid #d8e6f3;
    padding-bottom: 6px;
}}
table {{ width: 100%; border-collapse: collapse; table-layout: fixed; margin: 10px 0 18px; font-size: 13px; }}
th {{ background: #d8e6f3; color: #17324d; border: 1px solid #cbd5e1; padding: 8px; text-align: left; }}
td {{ border: 1px solid #e5e7eb; padding: 8px; word-break: break-word; }}
tr:nth-child(even) td {{ background: #f8fbff; }}
.number {{ text-align: right; white-space: nowrap; }}
.note {{
    margin: 18px 0;
    padding: 12px 14px;
    border-left: 4px solid #f4a261;
    background: #fff8eb;
    border-radius: 6px;
}}
.empty {{ text-align: center; color: #6b7280; }}
.footer {{ margin-top: 20px; color: #6b7280; font-size: 12px; border-top: 1px solid #e5e7eb; padding-top: 14px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>L2 Support Weekly Summary</h1>
    <p>IT Support Analytics Hub | SLA, ticket risk, and FTE workload summary</p>
  </div>
  <div class="content">
    <p>各位同事好，以下为当前筛选范围内的 L2 Support 工单、SLA 风险、Change Request 和 FTE 负载摘要。</p>
    <div class="summary-grid">
      <div class="card"><div class="label">Reported Tickets</div><div class="value">{metrics['reported_tickets']}</div></div>
      <div class="card"><div class="label">Closed Tickets</div><div class="value">{metrics['closed_tickets']}</div></div>
      <div class="card warning"><div class="label">Pending Tickets</div><div class="value">{metrics['pending_tickets']}</div></div>
      <div class="card warning"><div class="label">SLA Breach Rate</div><div class="value">{format_percent(metrics['sla_breach_rate'])}</div></div>
      <div class="card"><div class="label">Released CR</div><div class="value">{metrics['released_cr']}</div></div>
      <div class="card warning"><div class="label">In Progress CR</div><div class="value">{metrics['in_progress_cr']}</div></div>
      <div class="card"><div class="label">Total Used FTEs</div><div class="value">{metrics['total_used_ftes']:,.1f}</div></div>
      <div class="card"><div class="label">Avg Resolution Hours</div><div class="value">{metrics['avg_resolution_hours']:,.1f}</div></div>
    </div>
    <div class="note"><strong>Risk reminder:</strong> Please prioritize high-priority SLA breaches, long-pending tickets, emergency changes, and systems with concentrated workload.</div>

    <h2>High Risk Tickets TOP10</h2>
    <table>
      <thead><tr><th>Ticket</th><th>Priority</th><th>System</th><th>Entity</th><th>Status</th><th>Risk Type</th><th>Elapsed Hours</th></tr></thead>
      <tbody>{risk_rows}</tbody>
    </table>

    <h2>High Workload Systems TOP10</h2>
    <table>
      <thead><tr><th>System</th><th>Workload Hours</th></tr></thead>
      <tbody>{system_rows}</tbody>
    </table>

    <div class="footer">This weekly summary is generated from simulated Jira-style tickets and FTE data. It does not contain real company, employee, customer, email, or system link information.</div>
  </div>
</div>
</body>
</html>""".strip()


def generate_risk_ticket_csv(risk_tickets: pd.DataFrame) -> str:
    """Return risk ticket list as a CSV string."""
    output = StringIO()
    risk_tickets.to_csv(output, index=False)
    return output.getvalue()

