# -*- coding: utf-8 -*-
"""
Sapas Local SQLite Storage Engine (Edge-First Station Database).

Stores per-cycle station execution records and structured measurement snapshots
into a single high-performance SQLite database per station/fixture:
    output/sapas_local_{STATION}_{FIXTURE_ID}.db

Key Design Features:
- WAL (Write-Ahead Logging) mode for sub-2ms non-blocking writes.
- Fixed relational columns for fast indexing & aggregation + JSON column for full sub-item snapshots.
- Zero external database server dependencies (100% offline capable).
"""

import json
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _sanitize_token(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", (value or "").strip())
    cleaned = cleaned.strip("_")
    return cleaned.upper() if cleaned else fallback


def resolve_db_filename(station_name: str = "", fixture_id: str = "") -> str:
    """
    Returns the standardized SQLite database filename:
        sapas_local_{STATION}_{FIXTURE_ID}.db
    """
    st_token = _sanitize_token(station_name, "STATION")
    fx_token = _sanitize_token(fixture_id, "NA")
    return f"sapas_local_{st_token}_{fx_token}.db"


def format_iso_test_time(raw_timestamp: str) -> str:
    """
    Converts Sapas timestamp 'YYYYMMDD_HHMMSS' into 'YYYY-MM-DD HH:MM:SS'.
    Falls back to current local time if parsing fails.
    """
    raw = (raw_timestamp or "").strip()
    try:
        dt = datetime.strptime(raw, "%Y%m%d_%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass
    m = re.search(r"(\d{4})(\d{2})(\d{2})[_-]?(\d{2})(\d{2})(\d{2})", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}:{m.group(6)}"
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class LocalDBManager:
    """
    Manages the local SQLite database for a station/fixture.
    """

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS test_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sn TEXT NOT NULL,
                    test_time TEXT NOT NULL,
                    raw_timestamp TEXT NOT NULL,
                    project TEXT,
                    station TEXT,
                    fixture_id TEXT,
                    status TEXT NOT NULL,
                    fail_on_py TEXT,
                    error_code TEXT,
                    error_desc TEXT,
                    elapsed_sec REAL,
                    total_items INTEGER,
                    pass_items INTEGER,
                    failed_items INTEGER,
                    html_report_path TEXT,
                    measurements_json TEXT
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_records_sn ON test_records(sn);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_records_time ON test_records(test_time);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_records_status ON test_records(status);")
            conn.commit()
        finally:
            conn.close()

    def insert_test_record(
        self,
        serial_number: str,
        raw_timestamp: str,
        status: str,
        project_name: str = "",
        station_name: str = "",
        fixture_id: str = "",
        elapsed_sec: float = 0.0,
        first_error_code: str = "",
        first_error_desc: str = "",
        fail_on_py: str = "",
        html_report_relpath: str = "",
        measurements: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[int, float]:
        """
        Inserts a single test cycle record into `test_records`.

        Returns:
            Tuple[int, float]: (inserted_row_id, write_duration_ms)
        """
        t0 = time.perf_counter()
        measurements = measurements or []
        total_items = len(measurements)
        pass_items = sum(1 for m in measurements if str(m.get("status", "")).upper() == "PASS")
        failed_items = sum(
            1 for m in measurements if str(m.get("status", "")).upper() not in ("PASS", "NA", "SKIP")
        )

        raw_status = (status or "UNKNOWN").upper()
        is_stop = raw_status == "STOP"
        is_pass = (raw_status == "PASS") and (failed_items == 0)
        normalized_status = "PASS" if is_pass else ("STOP" if is_stop else "FAIL")

        # Auto-infer fail_on_py / first_error_code / first_error_desc from measurements if not provided
        if not is_pass:
            for m in measurements:
                if str(m.get("status", "")).upper() not in ("PASS", "NA", "SKIP"):
                    if not fail_on_py and m.get("script"):
                        fail_on_py = str(m.get("script")).split()[0]
                    if (not first_error_code or first_error_code.upper() == "PASS") and m.get("err_code"):
                        cand_err = str(m.get("err_code"))
                        if cand_err and cand_err != "None":
                            first_error_code = cand_err
                    if not first_error_desc and m.get("desc"):
                        first_error_desc = str(m.get("desc"))
                    break

        if is_pass:
            final_err_code = "PASS"
            final_err_desc = ""
            final_fail_py = ""
        else:
            final_err_code = (
                first_error_code
                if (first_error_code and first_error_code.upper() != "PASS")
                else (raw_status if raw_status != "PASS" else "FAIL")
            )
            final_err_desc = first_error_desc or ""
            final_fail_py = fail_on_py or ""

        iso_time = format_iso_test_time(raw_timestamp)
        measurements_payload = json.dumps(measurements, ensure_ascii=False)

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO test_records (
                    sn, test_time, raw_timestamp, project, station, fixture_id,
                    status, fail_on_py, error_code, error_desc, elapsed_sec,
                    total_items, pass_items, failed_items, html_report_path, measurements_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    serial_number or "UNKNOWN",
                    iso_time,
                    raw_timestamp or "",
                    project_name or "",
                    station_name or "",
                    str(fixture_id or "N/A"),
                    normalized_status,
                    final_fail_py,
                    final_err_code,
                    final_err_desc,
                    round(float(elapsed_sec or 0.0), 2),
                    total_items,
                    pass_items,
                    failed_items,
                    html_report_relpath or "",
                    measurements_payload,
                ),
            )
            row_id = cur.lastrowid or 0
            conn.commit()
        finally:
            conn.close()

        duration_ms = (time.perf_counter() - t0) * 1000.0
        return row_id, duration_ms

    @staticmethod
    def fetch_all_records(db_path: Path | str) -> List[Dict[str, Any]]:
        """
        Reads all test records from the specified SQLite `.db` file.
        Supports both Sapas `test_records` schema and legacy `result_log` schema.
        """
        path_obj = Path(db_path).resolve()
        if not path_obj.is_file():
            raise FileNotFoundError(f"Database file not found: {path_obj}")

        conn = sqlite3.connect(str(path_obj), timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            tables = [
                r[0]
                for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            ]

            if "test_records" in tables:
                rows = cur.execute(
                    "SELECT * FROM test_records ORDER BY test_time ASC, id ASC"
                ).fetchall()
                results: List[Dict[str, Any]] = []
                for r in rows:
                    d = dict(r)
                    raw_json = d.get("measurements_json")
                    try:
                        d["measurements"] = json.loads(raw_json) if raw_json else []
                    except Exception:
                        d["measurements"] = []
                    d.pop("measurements_json", None)
                    results.append(d)
                return results

            # Fallback support if someone opens a legacy xSIG `result_log` database
            if "result_log" in tables:
                rows = cur.execute("SELECT * FROM result_log ORDER BY id ASC").fetchall()
                results = []
                for idx, r in enumerate(rows, 1):
                    d = dict(r)
                    raw_res = str(d.get("Result") or "UNKNOWN").upper()
                    status = "PASS" if raw_res == "PASS" else ("STOP" if raw_res == "STOP" else "FAIL")
                    err_code = "PASS" if status == "PASS" else raw_res
                    el_raw = str(d.get("Elapsed Time") or "0").replace("s", "").strip()
                    try:
                        el_sec = float(el_raw)
                    except ValueError:
                        el_sec = 0.0
                    details_raw = d.get("details_json")
                    measurements = []
                    if details_raw:
                        try:
                            det_dict = json.loads(details_raw)
                            if isinstance(det_dict, dict):
                                for k, v in det_dict.items():
                                    measurements.append({
                                        "script": str(d.get("FailOnPy") or "test_item.py"),
                                        "item": str(k),
                                        "lsl": "-",
                                        "measured": str(v),
                                        "usl": "-",
                                        "status": "PASS",
                                        "desc": "",
                                        "err_code": "None",
                                    })
                        except Exception:
                            pass
                    t_str = str(d.get("testing_started_at") or "")
                    results.append({
                        "id": d.get("id", idx),
                        "sn": str(d.get("SN") or "UNKNOWN"),
                        "test_time": format_iso_test_time(t_str) if "_" in t_str else (t_str or ""),
                        "raw_timestamp": t_str,
                        "project": "",
                        "station": "",
                        "fixture_id": str(d.get("FIXTURE_ID") or "N/A"),
                        "status": status,
                        "fail_on_py": str(d.get("FailOnPy") or ""),
                        "error_code": err_code,
                        "error_desc": str(d.get("errorSubDescription") or ""),
                        "elapsed_sec": el_sec,
                        "total_items": len(measurements),
                        "pass_items": len(measurements) if status == "PASS" else max(0, len(measurements) - 1),
                        "failed_items": 0 if status == "PASS" else 1,
                        "html_report_path": "",
                        "measurements": measurements,
                    })
                return results

            raise ValueError(
                f"Unrecognized database schema in '{path_obj.name}'. Expected table 'test_records'."
            )
        finally:
            conn.close()
