"""
Component Library Tracker — main_app.py (revizyonlu + QR)
Tarih: 2025-08-08

Bu sürüm:
- QR etiketi üretimi (eklerken sorar, context menüden de üret/print)
- Duplicate akışı düzeltilmiş (önce kontrol → merge → yoksa ekle)
- ensure_config_defaults(): QR ayarları COLUMNS dışında
- Inline edit güvenli commit, tema duyarlı grafik, güvenli path/URL açma vb.
"""
from __future__ import annotations

# --- Standart kütüphaneler
import os
import sys
import csv
import datetime as dt
import logging
import platform
import subprocess
import json
import io
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# --- UI ve görseller
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import matplotlib
matplotlib.use("Agg")  # TkAgg embed öncesi figür üretiminde güvenlik için
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from PIL import Image, ImageTk, ImageDraw, ImageFont


# --- 3. parti
import sv_ttk

# QR backend (tercihen segno, yoksa qrcode)
try:
    import segno
    _QR_LIB = 'segno'
except Exception:
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_Q
        _QR_LIB = 'qrcode'
    except Exception:
        _QR_LIB = None

# --- Windows koyu başlık (opsiyonel)
try:
    import ctypes
    from ctypes import wintypes
except Exception:  # platform dışı
    ctypes = None
    wintypes = None

# --- Yerel modüller
import config
import db_handler
import export_utils
from db_handler import execute_query


# ================================================================
# Yardımcılar ve başlangıç
# ================================================================

LOG = logging.getLogger("component_tracker")
if not LOG.handlers:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def ensure_config_defaults() -> None:
    """config.* içinde eksik sabitleri güvenli varsayılanlarla doldur."""
    defaults = {
        "COLUMNS": [
            "id",
            "name",
            "category",
            "drawer_code",
            "quantity",
            "datasheet",
            "image_path",
            "added_date",
        ],
        "COLUMN_TITLES": {
            "id": "ID",
            "name": "Name",
            "category": "Category",
            "drawer_code": "Drawer Code",
            "quantity": "Qty",
            "datasheet": "Datasheet",
            "image_path": "Image",
            "added_date": "Added",
        },
        "COLUMN_WIDTHS": {
            "id": 60,
            "name": 200,
            "category": 140,
            "drawer_code": 120,
            "quantity": 80,
            "datasheet": 180,
            "image_path": 160,
            "added_date": 120,
        },
        "FORM_LABELS": {
            "name": "Component Name",
            "category": "Category",
            "drawer_code": "Drawer Code",
            "quantity": "Quantity",
            "datasheet": "Datasheet (URL/File)",
            "image_path": "Image Path",
            "added_date": "Added Date (YYYY-MM-DD)",
        },
        "LOW_STOCK_THRESHOLD": 2,
        "IMAGE_PREVIEW_SIZE": (360, 240),

        # --- QR ayarları (COLUMNS DIŞINDA!)
        "QR_DEFAULT_SCALE": 4,                         # Termal yazıcılar için ideal başlangıç
        "QR_BORDER": 2,
        "QR_FILENAME_FORMAT": "QR_{drawer_code}_{name}_{id}.png",

        "QR_PAYLOAD_STYLE": "pretty",  # "pretty" ya da "json"
        "QR_PRETTY_TEMPLATE": (
        "{name}  |  {drawer_code}\n"
        "Qty: {quantity}    ID: {id}\n"
        "Cat: {category}\n"
        "Added: {added_date}\n"
        "ComponentTracker"
),

    }
    for k, v in defaults.items():
        if not hasattr(config, k):
            setattr(config, k, v)
            LOG.warning("config.%s bulunamadı, varsayılan atandı.", k)


def _safe_filename(name: str) -> str:
    name = name or ""
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
    return s or "label"


def _build_qr_payload(comp: Dict[str, Any]) -> str:
    """QR içine gömeceğimiz veri: 'pretty' metin ya da JSON."""
    style = getattr(config, "QR_PAYLOAD_STYLE", "pretty")
    if style == "pretty":
        tpl = getattr(config, "QR_PRETTY_TEMPLATE", "{name} | {drawer_code}")
        # Boş değerleri engelle
        ctx = {
            "id": comp.get("id") or "",
            "name": comp.get("name") or "",
            "category": comp.get("category") or "",
            "drawer_code": comp.get("drawer_code") or "",
            "quantity": comp.get("quantity") or "",
            "datasheet": comp.get("datasheet") or "",
            "added_date": comp.get("added_date") or "",
        }
        return tpl.format(**ctx)
    else:
        payload = {
            "id": comp.get("id"),
            "name": comp.get("name"),
            "category": comp.get("category"),
            "drawer_code": comp.get("drawer_code"),
            "quantity": comp.get("quantity"),
            "datasheet": comp.get("datasheet"),
            "added_date": comp.get("added_date"),
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
            "app": "ComponentTracker",
            "v": 1,
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))



def _render_qr_image(payload: str, scale: Optional[int] = None, border: Optional[int] = None) -> Image.Image:
    """QR’ı PIL.Image olarak döndürür. segno varsa onu; yoksa qrcode kullanır."""
    if _QR_LIB is None:
        raise RuntimeError("QR kütüphanesi yok. 'pip install segno' veya 'pip install qrcode[pil]' kur.")
    if scale is None:
        scale = getattr(config, "QR_DEFAULT_SCALE", 4)
    if border is None:
        border = getattr(config, "QR_BORDER", 2)

    if _QR_LIB == "segno":
        q = segno.make(payload, error="q")  # ~%25 hata düzeltme
        buf = io.BytesIO()
        q.save(buf, kind="png", scale=scale, border=border, light="white", dark="black")
        buf.seek(0)
        im = Image.open(buf)
        return im.convert("RGB")
    else:
        # qrcode
        qr = qrcode.QRCode(
            version=None,  # otomatik
            error_correction=ERROR_CORRECT_Q,
            box_size=scale,
            border=border,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        return img.convert("RGB")

def _qr_with_label(qr_img: Image.Image, label_text: str, font_size: Optional[int] = None, padding: int = 12) -> Image.Image:
    """
    QR görselinin altına beyaz zemin üzerinde ortalanmış bir etiket (drawer_code) ekler.
    Büyük punto için font boyutu QR genişliğine göre otomatik seçilir.
    """
    label_text = (label_text or "").strip()
    if not label_text:
        return qr_img

    W, H = qr_img.size
    if font_size is None:
        # Büyük punto: QR genişliğinin ~%14'ü. Çok küçük olmasın diye taban 18.
        font_size = max(18, int(W * 0.14))

    # Font seçimi: Windows'ta Arial, değilse DejaVu; olmazsa default
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    # Yazı boyutunu ölç
    tmp_draw = ImageDraw.Draw(qr_img)
    try:
        bbox = tmp_draw.textbbox((0, 0), label_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except Exception:
        text_w, text_h = tmp_draw.textsize(label_text, font=font)

    # Yeni görüntü: üstte QR, altta etiket
    total_h = H + padding + text_h + padding // 2
    out = Image.new("RGB", (W, total_h), "white")
    out.paste(qr_img, (0, 0))

    draw = ImageDraw.Draw(out)
    x = max(0, (W - text_w) // 2)
    y = H + (padding // 2)
    # İnce stroke daha okunaklı yapar
    try:
        draw.text((x, y), label_text, font=font, fill="black", stroke_width=1, stroke_fill="black")
    except TypeError:
        # Eski PIL sürümleri için stroke yoksa düz yaz
        draw.text((x, y), label_text, font=font, fill="black")

    return out


# --- Platform API

def enable_windows_dark_titlebar(window: tk.Tk) -> None:
    """Uyumlu Windows sürümlerinde başlık çubuğunu koyu moda alır."""
    if sys.platform != "win32" or ctypes is None:
        return
    try:
        hwnd = window.winfo_id()
        for attr in (20, 19):  # Win11 -> Win10 fallback
            try:
                use_dark = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    wintypes.HWND(hwnd), wintypes.DWORD(attr),
                    ctypes.byref(use_dark), ctypes.sizeof(use_dark)
                )
            except Exception:
                continue
        LOG.debug("Dark title bar denendi.")
    except Exception as e:
        LOG.debug("Dark title bar başarısız: %s", e)


def _is_url(s: str) -> bool:
    return s.lower().startswith(("http://", "https://"))


def open_path_or_url(path_str: str) -> Tuple[bool, Optional[str]]:
    """HTTP(S) ise tarayıcıda, dosya ise sistem varsayılanı ile aç."""
    if not path_str:
        return False, "Empty path"
    try:
        if _is_url(path_str):
            import webbrowser
            webbrowser.open(path_str)
            return True, None
        p = Path(path_str).expanduser()
        if not p.exists():
            return False, f"Not found: {p}"
        system = platform.system()
        if system == "Windows":
            os.startfile(p)  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.run(["open", str(p)], check=False)
        else:
            subprocess.run(["xdg-open", str(p)], check=False)
        return True, None
    except Exception as e:
        return False, str(e)


def open_containing_folder(path_str: str) -> Tuple[bool, Optional[str]]:
    """Verilen yolun bulunduğu klasörü açar ve (mümkünse) dosyayı seçer. URL ise URL'yi açar."""
    try:
        if not path_str:
            return False, "Empty path"
        if _is_url(path_str):
            return open_path_or_url(path_str)
        p = Path(path_str).expanduser()
        if not p.exists():
            return False, f"Not found: {p}"
        system = platform.system()
        if system == "Windows":
            subprocess.run(["explorer", f"/select,{str(p)}"], check=False)
        elif system == "Darwin":
            subprocess.run(["open", "-R", str(p)], check=False)
        else:
            subprocess.run(["xdg-open", str(p.parent)], check=False)
        return True, None
    except Exception as e:
        return False, str(e)


# ================================================================
# Uygulama
# ================================================================

class ComponentTrackerApp:
    """Bileşen kütüphanesi yöneticisi (Tkinter)."""

    READONLY_COLUMNS = {"id"}
    NON_INLINE_EDITABLE = {"id", "image_path", "datasheet"}

    def __init__(self, root: tk.Tk):
        ensure_config_defaults()

        # Grafik penceresi/Mpl objeleri
        self.chart_win: Optional[tk.Toplevel] = None
        self.chart_fig = None
        self.chart_ax = None
        self.chart_canvas: Optional[FigureCanvasTkAgg] = None

        self.root = root
        self.root.title("Component Library Tracker")

        # Seçim / görsel
        self.selected_item_data: Optional[Dict[str, Any]] = None
        self.photo_image: Optional[ImageTk.PhotoImage] = None  # GC için referans

        # Çeşitli durumlar
        self._search_after_id: Optional[str] = None  # debounce timer id
        self._inline_editor: Optional[tk.Entry] = None
        self._edit_ctx: Optional[Tuple[str, str]] = None  # (row_id, col_name)
        self._last_sort: Optional[Tuple[str, bool]] = None  # (col, reverse)

        # Ayarları yükle Uİ kurulumundan önce (tema vs.)
        self._load_and_apply_settings()

        # UI
        self._create_widgets()
        self._bind_events()

        # Başlangıç verisi
        self.refresh_treeview()

        # Tema
        self.on_theme_change()

    # ------------- Ayarlar -------------

    def _load_and_apply_settings(self) -> None:
        settings = config.load_settings()
        w, h = settings.get("window_size", (1300, 750))
        self.root.geometry(f"{w}x{h}")
        self.theme_var = tk.StringVar(value=settings.get("theme", "dark"))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------- Kirli Form Tespiti -------------

    def is_form_dirty(self) -> bool:
        if self.selected_item_data:
            for key, entry in self.entries.items():
                old = str(self.selected_item_data.get(key) or "").strip()
                new = entry.get().strip()
                if new != old:
                    return True
            return False
        for entry in self.entries.values():
            if entry.get().strip():
                return True
        return False


        # ---------- Export yardımcıları ----------

    def export_selected_rows(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Export Selected", "No rows selected.")
            return
        save_path = filedialog.asksaveasfilename(
            title="Export selected to CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")]
        )
        if not save_path:
            return
        try:
            with open(save_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(config.COLUMNS)
                for iid in sel:
                    values = self.tree.item(iid, "values")
                    writer.writerow(values)
            self.update_status(f"Exported {len(sel)} row(s) → {save_path}")
        except Exception as e:
            messagebox.showerror("Export Selected", f"Failed: {e}")


    # ------------- UI Kurulumu -------------

    def _create_widgets(self) -> None:
        top_frame, main_pane, bottom_container, button_frame, self.status_bar = self._setup_layout()
        self._create_top_bar(top_frame)
        tree_frame = self._create_tree_view(main_pane)
        self._create_bottom_pane(bottom_container)
        self._create_action_buttons(button_frame)
        main_pane.add(tree_frame, weight=3)
        main_pane.add(bottom_container, weight=1)

    def _setup_layout(self):
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill="x")

        main_pane = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_pane.pack(fill="both", expand=True, padx=10, pady=5)

        bottom_container = ttk.Frame(main_pane)

        button_frame = ttk.Frame(self.root, padding="10")
        button_frame.pack(fill="x")

        self.status_text = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_text, relief=tk.SUNKEN, anchor="w", padding=5)
        status_bar.pack(side="bottom", fill="x")
        return top_frame, main_pane, bottom_container, button_frame, status_bar

    def _create_top_bar(self, parent_frame) -> None:
        ttk.Label(parent_frame, text="🔎 Search:", font=("Arial", 10)).pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)  # debounce
        self.search_entry = ttk.Entry(parent_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side="left", padx=5)

        ttk.Label(parent_frame, text="Category:", font=("Arial", 10)).pack(side="left", padx=(15, 5))
        self.category_filter_var = tk.StringVar(value="All")
        self.category_filter = ttk.Combobox(parent_frame, textvariable=self.category_filter_var, state="readonly")
        self.category_filter.pack(side="left", padx=5)
        self.category_filter.bind("<<ComboboxSelected>>", lambda *_: self.filter_and_search())

        ttk.Label(parent_frame, text="Theme:", font=("Arial", 10)).pack(side="left", padx=(15, 5))
        theme_combo = ttk.Combobox(parent_frame, textvariable=self.theme_var, values=["light", "dark"], state="readonly", width=6)
        theme_combo.pack(side="left", padx=5)
        theme_combo.bind("<<ComboboxSelected>>", self.on_theme_change)

        ttk.Button(parent_frame, text="Reset Filters", command=self._reset_filters).pack(side="left", padx=(15, 0))

    def _create_tree_view(self, parent_pane) -> ttk.Frame:
        tree_frame = ttk.Frame(parent_pane, padding=(0, 0, 0, 5))
        self.tree = ttk.Treeview(tree_frame, columns=config.COLUMNS, show='headings')

        for col in config.COLUMNS:
            if col == "image_path":
                # Kolonu gizliyorsak başlık vermeyelim
                continue
            self.tree.heading(col, text=config.COLUMN_TITLES.get(col, col), command=lambda c=col: self.sort_treeview_column(c, False))
            self.tree.column(col, width=config.COLUMN_WIDTHS.get(col, 100), anchor="w")

        # Gizlenecek kolonlar
        self.tree.column("id", width=0, stretch=tk.NO)
        self.tree.column("image_path", width=0, stretch=tk.NO)

        # Düşük stok etiketi
        self.tree.tag_configure("low_stock", foreground="tomato")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return tree_frame

    def _create_bottom_pane(self, parent_container) -> None:
        form_frame = ttk.LabelFrame(parent_container, text="Component Details", padding="10")
        form_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        image_frame = ttk.LabelFrame(parent_container, text="Image Preview", padding="10")
        image_frame.pack(side="right", fill="both", expand=True, ipadx=10, ipady=10)
        image_frame.columnconfigure(0, weight=1)
        image_frame.rowconfigure(0, weight=1)

        self.image_label = ttk.Label(image_frame, text="No Image", anchor="center")
        self.image_label.grid(row=0, column=0, sticky="nsew")

        # Form alanları
        self.entries: Dict[str, ttk.Entry] = {}
        for i, (key, text) in enumerate(config.FORM_LABELS.items()):
            ttk.Label(form_frame, text=text).grid(row=i, column=0, padx=5, pady=4, sticky="w")
            entry_frame = ttk.Frame(form_frame)
            entry_frame.grid(row=i, column=1, sticky="ew", padx=5, pady=4)

            if key in ["datasheet", "image_path"]:
                entry = ttk.Entry(entry_frame)
                entry.pack(side="left", fill="x", expand=True)
                ttk.Button(entry_frame, text="...", width=3, command=lambda k=key: self.browse_file(k)).pack(side="right")
                if key == "image_path":
                    ttk.Button(entry_frame, text="🗁", width=3, command=self._open_image_folder).pack(side="right", padx=(5, 2))
                    ttk.Button(entry_frame, text="🖼", width=3, command=self._open_image_file).pack(side="right", padx=(5, 2))
            elif key == "quantity":
                entry = ttk.Entry(entry_frame, width=10)
                entry.pack(side="left")
                qty_button_frame = ttk.Frame(entry_frame)
                qty_button_frame.pack(side="left", padx=(5, 0))
                ttk.Button(qty_button_frame, text="+", width=2, command=lambda: self.adjust_quantity(1)).pack(side="left")
                ttk.Button(qty_button_frame, text="-", width=2, command=lambda: self.adjust_quantity(-1)).pack(side="left")
            else:
                entry = ttk.Entry(entry_frame)
                entry.pack(side="left", fill="x", expand=True)

            self.entries[key] = entry

        form_frame.grid_columnconfigure(1, weight=1)

    def _create_action_buttons(self, parent_frame) -> None:
        style = ttk.Style()
        style.configure("Success.TButton", foreground="white", background="#4CAF50")
        style.configure("Danger.TButton", foreground="white", background="#f44336")
        style.configure("Info.TButton", foreground="white", background="#2196F3")

        ttk.Button(parent_frame, text="➕ Add", command=self.add_component, style="Success.TButton").pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(parent_frame, text="💾 Update", command=self.update_component, style="Info.TButton").pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(parent_frame, text="🗑️ Delete", command=self.delete_selected, style="Danger.TButton").pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(parent_frame, text="🧹 Clear Form", command=self.clear_form_and_selection).pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(parent_frame, text="📥 Import CSV", command=self.import_csv).pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(parent_frame, text="📤 Export CSV", command=lambda: export_utils.export_to_csv(self.update_status)).pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(parent_frame, text="📄 Export PDF", command=lambda: export_utils.export_to_pdf(self.update_status)).pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(parent_frame, text="📊 Category Chart", command=self.show_category_chart).pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(parent_frame, text="🧾 QR Preview", command=self.qr_preview_selected)\
            .pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(parent_frame, text="📤 Export Selected", command=self.export_selected_rows).pack(side="left", expand=True, fill="x", padx=5)

    # ------------- Event Bindings -------------

    def _bind_events(self) -> None:
        # Tree
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        self.tree.bind("<Double-1>", self.on_cell_double_click)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.tree.bind("<Button-3>", self.show_context_menu)

        # Kısayollar
        self.root.bind("<Control-n>", lambda e: self.clear_form_and_selection())
        self.root.bind("<Control-s>", lambda e: self.update_component())
        self.root.bind("<Delete>", lambda e: self.delete_selected())
        self.root.bind("<Control-f>", lambda e: self._focus_search())
        self.root.bind("<F5>", lambda e: self.refresh_treeview())
        self.root.bind("<Control-e>", lambda e: self.export_selected_rows())
        self.root.bind("<Return>", self._maybe_commit_inline_edit)
        self.root.bind("<Escape>", self._cancel_inline_edit)
        self.root.bind("<Control-p>", lambda e: self.print_qr_for_selected())

        # Context menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="✏️ Edit", command=self.edit_via_context)
        self.context_menu.add_command(label="🗑️ Delete", command=self.delete_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📄 Open Datasheet", command=self.open_datasheet)
        self.context_menu.add_command(label="🖼 Open Image", command=self._open_image_file)
        self.context_menu.add_command(label="🗁 Open Containing Folder", command=self._open_any_folder)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📋 Copy Drawer Code", command=self._copy_drawer_code)
        # --- QR menüleri
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🧾 Generate QR…", command=self.generate_qr_for_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🧾 Generate QR (Preview)", command=self.qr_preview_selected)
        self.context_menu.add_command(label="🖨️ Print QR", command=self.print_qr_for_selected)

        if sys.platform == "win32":
            self.context_menu.add_command(label="🖨️ Print QR (Windows)", command=self.print_qr_for_selected)

    # ------------- Çekirdek Mantık -------------

    def on_close(self) -> None:
        # Çıkmadan önce form kirli ise kullanıcıya sor
        if self.is_form_dirty():
            if messagebox.askyesno("Save Changes?", "You have unsaved changes. Save before exit?"):
                if self.selected_item_data:
                    if not self.update_component():
                        return  # kaydedemediysek kapatma
                else:
                    if not self.add_component():
                        return

        self.update_status("Saving settings…")
        settings = config.load_settings()
        settings["window_size"] = (self.root.winfo_width(), self.root.winfo_height())
        settings["column_widths"] = {col: self.tree.column(col, option="width") for col in config.COLUMNS}
        if self._last_sort:
            settings["last_sort"] = {"col": self._last_sort[0], "reverse": self._last_sort[1]}
        settings["theme"] = self.theme_var.get()
        config.save_settings(settings)

        # Grafik penceresi açıksa düzgün kapat
        if self.chart_win and self.chart_win.winfo_exists():
            self._close_chart()

        self.root.destroy()

    def on_theme_change(self, event: Optional[tk.Event] = None) -> None:
        new_theme = self.theme_var.get()
        sv_ttk.set_theme(new_theme)
        enable_windows_dark_titlebar(self.root)
        settings = config.load_settings()
        settings["theme"] = new_theme
        config.save_settings(settings)
        self.update_status(f"Theme set to '{new_theme}'")
        # Tema değişirse grafik renklerini de güncelle
        if self.chart_win and self.chart_win.winfo_exists():
            self._update_chart()

    # ---------- Veri Yükleme / Arama ----------

    def refresh_treeview(self, data: Optional[Sequence[Sequence[Any]]] = None) -> None:
        current_selection_id = self.get_selected_id()
        self.tree.delete(*self.tree.get_children())

        if data is None:
            data = db_handler.get_all_components()

        total_qty = 0
        for comp in data:
            values = comp  # tuple/list, config.COLUMNS sırasıyla
            iid = comp[0]
            tags: Tuple[str, ...] = tuple()
            try:
                q_idx = config.COLUMNS.index("quantity") if "quantity" in config.COLUMNS else None
                if q_idx is not None:
                    q_val = int(values[q_idx] or 0)
                    total_qty += q_val
                    if q_val <= getattr(config, "LOW_STOCK_THRESHOLD", 0):
                        tags = ("low_stock",)
            except Exception:
                pass
            self.tree.insert('', 'end', values=values, iid=iid, tags=tags)

        self.update_category_filter()

        if current_selection_id and self.tree.exists(current_selection_id):
            self.tree.selection_set(current_selection_id)
            self.tree.focus(current_selection_id)
            self.tree.see(current_selection_id)

        self.update_status(f"Displayed {len(data)} components | Total qty: {total_qty}")
        self.apply_column_widths()

        if not self._last_sort:
            settings = config.load_settings()
            ls = settings.get("last_sort")
            if ls:
                self.sort_treeview_column(ls.get("col"), ls.get("reverse", False))

        if self.chart_win and self.chart_win.winfo_exists():
            self._update_chart()

    # ---------- CRUD ----------

    def add_component(self) -> bool:
        data = self.get_form_data()
        if data is None:
            return False

        # Önce duplicate kontrolü
        if self._component_exists(data["name"], data["drawer_code"]):
            if messagebox.askyesno("Duplicate Found", "This component already exists.\nIncrease its quantity instead?"):
                self._merge_quantity(data)
                self.refresh_treeview()
                self.clear_form_and_selection()
                return True
            return False

        # Ekle
        if db_handler.add_component(data):
            self.update_status(f"Component '{data['name']}' added successfully.")
            # Yeni kaydı bulalım (id için)
            try:
                new_comp = self._get_latest_component_by_name_drawer(data['name'], data['drawer_code'])
            except Exception:
                new_comp = None

            self.refresh_treeview()
            self.clear_form_and_selection()

            # Kullanıcıya sor: QR üretelim mi? -> GUI önizleme
            if new_comp and messagebox.askyesno("QR Code", "Generate QR code label for this component now?"):
                self._show_qr_dialog(new_comp)

            return True

        messagebox.showerror("Database Error", "Failed to add the component.")
        return False


    def update_component(self) -> bool:
        if not self.selected_item_data:
            messagebox.showwarning("No Selection", "Please select a component to update.")
            return False
        comp_id = self.selected_item_data['id']
        data = self.get_form_data()
        if data is None:
            return False

        if self._component_exists(data["name"], data["drawer_code"], exclude_id=comp_id):
            if messagebox.askyesno("Duplicate Found", "Another record with same name & drawer code exists. Merge quantities?"):
                self._merge_quantity(data)
                # Basit yaklaşım: mevcut satırı sil
                db_handler.delete_component(comp_id)
                self.refresh_treeview()
                self.clear_form_and_selection()
                return True
            return False

        if db_handler.update_component(comp_id, data):
            self.update_status(f"Component '{data['name']}' updated successfully.")
            self.refresh_treeview()
            return True
        else:
            messagebox.showerror("Database Error", "Failed to update the component.")
            return False

    def delete_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select component(s) to delete.")
            return

        names: List[str] = []
        ids: List[Any] = []
        for iid in sel:
            values = self.tree.item(iid, "values")
            row = dict(zip(config.COLUMNS, values))
            names.append(row.get("name", str(iid)))
            ids.append(row.get("id", iid))

        if not messagebox.askyesno("Confirm Deletion", f"Delete {len(ids)} component(s)?\n\n" + "\n".join(names[:6]) + ("\n…" if len(names) > 6 else "")):
            return

        fail = 0
        for comp_id in ids:
            try:
                if not db_handler.delete_component(comp_id):
                    fail += 1
            except Exception as e:
                LOG.error("Silme hatası (%s): %s", comp_id, e)
                fail += 1
        if fail:
            messagebox.showerror("Database Error", f"Failed to delete {fail} item(s).")
        else:
            self.update_status(f"Deleted {len(ids)} component(s).")
        self.refresh_treeview()
        self.clear_form_and_selection()

    # ---------- UI Etkileşimleri ----------

    def on_row_select(self, event: Optional[tk.Event] = None) -> None:
        sel = self.tree.selection()
        if not sel:
            self.selected_item_data = None
            return
        item_id = sel[0]
        values = self.tree.item(item_id, "values")
        self.selected_item_data = dict(zip(config.COLUMNS, values))

        self.clear_form_entries()
        for key, entry_widget in self.entries.items():
            if key in self.selected_item_data:
                entry_widget.insert(0, self.selected_item_data[key] or "")

        self.update_status(f"Selected: {self.selected_item_data.get('name','')}")
        self.update_image_preview(self.selected_item_data.get('image_path'))

    def on_tree_click(self, event: tk.Event) -> None:
        region = self.tree.identify_region(event.x, event.y)
        if region == "nothing":
            if self.is_form_dirty():
                kaydet = messagebox.askyesno("Save Changes?", "You have unsaved changes. Save now?")
                if kaydet:
                    if self.selected_item_data:
                        success = self.update_component()
                    else:
                        success = self.add_component()
                    if not success:
                        return
            self.clear_form_and_selection()

    def show_context_menu(self, event: tk.Event) -> None:
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.on_row_select()
            self.context_menu.post(event.x_root, event.y_root)

    def edit_via_context(self) -> None:
        if not self.selected_item_data:
            return
        self.update_status(f"Context: editing '{self.selected_item_data['name']}' — use form or double-click a cell")

    def on_cell_double_click(self, event: tk.Event) -> None:
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)  # "#1", "#2", …
        if not row_id or not col_id:
            return

        # Seçimi garanti et ve formu doldur
        self.tree.selection_set(row_id)
        self.on_row_select()

        col_index = int(col_id.replace("#", "")) - 1
        col_name = config.COLUMNS[col_index]

        # Özel davranışlar
        if col_name == "drawer_code":
            code = self.tree.set(row_id, "drawer_code")
            popup = tk.Toplevel(self.root)
            popup.title("Drawer Code")
            popup.geometry("400x200")
            txt = tk.Text(popup, font=("Consolas", 24), wrap="none")
            txt.insert("1.0", code)
            txt.config(state="disabled")
            txt.pack(expand=True, fill="both", padx=10, pady=10)
            return
        if col_name == "datasheet":
            self.open_datasheet()
            return
        if col_name == "image_path":
            self._open_image_file()
            return
        if col_name in self.NON_INLINE_EDITABLE:
            return

        # Hücre üzerinde inline editör aç
        bbox = self.tree.bbox(row_id, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        value = self.tree.set(row_id, col_name)

        # Var olan editör varsa kapat
        self._cancel_inline_edit()

        self._inline_editor = tk.Entry(self.tree)
        self._inline_editor.insert(0, value)
        self._inline_editor.place(x=x, y=y, width=w, height=h)
        self._inline_editor.focus_set()
        self._inline_editor.bind("<FocusOut>", self._maybe_commit_inline_edit)
        self._edit_ctx = (row_id, col_name)  # güvenli bağlam

    # ---------- Inline edit yardımcıları ----------

    def _maybe_commit_inline_edit(self, event: Optional[tk.Event] = None) -> None:
        if not (self._inline_editor and self._inline_editor.winfo_exists() and self._edit_ctx):
            return
        editor = self._inline_editor
        row_id, col_name = self._edit_ctx
        new_val = editor.get()

        # Temizlik
        self._inline_editor = None
        self._edit_ctx = None
        editor.destroy()

        # Formda değerini güncelle
        if col_name in self.entries:
            self.entries[col_name].delete(0, tk.END)
            self.entries[col_name].insert(0, new_val)
        # Güncelle
        self.update_component()

    def _cancel_inline_edit(self, event: Optional[tk.Event] = None) -> None:
        if self._inline_editor and self._inline_editor.winfo_exists():
            self._inline_editor.destroy()
        self._inline_editor = None
        self._edit_ctx = None

    # ---------- Yardımcılar ----------

    def open_datasheet(self, event: Optional[tk.Event] = None) -> None:
        if not self.selected_item_data:
            return
        link = self.selected_item_data.get('datasheet', '')
        if not link:
            messagebox.showinfo("No Datasheet", "No datasheet provided for this component.")
            return
        ok, err = open_path_or_url(link)
        if not ok:
            messagebox.showerror("Error", f"Could not open the datasheet.\nError: {err}")

    def import_csv(self) -> None:
        file_path = filedialog.askopenfilename(title="Select CSV File", filetypes=[("CSV Files", "*.csv"), ("Text Files", "*.txt"), ("All Files", "*.*")])
        if not file_path:
            return
        try:
            with open(file_path, newline='', encoding='utf-8-sig') as csvfile:
                try:
                    sample = csvfile.read(2048)
                    csvfile.seek(0)
                    dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
                except csv.Error:
                    dialect = 'excel'
                    csvfile.seek(0)

                reader = csv.DictReader(csvfile, dialect=dialect)
                if not reader.fieldnames:
                    messagebox.showerror("Import Failed", "CSV has no header row.")
                    return
                reader.fieldnames = [h.strip().lower().replace(' ', '_') for h in reader.fieldnames]

                count_new = 0
                count_skipped = 0
                count_merged = 0

                for row in reader:
                    if not all(k in row for k in ("name", "drawer_code", "quantity")):
                        count_skipped += 1
                        continue
                    data = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
                    try:
                        data["quantity"] = int(data.get("quantity") or 0)
                    except (ValueError, TypeError):
                        data["quantity"] = 0
                    if not data.get("added_date"):
                        data["added_date"] = dt.date.today().isoformat()

                    if self._component_exists(data["name"], data["drawer_code"]):
                        self._merge_quantity(data)
                        count_merged += 1
                        continue

                    if db_handler.add_component(data):
                        count_new += 1
                    else:
                        count_skipped += 1

                messagebox.showinfo("Import Complete", f"{count_new} new component(s) imported.\n{count_merged} duplicate(s) merged.\n{count_skipped} skipped.")
                self.refresh_treeview()
        except Exception as e:
            messagebox.showerror("Import Failed", f"An error occurred:\n{e}")

    def get_form_data(self) -> Optional[Dict[str, Any]]:
        data: Dict[str, Any] = {key: entry.get().strip() for key, entry in self.entries.items()}
        if not data.get("name") or not data.get("drawer_code"):
            messagebox.showwarning("Missing Information", "Component Name and Drawer Code are required.")
            return None
        # Quantity
        try:
            data["quantity"] = int(data.get("quantity") or 0)
        except ValueError:
            messagebox.showerror("Invalid Input", "Quantity must be a valid number.")
            return None
        # Date
        if not data.get("added_date"):
            data["added_date"] = dt.date.today().isoformat()
        else:
            try:
                # ISO tarih bekliyoruz
                dt.date.fromisoformat(data["added_date"])  # doğrulama
            except Exception:
                messagebox.showerror("Invalid Date", "Added Date must be in YYYY-MM-DD format.")
                return None
        # Datasheet alanı URL ya da mevcut dosya olabilir; zorunlu değil
        ds = data.get("datasheet")
        if ds and (not _is_url(ds)):
            p = Path(ds).expanduser()
            if not p.exists():
                if not messagebox.askyesno("Invalid Datasheet", "Datasheet path does not exist. Keep anyway?"):
                    data["datasheet"] = ""
        return data

    def adjust_quantity(self, amount: int) -> None:
        try:
            current = int(self.entries["quantity"].get() or 0)
            new_val = max(0, current + amount)
        except ValueError:
            new_val = max(0, amount)
        self.entries["quantity"].delete(0, tk.END)
        self.entries["quantity"].insert(0, str(new_val))
        if self.selected_item_data:
            self.update_component()
            if self.chart_win and self.chart_win.winfo_exists():
                self._update_chart()

    def clear_form_and_selection(self) -> None:
        self.clear_form_entries()
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
        self.selected_item_data = None
        self.update_image_preview(None)
        self.update_status("Form cleared. Ready to add a new component.")

    def clear_form_entries(self) -> None:
        for entry in self.entries.values():
            entry.delete(0, tk.END)

    def filter_and_search(self) -> None:
        search_term = (self.search_var.get() or "").lower()
        category = self.category_filter_var.get()
        category_arg = None if category in ("All", "", None) else category
        filtered_data = db_handler.search_components(search_term, category_arg)
        self.refresh_treeview(data=filtered_data)

    def _parse_for_sort(self, val: Any) -> Any:
        s = "" if val is None else str(val)
        # Sayı
        try:
            if "." in s:
                return float(s)
            return int(s)
        except Exception:
            pass
        # ISO tarih
        try:
            return dt.datetime.fromisoformat(s)
        except Exception:
            pass
        return s.lower()

    def sort_treeview_column(self, col: str, reverse: bool) -> None:
        data = [(self.tree.set(child, col), child) for child in self.tree.get_children('')]
        data.sort(key=lambda item: self._parse_for_sort(item[0]), reverse=reverse)
        for index, (_, child) in enumerate(data):
            self.tree.move(child, '', index)
        self.tree.heading(col, command=lambda: self.sort_treeview_column(col, not reverse))
        self._last_sort = (col, reverse)

    def browse_file(self, key: str) -> None:
        filetypes = {
            'datasheet': [("PDF Files", "*.pdf"), ("All files", "*.*")],
            'image_path': [("Image Files", "*.jpg *.jpeg *.png *.gif"), ("All files", "*.*")]
        }
        types = filetypes.get(key, [("All files", "*.*")])
        path = filedialog.askopenfilename(title=f"Select {key}", filetypes=types)
        if path:
            self.entries[key].delete(0, tk.END)
            self.entries[key].insert(0, path)
            if key == "image_path":
                self.update_image_preview(path)

    # ---------- Görsel/Önizleme ----------

    def update_image_preview(self, image_path: Optional[str]) -> None:
        if image_path and os.path.exists(image_path):
            try:
                with Image.open(image_path) as img:
                    self.image_label.update_idletasks()
                    max_w = self.image_label.winfo_width()
                    max_h = self.image_label.winfo_height()
                    if max_w <= 1 or max_h <= 1:
                        max_w, max_h = config.IMAGE_PREVIEW_SIZE
                    img_w, img_h = img.size
                    img_ratio = img_w / img_h
                    box_ratio = max_w / max_h
                    if img_ratio > box_ratio:
                        new_w = max_w
                        new_h = int(max_w / img_ratio)
                    else:
                        new_h = max_h
                        new_w = int(max_h * img_ratio)
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                    self.photo_image = ImageTk.PhotoImage(img)
                self.image_label.config(image=self.photo_image, text="")
            except Exception as e:
                LOG.warning("Image preview error: %s", e)
                self.image_label.config(image="", text="Error loading image")
        else:
            self.image_label.config(image="", text="No Image")
            self.photo_image = None

    def update_category_filter(self) -> None:
        current_selection = self.category_filter_var.get()
        cats = db_handler.get_distinct_categories() or []
        # None/boş kategorileri kullanıcı dostu ismine map et
        cleaned = [c if c not in (None, "") else "Uncategorized" for c in cats]
        categories = ["All"] + cleaned
        self.category_filter['values'] = categories
        if current_selection in categories:
            self.category_filter_var.set(current_selection)
        else:
            self.category_filter_var.set("All")

    def apply_column_widths(self) -> None:
        settings = config.load_settings()
        for col, w in settings.get("column_widths", {}).items():
            if col in config.COLUMNS:
                try:
                    self.tree.column(col, width=int(w))
                except Exception:
                    pass

    def get_selected_id(self) -> Optional[str]:
        try:
            return self.tree.selection()[0]
        except Exception:
            return None

    def update_status(self, text: str) -> None:
        self.status_text.set(text)

    # ---------- Grafik ----------

    def _theme_colors(self) -> Tuple[str, str, str]:
        """(bg, fg, legend_face) döndür."""
        if self.theme_var.get() == "dark":
            return ("#2e2e2e", "white", "#2e2e2e")
        return ("white", "black", "white")

    def _update_chart(self) -> None:
        cats_counts = db_handler.get_category_counts()
        if not cats_counts:
            return
        cats, counts = zip(*cats_counts)
        bg, fg, legend_face = self._theme_colors()
        self.chart_ax.clear()
        wedges, texts, autotexts = self.chart_ax.pie(
            counts, labels=cats, autopct="%1.1f%%", startangle=90,
            textprops={"color": fg}, wedgeprops={"edgecolor": bg},
        )
        self.chart_ax.set_title("Category Distribution", color=fg)
        self.chart_ax.legend(
            wedges, cats, title="Categories", loc="center left",
            bbox_to_anchor=(1, 0, 0.3, 1), facecolor=legend_face, edgecolor=legend_face,
        )
        self.chart_fig.set_facecolor(bg)
        self.chart_canvas.draw()

    def _close_chart(self) -> None:
        try:
            if self.chart_canvas:
                self.chart_canvas.get_tk_widget().destroy()
            if self.chart_fig is not None:
                plt.close(self.chart_fig)
        finally:
            if self.chart_win and self.chart_win.winfo_exists():
                self.chart_win.destroy()
            self.chart_win = None
            self.chart_ax = None
            self.chart_fig = None
            self.chart_canvas = None

    def show_category_chart(self) -> None:
        if self.chart_win and self.chart_win.winfo_exists():
            self._update_chart()
            return
        cats_counts = db_handler.get_category_counts()
        if not cats_counts:
            messagebox.showinfo("No Data", "No categories to display.")
            return
        self.chart_win = tk.Toplevel(self.root)
        self.chart_win.title("Category Chart")
        bg, fg, _ = self._theme_colors()
        self.chart_win.configure(bg=bg)
        self.chart_win.geometry("900x600")
        self.chart_win.resizable(True, True)
        self.chart_win.protocol("WM_DELETE_WINDOW", self._close_chart)

        self.chart_fig, self.chart_ax = plt.subplots(figsize=(7, 7), facecolor=bg)
        self.chart_canvas = FigureCanvasTkAgg(self.chart_fig, master=self.chart_win)
        self.chart_canvas.get_tk_widget().pack(fill="both", expand=True)
        self._update_chart()

    # ---------- Bağlam menüsü eylemleri ----------

    def _open_image_file(self) -> None:
        if not self.selected_item_data:
            return
        path = self.selected_item_data.get('image_path')
        ok, err = open_path_or_url(path)
        if not ok and err:
            messagebox.showerror("Open Image", err)

    def _open_image_folder(self) -> None:
        if not self.selected_item_data:
            return
        path = self.selected_item_data.get('image_path')
        ok, err = open_containing_folder(path)
        if not ok and err:
            messagebox.showerror("Open Folder", err)

    def _open_any_folder(self) -> None:
        if not self.selected_item_data:
            return
        path = self.selected_item_data.get('datasheet') or self.selected_item_data.get('image_path')
        if _is_url(str(path)):
            ok, err = open_path_or_url(str(path))
        else:
            ok, err = open_containing_folder(str(path))
        if not ok and err:
            messagebox.showerror("Open Folder", err)

    def _copy_drawer_code(self) -> None:
        if not self.selected_item_data:
            return
        code = self.selected_item_data.get('drawer_code', '')
        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        self.update_status("Drawer code copied to clipboard")

    # ---------- QR yardımcıları ----------

    def generate_qr_for_selected(self) -> None:
        if not self.selected_item_data:
            messagebox.showinfo("QR", "Select a component first.")
            return
        try:
            payload = _build_qr_payload(self.selected_item_data)
            img = _render_qr_image(payload)
            # Altına büyük puntolu drawer_code ekle
            label_text = str(self.selected_item_data.get("drawer_code") or "")
            img = _qr_with_label(img, label_text)

            fmt = getattr(config, "QR_FILENAME_FORMAT", "QR_{drawer_code}_{name}_{id}.png")
            default_name = fmt.format(
                id=self.selected_item_data.get("id") or "",
                name=_safe_filename(str(self.selected_item_data.get("name") or "")),
                drawer_code=_safe_filename(str(self.selected_item_data.get("drawer_code") or "")),
            )
            self._save_image_dialog(img, default_name)
        except Exception as e:
            messagebox.showerror("QR Error", str(e))

    def print_qr_for_selected(self) -> None:
        if sys.platform != "win32":
            messagebox.showinfo("Print", "Direct printing is only implemented on Windows.")
            return
        if not self.selected_item_data:
            messagebox.showinfo("Print", "Select a component first.")
            return
        try:
            payload = _build_qr_payload(self.selected_item_data)
            img = _render_qr_image(payload)
            # Altına büyük puntolu drawer_code ekle
            label_text = str(self.selected_item_data.get("drawer_code") or "")
            img = _qr_with_label(img, label_text)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                temp_path = tmp.name
            img.save(temp_path, format="PNG")
            os.startfile(temp_path, "print")  # type: ignore[attr-defined]
            self.update_status("QR sent to default printer.")
        except Exception as e:
            messagebox.showerror("Print Error", f"Failed to print.\n{e}")


    def _get_latest_component_by_name_drawer(self, name: str, drawer_code: str) -> Optional[Dict[str, Any]]:
        try:
            row = execute_query(
                "SELECT * FROM components WHERE name = ? AND drawer_code = ? ORDER BY id DESC LIMIT 1",
                (name, drawer_code),
                fetch="one",
            )
            if not row:
                return None
            return dict(zip(config.COLUMNS, row))
        except Exception:
            return None

    def _save_image_dialog(self, image: Image.Image, default_filename: str) -> None:
        path = filedialog.asksaveasfilename(
            title="Save QR code",
            initialfile=_safe_filename(default_filename),
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        image.save(path, format="PNG")
        self.update_status(f"QR saved → {path}")
        if messagebox.askyesno("QR Saved", "Open containing folder?"):
            ok, err = open_containing_folder(path)
            if not ok and err:
                messagebox.showerror("Open Folder", err)

    def print_qr_for_selected(self) -> None:
        if sys.platform != "win32":
            messagebox.showinfo("Print", "Direct printing is only implemented on Windows.")
            return
        if not self.selected_item_data:
            messagebox.showinfo("Print", "Select a component first.")
            return
        try:
            payload = _build_qr_payload(self.selected_item_data)
            img = _render_qr_image(payload)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                temp_path = tmp.name
            img.save(temp_path, format="PNG")
            os.startfile(temp_path, "print")  # type: ignore[attr-defined]
            self.update_status("QR sent to default printer.")
        except Exception as e:
            messagebox.showerror("Print Error", f"Failed to print.\n{e}")


    def _save_image_dialog(self, image: Image.Image, default_filename: str) -> None:
        path = filedialog.asksaveasfilename(
            title="Save QR code",
            initialfile=_safe_filename(default_filename),
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        image.save(path, format="PNG")
        self.update_status(f"QR saved → {path}")
        if messagebox.askyesno("QR Saved", "Open containing folder?"):
            ok, err = open_containing_folder(path)
            if not ok and err:
                messagebox.showerror("Open Folder", err)

    def _ask_make_qr(self, comp: Optional[Dict[str, Any]]) -> None:
        if not comp:
            return
        if messagebox.askyesno("QR Code", "Generate QR code label for this component now?"):
            try:
                payload = _build_qr_payload(comp)
                img = _render_qr_image(payload)
                fmt = getattr(config, "QR_FILENAME_FORMAT", "QR_{drawer_code}_{name}_{id}.png")
                default_name = fmt.format(
                    id=comp.get("id") or "",
                    name=_safe_filename(str(comp.get("name") or "")),
                    drawer_code=_safe_filename(str(comp.get("drawer_code") or "")),
                )
                self._save_image_dialog(img, default_name)
            except Exception as e:
                messagebox.showerror("QR Error", str(e))




    # ---------- QR/Etiket Önizleme ----------

    def qr_preview_selected(self) -> None:
        if not self.selected_item_data:
            messagebox.showinfo("QR", "Select a component first.")
            return
        self._show_qr_dialog(self.selected_item_data)


    def _show_qr_dialog(self, comp: Dict[str, Any]) -> None:
        """QR'ı GUI'de canlı önizler; PNG kaydı ve (Windows) yazdırma sağlar."""
        if not comp:
            messagebox.showinfo("QR", "No component data.")
            return

        payload = _build_qr_payload(comp)
        default_fmt = getattr(config, "QR_FILENAME_FORMAT", "QR_{drawer_code}_{name}_{id}.png")
        default_name = default_fmt.format(
            id=comp.get("id") or "",
            name=_safe_filename(str(comp.get("name") or "")),
            drawer_code=_safe_filename(str(comp.get("drawer_code") or "")),
        )

        win = tk.Toplevel(self.root)
        win.title(f"QR — {comp.get('name','')}")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        # Üst bilgi
        info = ttk.Label(win, text=f"{comp.get('name','')}  |  {comp.get('drawer_code','')}")
        info.pack(padx=12, pady=(12, 6), anchor="w")

        # Görsel alanı
        img_label = ttk.Label(win)
        img_label.pack(padx=12, pady=6)

        # Ayarlar
        ctrl_frame = ttk.Frame(win)
        ctrl_frame.pack(fill="x", padx=12, pady=(6, 6))

        ttk.Label(ctrl_frame, text="Scale").grid(row=0, column=0, sticky="w")
        scale_var = tk.IntVar(value=getattr(config, "QR_DEFAULT_SCALE", 4))
        scale_spin = ttk.Spinbox(ctrl_frame, from_=2, to=20, width=5, textvariable=scale_var)
        scale_spin.grid(row=0, column=1, padx=(6, 18), sticky="w")

        ttk.Label(ctrl_frame, text="Border").grid(row=0, column=2, sticky="w")
        border_var = tk.IntVar(value=getattr(config, "QR_BORDER", 2))
        border_spin = ttk.Spinbox(ctrl_frame, from_=0, to=10, width=5, textvariable=border_var)
        border_spin.grid(row=0, column=3, padx=(6, 18), sticky="w")

        # Butonlar
        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=12, pady=(6, 12))
        save_btn = ttk.Button(btns, text="💾 Save PNG")
        print_btn = ttk.Button(btns, text="🖨️ Print")
        close_btn = ttk.Button(btns, text="Close", command=win.destroy)
        save_btn.pack(side="left")
        print_btn.pack(side="left", padx=(8, 0))
        close_btn.pack(side="right")

        # Son render'ı saklamak için
        self._qr_preview_pil: Optional[Image.Image] = None
        self._qr_preview_tk: Optional[ImageTk.PhotoImage] = None



        def render():
            try:
                img = _render_qr_image(payload, scale=scale_var.get(), border=border_var.get())
                # ALTINA BÜYÜK PUNTO İLE DRAWER CODE EKLE
                label_text = str(comp.get("drawer_code") or "")
                img = _qr_with_label(img, label_text)  # ← burada birleştiriyoruz

                self._qr_preview_pil = img
                self._qr_preview_tk = ImageTk.PhotoImage(img)
                img_label.config(image=self._qr_preview_tk)
            except Exception as e:
                messagebox.showerror("QR Error", str(e))

        def on_save():
            if not self._qr_preview_pil:
                return
            self._save_image_dialog(self._qr_preview_pil, default_name)

        def on_print():
            if sys.platform != "win32":
                messagebox.showinfo("Print", "Direct printing is only implemented on Windows.")
                return
            if not self._qr_preview_pil:
                return
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp_path = tmp.name
                self._qr_preview_pil.save(tmp_path, format="PNG")
                os.startfile(tmp_path, "print")  # type: ignore[attr-defined]
                self.update_status("QR sent to default printer.")
            except Exception as e:
                messagebox.showerror("Print Error", f"Failed to print.\n{e}")

        save_btn.config(command=on_save)
        print_btn.config(command=on_print)

        # Değişince yeniden üret
        scale_spin.configure(command=render)
        border_spin.configure(command=render)
        scale_var.trace_add("write", lambda *_: render())
        border_var.trace_add("write", lambda *_: render())

        render()

    # ---------- DB yardımcıları ----------

    def _component_exists(self, name: str, drawer_code: str, exclude_id: Optional[Any] = None) -> bool:
        if exclude_id is None:
            q = "SELECT 1 FROM components WHERE name = ? AND drawer_code = ? LIMIT 1"
            row = execute_query(q, (name, drawer_code), fetch="one")
        else:
            q = "SELECT 1 FROM components WHERE name = ? AND drawer_code = ? AND id <> ? LIMIT 1"
            row = execute_query(q, (name, drawer_code, exclude_id), fetch="one")
        return row is not None

    def _merge_quantity(self, data: Dict[str, Any]) -> None:
        q = "UPDATE components SET quantity = COALESCE(quantity,0) + ? WHERE name = ? AND drawer_code = ?"
        try:
            execute_query(q, (int(data.get("quantity") or 0), data["name"], data["drawer_code"]))
            self.update_status("Merged quantity into existing record.")
        except Exception as e:
            messagebox.showerror("Merge Failed", str(e))

    # ---------- Arayüz yardımcıları ----------

    def _on_search_changed(self, *_):
        if self._search_after_id:
            try:
                self.root.after_cancel(self._search_after_id)
            except Exception:
                pass
        self._search_after_id = self.root.after(300, self.filter_and_search)

    def _reset_filters(self) -> None:
        self.search_var.set("")
        self.category_filter_var.set("All")
        self.filter_and_search()

    def _focus_search(self) -> None:
        self.search_entry.focus_set()
        self.search_entry.select_range(0, tk.END)


# ================================================================
# main
# ================================================================

def main() -> None:
    ensure_config_defaults()
    root = tk.Tk()
    settings = config.load_settings()
    initial_theme = settings.get("theme", "dark")
    sv_ttk.set_theme(initial_theme)
    root.update_idletasks()
    enable_windows_dark_titlebar(root)
    app = ComponentTrackerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
