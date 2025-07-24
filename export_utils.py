# export_utils.py
import csv
from tkinter import filedialog, messagebox
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import db_handler

def export_to_csv():
    """Exports all component data to a CSV file."""
    file_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")]
    )
    if not file_path:
        return

    components = db_handler.get_all_components()
    if components is None:
        messagebox.showerror("Error", "Could not fetch data from the database.")
        return

    headers = ["ID", "Name", "Category", "Drawer Code", "Quantity", "Datasheet", "Description", "Added Date", "Image Path"]

    try:
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(headers)
            writer.writerows(components)
        messagebox.showinfo("Success", f"Data successfully exported to:\n{file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export to CSV.\nError: {e}")

def export_to_pdf():
    """Exports all component data to a PDF file."""
    file_path = filedialog.asksaveasfilename(
        defaultextension=".pdf",
        filetypes=[("PDF files", "*.pdf")]
    )
    if not file_path:
        return

    try:
        doc = SimpleDocTemplate(file_path, pagesize=landscape(letter))
        elements = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph("Component Library List", styles['h1']))

        headers = ["ID", "Name", "Category", "Drawer", "Qty", "Datasheet", "Description", "Date", "Image"]
        components_data = db_handler.get_all_components()
        if components_data is None:
             messagebox.showerror("Error", "Could not fetch data for PDF export.")
             return

        data = [headers]
        for comp in components_data:
            row = [Paragraph(str(item) if item is not None else "", styles['Normal']) for item in comp]
            data.append(row)

        table = Table(data, colWidths=[30, 100, 70, 70, 30, 100, 140, 60, 80])
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ])
        table.setStyle(style)
        elements.append(table)

        doc.build(elements)
        messagebox.showinfo("Success", f"Data successfully exported to PDF:\n{file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export to PDF.\nError: {e}")