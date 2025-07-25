# export_utils.py
import csv
import os
from tkinter import filedialog, messagebox
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import db_handler
import config

def export_to_csv(status_callback):
    """Exports all component data to a CSV file, reporting via status_callback."""
    path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV Files", "*.csv")],
        title="Save CSV As"
    )
    if not path:
        return

    # Sütun başlıkları (config'den okunup 'id' ve 'image_path' dışlanabilir)
    headers = [config.COLUMN_TITLES[c] for c in config.COLUMNS if c not in ("id","image_path")]

    try:
        rows = db_handler.get_all_components()
        if rows is None:
            raise RuntimeError("Database returned no data.")

        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            # Her row bir tuple; yine 'id' ve 'image_path' indekslerini atlayarak yazıyoruz
            for row in rows:
                writer.writerow([row[i] for i, c in enumerate(config.COLUMNS) if c not in ("id","image_path")])

        status_callback(f"Export CSV ✓ ({os.path.basename(path)})")
        messagebox.showinfo("Export CSV", f"Successfully exported to:\n{path}")
    except Exception as e:
        status_callback("Export CSV ✗")
        messagebox.showerror("Export CSV Failed", str(e))


def export_to_pdf(status_callback):
    """Exports all component data to a PDF file, reporting via status_callback."""
    path = filedialog.asksaveasfilename(
        defaultextension=".pdf",
        filetypes=[("PDF Files", "*.pdf")],
        title="Save PDF As"
    )
    if not path:
        return

    try:
        rows = db_handler.get_all_components()
        if rows is None:
            raise RuntimeError("Database returned no data.")

        doc = SimpleDocTemplate(path, pagesize=landscape(letter))
        styles = getSampleStyleSheet()
        elements = [Paragraph("Component Library Export", styles['Title'])]

        # Tablo veri hazırlığı
        headers = [config.COLUMN_TITLES[c] for c in config.COLUMNS if c not in ("id","image_path")]
        data = [headers]
        for row in rows:
            data.append([str(row[i]) for i, c in enumerate(config.COLUMNS) if c not in ("id","image_path")])

        # Tablo oluştur ve stil uygula
        table = Table(data, repeatRows=1)
        style = TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.darkblue),
            ("TEXTCOLOR",  (0,0), (-1,0), colors.whitesmoke),
            ("ALIGN",      (0,0), (-1,-1), "CENTER"),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,0), 12),
            ("BOTTOMPADDING", (0,0), (-1,0), 8),
            ("GRID",       (0,0), (-1,-1), 0.5, colors.grey),
        ])
        table.setStyle(style)
        elements.append(table)

        doc.build(elements)

        status_callback(f"Export PDF ✓ ({os.path.basename(path)})")
        messagebox.showinfo("Export PDF", f"Successfully exported to:\n{path}")
    except Exception as e:
        status_callback("Export PDF ✗")
        messagebox.showerror("Export PDF Failed", str(e))
