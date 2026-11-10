import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plate_track.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicle_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plate_number TEXT NOT NULL,
        in_time TEXT NOT NULL,
        out_time TEXT,
        stay_seconds INTEGER DEFAULT 0,
        confidence REAL DEFAULT 0.0,
        plate_crop_path TEXT,
        vehicle_image_path TEXT,
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT DEFAULT (datetime('now', 'localtime'))
    );
    """)
    conn.commit()
    conn.close()

def format_stay_time(seconds: int) -> str:
    if seconds is None or seconds < 0:
        return "0h 0m 0s"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    rem_seconds = seconds % 60
    return f"{hours}h {minutes}m {rem_seconds}s"

def parse_time(timestr: str) -> datetime:
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(timestr, fmt)
        except ValueError:
            pass
    return datetime.fromisoformat(timestr)

def get_open_record(plate_number: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM vehicle_logs
        WHERE plate_number = ? AND (out_time IS NULL OR out_time = '' OR out_time = 'Inside')
        ORDER BY id DESC LIMIT 1
    """, (plate_number.strip().upper(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_last_record(plate_number: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM vehicle_logs
        WHERE plate_number = ?
        ORDER BY id DESC LIMIT 1
    """, (plate_number.strip().upper(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def record_detection(
    plate_number: str,
    mode: str = "AUTO",
    confidence: float = 0.0,
    crop_path: Optional[str] = None,
    image_path: Optional[str] = None
) -> Dict[str, Any]:
    plate_number = plate_number.strip().upper()
    mode = (mode or "AUTO").upper()
    now_dt = datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    open_rec = get_open_record(plate_number)

    if open_rec is not None:
        in_dt = parse_time(open_rec["in_time"])
        delta_sec = (now_dt - in_dt).total_seconds()

        # 10s debounce check
        if delta_sec < 10.0:
            return {
                "status": "debounced",
                "action": "ignored",
                "message": f"Detection ignored: within {int(delta_sec)}s (<10s) debounce window for {plate_number}.",
                "record": open_rec
            }

        if mode == "ENTRY":
            return {
                "status": "already_inside",
                "action": "none",
                "message": f"Vehicle {plate_number} is already recorded as inside since {open_rec['in_time']}.",
                "record": open_rec
            }

        # EXIT or AUTO -> mark vehicle as exited
        stay_seconds = max(0, int(delta_sec))
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE vehicle_logs
            SET out_time = ?, stay_seconds = ?, updated_at = ?,
                confidence = CASE WHEN ? > confidence THEN ? ELSE confidence END
            WHERE id = ?
        """, (now_str, stay_seconds, now_str, confidence, confidence, open_rec["id"]))
        conn.commit()

        cursor.execute("SELECT * FROM vehicle_logs WHERE id = ?", (open_rec["id"],))
        updated_row = dict(cursor.fetchone())
        conn.close()

        updated_row["stay_time_formatted"] = format_stay_time(stay_seconds)
        return {
            "status": "exit",
            "action": "exited",
            "message": f"Exit recorded for {plate_number}. Stay duration: {format_stay_time(stay_seconds)}.",
            "record": updated_row
        }

    else:
        # Check debounce for recently closed record
        last_rec = get_last_record(plate_number)
        if last_rec is not None and last_rec.get("out_time") and last_rec["out_time"] != "Inside":
            try:
                out_dt = parse_time(last_rec["out_time"])
                delta_out = (now_dt - out_dt).total_seconds()
                if delta_out < 10.0:
                    return {
                        "status": "debounced",
                        "action": "ignored",
                        "message": f"Detection ignored: {plate_number} exited {int(delta_out)}s ago (<10s debounce).",
                        "record": last_rec
                    }
            except Exception:
                pass

        if mode == "EXIT":
            return {
                "status": "not_inside",
                "action": "none",
                "message": f"Vehicle {plate_number} cannot exit because no active entry record was found.",
                "record": None
            }

        # ENTRY or AUTO -> create new record
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO vehicle_logs (plate_number, in_time, out_time, stay_seconds, confidence, plate_crop_path, vehicle_image_path)
            VALUES (?, ?, NULL, 0, ?, ?, ?)
        """, (plate_number, now_str, confidence, crop_path, image_path))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.execute("SELECT * FROM vehicle_logs WHERE id = ?", (new_id,))
        new_row = dict(cursor.fetchone())
        conn.close()

        new_row["stay_time_formatted"] = "0h 0m 0s"
        return {
            "status": "entry",
            "action": "entered",
            "message": f"Entry recorded for vehicle {plate_number} at {now_str}.",
            "record": new_row
        }

def get_logs(
    search: str = "",
    date_filter: str = "",
    sort_by: str = "id",
    sort_order: str = "desc",
    page: int = 1,
    per_page: int = 10
) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()

    conditions = []
    params = []

    if search.strip():
        conditions.append("plate_number LIKE ?")
        params.append(f"%{search.strip().upper()}%")

    if date_filter.strip():
        conditions.append("date(in_time) = date(?)")
        params.append(date_filter.strip())

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Valid sort columns
    allowed_sort_cols = {
        "id": "id",
        "plate_number": "plate_number",
        "in_time": "in_time",
        "out_time": "out_time",
        "stay_seconds": "stay_seconds",
        "confidence": "confidence"
    }
    sort_col = allowed_sort_cols.get(sort_by, "id")
    sort_dir = "ASC" if str(sort_order).lower() == "asc" else "DESC"

    # Count total
    cursor.execute(f"SELECT COUNT(*) FROM vehicle_logs {where_clause}", params)
    total_count = cursor.fetchone()[0]

    # Pagination
    limit = max(1, per_page)
    offset = max(0, (page - 1) * limit)

    query = f"""
        SELECT * FROM vehicle_logs
        {where_clause}
        ORDER BY {sort_col} {sort_dir}
        LIMIT ? OFFSET ?
    """
    cursor.execute(query, params + [limit, offset])
    rows = cursor.fetchall()
    conn.close()

    now_dt = datetime.now()
    results = []
    for r in rows:
        row_dict = dict(r)
        is_inside = not row_dict["out_time"] or row_dict["out_time"] == "Inside"
        if is_inside:
            in_dt = parse_time(row_dict["in_time"])
            live_stay_sec = max(0, int((now_dt - in_dt).total_seconds()))
            row_dict["out_time"] = "Inside"
            row_dict["current_stay_seconds"] = live_stay_sec
            row_dict["stay_time_formatted"] = format_stay_time(live_stay_sec)
        else:
            row_dict["current_stay_seconds"] = row_dict["stay_seconds"]
            row_dict["stay_time_formatted"] = format_stay_time(row_dict["stay_seconds"])
        results.append(row_dict)

    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1

    return {
        "logs": results,
        "total": total_count,
        "page": page,
        "per_page": limit,
        "total_pages": total_pages
    }

def get_summary_stats() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()

    today_str = datetime.now().strftime("%Y-%m-%d")

    # Total vehicles today (unique plates or total records today)
    cursor.execute("""
        SELECT COUNT(*), COUNT(DISTINCT plate_number)
        FROM vehicle_logs
        WHERE date(in_time) = date('now', 'localtime')
    """)
    row = cursor.fetchone()
    total_today = row[0] if row else 0
    unique_plates_today = row[1] if row else 0

    # Currently inside
    cursor.execute("""
        SELECT COUNT(*)
        FROM vehicle_logs
        WHERE out_time IS NULL OR out_time = '' OR out_time = 'Inside'
    """)
    row = cursor.fetchone()
    currently_inside = row[0] if row else 0

    # Average stay time for closed records
    cursor.execute("""
        SELECT AVG(stay_seconds), MAX(stay_seconds)
        FROM vehicle_logs
        WHERE out_time IS NOT NULL AND out_time != '' AND out_time != 'Inside'
    """)
    row = cursor.fetchone()
    avg_stay_seconds = int(row[0]) if (row and row[0] is not None) else 0
    longest_stay_seconds = int(row[1]) if (row and row[1] is not None) else 0

    conn.close()

    return {
        "total_today": total_today,
        "unique_plates_today": unique_plates_today,
        "currently_inside": currently_inside,
        "avg_stay_seconds": avg_stay_seconds,
        "avg_stay_formatted": format_stay_time(avg_stay_seconds),
        "longest_stay_seconds": longest_stay_seconds,
        "longest_stay_formatted": format_stay_time(longest_stay_seconds)
    }

def get_hourly_traffic() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT strftime('%H:00', in_time) as hr, COUNT(*) as cnt
        FROM vehicle_logs
        WHERE date(in_time) = date('now', 'localtime')
        GROUP BY hr
        ORDER BY hr ASC
    """)
    entry_counts = {row["hr"]: row["cnt"] for row in cursor.fetchall()}

    cursor.execute("""
        SELECT strftime('%H:00', out_time) as hr, COUNT(*) as cnt
        FROM vehicle_logs
        WHERE date(out_time) = date('now', 'localtime') AND out_time IS NOT NULL AND out_time != '' AND out_time != 'Inside'
        GROUP BY hr
        ORDER BY hr ASC
    """)
    exit_counts = {row["hr"]: row["cnt"] for row in cursor.fetchall()}
    conn.close()

    hours = [f"{h:02d}:00" for h in range(8, 23, 2)]
    return {
        "hours": hours,
        "entries": [entry_counts.get(h, 0) for h in hours],
        "exits": [exit_counts.get(h, 0) for h in hours]
    }

def delete_log(log_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vehicle_logs WHERE id = ?", (log_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def clear_all_logs() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vehicle_logs")
    deleted_count = cursor.rowcount
    cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'vehicle_logs'")
    conn.commit()
    conn.close()
    return deleted_count
