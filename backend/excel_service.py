import os
from io import BytesIO
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from database import get_connection, format_stay_time, parse_time

def generate_excel_bytes() -> tuple[bytes, str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, plate_number, in_time, out_time, stay_seconds
        FROM vehicle_logs
        ORDER BY id ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Vehicle Logs"

    # Columns requested: S.No, Plate Number, In Time, Out Time, Stay Time
    headers = ["S.No", "Plate Number", "In Time", "Out Time", "Stay Time"]
    ws.append(headers)

    # Styles
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid") # Slate-800
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border
    ws.row_dimensions[1].height = 26

    # Data rows
    row_font = Font(name="Calibri", size=10)
    data_align = Alignment(horizontal="center", vertical="center")
    now_dt = datetime.now()

    for idx, row in enumerate(rows, start=1):
        r_dict = dict(row)
        out_val = r_dict["out_time"]
        if not out_val or out_val == "Inside":
            out_display = "Inside"
            in_dt = parse_time(r_dict["in_time"])
            stay_sec = max(0, int((now_dt - in_dt).total_seconds()))
        else:
            out_display = out_val
            stay_sec = r_dict["stay_seconds"]

        stay_display = format_stay_time(stay_sec)

        row_data = [
            idx,
            r_dict["plate_number"],
            r_dict["in_time"],
            out_display,
            stay_display
        ]
        ws.append(row_data)
        row_num = idx + 1
        ws.row_dimensions[row_num].height = 20

        # Alternate row fill
        fill_color = "F8FAFC" if idx % 2 == 0 else "FFFFFF"
        row_fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_num, column=col_idx)
            cell.font = row_font
            cell.alignment = data_align
            cell.border = thin_border
            cell.fill = row_fill

    # Auto-fit column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 5, 14)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"PlateTrack_{now_dt.strftime('%Y-%m-%d')}.xlsx"
    return output.getvalue(), filename
