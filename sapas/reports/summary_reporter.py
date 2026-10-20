# -*- coding: utf-8 -*-
"""
Sapas Interactive Station Quality & Yield Summary Dashboard Generator.

Reads test records from a local SQLite database (`sapas_local_{STATION}_{FIXTURE_ID}.db`)
and compiles a 100% offline, self-contained Single-Page Application (SPA) HTML dashboard:
    station_summary_{STATION}_{FIXTURE_ID}.html

Features:
- Pure client-side interactive filtering (Today, Yesterday, Last 7 Days, Last 30 Days, Custom Date Range, Status, Search).
- Real-time KPI recalculation: Total Runs, Unique Units, Overall Yield %, First Pass Yield (FPY %), Avg Cycle Time, Top Failure.
- Top Failure Pareto Breakdown (by Error Code & .py script) with click-to-filter support.
- Dynamic Yield & Throughput Trend Chart (auto-switches between Hourly and Daily granularity).
- Built-in Diagnostic Snapshot Modal: reconstructs the full collapsible `[+] script.py` measurement table
  directly from the SQLite database even when raw log folders have been archived to FTP/NAS.
"""

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sapas.database.local_db import LocalDBManager


def _infer_station_fixture_from_filename(db_path: Path) -> tuple[str, str]:
    stem = db_path.stem
    m = re.match(r"^sapas_local_([A-Za-z0-9_-]+?)_([A-Za-z0-9_-]+)$", stem, re.IGNORECASE)
    if m:
        return m.group(1).upper(), m.group(2).upper()
    m2 = re.match(r"^\d{8}_([A-Za-z0-9_-]+?)_([A-Za-z0-9_-]+)$", stem, re.IGNORECASE)
    if m2:
        return m2.group(1).upper(), m2.group(2).upper()
    return "STATION", "NA"


def generate_summary_dashboard(
    db_path: Path | str,
    output_dir: Optional[Path | str] = None,
) -> Path:
    """
    Reads all records from `db_path` and generates an interactive HTML summary dashboard.

    Args:
        db_path: Path to the SQLite `.db` file.
        output_dir: Directory to write the HTML report (defaults to `db_path.parent`).

    Returns:
        Path: Absolute path to the generated `station_summary_*.html` file.
    """
    db_file = Path(db_path).resolve()
    if not db_file.is_file():
        raise FileNotFoundError(f"SQLite database file not found: {db_file}")

    records = LocalDBManager.fetch_all_records(db_file)

    # Infer metadata from records or filename
    fn_station, fn_fixture = _infer_station_fixture_from_filename(db_file)
    station_name = ""
    fixture_id = ""
    project_name = ""

    for r in reversed(records):
        if not station_name and r.get("station"):
            station_name = str(r["station"])
        if not fixture_id and r.get("fixture_id") and str(r["fixture_id"]) != "N/A":
            fixture_id = str(r["fixture_id"])
        if not project_name and r.get("project"):
            project_name = str(r["project"])
        if station_name and fixture_id and project_name:
            break

    station_name = station_name or fn_station
    fixture_id = fixture_id or fn_fixture
    project_name = project_name or "General"

    safe_station_token = re.sub(r"[^A-Za-z0-9_-]+", "_", station_name).strip("_").upper() or "STATION"
    safe_fixture_token = re.sub(r"[^A-Za-z0-9_-]+", "_", fixture_id).strip("_").upper() or "NA"

    target_dir = Path(output_dir).resolve() if output_dir else db_file.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    out_html_path = target_dir / f"station_summary_{safe_station_token}_{safe_fixture_token}.html"

    # Compute per-SN run numbers (Run #1, Run #2 Retest, ...) in chronological order
    sn_counts: Dict[str, int] = {}
    for r in records:
        sn = str(r.get("sn") or "UNKNOWN")
        sn_counts[sn] = sn_counts.get(sn, 0) + 1
        r["run_num"] = sn_counts[sn]

    records_json = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    safe_station = html.escape(station_name)
    safe_fixture = html.escape(fixture_id)
    safe_project = html.escape(project_name)
    safe_db_name = html.escape(db_file.name)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Station Quality Dashboard - {safe_station} ({safe_fixture}) | Sapas</title>
    <style>
        :root {{
            --bg-page: #0d1117;
            --bg-card: #161b22;
            --bg-card-subtle: #21262d;
            --bg-hover: #282e37;
            --border-color: #30363d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --text-muted: #c9d1d9;
            --accent-blue: #58a6ff;
            --accent-blue-bg: rgba(88, 166, 255, 0.15);
            --color-pass: #238636;
            --color-pass-bg: rgba(35, 134, 54, 0.15);
            --color-pass-text: #3fb950;
            --color-fail: #da3633;
            --color-fail-bg: rgba(218, 54, 51, 0.18);
            --color-fail-border: #f85149;
            --color-fail-text: #ff7b72;
            --color-stop: #9e6a03;
            --color-stop-bg: rgba(210, 153, 34, 0.18);
            --color-stop-text: #d29922;
            --font-mono: 'Consolas', 'Cascadia Code', 'Fira Code', monospace;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-page);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.5;
            padding: 24px 12%;
        }}

        .container {{
            width: 100%;
            max-width: 1440px;
            margin: 0 auto;
        }}

        /* Top Header Banner */
        .top-banner {{
            background: linear-gradient(135deg, rgba(88, 166, 255, 0.16) 0%, rgba(22, 27, 34, 0.95) 100%);
            border: 1px solid rgba(88, 166, 255, 0.4);
            border-radius: 12px;
            padding: 22px 28px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}

        .banner-left {{
            display: flex;
            align-items: center;
            gap: 18px;
        }}

        .station-badge {{
            background-color: #1f6feb;
            color: #ffffff;
            font-weight: 800;
            font-size: 14px;
            padding: 8px 14px;
            border-radius: 8px;
            letter-spacing: 0.8px;
            text-transform: uppercase;
            font-family: var(--font-mono);
        }}

        .banner-title h1 {{
            font-size: 22px;
            font-weight: 700;
            font-family: var(--font-mono);
            margin-bottom: 3px;
        }}

        .banner-title p {{
            font-size: 13.5px;
            color: var(--text-secondary);
        }}

        .banner-right {{
            text-align: right;
            font-size: 12.5px;
            color: var(--text-secondary);
            font-family: var(--font-mono);
        }}

        /* Interactive Filter Bar */
        .filter-bar {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 14px 18px;
            margin-bottom: 20px;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 14px;
        }}

        .filter-group {{
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .filter-label {{
            font-size: 11.5px;
            font-weight: 700;
            text-transform: uppercase;
            color: var(--text-secondary);
            letter-spacing: 0.5px;
            margin-right: 4px;
        }}

        .btn-filter {{
            background-color: var(--bg-card-subtle);
            color: var(--text-muted);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 12.5px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }}

        .btn-filter:hover {{
            background-color: var(--bg-hover);
            color: var(--text-primary);
        }}

        .btn-filter.active {{
            background-color: var(--accent-blue-bg);
            color: var(--accent-blue);
            border-color: var(--accent-blue);
        }}

        .date-wrap {{
            position: relative;
            display: inline-flex;
            align-items: center;
            background-color: var(--bg-page);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 5px 10px;
            cursor: pointer;
            transition: border-color 0.15s ease;
        }}

        .date-wrap:hover, .date-wrap:focus-within {{
            border-color: var(--accent-blue);
        }}

        .date-display {{
            font-size: 12.5px;
            font-family: var(--font-mono);
            color: var(--text-primary);
            display: inline-flex;
            align-items: center;
            gap: 8px;
            pointer-events: none;
            white-space: nowrap;
        }}

        .date-display.empty {{
            color: var(--text-secondary);
        }}

        .date-arrow {{
            color: var(--accent-blue);
            font-size: 11px;
            margin-left: 2px;
        }}

        .date-input {{
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            opacity: 0;
            cursor: pointer;
            color-scheme: dark;
        }}

        .search-input {{
            background-color: var(--bg-page);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 12.5px;
            font-family: var(--font-mono);
            outline: none;
            min-width: 240px;
        }}

        .search-input:focus {{
            border-color: var(--accent-blue);
        }}

        /* KPI Cards */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 14px;
            margin-bottom: 20px;
        }}

        @media (max-width: 1100px) {{
            .kpi-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

        .kpi-card {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 16px 18px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}

        .kpi-label {{
            font-size: 11.5px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}

        .kpi-value {{
            font-size: 24px;
            font-weight: 800;
            font-family: var(--font-mono);
            color: var(--text-primary);
        }}

        .kpi-sub {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 6px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .yield-bar-track {{
            width: 100%;
            height: 6px;
            background-color: var(--bg-card-subtle);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 8px;
        }}

        .yield-bar-fill {{
            height: 100%;
            background-color: var(--color-pass-text);
            transition: width 0.25s ease;
        }}

        /* Analytics 2-Column Section */
        .analytics-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 24px;
        }}

        @media (max-width: 1000px) {{
            .analytics-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .panel-card {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 18px 20px;
            height: 326px;
            display: flex;
            flex-direction: column;
        }}

        #pareto-container {{
            flex: 1;
            overflow-y: auto;
            padding-right: 4px;
            min-height: 0;
        }}

        #retest-container {{
            flex: 1;
            display: flex;
            flex-direction: column;
            min-height: 0;
        }}

        .panel-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
        }}

        .panel-title {{
            font-size: 15px;
            font-weight: 700;
        }}

        .panel-hint {{
            font-size: 12px;
            color: var(--text-secondary);
        }}

        /* Top Failures Pareto List */
        .pareto-item {{
            padding: 10px 12px;
            border-radius: 8px;
            background-color: rgba(255, 255, 255, 0.02);
            border: 1px solid transparent;
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 0.15s ease;
        }}

        .pareto-item:hover {{
            background-color: rgba(218, 54, 51, 0.08);
            border-color: rgba(248, 81, 73, 0.35);
        }}

        .pareto-item.selected {{
            background-color: rgba(218, 54, 51, 0.16);
            border-color: var(--color-fail-border);
        }}

        .pareto-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
            gap: 8px;
        }}

        .pareto-left {{
            display: flex;
            align-items: center;
            gap: 8px;
            overflow: hidden;
        }}

        .rank-badge {{
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 700;
            color: var(--text-secondary);
            background-color: var(--bg-card-subtle);
            padding: 2px 6px;
            border-radius: 4px;
        }}

        .err-badge {{
            font-family: var(--font-mono);
            font-size: 12.5px;
            font-weight: 700;
            color: var(--color-fail-text);
            background-color: var(--color-fail-bg);
            border: 1px solid rgba(248, 81, 73, 0.4);
            padding: 1px 8px;
            border-radius: 6px;
        }}

        .py-badge {{
            font-family: var(--font-mono);
            font-size: 12.5px;
            font-weight: 600;
            color: var(--accent-blue);
        }}

        .pareto-stats {{
            font-family: var(--font-mono);
            font-size: 12.5px;
            font-weight: 700;
            color: var(--text-primary);
            white-space: nowrap;
        }}

        .pareto-bar-bg {{
            width: 100%;
            height: 6px;
            background-color: var(--bg-card-subtle);
            border-radius: 3px;
            overflow: hidden;
        }}

        .pareto-bar-fill {{
            height: 100%;
            background-color: var(--color-fail-border);
            border-radius: 3px;
        }}

        /* Retest & Recovery Breakdown */
        .retest-summary-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-bottom: 12px;
            flex-shrink: 0;
        }}

        .retest-stat-box {{
            background-color: var(--bg-card-subtle);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 10px 12px;
            cursor: pointer;
            transition: all 0.15s ease;
        }}

        .retest-stat-box:hover {{
            border-color: var(--text-secondary);
        }}

        .retest-stat-box.selected {{
            border-color: var(--accent-blue);
            background-color: var(--accent-blue-bg);
        }}

        .retest-unit-list {{
            flex: 1;
            overflow-y: auto;
            padding-right: 4px;
            min-height: 0;
        }}

        .retest-unit-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
            padding: 7px 10px;
            border-radius: 6px;
            border: 1px solid transparent;
            border-bottom: 1px solid rgba(48, 54, 61, 0.45);
            font-family: var(--font-mono);
            font-size: 12.5px;
            cursor: pointer;
            transition: all 0.12s ease;
        }}

        .retest-unit-row:hover {{
            background-color: rgba(255, 255, 255, 0.04);
            border-color: var(--border-color);
        }}

        .retest-unit-row.selected {{
            background-color: var(--accent-blue-bg);
            border-color: var(--accent-blue);
        }}

        /* Full-Width X-Y Coordinate Chart */
        .xy-chart-card {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 18px 20px;
            margin-bottom: 24px;
        }}

        .xy-controls {{
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }}

        .xy-select {{
            background-color: var(--bg-card-subtle);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 5px 10px;
            font-size: 12.5px;
            font-family: var(--font-mono);
            outline: none;
            max-width: 280px;
        }}

        .xy-select:focus {{
            border-color: var(--accent-blue);
        }}

        .xy-svg-wrap {{
            width: 100%;
            min-height: 220px;
            height: auto;
            position: relative;
            margin-top: 8px;
        }}

        .xy-node {{
            cursor: pointer;
            transition: r 0.15s ease, stroke-width 0.15s ease;
        }}

        .xy-node:hover {{
            r: 7px;
            stroke-width: 3px;
        }}

        /* History Table */
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}

        .section-title {{
            font-size: 17px;
            font-weight: 700;
        }}

        .table-container {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 28px;
        }}

        table {{
            width: 100%;
            table-layout: fixed;
            border-collapse: collapse;
            text-align: left;
            font-size: 13.5px;
        }}

        th {{
            background-color: var(--bg-card-subtle);
            color: var(--text-secondary);
            font-weight: 600;
            padding: 12px 14px;
            border-bottom: 1px solid var(--border-color);
            font-size: 11.5px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        td {{
            padding: 12px 14px;
            border-bottom: 1px solid var(--border-color);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        th:first-child, td:first-child {{
            text-align: center;
            padding-left: 8px;
            padding-right: 8px;
            text-overflow: clip;
        }}

        th:last-child, td:last-child {{
            text-align: center;
            padding-left: 8px;
            padding-right: 12px;
            text-overflow: clip;
            overflow: visible;
        }}

        tr.record-row {{
            cursor: pointer;
            transition: background-color 0.12s ease;
        }}

        tr.record-row:hover {{
            background-color: rgba(255, 255, 255, 0.05);
        }}

        tr.record-row.row-fail {{
            background-color: rgba(218, 54, 51, 0.08);
        }}

        tr.record-row.row-fail:hover {{
            background-color: rgba(218, 54, 51, 0.15);
        }}

        .pill {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 11.5px;
            font-weight: 700;
            letter-spacing: 0.4px;
            font-family: var(--font-mono);
        }}

        .pill.pass {{
            background-color: var(--color-pass-bg);
            color: var(--color-pass-text);
            border: 1px solid rgba(63, 185, 80, 0.35);
        }}

        .pill.fail {{
            background-color: var(--color-fail-bg);
            color: var(--color-fail-text);
            border: 1px solid var(--color-fail-border);
        }}

        .pill.stop {{
            background-color: var(--color-stop-bg);
            color: var(--color-stop-text);
            border: 1px solid var(--color-stop-text);
        }}

        .num-col {{
            font-family: var(--font-mono);
        }}

        .btn-view {{
            background-color: var(--bg-card-subtle);
            color: var(--accent-blue);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
        }}

        .btn-view:hover {{
            border-color: var(--accent-blue);
            background-color: var(--accent-blue-bg);
        }}

        /* Modal Overlay for DB Snapshot Inspection */
        .modal-overlay {{
            position: fixed;
            inset: 0;
            background-color: rgba(0, 0, 0, 0.75);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            padding: 24px 8%;
        }}

        .modal-overlay.open {{
            display: flex;
        }}

        .modal-box {{
            background-color: var(--bg-page);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            width: 100%;
            max-width: 1320px;
            max-height: 90vh;
            display: flex;
            flex-direction: column;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.7);
            overflow: hidden;
        }}

        .modal-header {{
            background-color: var(--bg-card);
            padding: 16px 24px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
        }}

        .modal-body {{
            padding: 20px 24px;
            overflow-y: auto;
        }}

        .btn-close {{
            background-color: var(--bg-card-subtle);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
        }}

        .btn-close:hover {{
            background-color: var(--color-fail);
            border-color: var(--color-fail-border);
        }}

        /* Collapsible Script Group Rows inside Modal */
        tr.script-group-row {{
            background-color: rgba(255, 255, 255, 0.025);
            cursor: pointer;
            user-select: none;
        }}

        tr.script-group-row:hover {{
            background-color: rgba(255, 255, 255, 0.06);
        }}

        tr.script-group-row.group-fail {{
            background-color: rgba(218, 54, 51, 0.1);
        }}

        .toggle-btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 22px;
            height: 22px;
            border-radius: 5px;
            background-color: var(--bg-card-subtle);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            font-family: var(--font-mono);
            font-size: 14px;
            font-weight: 700;
        }}

        .script-name {{
            font-family: var(--font-mono);
            font-weight: 700;
            color: var(--accent-blue);
        }}

        tr.script-group-row.group-fail .script-name {{
            color: var(--color-fail-text);
        }}

        .group-meta {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11.5px;
            font-family: var(--font-mono);
            background-color: var(--bg-card-subtle);
            color: var(--text-secondary);
            border: 1px solid var(--border-color);
        }}

        .group-meta.fail {{
            background-color: rgba(218, 54, 51, 0.15);
            color: var(--color-fail-text);
            border-color: rgba(248, 81, 73, 0.4);
        }}

        .duration-tag {{
            display: inline-block;
            font-family: var(--font-mono);
            font-size: 11.5px;
            color: var(--text-muted);
            background-color: var(--bg-card-subtle);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 1px 6px;
        }}

        .tree-branch {{
            color: var(--text-secondary);
            opacity: 0.55;
            margin-right: 8px;
        }}

        .footer {{
            text-align: center;
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 24px;
            padding-bottom: 16px;
        }}
    </style>
</head>
<body>

<div class="container">
    <!-- Top Banner -->
    <div class="top-banner">
        <div class="banner-left">
            <div class="station-badge">Quality Dashboard</div>
            <div class="banner-title">
                <h1>Station: {safe_station} &nbsp;•&nbsp; Fixture: {safe_fixture}</h1>
                <p>Project: <strong>{safe_project}</strong> &nbsp;•&nbsp; Database: <code>{safe_db_name}</code></p>
            </div>
        </div>
        <div class="banner-right">
            <div>Generated: <strong>{generated_at}</strong></div>
            <div style="margin-top: 2px;">100% Offline Interactive SPA</div>
        </div>
    </div>

    <!-- Interactive Filter Bar -->
    <div class="filter-bar">
        <div class="filter-group">
            <span class="filter-label">Period:</span>
            <button class="btn-filter" id="btn-range-today" onclick="setQuickRange('today')">Today</button>
            <button class="btn-filter" id="btn-range-yesterday" onclick="setQuickRange('yesterday')">Yesterday</button>
            <button class="btn-filter" id="btn-range-7d" onclick="setQuickRange('7d')">Last 7 Days</button>
            <button class="btn-filter" id="btn-range-30d" onclick="setQuickRange('30d')">Last 30 Days</button>
            <button class="btn-filter active" id="btn-range-all" onclick="setQuickRange('all')">All Time</button>

            <div class="date-wrap" onclick="openDatePicker('date-from')" title="Select Start Date (YYYY-MM-DD)">
                <span class="date-display empty" id="date-from-label">📅 <span id="date-from-text">YYYY-MM-DD</span> <span class="date-arrow">▾</span></span>
                <input type="date" id="date-from" class="date-input" lang="en-US" onchange="onCustomDateChange()">
            </div>
            <span style="color: var(--text-secondary); font-size: 12.5px;">to</span>
            <div class="date-wrap" onclick="openDatePicker('date-to')" title="Select End Date (YYYY-MM-DD)">
                <span class="date-display empty" id="date-to-label">📅 <span id="date-to-text">YYYY-MM-DD</span> <span class="date-arrow">▾</span></span>
                <input type="date" id="date-to" class="date-input" lang="en-US" onchange="onCustomDateChange()">
            </div>
        </div>

        <div style="font-size: 12px; color: var(--text-secondary);" id="period-summary-hint">
            Showing all recorded station cycles
        </div>
    </div>

    <!-- KPI Summary Cards -->
    <div class="kpi-grid">
        <div class="kpi-card">
            <div>
                <div class="kpi-label">Total Tested</div>
                <div class="kpi-value" id="kpi-total">0</div>
            </div>
            <div class="kpi-sub" id="kpi-unique-sub">0 Unique Units (0 Retests)</div>
        </div>

        <div class="kpi-card">
            <div>
                <div class="kpi-label">Overall Yield Rate</div>
                <div class="kpi-value" id="kpi-yield">0.0%</div>
                <div class="yield-bar-track"><div class="yield-bar-fill" id="kpi-yield-bar" style="width: 0%;"></div></div>
            </div>
            <div class="kpi-sub" id="kpi-yield-sub">0 PASS / 0 FAIL</div>
        </div>

        <div class="kpi-card">
            <div>
                <div class="kpi-label">First Pass Yield (FPY)</div>
                <div class="kpi-value" id="kpi-fpy">0.0%</div>
            </div>
            <div class="kpi-sub" id="kpi-fpy-sub">First-run pass rate by SN</div>
        </div>

        <div class="kpi-card">
            <div>
                <div class="kpi-label">Avg Cycle Time</div>
                <div class="kpi-value" id="kpi-avg-time">0.0s</div>
            </div>
            <div class="kpi-sub" id="kpi-time-sub">PASS Avg: --</div>
        </div>

        <div class="kpi-card">
            <div>
                <div class="kpi-label">#1 Top Failure</div>
                <div class="kpi-value" id="kpi-top-err" style="font-size: 20px;">None</div>
            </div>
            <div class="kpi-sub" id="kpi-top-err-sub">No failures in range</div>
        </div>
    </div>

    <!-- Visual Analytics Section (2-Column: Pareto + Retest/False-Fail Analysis) -->
    <div class="analytics-grid">
        <!-- Left: Top Failures Pareto -->
        <div class="panel-card">
            <div class="panel-header">
                <div class="panel-title">🚨 Top Failures Pareto (Error Code &amp; Script)</div>
                <div class="panel-hint" id="pareto-hint">Click a bar to filter table below</div>
            </div>
            <div id="pareto-container"></div>
        </div>

        <!-- Right: Retest & False-Fail Recovery Breakdown -->
        <div class="panel-card">
            <div class="panel-header">
                <div class="panel-title">🔁 Retest &amp; False-Fail Analysis (Unit Recovery)</div>
                <div class="panel-hint" id="retest-hint">Click to filter retested units</div>
            </div>
            <div id="retest-container"></div>
        </div>
    </div>

    <!-- Full-Width Interactive X-Y Coordinate Chart -->
    <div class="xy-chart-card">
        <div class="panel-header" style="margin-bottom: 8px;">
            <div>
                <div class="panel-title" id="xy-chart-title">📈 Yield Rate &amp; Throughput Trend (X: Date/Time, Y: Yield %)</div>
                <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;" id="xy-chart-sub">Daily / Hourly station yield rate trajectory and test volume</div>
            </div>
            <div class="xy-controls">
                <select id="spc-item-select" class="xy-select" style="display: none;" onchange="renderXYChart()"></select>
                <div class="btn-group">
                    <button class="btn-filter active" id="btn-xy-yield" onclick="setXYChartMode('yield')">📈 Yield Trend</button>
                    <button class="btn-filter" id="btn-xy-cycletime" onclick="setXYChartMode('cycletime')">⏱️ Cycle Time</button>
                    <button class="btn-filter" id="btn-xy-spc" onclick="setXYChartMode('spc')">🎯 Item SPC</button>
                </div>
            </div>
        </div>
        <div class="xy-svg-wrap" id="xy-svg-container"></div>
    </div>

    <!-- Test Execution History Table -->
    <div class="section-header">
        <div class="section-title" id="table-title">📋 Test Execution Records (0)</div>
        <div style="display: flex; align-items: center; gap: 12px;">
            <span style="font-size: 12.5px; color: var(--text-secondary);">Click any row to inspect DB snapshot</span>
            <input type="text" id="search-box" class="search-input" placeholder="🔍 Search SN / ErrCode / .py..." oninput="renderTable()">
        </div>
    </div>

    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th style="width: 52px;">#</th>
                    <th style="width: 15%;">Test Time</th>
                    <th style="width: 15%;">Serial Number</th>
                    <th style="width: 9%;">Run</th>
                    <th style="width: 8%;">Status</th>
                    <th style="width: 14%;">Failed Script</th>
                    <th style="width: 9%;">ErrCode</th>
                    <th style="width: 16%;">Description</th>
                    <th style="width: 6%;">Time</th>
                    <th style="width: 108px;">Report</th>
                </tr>
            </thead>
            <tbody id="records-tbody"></tbody>
        </table>
    </div>

    <div class="footer">
        Generated by <strong>Sapas Hardware Automation Platform</strong> &nbsp;•&nbsp; Local SQLite Station Analytics
    </div>
</div>

<!-- Diagnostic Snapshot Modal (Works even when local HTML/Log folders are moved to FTP!) -->
<div class="modal-overlay" id="snapshot-modal" onclick="if(event.target===this) closeSnapshotModal()">
    <div class="modal-box">
        <div class="modal-header">
            <div style="display: flex; align-items: center; gap: 12px;">
                <span class="pill pass" id="modal-status-pill">PASS</span>
                <span style="font-family: var(--font-mono); font-size: 18px; font-weight: 700;" id="modal-sn-title">SN</span>
                <span style="color: var(--text-secondary); font-size: 13px;" id="modal-meta-sub"></span>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
                <a id="modal-local-link" href="#" target="_blank" class="btn-view" style="text-decoration: none; padding: 6px 12px;">↗ Open Full Local HTML Report</a>
                <button class="btn-close" onclick="closeSnapshotModal()">✕ Close (Esc)</button>
            </div>
        </div>
        <div class="modal-body">
            <div id="modal-archive-notice" style="background-color: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px; padding: 10px 16px; margin-bottom: 16px; font-size: 12.5px; color: var(--text-secondary);">
                💡 <strong>Database Snapshot View</strong>: Complete measurement items below are loaded directly from <code>{safe_db_name}</code>. If raw log files have been archived to FTP/NAS, you can still inspect all sub-item values here.
            </div>
            <div class="table-container" style="margin-bottom: 0;">
                <table>
                    <thead>
                        <tr>
                            <th style="width: 52px;">#</th>
                            <th style="width: 23%;">Test Item</th>
                            <th style="width: 9%;">LSL</th>
                            <th style="width: 14%;">Measured</th>
                            <th style="width: 9%;">USL</th>
                            <th style="width: 8%;">Status</th>
                            <th style="width: 20%;">Description</th>
                            <th style="width: 8%;">ErrCode</th>
                            <th style="width: 7%;">Time</th>
                        </tr>
                    </thead>
                    <tbody id="modal-measurements-tbody"></tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<script>
const RAW_RECORDS = {records_json};

let currentQuickRange = 'all';
let currentStatusFilter = 'ALL';
let selectedParetoError = null;
let selectedRetestFilter = null; // 'ONESHOT' | 'RECOVERED' | 'HARDFAIL' | 'SN:<sn>' | null
let currentXYMode = 'yield';     // 'yield' | 'cycletime' | 'spc'
let filteredRecords = [];

function escapeHtml(str) {{
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}}

function formatDateYMD(dt) {{
    const y = dt.getFullYear();
    const m = String(dt.getMonth() + 1).padStart(2, '0');
    const d = String(dt.getDate()).padStart(2, '0');
    return `${{y}}-${{m}}-${{d}}`;
}}

function openDatePicker(inputId) {{
    const el = document.getElementById(inputId);
    if (!el) return;
    if (typeof el.showPicker === 'function') {{
        try {{ el.showPicker(); return; }} catch (e) {{}}
    }}
    el.focus();
}}

function syncDateLabels() {{
    const fromVal = document.getElementById('date-from').value;
    const toVal = document.getElementById('date-to').value;

    const fromLbl = document.getElementById('date-from-label');
    const fromTxt = document.getElementById('date-from-text');
    if (fromLbl && fromTxt) {{
        fromTxt.textContent = fromVal || 'YYYY-MM-DD';
        fromLbl.classList.toggle('empty', !fromVal);
    }}

    const toLbl = document.getElementById('date-to-label');
    const toTxt = document.getElementById('date-to-text');
    if (toLbl && toTxt) {{
        toTxt.textContent = toVal || 'YYYY-MM-DD';
        toLbl.classList.toggle('empty', !toVal);
    }}
}}

function setQuickRange(mode) {{
    currentQuickRange = mode;
    selectedParetoError = null;
    selectedRetestFilter = null;
    ['today', 'yesterday', '7d', '30d', 'all'].forEach(k => {{
        const btn = document.getElementById('btn-range-' + k);
        if (btn) btn.classList.toggle('active', k === mode);
    }});

    const now = new Date();
    const todayStr = formatDateYMD(now);
    const fromInput = document.getElementById('date-from');
    const toInput = document.getElementById('date-to');

    if (mode === 'today') {{
        fromInput.value = todayStr;
        toInput.value = todayStr;
    }} else if (mode === 'yesterday') {{
        const yest = new Date(now);
        yest.setDate(now.getDate() - 1);
        const yStr = formatDateYMD(yest);
        fromInput.value = yStr;
        toInput.value = yStr;
    }} else if (mode === '7d') {{
        const d7 = new Date(now);
        d7.setDate(now.getDate() - 6);
        fromInput.value = formatDateYMD(d7);
        toInput.value = todayStr;
    }} else if (mode === '30d') {{
        const d30 = new Date(now);
        d30.setDate(now.getDate() - 29);
        fromInput.value = formatDateYMD(d30);
        toInput.value = todayStr;
    }} else {{
        fromInput.value = '';
        toInput.value = '';
    }}
    syncDateLabels();
    applyFilters();
}}

function onCustomDateChange() {{
    currentQuickRange = 'custom';
    selectedParetoError = null;
    selectedRetestFilter = null;
    ['today', 'yesterday', '7d', '30d', 'all'].forEach(k => {{
        const btn = document.getElementById('btn-range-' + k);
        if (btn) btn.classList.remove('active');
    }});
    syncDateLabels();
    applyFilters();
}}

function toggleParetoFilter(paretoKey) {{
    selectedRetestFilter = null;
    if (selectedParetoError === paretoKey) {{
        selectedParetoError = null;
    }} else {{
        selectedParetoError = paretoKey;
    }}
    renderPareto();
    renderRetestPanel();
    renderTable();
}}

function toggleRetestFilter(filterKey) {{
    selectedParetoError = null;
    if (selectedRetestFilter === filterKey) {{
        selectedRetestFilter = null;
    }} else {{
        selectedRetestFilter = filterKey;
    }}
    renderPareto();
    renderRetestPanel();
    renderTable();
}}

function clearParetoFilter() {{
    selectedParetoError = null;
    selectedRetestFilter = null;
    const sb = document.getElementById('search-box');
    if (sb) sb.value = '';
    renderPareto();
    renderRetestPanel();
    renderTable();
}}

function setXYChartMode(mode) {{
    currentXYMode = mode;
    ['yield', 'cycletime', 'spc'].forEach(k => {{
        const btn = document.getElementById('btn-xy-' + k);
        if (btn) btn.classList.toggle('active', k === mode);
    }});
    const sel = document.getElementById('spc-item-select');
    if (sel) sel.style.display = (mode === 'spc') ? 'inline-block' : 'none';
    renderXYChart();
}}

function applyFilters() {{
    const fromVal = document.getElementById('date-from').value;
    const toVal = document.getElementById('date-to').value;

    filteredRecords = RAW_RECORDS.filter(r => {{
        const datePart = (r.test_time || '').slice(0, 10);
        if (fromVal && datePart < fromVal) return false;
        if (toVal && datePart > toVal) return false;
        return true;
    }});

    const periodHint = document.getElementById('period-summary-hint');
    if (periodHint) {{
        if (fromVal && toVal) {{
            periodHint.textContent = fromVal === toVal ? `Date: ${{fromVal}} (${{filteredRecords.length}} runs)` : `Range: ${{fromVal}} ~ ${{toVal}} (${{filteredRecords.length}} runs)`;
        }} else if (fromVal) {{
            periodHint.textContent = `From: ${{fromVal}} (${{filteredRecords.length}} runs)`;
        }} else if (toVal) {{
            periodHint.textContent = `Until: ${{toVal}} (${{filteredRecords.length}} runs)`;
        }} else {{
            periodHint.textContent = `Showing all ${{filteredRecords.length}} recorded station cycles`;
        }}
    }}

    populateSPCItems();
    renderKPIs();
    renderPareto();
    renderRetestPanel();
    renderXYChart();
    renderTable();
}}

function renderKPIs() {{
    const total = filteredRecords.length;
    let passCount = 0;
    let failCount = 0;
    let stopCount = 0;
    let totalSec = 0;
    let passSec = 0;

    const firstRunBySn = new Map();
    const errCounts = new Map();

    filteredRecords.forEach(r => {{
        const st = (r.status || '').toUpperCase();
        const el = Number(r.elapsed_sec || 0);
        totalSec += el;

        if (st === 'PASS') {{
            passCount++;
            passSec += el;
        }} else if (st === 'STOP') {{
            stopCount++;
        }} else {{
            failCount++;
            const ec = r.error_code || 'FAIL';
            const py = r.fail_on_py || 'unknown.py';
            const key = `${{ec}}|||${{py}}`;
            errCounts.set(key, (errCounts.get(key) || 0) + 1);
        }}

        const sn = r.sn || 'UNKNOWN';
        if (!firstRunBySn.has(sn)) {{
            firstRunBySn.set(sn, st);
        }}
    }});

    const uniqueUnits = firstRunBySn.size;
    const retests = Math.max(0, total - uniqueUnits);
    let fpyPass = 0;
    firstRunBySn.forEach(st => {{
        if (st === 'PASS') fpyPass++;
    }});

    const yieldPct = total > 0 ? (passCount * 100.0 / total) : 0.0;
    const fpyPct = uniqueUnits > 0 ? (fpyPass * 100.0 / uniqueUnits) : 0.0;
    const avgTime = total > 0 ? (totalSec / total) : 0.0;
    const avgPassTime = passCount > 0 ? (passSec / passCount) : 0.0;

    document.getElementById('kpi-total').textContent = total;
    document.getElementById('kpi-unique-sub').textContent = `${{uniqueUnits}} Unique Units (${{retests}} Retests)`;

    const yieldEl = document.getElementById('kpi-yield');
    yieldEl.textContent = `${{yieldPct.toFixed(1)}}%`;
    yieldEl.style.color = yieldPct >= 95 ? 'var(--color-pass-text)' : (yieldPct >= 80 ? 'var(--color-stop-text)' : 'var(--color-fail-text)');

    const barEl = document.getElementById('kpi-yield-bar');
    barEl.style.width = `${{yieldPct.toFixed(1)}}%`;
    barEl.style.backgroundColor = yieldPct >= 95 ? 'var(--color-pass-text)' : (yieldPct >= 80 ? 'var(--color-stop-text)' : 'var(--color-fail-border)');
    document.getElementById('kpi-yield-sub').textContent = `${{passCount}} PASS / ${{failCount}} FAIL${{stopCount ? ' / ' + stopCount + ' STOP' : ''}}`;

    document.getElementById('kpi-fpy').textContent = `${{fpyPct.toFixed(1)}}%`;
    document.getElementById('kpi-fpy-sub').textContent = `${{fpyPass}} / ${{uniqueUnits}} First-Run PASS`;

    document.getElementById('kpi-avg-time').textContent = `${{avgTime.toFixed(1)}}s`;
    document.getElementById('kpi-time-sub').textContent = passCount > 0 ? `PASS Avg: ${{avgPassTime.toFixed(1)}}s` : 'PASS Avg: --';

    // Top 1 Error
    let topKey = null;
    let topVal = 0;
    errCounts.forEach((cnt, k) => {{
        if (cnt > topVal) {{
            topVal = cnt;
            topKey = k;
        }}
    }});

    const topErrEl = document.getElementById('kpi-top-err');
    const topErrSub = document.getElementById('kpi-top-err-sub');
    if (topKey) {{
        const [ec, py] = topKey.split('|||');
        topErrEl.textContent = ec;
        topErrEl.style.color = 'var(--color-fail-text)';
        topErrSub.textContent = `${{py}} (${{topVal}} fails)`;
    }} else {{
        topErrEl.textContent = 'None';
        topErrEl.style.color = 'var(--color-pass-text)';
        topErrSub.textContent = '100% Clean in selection';
    }}
}}

function renderPareto() {{
    const container = document.getElementById('pareto-container');
    const hintEl = document.getElementById('pareto-hint');
    if (hintEl) {{
        if (selectedParetoError) {{
            hintEl.innerHTML = `<button onclick="clearParetoFilter()" class="btn-view" style="border-color: var(--color-fail-border); color: var(--color-fail-text); background-color: var(--color-fail-bg); padding: 2px 10px; font-size: 11.5px;">✕ Clear Table Filter</button>`;
        }} else {{
            hintEl.textContent = 'Click a bar to filter table below';
        }}
    }}

    const baseFailures = filteredRecords.filter(r => {{
        const st = (r.status || '').toUpperCase();
        return st !== 'PASS' && st !== 'STOP';
    }});

    if (baseFailures.length === 0) {{
        container.innerHTML = `<div style="text-align: center; color: var(--text-secondary); padding: 48px 16px;">🎉 Zero failures recorded in the selected period!</div>`;
        return;
    }}

    const map = new Map();
    baseFailures.forEach(r => {{
        const ec = r.error_code || 'FAIL';
        const py = r.fail_on_py || 'unknown.py';
        const pKey = `${{ec}}|||${{py}}`;
        if (!map.has(pKey)) {{
            map.set(pKey, {{
                key: pKey,
                err_code: ec,
                fail_on_py: py,
                desc: r.error_desc || '',
                count: 0
            }});
        }}
        map.get(pKey).count++;
    }});

    const sorted = Array.from(map.values()).sort((a, b) => b.count - a.count).slice(0, 10);
    const totalFails = baseFailures.length;

    container.innerHTML = sorted.map((item, idx) => {{
        const pct = (item.count * 100.0 / totalFails).toFixed(1);
        const isActive = selectedParetoError === item.key;
        const isSel = isActive ? 'selected' : '';
        const clearTag = isActive ? `<span style="color: var(--color-fail-text); font-size: 11px; margin-right: 8px;">✕ Click again to show all</span>` : '';
        return `
            <div class="pareto-item ${{isSel}}" onclick="toggleParetoFilter('${{escapeHtml(item.key)}}')" title="${{isActive ? 'Click again to clear table filter' : 'Click to filter table below by ' + escapeHtml(item.err_code) + ' (' + escapeHtml(item.fail_on_py) + ')'}}">
                <div class="pareto-top">
                    <div class="pareto-left">
                        <span class="rank-badge">#${{idx + 1}}</span>
                        <span class="err-badge">${{escapeHtml(item.err_code)}}</span>
                        <span class="py-badge">${{escapeHtml(item.fail_on_py)}}</span>
                        <span style="color: var(--text-secondary); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${{escapeHtml(item.desc)}}</span>
                    </div>
                    <div class="pareto-stats">${{clearTag}}${{item.count}} (${{pct}}%)</div>
                </div>
                <div class="pareto-bar-bg">
                    <div class="pareto-bar-fill" style="width: ${{pct}}%;"></div>
                </div>
            </div>
        `;
    }}).join('');
}}

function classifyUnits(records) {{
    const bySn = new Map();
    records.forEach(r => {{
        const sn = r.sn || 'UNKNOWN';
        if (!bySn.has(sn)) bySn.set(sn, []);
        bySn.get(sn).push(r);
    }});

    const oneShotSn = new Set();
    const recoveredSn = new Set();
    const hardFailSn = new Set();
    const allUnits = [];
    const attentionUnits = [];

    bySn.forEach((runs, sn) => {{
        const statuses = runs.map(x => (x.status || '').toUpperCase());
        const lastSt = statuses[statuses.length - 1];
        const hadFail = statuses.some(s => s !== 'PASS');

        let category = 'ONESHOT';
        if (!hadFail && runs.length === 1) {{
            oneShotSn.add(sn);
            category = 'ONESHOT';
        }} else if (lastSt === 'PASS' && (hadFail || runs.length > 1)) {{
            if (hadFail) {{
                recoveredSn.add(sn);
                category = 'RECOVERED';
            }} else {{
                oneShotSn.add(sn);
                category = 'ONESHOT';
            }}
        }} else {{
            hardFailSn.add(sn);
            category = 'HARDFAIL';
        }}

        // Priority: 0 = RECOVERED (False-Fail), 1 = HARDFAIL (Unrecovered), 2 = ONESHOT multi-run, 3 = ONESHOT single-run
        const priority = category === 'RECOVERED' ? 0 : (category === 'HARDFAIL' ? 1 : (runs.length > 1 ? 2 : 3));
        const unitObj = {{
            sn,
            runs,
            statuses,
            hadFail,
            lastSt,
            category,
            priority
        }};
        allUnits.push(unitObj);
        if (runs.length > 1 || category === 'HARDFAIL') {{
            attentionUnits.push(unitObj);
        }}
    }});

    const sortUnits = (a, b) => {{
        if (a.priority !== b.priority) return a.priority - b.priority;
        return b.runs.length - a.runs.length;
    }};
    allUnits.sort(sortUnits);
    attentionUnits.sort(sortUnits);

    return {{ oneShotSn, recoveredSn, hardFailSn, allUnits, attentionUnits, totalUnique: bySn.size }};
}}

function formatStatusToken(s) {{
    const c = s === 'PASS' ? 'var(--color-pass-text)' : (s === 'STOP' ? 'var(--color-stop-text)' : 'var(--color-fail-text)');
    return `<span style="color: ${{c}}; font-weight: 700;">${{s}}</span>`;
}}

function formatRunChain(statuses) {{
    const sep = ' <span style="color: var(--text-secondary);">→</span> ';
    if (statuses.length <= 4) {{
        return statuses.map(formatStatusToken).join(sep);
    }}
    const first = formatStatusToken(statuses[0]);
    const midCount = statuses.length - 3;
    const mid = `<span style="color: var(--text-secondary); font-size: 11px;">…(×${{midCount}})…</span>`;
    const penult = formatStatusToken(statuses[statuses.length - 2]);
    const last = formatStatusToken(statuses[statuses.length - 1]);
    return [first, mid, penult, last].join(sep);
}}

function renderRetestPanel() {{
    const container = document.getElementById('retest-container');
    const hintEl = document.getElementById('retest-hint');
    if (hintEl) {{
        if (selectedRetestFilter) {{
            hintEl.innerHTML = `<button onclick="clearParetoFilter()" class="btn-view" style="border-color: var(--accent-blue); color: var(--accent-blue); background-color: var(--accent-blue-bg); padding: 2px 10px; font-size: 11.5px;">✕ Clear Table Filter</button>`;
        }} else {{
            hintEl.textContent = 'Click box or SN to filter table';
        }}
    }}

    if (filteredRecords.length === 0) {{
        container.innerHTML = `<div style="text-align: center; color: var(--text-secondary); padding: 48px 16px;">No records in selected period.</div>`;
        return;
    }}

    const {{ oneShotSn, recoveredSn, hardFailSn, allUnits, attentionUnits, totalUnique }} = classifyUnits(filteredRecords);
    const oneShotPct = totalUnique > 0 ? (oneShotSn.size * 100 / totalUnique).toFixed(0) : 0;
    const recovPct = totalUnique > 0 ? (recoveredSn.size * 100 / totalUnique).toFixed(0) : 0;
    const hardPct = totalUnique > 0 ? (hardFailSn.size * 100 / totalUnique).toFixed(0) : 0;

    let visibleUnits = attentionUnits;
    let listHeaderLabel = `Retested & Unrecovered Serial Numbers (${{attentionUnits.length}} units) — Click to inspect runs:`;
    if (selectedRetestFilter === 'RECOVERED' || selectedRetestFilter === 'HARDFAIL' || selectedRetestFilter === 'ONESHOT') {{
        visibleUnits = allUnits.filter(u => u.category === selectedRetestFilter);
        const catTitle = selectedRetestFilter === 'RECOVERED'
            ? '🟡 RETEST → PASS'
            : (selectedRetestFilter === 'HARDFAIL' ? '🔴 HARD FAIL' : '🟢 ONE-SHOT PASS');
        listHeaderLabel = `${{catTitle}} Serial Numbers (${{visibleUnits.length}} units) — Click SN to lock:`;
    }}

    let multiHtml = '';
    if (visibleUnits.length === 0) {{
        multiHtml = `<div style="text-align: center; color: var(--text-secondary); padding: 18px 8px; font-size: 12.5px;">✨ No units in this category.</div>`;
    }} else {{
        multiHtml = `<div style="font-size: 11.5px; color: var(--text-secondary); margin-bottom: 6px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; flex-shrink: 0;">${{listHeaderLabel}}</div>` +
            `<div class="retest-unit-list">` +
            visibleUnits.map(u => {{
                const fKey = 'SN:' + u.sn;
                const isSel = selectedRetestFilter === fKey ? 'selected' : '';
                const chain = formatRunChain(u.statuses);
                const fullChainTitle = u.statuses.map((st, idx) => `Run #${{idx + 1}}: ${{st}}`).join(' → ');
                const runText = u.runs.length === 1 ? '1 run' : `${{u.runs.length}} runs`;
                return `
                    <div class="retest-unit-row ${{isSel}}" onclick="toggleRetestFilter('${{escapeHtml(fKey)}}')" title="${{escapeHtml(u.sn)}} — ${{escapeHtml(fullChainTitle)}}">
                        <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            <span style="font-weight: 700; color: var(--text-primary);">${{escapeHtml(u.sn)}}</span>
                            <span style="color: var(--text-secondary); font-size: 11.5px; margin-left: 6px;">(${{runText}})</span>
                        </div>
                        <div style="font-size: 12px; white-space: nowrap; flex-shrink: 0;">${{chain}}</div>
                    </div>
                `;
            }}).join('') +
            `</div>`;
    }}

    container.innerHTML = `
        <div class="retest-summary-grid">
            <div class="retest-stat-box ${{selectedRetestFilter === 'ONESHOT' ? 'selected' : ''}}" onclick="toggleRetestFilter('ONESHOT')" title="Units that passed without failing">
                <div style="font-size: 11px; color: var(--text-secondary); font-weight: 600;">🟢 ONE-SHOT PASS</div>
                <div style="font-size: 20px; font-weight: 800; font-family: var(--font-mono); color: var(--color-pass-text); margin: 4px 0;">${{oneShotSn.size}} <span style="font-size: 12px; font-weight: 600; color: var(--text-secondary);">(${{oneShotPct}}%)</span></div>
                <div style="font-size: 11px; color: var(--text-secondary);">Clean pass units</div>
            </div>
            <div class="retest-stat-box ${{selectedRetestFilter === 'RECOVERED' ? 'selected' : ''}}" onclick="toggleRetestFilter('RECOVERED')" title="Units that failed first but passed on retest (Potential False-Fail / Fixture issue)">
                <div style="font-size: 11px; color: var(--text-secondary); font-weight: 600;">🟡 RETEST → PASS</div>
                <div style="font-size: 20px; font-weight: 800; font-family: var(--font-mono); color: var(--color-stop-text); margin: 4px 0;">${{recoveredSn.size}} <span style="font-size: 12px; font-weight: 600; color: var(--text-secondary);">(${{recovPct}}%)</span></div>
                <div style="font-size: 11px; color: var(--text-secondary);">Suspected False-Fail</div>
            </div>
            <div class="retest-stat-box ${{selectedRetestFilter === 'HARDFAIL' ? 'selected' : ''}}" onclick="toggleRetestFilter('HARDFAIL')" title="Units whose latest test run is still FAIL">
                <div style="font-size: 11px; color: var(--text-secondary); font-weight: 600;">🔴 HARD FAIL</div>
                <div style="font-size: 20px; font-weight: 800; font-family: var(--font-mono); color: var(--color-fail-text); margin: 4px 0;">${{hardFailSn.size}} <span style="font-size: 12px; font-weight: 600; color: var(--text-secondary);">(${{hardPct}}%)</span></div>
                <div style="font-size: 11px; color: var(--text-secondary);">Unrecovered units</div>
            </div>
        </div>
        ${{multiHtml}}
    `;
}}

function isStrictDecimal(val) {{
    if (val === null || val === undefined) return false;
    const s = String(val).trim();
    if (!s) return false;
    // Only allow pure decimal numbers (e.g., 46.9, -12, 0, 528.88).
    // Rejects hex strings (0xf2fc5743, 0xff), multi-dot versions (2.1.0), and leading-zero IDs (0012).
    return /^[-+]?(?:0|[1-9]\\d*)(?:\\.\\d+)?$/.test(s);
}}

function isValidSpecBound(val) {{
    if (val === null || val === undefined) return true;
    const s = String(val).trim().toUpperCase();
    if (!s || s === 'RECORD' || s === '-' || s === 'N/A' || s === 'NONE') return true;
    return isStrictDecimal(s);
}}

function populateSPCItems() {{
    const sel = document.getElementById('spc-item-select');
    if (!sel) return;
    const prevVal = sel.value;
    const itemStats = new Map();

    filteredRecords.forEach(r => {{
        (r.measurements || []).forEach(m => {{
            const rawMeasured = m.measured !== null && m.measured !== undefined ? String(m.measured).trim() : '';
            if (!rawMeasured) return;
            const key = `${{m.script || 'script.py'}}:::${{m.item || 'Item'}}`;
            if (!itemStats.has(key)) {{
                itemStats.set(key, {{
                    script: m.script || 'script.py',
                    item: m.item || 'Item',
                    allNumeric: true,
                    validCount: 0,
                    hasRangeSpec: false,
                    hasDistinctRange: false,
                    lslStr: '',
                    uslStr: ''
                }});
            }}
            const st = itemStats.get(key);
            if (!isStrictDecimal(rawMeasured) || !isValidSpecBound(m.lsl) || !isValidSpecBound(m.usl)) {{
                st.allNumeric = false;
                return;
            }}
            // Also guard against RECORD-only serial/UID/version strings that happen to contain only digits
            const lslClean = String(m.lsl || '').trim().toUpperCase();
            const uslClean = String(m.usl || '').trim().toUpperCase();
            const isRecordOnly = (!lslClean || lslClean === 'RECORD') && (!uslClean || uslClean === 'RECORD');
            if (isRecordOnly && /(?:^|_)(?:sn|uid|uuid|mac|ver|version|crc|hash)(?:$|_)/i.test(st.item)) {{
                st.allNumeric = false;
                return;
            }}
            st.validCount++;
            if (isStrictDecimal(m.lsl) && isStrictDecimal(m.usl)) {{
                st.hasRangeSpec = true;
                st.lslStr = String(m.lsl).trim();
                st.uslStr = String(m.usl).trim();
                if (parseFloat(st.lslStr) < parseFloat(st.uslStr)) {{
                    st.hasDistinctRange = true;
                }}
            }}
        }});
    }});

    const validEntries = Array.from(itemStats.entries())
        .filter(([_, st]) => st.allNumeric && st.validCount > 0)
        .sort((a, b) => {{
            // Prioritize items with real LSL < USL continuous tolerance bands first
            if (a[1].hasDistinctRange !== b[1].hasDistinctRange) return a[1].hasDistinctRange ? -1 : 1;
            if (a[1].hasRangeSpec !== b[1].hasRangeSpec) return a[1].hasRangeSpec ? -1 : 1;
            return a[0].localeCompare(b[0]);
        }});

    if (validEntries.length === 0) {{
        sel.innerHTML = `<option value="">No numeric items in selection</option>`;
        return;
    }}

    sel.innerHTML = validEntries.map(([k, st]) => {{
        const specHint = st.hasDistinctRange ? ` [${{st.lslStr}} ~ ${{st.uslStr}}]` : '';
        const label = `${{st.item}} (${{st.script}})${{specHint}}`;
        return `<option value="${{escapeHtml(k)}}">${{escapeHtml(label)}}</option>`;
    }}).join('');

    const validKeySet = new Set(validEntries.map(([k]) => k));
    if (prevVal && validKeySet.has(prevVal)) {{
        sel.value = prevVal;
    }}
}}

function renderXYChart() {{
    const wrap = document.getElementById('xy-svg-container');
    const titleEl = document.getElementById('xy-chart-title');
    const subEl = document.getElementById('xy-chart-sub');
    if (!wrap) return;

    if (filteredRecords.length === 0) {{
        wrap.innerHTML = `<div style="text-align: center; color: var(--text-secondary); padding: 80px 16px;">No test records available to plot in the selected period.</div>`;
        return;
    }}

    const W = 1140;
    const H = 240;
    const padL = 62;
    const padR = 34;
    const padT = 22;
    const padB = 42;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;

    if (currentXYMode === 'yield') {{
        const uniqueDates = new Set(filteredRecords.map(r => (r.test_time || '').slice(0, 10)));
        const isSingleDay = uniqueDates.size === 1;
        titleEl.textContent = isSingleDay
            ? `📈 Hourly Yield Rate & Volume (${{Array.from(uniqueDates)[0]}})`
            : `📈 Daily Yield Rate & Volume Trend`;
        subEl.textContent = `X-Axis: ${{isSingleDay ? 'Hour of Day' : 'Date'}}  •  Y-Axis: Station Yield Rate (0% ~ 100%)  •  Bars: Tested Volume`;

        const buckets = new Map();
        filteredRecords.forEach(r => {{
            const t = r.test_time || '';
            const key = isSingleDay ? (t.slice(11, 13) + ':00') : t.slice(0, 10);
            if (!buckets.has(key)) buckets.set(key, {{ pass: 0, fail: 0, total: 0 }});
            const b = buckets.get(key);
            b.total++;
            if ((r.status || '').toUpperCase() === 'PASS') b.pass++;
            else b.fail++;
        }});

        const keys = Array.from(buckets.keys()).sort();
        const maxVol = Math.max(...keys.map(k => buckets.get(k).total), 1);
        const n = keys.length;
        const xFor = i => n === 1 ? (padL + plotW / 2) : (padL + (i / (n - 1)) * plotW);
        const yForPct = pct => padT + plotH - (pct / 100.0) * plotH;

        let gridSvg = '';
        [0, 25, 50, 75, 100].forEach(pct => {{
            const y = yForPct(pct);
            gridSvg += `<line x1="${{padL}}" y1="${{y}}" x2="${{W - padR}}" y2="${{y}}" stroke="#21262d" stroke-width="1" />`;
            gridSvg += `<text x="${{padL - 10}}" y="${{y + 4}}" text-anchor="end" fill="#8b949e" font-size="11" font-family="var(--font-mono)">${{pct}}%</text>`;
        }});

        // Volume background bars + X labels + Yield points
        let barsSvg = '';
        let points = [];
        let nodesSvg = '';
        const barW = Math.min(38, Math.max(12, (plotW / Math.max(n, 2)) * 0.45));
        const labelStep = Math.max(1, Math.ceil(n / 10));

        keys.forEach((k, i) => {{
            const b = buckets.get(k);
            const pct = (b.pass * 100.0) / b.total;
            const cx = xFor(i);
            const cy = yForPct(pct);
            points.push(`${{cx.toFixed(1)}},${{cy.toFixed(1)}}`);

            const bH = (b.total / maxVol) * (plotH * 0.65);
            const bY = padT + plotH - bH;
            barsSvg += `<rect x="${{(cx - barW / 2).toFixed(1)}}" y="${{bY.toFixed(1)}}" width="${{barW.toFixed(1)}}" height="${{bH.toFixed(1)}}" rx="3" fill="rgba(88, 166, 255, 0.14)" stroke="rgba(88, 166, 255, 0.28)" stroke-width="1"><title>${{k}} — Volume: ${{b.total}} (${{b.pass}} PASS / ${{b.fail}} FAIL)</title></rect>`;

            if (i % labelStep === 0 || i === n - 1) {{
                const shortLbl = isSingleDay ? k : k.slice(5);
                gridSvg += `<text x="${{cx.toFixed(1)}}" y="${{H - 14}}" text-anchor="middle" fill="#8b949e" font-size="11" font-family="var(--font-mono)">${{escapeHtml(shortLbl)}}</text>`;
            }}

            const nodeColor = pct >= 95 ? '#3fb950' : (pct >= 80 ? '#d29922' : '#f85149');
            nodesSvg += `
                <g>
                    <circle class="xy-node" cx="${{cx.toFixed(1)}}" cy="${{cy.toFixed(1)}}" r="5" fill="${{nodeColor}}" stroke="#0d1117" stroke-width="2">
                        <title>${{k}}\nYield: ${{pct.toFixed(1)}}% (${{b.pass}} PASS / ${{b.fail}} FAIL, Total ${{b.total}})</title>
                    </circle>
                    <text x="${{cx.toFixed(1)}}" y="${{(cy - 10).toFixed(1)}}" text-anchor="middle" fill="#f0f6fc" font-size="11" font-weight="700" font-family="var(--font-mono)">${{pct.toFixed(0)}}%</text>
                </g>
            `;
        }});

        const lineSvg = points.length > 1
            ? `<polyline fill="none" stroke="#58a6ff" stroke-width="2.5" points="${{points.join(' ')}}" />`
            : '';

        wrap.innerHTML = `<svg viewBox="0 0 ${{W}} ${{H}}" style="width: 100%; height: auto; display: block;">${{gridSvg}}${{barsSvg}}${{lineSvg}}${{nodesSvg}}</svg>`;

    }} else if (currentXYMode === 'cycletime') {{
        titleEl.textContent = `⏱️ Cycle Time Stability Trend (X: Test Sequence, Y: Elapsed Seconds)`;
        subEl.textContent = `Green = PASS • Red = FAIL • Dashed Blue Line = PASS Average Cycle Time (Click any node to inspect unit)`;

        const n = filteredRecords.length;
        const vals = filteredRecords.map(r => Number(r.elapsed_sec || 0));
        const passVals = filteredRecords.filter(r => (r.status || '').toUpperCase() === 'PASS').map(r => Number(r.elapsed_sec || 0));
        const passAvg = passVals.length > 0 ? (passVals.reduce((a, b) => a + b, 0) / passVals.length) : 0;

        const maxY = Math.max(...vals, passAvg, 5) * 1.15;
        const minY = 0;
        const xFor = i => n === 1 ? (padL + plotW / 2) : (padL + (i / (n - 1)) * plotW);
        const yFor = v => padT + plotH - ((v - minY) / (maxY - minY)) * plotH;

        let gridSvg = '';
        for (let s = 0; s <= 4; s++) {{
            const v = minY + (s / 4) * (maxY - minY);
            const y = yFor(v);
            gridSvg += `<line x1="${{padL}}" y1="${{y.toFixed(1)}}" x2="${{W - padR}}" y2="${{y.toFixed(1)}}" stroke="#21262d" stroke-width="1" />`;
            gridSvg += `<text x="${{padL - 10}}" y="${{(y + 4).toFixed(1)}}" text-anchor="end" fill="#8b949e" font-size="11" font-family="var(--font-mono)">${{v.toFixed(0)}}s</text>`;
        }}

        if (passAvg > 0) {{
            const avgY = yFor(passAvg);
            gridSvg += `<line x1="${{padL}}" y1="${{avgY.toFixed(1)}}" x2="${{W - padR}}" y2="${{avgY.toFixed(1)}}" stroke="#58a6ff" stroke-width="1.5" stroke-dasharray="5,5" />`;
            gridSvg += `<text x="${{W - padR - 4}}" y="${{(avgY - 6).toFixed(1)}}" text-anchor="end" fill="#58a6ff" font-size="11" font-family="var(--font-mono)">PASS Avg: ${{passAvg.toFixed(1)}}s</text>`;
        }}

        let points = [];
        let nodesSvg = '';
        const labelStep = Math.max(1, Math.ceil(n / 12));

        filteredRecords.forEach((r, i) => {{
            const v = Number(r.elapsed_sec || 0);
            const cx = xFor(i);
            const cy = yFor(v);
            points.push(`${{cx.toFixed(1)}},${{cy.toFixed(1)}}`);

            if (i % labelStep === 0 || i === n - 1) {{
                gridSvg += `<text x="${{cx.toFixed(1)}}" y="${{H - 14}}" text-anchor="middle" fill="#8b949e" font-size="11" font-family="var(--font-mono)">#${{i + 1}}</text>`;
            }}

            const st = (r.status || '').toUpperCase();
            const color = st === 'PASS' ? '#3fb950' : (st === 'STOP' ? '#d29922' : '#f85149');
            nodesSvg += `
                <circle class="xy-node" cx="${{cx.toFixed(1)}}" cy="${{cy.toFixed(1)}}" r="4.5" fill="${{color}}" stroke="#0d1117" stroke-width="2" onclick="openSnapshotModal(${{r.id}})">
                    <title>#${{i + 1}} | SN: ${{r.sn}}\nTime: ${{r.test_time}}\nCycle Time: ${{v.toFixed(1)}}s (${{st}})</title>
                </circle>
            `;
        }});

        const lineSvg = points.length > 1
            ? `<polyline fill="none" stroke="rgba(139, 148, 158, 0.45)" stroke-width="2" points="${{points.join(' ')}}" />`
            : '';

        wrap.innerHTML = `<svg viewBox="0 0 ${{W}} ${{H}}" style="width: 100%; height: auto; display: block;">${{gridSvg}}${{lineSvg}}${{nodesSvg}}</svg>`;

    }} else {{
        const sel = document.getElementById('spc-item-select');
        const selectedKey = sel ? sel.value : '';
        if (!selectedKey) {{
            wrap.innerHTML = `<div style="text-align: center; color: var(--text-secondary); padding: 80px 16px;">No numeric measurement items found in the selected records.</div>`;
            return;
        }}
        const [targetPy, targetItem] = selectedKey.split(':::');
        titleEl.textContent = `🎯 Parameter Control Chart: ${{targetItem}} (${{targetPy}})`;
        subEl.textContent = `X-Axis: Unit Sequence  •  Y-Axis: Measured Value  •  Red Dashed Lines: LSL / USL Spec Limits`;

        const ptsData = [];
        let lslNum = null;
        let uslNum = null;

        filteredRecords.forEach((r, idx) => {{
            const found = (r.measurements || []).find(m => (m.script || 'script.py') === targetPy && (m.item || 'Item') === targetItem);
            if (found && isStrictDecimal(found.measured)) {{
                const val = parseFloat(found.measured);
                ptsData.push({{ r, runIdx: idx + 1, val, m: found }});
                if (isStrictDecimal(found.lsl)) lslNum = parseFloat(found.lsl);
                if (isStrictDecimal(found.usl)) uslNum = parseFloat(found.usl);
            }}
        }});

        if (ptsData.length === 0) {{
            wrap.innerHTML = `<div style="text-align: center; color: var(--text-secondary); padding: 80px 16px;">Selected item was not measured in the current records.</div>`;
            return;
        }}

        const allY = ptsData.map(p => p.val);
        if (lslNum !== null) allY.push(lslNum);
        if (uslNum !== null) allY.push(uslNum);

        let minY = Math.min(...allY);
        let maxY = Math.max(...allY);
        const span = (maxY - minY) || Math.abs(maxY * 0.2) || 10;
        minY -= span * 0.15;
        maxY += span * 0.15;

        const n = ptsData.length;
        const xFor = i => n === 1 ? (padL + plotW / 2) : (padL + (i / (n - 1)) * plotW);
        const yFor = v => padT + plotH - ((v - minY) / (maxY - minY)) * plotH;

        let gridSvg = '';
        for (let s = 0; s <= 4; s++) {{
            const v = minY + (s / 4) * (maxY - minY);
            const y = yFor(v);
            gridSvg += `<line x1="${{padL}}" y1="${{y.toFixed(1)}}" x2="${{W - padR}}" y2="${{y.toFixed(1)}}" stroke="#21262d" stroke-width="1" />`;
            gridSvg += `<text x="${{padL - 8}}" y="${{(y + 4).toFixed(1)}}" text-anchor="end" fill="#8b949e" font-size="11" font-family="var(--font-mono)">${{Number(v.toPrecision(5))}}</text>`;
        }}

        if (uslNum !== null) {{
            const uy = yFor(uslNum);
            gridSvg += `<line x1="${{padL}}" y1="${{uy.toFixed(1)}}" x2="${{W - padR}}" y2="${{uy.toFixed(1)}}" stroke="#f85149" stroke-width="1.5" stroke-dasharray="6,4" />`;
            gridSvg += `<text x="${{W - padR - 4}}" y="${{(uy - 5).toFixed(1)}}" text-anchor="end" fill="#f85149" font-size="11" font-weight="700" font-family="var(--font-mono)">USL: ${{uslNum}}</text>`;
        }}
        if (lslNum !== null) {{
            const ly = yFor(lslNum);
            gridSvg += `<line x1="${{padL}}" y1="${{ly.toFixed(1)}}" x2="${{W - padR}}" y2="${{ly.toFixed(1)}}" stroke="#f85149" stroke-width="1.5" stroke-dasharray="6,4" />`;
            gridSvg += `<text x="${{W - padR - 4}}" y="${{(ly + 13).toFixed(1)}}" text-anchor="end" fill="#f85149" font-size="11" font-weight="700" font-family="var(--font-mono)">LSL: ${{lslNum}}</text>`;
        }}

        let points = [];
        let nodesSvg = '';
        const labelStep = Math.max(1, Math.ceil(n / 12));

        ptsData.forEach((p, i) => {{
            const cx = xFor(i);
            const cy = yFor(p.val);
            points.push(`${{cx.toFixed(1)}},${{cy.toFixed(1)}}`);

            if (i % labelStep === 0 || i === n - 1) {{
                gridSvg += `<text x="${{cx.toFixed(1)}}" y="${{H - 14}}" text-anchor="middle" fill="#8b949e" font-size="11" font-family="var(--font-mono)">#${{p.runIdx}}</text>`;
            }}

            const mst = (p.m.status || 'PASS').toUpperCase();
            const color = mst === 'PASS' ? '#3fb950' : '#f85149';
            nodesSvg += `
                <circle class="xy-node" cx="${{cx.toFixed(1)}}" cy="${{cy.toFixed(1)}}" r="5" fill="${{color}}" stroke="#0d1117" stroke-width="2" onclick="openSnapshotModal(${{p.r.id}})">
                    <title>#${{p.runIdx}} | SN: ${{p.r.sn}}\n${{targetItem}}: ${{p.val}} (LSL: ${{p.m.lsl}}, USL: ${{p.m.usl}}) [${{mst}}]</title>
                </circle>
            `;
        }});

        const lineSvg = points.length > 1
            ? `<polyline fill="none" stroke="#58a6ff" stroke-width="2" points="${{points.join(' ')}}" />`
            : '';

        wrap.innerHTML = `<svg viewBox="0 0 ${{W}} ${{H}}" style="width: 100%; height: auto; display: block;">${{gridSvg}}${{lineSvg}}${{nodesSvg}}</svg>`;
    }}
}}

function renderTable() {{
    const tbody = document.getElementById('records-tbody');
    const titleEl = document.getElementById('table-title');
    const query = (document.getElementById('search-box')?.value || '').trim().toLowerCase();

    let tableRecords = filteredRecords;
    let activeFilterHtml = '';

    if (selectedParetoError) {{
        const [selEc, selPy] = selectedParetoError.split('|||');
        tableRecords = tableRecords.filter(r => {{
            const st = (r.status || '').toUpperCase();
            if (st === 'PASS' || st === 'STOP') return false;
            const ec = r.error_code || 'FAIL';
            const py = r.fail_on_py || 'unknown.py';
            return ec === selEc && py === selPy;
        }});
        activeFilterHtml = ` — <span style="color: var(--color-fail-text);">Filtered by ${{escapeHtml(selEc)}} (${{escapeHtml(selPy)}})</span>`;
    }} else if (selectedRetestFilter) {{
        const {{ oneShotSn, recoveredSn, hardFailSn }} = classifyUnits(filteredRecords);
        let filterLabel = '';
        if (selectedRetestFilter === 'ONESHOT') {{
            tableRecords = tableRecords.filter(r => oneShotSn.has(r.sn || 'UNKNOWN'));
            filterLabel = 'One-Shot PASS Units';
        }} else if (selectedRetestFilter === 'RECOVERED') {{
            tableRecords = tableRecords.filter(r => recoveredSn.has(r.sn || 'UNKNOWN'));
            filterLabel = 'Retest → PASS (False-Fail) Units';
        }} else if (selectedRetestFilter === 'HARDFAIL') {{
            tableRecords = tableRecords.filter(r => hardFailSn.has(r.sn || 'UNKNOWN'));
            filterLabel = 'Unrecovered Hard FAIL Units';
        }} else if (selectedRetestFilter.startsWith('SN:')) {{
            const targetSn = selectedRetestFilter.slice(3);
            tableRecords = tableRecords.filter(r => (r.sn || 'UNKNOWN') === targetSn);
            filterLabel = `SN: ${{targetSn}} (All Runs)`;
        }}
        activeFilterHtml = ` — <span style="color: var(--accent-blue);">Filtered by ${{escapeHtml(filterLabel)}}</span>`;
    }}

    if (query) {{
        tableRecords = tableRecords.filter(r => {{
            const hay = `${{r.sn || ''}} ${{r.error_code || ''}} ${{r.fail_on_py || ''}} ${{r.error_desc || ''}} ${{r.status || ''}}`.toLowerCase();
            return hay.includes(query);
        }});
        if (!activeFilterHtml) {{
            activeFilterHtml = ` — <span style="color: var(--accent-blue);">Search: "${{escapeHtml(query)}}"</span>`;
        }}
    }}

    if (selectedParetoError || selectedRetestFilter || query) {{
        titleEl.innerHTML = `📋 Test Execution Records (${{tableRecords.length}} of ${{filteredRecords.length}})${{activeFilterHtml}} <button onclick="clearParetoFilter()" class="btn-view" style="margin-left: 8px; padding: 2px 10px; font-size: 11.5px; border-color: var(--accent-blue); color: var(--accent-blue); background-color: var(--accent-blue-bg);">✕ Clear Table Filter</button>`;
    }} else {{
        titleEl.textContent = `📋 Test Execution Records (${{tableRecords.length}})`;
    }}

    if (tableRecords.length === 0) {{
        tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-secondary); padding: 32px;">No matching test records found.</td></tr>`;
        return;
    }}

    // Show newest first
    const reversed = [...tableRecords].reverse();
    tbody.innerHTML = reversed.map((r, idx) => {{
        const st = (r.status || 'UNKNOWN').toUpperCase();
        const isPass = st === 'PASS';
        const isStop = st === 'STOP';
        const pillClass = isPass ? 'pass' : (isStop ? 'stop' : 'fail');
        const rowClass = isPass ? 'record-row' : 'record-row row-fail';
        const runLabel = r.run_num > 1 ? `Run #${{r.run_num}} (R)` : `Run #1`;
        const failPy = r.fail_on_py ? `<span style="color: var(--color-fail-text); font-family: var(--font-mono); font-weight: 600;">${{escapeHtml(r.fail_on_py)}}</span>` : '<span style="color: var(--text-secondary); opacity: 0.45;">-</span>';
        const errCode = isPass ? '<span style="color: var(--text-secondary);">None</span>' : `<span style="color: var(--color-fail-text); font-weight: 700;">${{escapeHtml(r.error_code)}}</span>`;
        const desc = r.error_desc ? escapeHtml(r.error_desc) : `<span style="color: var(--text-secondary);">${{r.pass_items || 0}} / ${{r.total_items || 0}} items passed</span>`;
        const elStr = `${{Number(r.elapsed_sec || 0).toFixed(1)}}s`;

        return `
            <tr class="${{rowClass}}" onclick="openSnapshotModal(${{r.id}})">
                <td class="num-col" style="color: var(--text-secondary); font-size: 12px;">${{reversed.length - idx}}</td>
                <td class="num-col" title="${{escapeHtml(r.test_time)}}">${{escapeHtml(r.test_time)}}</td>
                <td class="num-col" style="font-weight: 700; color: var(--text-primary);" title="${{escapeHtml(r.sn)}}">${{escapeHtml(r.sn)}}</td>
                <td class="num-col" style="color: var(--text-secondary); font-size: 12px;">${{runLabel}}</td>
                <td><span class="pill ${{pillClass}}">${{st}}</span></td>
                <td title="${{escapeHtml(r.fail_on_py || '')}}">${{failPy}}</td>
                <td class="num-col" title="${{escapeHtml(r.error_code || '')}}">${{errCode}}</td>
                <td title="${{escapeHtml(r.error_desc || '')}}">${{desc}}</td>
                <td class="num-col">${{elStr}}</td>
                <td><button class="btn-view" onclick="event.stopPropagation(); openSnapshotModal(${{r.id}})">🔍 Inspect</button></td>
            </tr>
        `;
    }}).join('');
}}

function openSnapshotModal(recordId) {{
    const rec = RAW_RECORDS.find(r => r.id === recordId);
    if (!rec) return;

    const st = (rec.status || 'UNKNOWN').toUpperCase();
    const isPass = st === 'PASS';
    const isStop = st === 'STOP';
    const pill = document.getElementById('modal-status-pill');
    pill.textContent = st;
    pill.className = 'pill ' + (isPass ? 'pass' : (isStop ? 'stop' : 'fail'));

    document.getElementById('modal-sn-title').textContent = rec.sn || 'UNKNOWN';
    document.getElementById('modal-meta-sub').textContent =
        `${{rec.test_time || ''}}  •  Station: ${{rec.station || '-'}}  •  Fixture: ${{rec.fixture_id || '-'}}  •  Elapsed: ${{Number(rec.elapsed_sec || 0).toFixed(1)}}s`;

    const localLink = document.getElementById('modal-local-link');
    if (rec.html_report_path) {{
        localLink.href = rec.html_report_path;
        localLink.style.display = 'inline-block';
    }} else {{
        localLink.style.display = 'none';
    }}

    // Group measurements by consecutive (script, script_run_id) just like standalone HTML report
    const measurements = rec.measurements || [];
    const tbody = document.getElementById('modal-measurements-tbody');

    if (measurements.length === 0) {{
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-secondary); padding: 32px;">No sub-item measurements stored for this record.</td></tr>`;
    }} else {{
        const groups = [];
        measurements.forEach((m, idx) => {{
            const sname = m.script || 'test_item.py';
            const rId = m.script_run_id !== undefined ? m.script_run_id : sname;
            const key = `${{sname}}__${{rId}}`;
            if (!groups.length || groups[groups.length - 1].key !== key) {{
                groups.push({{ key, script: sname, items: [] }});
            }}
            groups[groups.length - 1].items.push({{ idx: idx + 1, m }});
        }});

        const htmlRows = [];
        groups.forEach((grp, gIdx) => {{
            const grpId = `modal-grp-${{gIdx + 1}}`;
            const gItems = grp.items;
            const gTotal = gItems.length;
            let gPass = 0;
            let gFail = 0;
            let hasCrit = false;
            let dur = '';
            let firstErr = 'None';
            let firstDesc = `Click to view ${{gTotal}} ${{gTotal === 1 ? 'item' : 'items'}}`;

            gItems.forEach(({{ m }}) => {{
                const mst = (m.status || '').toUpperCase();
                if (!dur && m.script_duration) dur = m.script_duration;
                if (mst === 'PASS') gPass++;
                else if (mst !== 'NA' && mst !== 'SKIP') {{
                    gFail++;
                    if (mst === 'CRITICAL') hasCrit = true;
                    if (firstErr === 'None' && m.err_code && m.err_code !== 'None') firstErr = m.err_code;
                    if (m.desc && firstDesc.startsWith('Click to view')) firstDesc = m.desc;
                }}
            }});

            const hasFail = gFail > 0;
            const isOpen = hasFail;
            const toggleSym = isOpen ? '−' : '+';
            const grpRowCls = hasFail ? 'script-group-row group-fail' : 'script-group-row';
            const grpPillCls = hasFail ? 'fail' : 'pass';
            const grpStText = hasCrit ? 'CRITICAL' : (hasFail ? 'FAIL' : 'PASS');
            const badgeHtml = hasCrit
                ? `<span class="group-meta fail">CRITICAL / EXCEPTION</span>`
                : (hasFail ? `<span class="group-meta fail">${{gPass}} PASS / ${{gFail}} FAIL</span>` : `<span class="group-meta">${{gPass}} / ${{gTotal}} PASS</span>`);
            const durHtml = dur ? `<span class="duration-tag">${{escapeHtml(dur)}}</span>` : '<span style="color: var(--text-secondary); opacity: 0.45;">-</span>';
            const errHtml = (hasFail && firstErr !== 'None')
                ? `<span style="color: var(--color-fail-text); font-weight: 700;">${{escapeHtml(firstErr)}}</span>`
                : `<span style="color: var(--text-secondary);">${{escapeHtml(firstErr)}}</span>`;

            htmlRows.push(`
                <tr class="${{grpRowCls}}" onclick="toggleModalGroup('${{grpId}}')">
                    <td><span class="toggle-btn" id="btn-${{grpId}}">${{toggleSym}}</span></td>
                    <td title="${{escapeHtml(grp.script)}}"><span class="script-name">${{escapeHtml(grp.script)}}</span></td>
                    <td class="num-col" style="color: var(--text-secondary); opacity: 0.45;">-</td>
                    <td class="num-col">${{badgeHtml}}</td>
                    <td class="num-col" style="color: var(--text-secondary); opacity: 0.45;">-</td>
                    <td><span class="pill ${{grpPillCls}}">${{grpStText}}</span></td>
                    <td style="color: var(--text-secondary); font-size: 13px;" title="${{escapeHtml(firstDesc)}}">${{escapeHtml(firstDesc)}}</td>
                    <td class="num-col">${{errHtml}}</td>
                    <td class="num-col">${{durHtml}}</td>
                </tr>
            `);

            const childDisp = isOpen ? 'table-row' : 'none';
            gItems.forEach(({{ idx, m }}, cPos) => {{
                const mst = (m.status || 'UNKNOWN').toUpperCase();
                const itemPass = mst === 'PASS';
                const branch = (cPos === gTotal - 1) ? '└─' : '├─';
                const valDisp = itemPass ? escapeHtml(m.measured) : `${{escapeHtml(m.measured)}} ❌`;
                const cErr = (!itemPass && m.err_code && m.err_code !== 'None')
                    ? `<span style="color: var(--color-fail-text); font-weight: 700;">${{escapeHtml(m.err_code)}}</span>`
                    : `<span style="color: var(--text-secondary);">${{escapeHtml(m.err_code || 'None')}}</span>`;

                htmlRows.push(`
                    <tr class="child-row ${{grpId}} ${{itemPass ? '' : 'row-fail'}}" style="display: ${{childDisp}}; background-color: #11151c;">
                        <td class="num-col" style="color: var(--text-secondary); font-size: 12px;">${{String(idx).padStart(2, '0')}}</td>
                        <td class="num-col" style="font-weight: 600;" title="${{escapeHtml(m.item)}}"><span class="tree-branch">${{branch}}</span>${{escapeHtml(m.item)}}</td>
                        <td class="num-col" title="${{escapeHtml(m.lsl)}}">${{escapeHtml(m.lsl)}}</td>
                        <td class="num-col" style="${{itemPass ? '' : 'color: var(--color-fail-text); font-weight: 800;'}}" title="${{escapeHtml(m.measured)}}">${{valDisp}}</td>
                        <td class="num-col" title="${{escapeHtml(m.usl)}}">${{escapeHtml(m.usl)}}</td>
                        <td><span class="pill ${{itemPass ? 'pass' : 'fail'}}">${{mst}}</span></td>
                        <td style="color: var(--text-muted);" title="${{escapeHtml(m.desc)}}">${{escapeHtml(m.desc)}}</td>
                        <td class="num-col">${{cErr}}</td>
                        <td class="num-col" style="color: var(--text-secondary); opacity: 0.45;">-</td>
                    </tr>
                `);
            }});
        }});
        tbody.innerHTML = htmlRows.join('');
    }}

    document.getElementById('snapshot-modal').classList.add('open');
}}

function toggleModalGroup(grpId) {{
    const rows = document.querySelectorAll('tr.' + grpId);
    const btn = document.getElementById('btn-' + grpId);
    if (!rows.length) return;
    const isHidden = rows[0].style.display === 'none';
    rows.forEach(r => r.style.display = isHidden ? 'table-row' : 'none');
    if (btn) btn.textContent = isHidden ? '−' : '+';
}}

function closeSnapshotModal() {{
    document.getElementById('snapshot-modal').classList.remove('open');
}}

document.addEventListener('keydown', e => {{
    if (e.key === 'Escape') closeSnapshotModal();
}});

// Initial render
applyFilters();
</script>
</body>
</html>
"""

    out_html_path.write_text(html_content, encoding="utf-8")
    return out_html_path
