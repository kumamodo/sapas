# -*- coding: utf-8 -*-
"""
Sapas Standalone HTML Test Report Generator.

Generates self-contained, single-file HTML reports for hardware test cycles.
Features:
- 100% offline (no external CDN, fonts, or JS dependencies).
- Distinct PASS / FAIL / STOP visual identity.
- Hardware-focused measurement comparison table with highlighted failing items.
- Fixture ID and Retest tracking.
- Collapsible raw console log section.
"""

import html
from pathlib import Path
from typing import Any, Dict, List, Optional


def generate_html_report(
    output_dir: Path | str,
    serial_number: str,
    timestamp: str,
    status: str,
    project_name: str = "",
    station_name: str = "",
    fixture_id: str = "",
    elapsed_time_str: str = "",
    first_error_code: str = "",
    first_error_desc: str = "",
    measurements: Optional[List[Dict[str, Any]]] = None,
    raw_console_log: str = "",
    custom_run_count: Optional[int] = None,
) -> Path:
    """
    Renders and saves a self-contained HTML test report.

    Filename format: {SN}_{timestamp}_{status}.html
    Destination: output_dir / {SN}_{timestamp}_{status}.html

    Returns:
        Path: The absolute path of the generated HTML report file.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    measurements = measurements or []
    total_items = len(measurements)
    pass_count = sum(1 for m in measurements if str(m.get("status", "")).upper() == "PASS")
    fail_count = sum(1 for m in measurements if str(m.get("status", "")).upper() not in ("PASS", "NA", "SKIP"))

    raw_status_upper = (status or "UNKNOWN").upper()
    is_stop = raw_status_upper == "STOP"
    is_pass = (raw_status_upper == "PASS") and (fail_count == 0)
    status_upper = "PASS" if is_pass else ("STOP" if is_stop else "FAIL")
    theme_class = "pass" if is_pass else ("stop" if is_stop else "fail")

    # Detect Retest run count by scanning existing reports for this SN
    if custom_run_count is not None:
        run_count = custom_run_count
    else:
        existing_reports = list(output_path.glob(f"{serial_number}_*.html"))
        run_count = len(existing_reports) + 1

    run_label = f"Run #{run_count}" if run_count == 1 else f"Run #{run_count} (Retest)"

    if not is_pass and (not first_error_code or first_error_code.upper() == "PASS"):
        for m in measurements:
            if str(m.get("status", "")).upper() not in ("PASS", "NA", "SKIP"):
                cand_err = str(m.get("err_code", ""))
                if cand_err and cand_err != "None":
                    first_error_code = cand_err
                if not first_error_desc and m.get("desc"):
                    first_error_desc = str(m.get("desc", ""))
                break

    if is_pass and fail_count == 0 and (not first_error_code or first_error_code.upper() == "PASS"):
        display_err_code = "None"
    else:
        display_err_code = (
            first_error_code
            if (first_error_code and first_error_code.upper() != "PASS")
            else (raw_status_upper if raw_status_upper != "PASS" else "FAIL")
        )

    # Group measurements consecutively by (script, script_run_id)
    table_rows_html = []
    if measurements:
        groups: List[Dict[str, Any]] = []
        global_idx = 0
        for m in measurements:
            global_idx += 1
            script_name = str(m.get("script") or "test_item.py")
            run_id = m.get("script_run_id")
            group_key = (script_name, run_id)
            if not groups or groups[-1]["key"] != group_key:
                groups.append({
                    "key": group_key,
                    "script": script_name,
                    "items": [],
                })
            groups[-1]["items"].append((global_idx, m))

        for g_idx, grp in enumerate(groups, 1):
            grp_id = f"script-grp-{g_idx}"
            safe_script = html.escape(grp["script"])
            g_items = grp["items"]
            g_total = len(g_items)
            g_pass = sum(1 for _, m in g_items if str(m.get("status", "")).upper() == "PASS")
            g_fail = sum(1 for _, m in g_items if str(m.get("status", "")).upper() not in ("PASS", "NA", "SKIP"))
            has_group_fail = g_fail > 0
            has_critical = any(str(m.get("status", "")).upper() == "CRITICAL" for _, m in g_items)

            # Extract per-script execution duration if recorded
            raw_dur = ""
            for _, m in g_items:
                if m.get("script_duration"):
                    raw_dur = str(m.get("script_duration"))
                    break
            safe_dur = html.escape(raw_dur) if raw_dur else "-"
            dur_cell_html = f'<span class="duration-tag">{safe_dur}</span>' if raw_dur else '<span style="color: var(--text-secondary); opacity: 0.45;">-</span>'

            # Auto-expand if the script group has any FAIL item; collapse by default if all PASS
            is_open = has_group_fail
            toggle_symbol = "−" if is_open else "+"
            grp_row_class = "script-group-row group-fail" if has_group_fail else "script-group-row"
            grp_pill_class = "fail" if has_group_fail else "pass"
            grp_status_text = "CRITICAL" if has_critical else ("FAIL" if has_group_fail else "PASS")

            if has_critical:
                count_badge = '<span class="group-meta fail">CRITICAL / EXCEPTION</span>'
            elif has_group_fail:
                count_badge = f'<span class="group-meta fail">{g_pass} PASS / {g_fail} FAIL</span>'
            else:
                count_badge = f'<span class="group-meta">{g_pass} / {g_total} PASS</span>'

            # Find first error code & description in this group if failed
            grp_err = "None"
            grp_desc = f"Click to view {g_total} {'item' if g_total == 1 else 'items'}"
            if has_group_fail:
                for _, m in g_items:
                    if str(m.get("status", "")).upper() not in ("PASS", "NA", "SKIP"):
                        raw_err = str(m.get("err_code", "None"))
                        if raw_err and raw_err != "None":
                            grp_err = html.escape(raw_err)
                        raw_desc = str(m.get("desc", ""))
                        if raw_desc:
                            grp_desc = html.escape(raw_desc)
                        break

            grp_err_display = (
                f'<span class="highlight-fail">{grp_err}</span>'
                if has_group_fail and grp_err != "None"
                else f'<span style="color: var(--text-secondary);">{grp_err}</span>'
            )

            table_rows_html.append(f"""
                <tr class="{grp_row_class}" onclick="toggleScriptGroup('{grp_id}')">
                    <td><span class="toggle-btn" id="btn-{grp_id}">{toggle_symbol}</span></td>
                    <td title="{safe_script}"><span class="script-name">{safe_script}</span></td>
                    <td class="num-col" style="color: var(--text-secondary); opacity: 0.45;">-</td>
                    <td class="num-col">{count_badge}</td>
                    <td class="num-col" style="color: var(--text-secondary); opacity: 0.45;">-</td>
                    <td><span class="pill {grp_pill_class}">{grp_status_text}</span></td>
                    <td style="color: var(--text-secondary); font-size: 13px;" title="{grp_desc}">{grp_desc}</td>
                    <td class="num-col" title="{grp_err}">{grp_err_display}</td>
                    <td class="num-col" title="{safe_dur}">{dur_cell_html}</td>
                </tr>
            """)

            child_display = "table-row" if is_open else "none"
            for c_pos, (idx, m) in enumerate(g_items):
                item_name = html.escape(str(m.get("item", "--")))
                lsl = html.escape(str(m.get("lsl", "--")))
                usl = html.escape(str(m.get("usl", "--")))
                val = html.escape(str(m.get("measured", "--")))
                m_status = html.escape(str(m.get("status", "--"))).upper()
                desc = html.escape(str(m.get("desc", "--")))
                err = html.escape(str(m.get("err_code", "--")))

                is_item_pass = m_status == "PASS"
                row_class = f"child-row {grp_id}" + ("" if is_item_pass else " row-fail")
                pill_class = "pass" if is_item_pass else "fail"
                measured_class = "num-col" if is_item_pass else "num-col item-measured"
                val_display = val if is_item_pass else f"{val} ❌"
                err_display = (
                    f'<span class="highlight-fail">{err}</span>'
                    if not is_item_pass and err != "None"
                    else f'<span style="color: var(--text-secondary);">{err}</span>'
                )
                branch_char = "└─" if c_pos == g_total - 1 else "├─"

                table_rows_html.append(f"""
                    <tr class="{row_class}" style="display: {child_display};">
                        <td style="color: var(--text-secondary); font-family: var(--font-mono); font-size: 12px;">{idx:02d}</td>
                        <td class="item-name child-item-cell" title="{item_name}"><span class="tree-branch">{branch_char}</span>{item_name}</td>
                        <td class="num-col" title="{lsl}">{lsl}</td>
                        <td class="{measured_class}" title="{val}">{val_display}</td>
                        <td class="num-col" title="{usl}">{usl}</td>
                        <td><span class="pill {pill_class}">{m_status}</span></td>
                        <td style="color: var(--text-muted);" title="{desc}">{desc}</td>
                        <td class="num-col" title="{err}">{err_display}</td>
                        <td class="num-col" style="color: var(--text-secondary); opacity: 0.45;">-</td>
                    </tr>
                """)
    else:
        table_rows_html.append("""
            <tr>
                <td colspan="9" style="text-align: center; color: var(--text-secondary); padding: 32px 16px;">
                    No structured criteria measurements registered for this test cycle.
                </td>
            </tr>
        """)

    # Build Log Content HTML
    escaped_log = html.escape(raw_console_log or "No console logs recorded.")

    # Safe HTML attributes
    safe_sn = html.escape(serial_number or "UNKNOWN")
    safe_station = html.escape(station_name or "UnknownStation")
    safe_fixture = html.escape(fixture_id or "N/A")
    safe_project = html.escape(project_name or "General")
    safe_elapsed = html.escape(elapsed_time_str or "--")
    safe_timestamp = html.escape(timestamp or "--")
    safe_err_desc = html.escape(first_error_desc or "")

    summary_status_text = f"{pass_count} PASS / {fail_count} FAIL" if measurements else status_upper

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>[{status_upper}] {safe_sn} - Station: {safe_station} | Sapas Report</title>
    <style>
        :root {{
            --bg-page: #0d1117;
            --bg-card: #161b22;
            --bg-card-subtle: #21262d;
            --border-color: #30363d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --text-muted: #c9d1d9;
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

        /* Top Result Banner */
        .banner {{
            border-radius: 12px;
            padding: 24px 32px;
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}

        .banner.fail {{
            background: linear-gradient(135deg, rgba(218, 54, 51, 0.25) 0%, rgba(218, 54, 51, 0.08) 100%);
            border: 1px solid var(--color-fail-border);
            box-shadow: 0 4px 20px rgba(218, 54, 51, 0.2);
        }}

        .banner.pass {{
            background: linear-gradient(135deg, rgba(35, 134, 54, 0.25) 0%, rgba(35, 134, 54, 0.08) 100%);
            border: 1px solid var(--color-pass-text);
            box-shadow: 0 4px 20px rgba(35, 134, 54, 0.2);
        }}

        .banner.stop {{
            background: linear-gradient(135deg, rgba(210, 153, 34, 0.25) 0%, rgba(210, 153, 34, 0.08) 100%);
            border: 1px solid var(--color-stop-text);
            box-shadow: 0 4px 20px rgba(210, 153, 34, 0.2);
        }}

        .banner-left {{
            display: flex;
            align-items: center;
            gap: 20px;
        }}

        .badge-status {{
            font-size: 32px;
            font-weight: 800;
            padding: 6px 20px;
            border-radius: 8px;
            letter-spacing: 1px;
        }}

        .banner.fail .badge-status {{
            background-color: var(--color-fail);
            color: #ffffff;
        }}

        .banner.pass .badge-status {{
            background-color: var(--color-pass);
            color: #ffffff;
        }}

        .banner.stop .badge-status {{
            background-color: var(--color-stop);
            color: #ffffff;
        }}

        .banner-title h1 {{
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 4px;
            font-family: var(--font-mono);
        }}

        .banner-title p {{
            color: var(--text-secondary);
            font-size: 14px;
        }}

        .banner-right {{
            text-align: right;
        }}

        .elapsed-box {{
            font-size: 28px;
            font-weight: 700;
            font-family: var(--font-mono);
            color: var(--text-primary);
        }}

        .elapsed-label {{
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        /* Summary Cards Grid */
        .grid-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}

        .card {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 16px 20px;
        }}

        .card-label {{
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-bottom: 6px;
            letter-spacing: 0.5px;
        }}

        .card-value {{
            font-size: 18px;
            font-weight: 600;
            color: var(--text-primary);
        }}

        .card-value.highlight-fail {{
            color: var(--color-fail-text);
            font-family: var(--font-mono);
        }}

        /* Measurements Table */
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}

        .section-title {{
            font-size: 18px;
            font-weight: 600;
        }}

        .table-container {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 24px;
        }}

        table {{
            width: 100%;
            table-layout: fixed;
            border-collapse: collapse;
            text-align: left;
            font-size: 14px;
        }}

        th {{
            background-color: var(--bg-card-subtle);
            color: var(--text-secondary);
            font-weight: 600;
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        td {{
            padding: 13px 16px;
            border-bottom: 1px solid var(--border-color);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        th:first-child,
        td:first-child {{
            text-align: center;
            padding-left: 8px;
            padding-right: 8px;
            text-overflow: clip;
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        .item-name {{
            font-family: var(--font-mono);
            font-weight: 600;
            color: var(--text-primary);
        }}

        .num-col {{
            font-family: var(--font-mono);
        }}

        /* Status Pills */
        .pill {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-align: center;
        }}

        .pill.pass {{
            background-color: var(--color-pass-bg);
            color: var(--color-pass-text);
            border: 1px solid rgba(63, 185, 80, 0.3);
        }}

        .pill.fail {{
            background-color: var(--color-fail-bg);
            color: var(--color-fail-text);
            border: 1px solid var(--color-fail-border);
        }}

        /* Highlighting failed rows */
        tr.row-fail {{
            background-color: rgba(218, 54, 51, 0.14);
        }}

        tr.row-fail td {{
            border-color: rgba(218, 54, 51, 0.3);
        }}

        tr.row-fail .item-measured {{
            color: var(--color-fail-text);
            font-weight: 800;
            font-size: 15px;
        }}

        /* Collapsible Script Group Rows */
        tr.script-group-row {{
            background-color: rgba(255, 255, 255, 0.025);
            cursor: pointer;
            user-select: none;
            transition: background-color 0.15s ease;
        }}

        tr.script-group-row:hover {{
            background-color: rgba(255, 255, 255, 0.06);
        }}

        tr.script-group-row.group-fail {{
            background-color: rgba(218, 54, 51, 0.09);
        }}

        tr.script-group-row.group-fail:hover {{
            background-color: rgba(218, 54, 51, 0.15);
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
            line-height: 1;
        }}

        tr.script-group-row.group-fail .toggle-btn {{
            border-color: var(--color-fail-border);
            color: var(--color-fail-text);
            background-color: rgba(218, 54, 51, 0.15);
        }}

        .script-name {{
            font-family: var(--font-mono);
            font-weight: 700;
            font-size: 14.5px;
            color: #58a6ff;
            margin-right: 10px;
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
            margin-right: 8px;
        }}

        tr.child-row {{
            background-color: #11151c;
        }}

        .child-item-cell {{
            padding-left: 12px;
        }}

        .tree-branch {{
            color: var(--text-secondary);
            opacity: 0.55;
            margin-right: 8px;
            font-weight: 400;
        }}

        /* Collapsible Log Section */
        details.log-accordion {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 24px;
        }}

        details.log-accordion summary {{
            padding: 14px 20px;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
            display: flex;
            align-items: center;
            gap: 10px;
            background-color: var(--bg-card-subtle);
            color: var(--text-primary);
            transition: background 0.15s ease;
        }}

        details.log-accordion summary:hover {{
            background-color: #282e37;
        }}

        pre.terminal-log {{
            background-color: #05070a;
            color: #d1d5db;
            font-family: var(--font-mono);
            font-size: 13px;
            line-height: 1.6;
            padding: 20px;
            overflow-x: auto;
            max-height: 520px;
            border-top: 1px solid var(--border-color);
        }}

        /* Footer */
        .footer {{
            text-align: center;
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 32px;
            padding-bottom: 16px;
        }}
    </style>
</head>
<body>

<div class="container">
    <!-- Top Result Banner -->
    <div class="banner {theme_class}">
        <div class="banner-left">
            <div class="badge-status">{status_upper}</div>
            <div class="banner-title">
                <h1>{safe_sn}</h1>
                <p>Station: <strong>{safe_station}</strong> &nbsp;•&nbsp; Fixture: <strong>{safe_fixture}</strong> &nbsp;•&nbsp; Project: <strong>{safe_project}</strong> &nbsp;•&nbsp; {run_label}</p>
            </div>
        </div>
        <div class="banner-right">
            <div class="elapsed-box">{safe_elapsed}</div>
            <div class="elapsed-label">Total Elapsed Time</div>
        </div>
    </div>

    <!-- Summary Cards -->
    <div class="grid-cards">
        <div class="card">
            <div class="card-label">Test Timestamp</div>
            <div class="card-value" style="font-size: 15px; font-family: var(--font-mono);">{safe_timestamp}</div>
        </div>
        <div class="card">
            <div class="card-label">Fixture ID / Station</div>
            <div class="card-value" style="font-family: var(--font-mono);">{safe_fixture} <span style="font-size: 13px; color: var(--text-secondary);">({safe_station})</span></div>
        </div>
        <div class="card">
            <div class="card-label">Result Summary</div>
            <div class="card-value">
                <span>{summary_status_text}</span>
            </div>
        </div>
        <div class="card">
            <div class="card-label">First Error Code</div>
            <div class="card-value {'highlight-fail' if not is_pass and display_err_code != 'None' else ''}">{display_err_code}</div>
            {f'<div style="font-size: 12px; color: var(--color-fail-text); margin-top: 4px;">{safe_err_desc}</div>' if safe_err_desc else ''}
        </div>
    </div>

    <!-- Test Criteria Table -->
    <div class="section-header">
        <div class="section-title">📊 Measurement Results ({total_items} Items)</div>
    </div>

    <div class="table-container">
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
            <tbody>
                {''.join(table_rows_html)}
            </tbody>
        </table>
    </div>

    <!-- Collapsible Raw Terminal Output -->
    <details class="log-accordion">
        <summary>
            <span>📄 Raw Console Log</span>
            <span style="font-size: 12px; color: var(--text-secondary); margin-left: auto;">Click to expand / collapse</span>
        </summary>
        <pre class="terminal-log">{escaped_log}</pre>
    </details>

    <div class="footer">
        Generated by <strong>Sapas Hardware Automation Platform</strong> &nbsp;•&nbsp; Standalone Diagnostic Report
    </div>
</div>

<script>
function toggleScriptGroup(grpId) {{
    var rows = document.querySelectorAll('tr.' + grpId);
    var btn = document.getElementById('btn-' + grpId);
    if (!rows.length) return;
    var isHidden = rows[0].style.display === 'none';
    for (var i = 0; i < rows.length; i++) {{
        rows[i].style.display = isHidden ? 'table-row' : 'none';
    }}
    if (btn) {{
        btn.textContent = isHidden ? '−' : '+';
    }}
}}
</script>
</body>
</html>
"""

    report_filename = f"{serial_number}_{timestamp}_{status_upper}.html"
    report_file_path = output_path / report_filename
    report_file_path.write_text(html_content, encoding="utf-8")
    return report_file_path
