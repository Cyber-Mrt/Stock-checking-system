# main_app.py
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import webbrowser
import platform
import sys
import csv
import datetime
from pathlib import Path  # Modern, object-oriented way to handle file paths
from db_handler import execute_query

# Third-party libraries
import sv_ttk
import ctypes
from ctypes import wintypes
from PIL import Image, ImageTk

# Import our separated modules
import db_handler
import export_utils
import config



def enable_windows_dark_titlebar(window):
    """
    Sets the title bar to dark mode on compatible Windows versions.
    Does nothing on other operating systems.
    """
    if sys.platform != "win32":
        return

    try:
        # DWMWA_USE_IMMERSIVE_DARK_MODE value is 20 for Windows 11, 19 for Windows 10 1809+
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        
        hwnd = window.winfo_id()
        use_dark = ctypes.c_int(1) # 1 for dark, 0 for light
        
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            wintypes.DWORD(DWMWA_USE_IMMERSIVE_DARK_MODE),
            ctypes.byref(use_dark),
            ctypes.sizeof(use_dark)
        )
    except Exception as e:
        print(f"[DWM] Failed to set dark title bar: {e}")

class ComponentTrackerApp:
    
    def __init__(self, root):
        # chart penceresi ve Matplotlib objelerini saklamak için
        self.chart_win    = None
        self.chart_fig    = None
        self.chart_ax     = None
        self.chart_canvas = None

        self.root = root
        self.root.title("Component Library Tracker")

        # This will hold the data of the currently selected Treeview item
        self.selected_item_data = None
        # This will hold the PhotoImage object to prevent it from being garbage collected
        self.photo_image = None

        # Load settings and configure the window
        self._load_and_apply_settings()

        # Create all the UI elements
        self._create_widgets()
        
        # Bind events and keyboard shortcuts
        self._bind_events()

        # Load initial data into the Treeview
        self.refresh_treeview()
        
        # Set the theme based on saved settings
        self.on_theme_change()

    

    def _load_and_apply_settings(self):
        """Loads settings from config and applies them to the window."""
        settings = config.load_settings()
        
        # Set window size
        w, h = settings.get("window_size", (1300, 750))
        self.root.geometry(f"{w}x{h}")

        # Set theme variable (will be applied by on_theme_change)
        self.theme_var = tk.StringVar(value=settings.get("theme", "dark"))
        
        # Set protocol for saving settings on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)



    def is_form_dirty(self):
        """
        Formdaki alanlarla seçili item’ın eski değerlerini karşılaştırır.
        Eğer en az birinde fark varsa True döner.
        """
        if not self.selected_item_data:
            return False

        for key, entry in self.entries.items():
            old = str(self.selected_item_data.get(key) or "").strip()
            new = entry.get().strip()
            if new != old:
                return True
        return False

    # --- Widget Creation (Refactored for Readability) ---

    def _create_widgets(self):
        """Creates and organizes all the application's widgets by calling sub-methods."""
        # Main layout frames
        top_frame, main_pane, bottom_container, button_frame, self.status_bar = self._setup_layout()

        # Populate the frames with widgets
        self._create_top_bar(top_frame)
        tree_frame = self._create_tree_view(main_pane)
        self._create_bottom_pane(bottom_container)
        self._create_action_buttons(button_frame)
        
        # Add frames to the PanedWindow
        main_pane.add(tree_frame, weight=3)
        main_pane.add(bottom_container, weight=1)

        

    def _setup_layout(self):
        """Creates the main layout frames and status bar."""
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill="x")

        main_pane = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_pane.pack(fill="both", expand=True, padx=10, pady=5)

        # This container holds both the form and the image preview side-by-side
        bottom_container = ttk.Frame(main_pane)
        
        button_frame = ttk.Frame(self.root, padding="10")
        button_frame.pack(fill="x")
        
        status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor="w", padding=5)
        status_bar.pack(side="bottom", fill="x")

        return top_frame, main_pane, bottom_container, button_frame, status_bar
    
    def component_exists(name, drawer_code):
        """
        Aynı name ve drawer_code ile bir kayıt var mı diye bakar.
        Varsa True, yoksa False döner.
        """
        query = "SELECT 1 FROM components WHERE name = ? AND drawer_code = ?"
        row = execute_query(query, (name, drawer_code), fetch="one")
        return row is not None

    def _create_top_bar(self, parent_frame):
        """Creates search, filter, and theme selection widgets."""
        ttk.Label(parent_frame, text="🔎 Search:", font=("Arial", 10)).pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.filter_and_search())
        ttk.Entry(parent_frame, textvariable=self.search_var, width=30).pack(side="left", padx=5)

        ttk.Label(parent_frame, text="Category:", font=("Arial", 10)).pack(side="left", padx=(15, 5))
        self.category_filter_var = tk.StringVar(value="All")
        self.category_filter = ttk.Combobox(parent_frame, textvariable=self.category_filter_var, state="readonly")
        self.category_filter.pack(side="left", padx=5)
        self.category_filter.bind("<<ComboboxSelected>>", lambda *args: self.filter_and_search())

        ttk.Label(parent_frame, text="Theme:", font=("Arial", 10)).pack(side="left", padx=(15, 5))
        theme_combo = ttk.Combobox(
            parent_frame, textvariable=self.theme_var, values=["light", "dark"],
            state="readonly", width=6
        )
        theme_combo.pack(side="left", padx=5)
        theme_combo.bind("<<ComboboxSelected>>", self.on_theme_change)

    def _create_tree_view(self, parent_pane):
        """Creates the Treeview and its scrollbar."""
        tree_frame = ttk.Frame(parent_pane, padding=(0, 0, 0, 5))
        self.tree = ttk.Treeview(tree_frame, columns=config.COLUMNS, show='headings')
        
        for col in config.COLUMNS:
            if col == "image_path": continue # Don't show image_path column
            self.tree.heading(col, text=config.COLUMN_TITLES[col], command=lambda c=col: self.sort_treeview_column(c, False))
            self.tree.column(col, width=config.COLUMN_WIDTHS.get(col, 100), anchor="w")
        
        # Hide 'id' and 'image_path' columns from view
        self.tree.column("id", width=0, stretch=tk.NO)
        self.tree.column("image_path", width=0, stretch=tk.NO)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        return tree_frame

    def on_cell_double_click(self, event):
        # Tıkladığın hücrenin bölge ve sütununu tespit et
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        col_id = self.tree.identify_column(event.x)    # "#1", "#2", ...
        col_index = int(col_id.replace("#","")) - 1     # 0‑based index
        col_name = config.COLUMNS[col_index]

        # Eğer drawer_code sütunuysa, özel popup göster
        if col_name == "drawer_code":
            row_id = self.tree.identify_row(event.y)
            if not row_id:
                return
            code = self.tree.set(row_id, "drawer_code")

            popup = tk.Toplevel(self.root)
            popup.title("Drawer Code")
            # pencereyi ortala ve biraz büyük ver
            popup.geometry("400x200")
            txt = tk.Text(popup, font=("Consolas", 24), wrap="none")
            txt.insert("1.0", code)
            txt.config(state="disabled")
            txt.pack(expand=True, fill="both", padx=10, pady=10)
            return

        # değilse eskiden datasheet açan fonksiyonu çağır
        self.open_datasheet(event)    

    def _create_bottom_pane(self, parent_container):
        """Creates the component details form and the image preview area."""
        # Form on the left
        form_frame = ttk.LabelFrame(parent_container, text="Component Details", padding="10")
        form_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Image preview on the right
        image_frame = ttk.LabelFrame(parent_container, text="Image Preview", padding="10")
        image_frame.pack(side="right", fill="both", expand=True, ipadx=10, ipady=10) # Use fill and expand
        image_frame.columnconfigure(0, weight=1) # Center the label
        image_frame.rowconfigure(0, weight=1)
        
        self.image_label = ttk.Label(image_frame, text="No Image", anchor="center")
        self.image_label.grid(row=0, column=0, sticky="nsew")

        # Populate the form with entry fields
        self.entries = {}
        for i, (key, text) in enumerate(config.FORM_LABELS.items()):
            ttk.Label(form_frame, text=text).grid(row=i, column=0, padx=5, pady=4, sticky="w")
            entry_frame = ttk.Frame(form_frame)
            entry_frame.grid(row=i, column=1, sticky="ew", padx=5, pady=4)

            if key in ["datasheet", "image_path"]:
                entry = ttk.Entry(entry_frame)
                entry.pack(side="left", fill="x", expand=True)
                browse_cmd = lambda k=key: self.browse_file(k)
                ttk.Button(entry_frame, text="...", width=3, command=browse_cmd).pack(side="right")
            elif key == "quantity":
                entry = ttk.Entry(entry_frame, width=10)
                entry.pack(side="left")
                qty_button_frame = ttk.Frame(entry_frame)
                qty_button_frame.pack(side="left", padx=(5,0))
                ttk.Button(qty_button_frame, text="+", width=2, command=lambda: self.adjust_quantity(1)).pack(side="left")
                ttk.Button(qty_button_frame, text="-", width=2, command=lambda: self.adjust_quantity(-1)).pack(side="left")
            else:
                entry = ttk.Entry(entry_frame)
                entry.pack(side="left", fill="x", expand=True)
            
            self.entries[key] = entry
        
        form_frame.grid_columnconfigure(1, weight=1)

    def _create_action_buttons(self, parent_frame):
        """Creates the main action buttons at the bottom of the window."""
        # Configure button styles for better visual feedback
        style = ttk.Style()
        style.configure("Success.TButton", foreground="white", background="#4CAF50")
        style.configure("Danger.TButton", foreground="white", background="#f44336")
        style.configure("Info.TButton", foreground="white", background="#2196F3")
        
        # Create and pack buttons
        ttk.Button(parent_frame, text="➕ Add", command=self.add_component, style="Success.TButton").pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(parent_frame, text="💾 Update", command=self.update_component, style="Info.TButton").pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(parent_frame, text="🗑️ Delete", command=self.delete_selected, style="Danger.TButton").pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(parent_frame, text="🧹 Clear Form", command=self.clear_form_and_selection).pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(parent_frame, text="📥 Import CSV", command=self.import_csv).pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(parent_frame, text="📤 Export CSV", command=lambda: export_utils.export_to_csv(self.update_status)).pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(parent_frame, text="📄 Export PDF", command=lambda: export_utils.export_to_pdf(self.update_status)).pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(parent_frame, text="📊 Category Chart", command=self.show_category_chart).pack(side="left", expand=True, fill="x", padx=5)
    
    def _bind_events(self):
        """Binds all mouse and keyboard events."""
        # Treeview events
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        self.tree.bind("<Double-1>", self.on_cell_double_click)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.tree.bind("<Button-3>", self.show_context_menu) # Right-click

        # Keyboard shortcuts
        self.root.bind("<Control-n>", lambda e: self.clear_form_and_selection())
        self.root.bind("<Control-s>", lambda e: self.update_component())
        self.root.bind("<Delete>", lambda e: self.delete_selected())

        # Context menu setup
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="✏️ Edit", command=self.edit_via_context)
        self.context_menu.add_command(label="🗑️ Delete", command=self.delete_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📄 Open Datasheet", command=self.open_datasheet)

    # --- Core Application Logic ---

    def on_close(self):
        """Saves settings and closes the application."""
        self.update_status("Saving settings...")
        settings = config.load_settings()
        
        # Save window size
        settings["window_size"] = (self.root.winfo_width(), self.root.winfo_height())
        
        # Save column widths
        settings["column_widths"] = {col: self.tree.column(col, option="width") for col in config.COLUMNS}
        
        config.save_settings(settings)
        self.root.destroy()

    def on_theme_change(self, event=None):
        """Applies the selected theme and saves the choice."""
        new_theme = self.theme_var.get()
        sv_ttk.set_theme(new_theme)
        enable_windows_dark_titlebar(self.root)

        # Save the theme choice to settings
        settings = config.load_settings()
        settings["theme"] = new_theme
        config.save_settings(settings)
        
        self.update_status(f"Theme set to '{new_theme}'")

    def refresh_treeview(self, data=None):
        """Clears and repopulates the treeview with data."""
        current_selection_id = self.get_selected_id()
        self.tree.delete(*self.tree.get_children())
        
        if data is None:
            data = db_handler.get_all_components()

        for comp in data:
            self.tree.insert('', 'end', values=comp, iid=comp[0])
        
        self.update_category_filter()
        
        # Re-select the previously selected item if it still exists
        if current_selection_id and self.tree.exists(current_selection_id):
            self.tree.selection_set(current_selection_id)
            self.tree.focus(current_selection_id)
            self.tree.see(current_selection_id)

        self.update_status(f"Displayed {len(data)} components.")
        self.apply_column_widths()

    def add_component(self):
        """Adds a new component to the database."""
        data = self.get_form_data()
        if data is None: return

        if db_handler.add_component(data):
            self.update_status(f"Component '{data['name']}' added successfully.")
            self.refresh_treeview()
            self.clear_form_and_selection()
        else:
            messagebox.showerror("Database Error", "Failed to add the component.")

    def update_component(self):
        """Updates the selected component in the database."""
        if not self.selected_item_data:
            messagebox.showwarning("No Selection", "Please select a component to update.")
            return

        comp_id = self.selected_item_data['id']
        data = self.get_form_data()
        if data is None: return
        
        if db_handler.update_component(comp_id, data):
            self.update_status(f"Component '{data['name']}' updated successfully.")
            self.refresh_treeview() 
        else:
            messagebox.showerror("Database Error", "Failed to update the component.")

    def delete_selected(self):
        """Deletes the selected component after confirmation."""
        if not self.selected_item_data:
            messagebox.showwarning("No Selection", "Please select a component to delete.")
            return
        
        comp_id = self.selected_item_data['id']
        comp_name = self.selected_item_data['name']

        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete '{comp_name}'?"):
            if db_handler.delete_component(comp_id):
                self.update_status(f"Component '{comp_name}' deleted.")
                self.refresh_treeview()
                self.clear_form_and_selection()
            else:
                messagebox.showerror("Database Error", "Failed to delete component.")

    # --- UI Interaction and Event Handlers ---

    def on_row_select(self, event=None):
        """Handles selection of a row in the treeview, populating the form."""
        selected_items = self.tree.selection()
        if not selected_items:
            self.selected_item_data = None
            return
        
        item_id = selected_items[0]
        values = self.tree.item(item_id, "values")
        self.selected_item_data = dict(zip(config.COLUMNS, values))
        
        self.clear_form_entries()
        for key, entry_widget in self.entries.items():
            if key in self.selected_item_data:
                entry_widget.insert(0, self.selected_item_data[key] or "")
        
        self.update_status(f"Selected: {self.selected_item_data['name']}")
        self.update_image_preview(self.selected_item_data.get('image_path'))

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "nothing":
            # eğer formda kaydedilmemiş değişiklik varsa sor
            if self.is_form_dirty():
                save = messagebox.askyesno(
                    "Unsaved changes",
                    "Yapılan değişiklikler kaydedilsin mi?"
                )
                if save:
                    # update_component, seçili öğeyi güncelliyor
                    self.update_component()
                else:
                    # eğer kaydetmezse, geri eski değerlere dönebiliriz
                    # ama biz clear_form_and_selection ile sıfırlıyoruz
                    pass

            # en sonunda formu temizle ve selection kaldır
            self.clear_form_and_selection()

    def show_context_menu(self, event):
        """Shows a context menu on right-click."""
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.on_row_select() # Ensure data is loaded for the context actions
            self.context_menu.post(event.x_root, event.y_root)

    def edit_via_context(self):
        """Placeholder for context menu edit action. Can be expanded later."""
        if not self.selected_item_data: return
        self.update_status(f"Context Menu: Editing '{self.selected_item_data['name']}'")
        # Future implementation: could open a dedicated edit window.
        # For now, the main form is already in "edit mode".

    def open_datasheet(self, event=None):
        """Opens the selected component's datasheet (URL or local file)."""
        if not self.selected_item_data: return

        link = self.selected_item_data.get('datasheet', '')
        if not link:
            messagebox.showinfo("No Datasheet", "No datasheet provided for this component.")
            return

        try:
            if link.lower().startswith("http"):
                webbrowser.open(link)
            elif Path(link).is_file():
                # Using pathlib and os.startfile/open/xdg-open for cross-platform support
                abs_path = Path(link).resolve()
                if platform.system() == "Windows":
                    os.startfile(abs_path)
                elif platform.system() == "Darwin": # macOS
                    os.system(f'open "{abs_path}"')
                else: # Linux and others
                    os.system(f'xdg-open "{abs_path}"')
            else:
                messagebox.showwarning("File Not Found", f"The path could not be found:\n{link}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open the datasheet.\nError: {e}")

    # --- Data Handling and Utility Methods ---

    def import_csv(self):
        """Imports components from a user-selected CSV file, skipping exact duplicates."""
        file_path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV Files", "*.csv"), ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, newline='', encoding='utf-8-sig') as csvfile:
                # CSV sniffer vs. fallback
                try:
                    dialect = csv.Sniffer().sniff(csvfile.read(2048), delimiters=";,\t|")
                    csvfile.seek(0)
                except csv.Error:
                    dialect = 'excel'
                    csvfile.seek(0)

                reader = csv.DictReader(csvfile, dialect=dialect)
                reader.fieldnames = [h.strip().lower().replace(' ', '_') for h in reader.fieldnames]

                count_new = 0
                count_skipped = 0

                for row in reader:
                    # temel alanlar yoksa atla
                    if not all(k in row for k in ("name", "drawer_code", "quantity")):
                        continue

                    # string→int dönüşümleri vs.
                    data = {k: v.strip() for k, v in row.items()}
                    try:
                        data["quantity"] = int(data["quantity"])
                    except (ValueError, TypeError):
                        data["quantity"] = 0

                    # eğer zaten bu ikili varsa atla
                    if db_handler.component_exists(data["name"], data["drawer_code"]):
                        count_skipped += 1
                        continue

                    # yoksa ekle
                    if not data.get("added_date"):
                        data["added_date"] = datetime.date.today().isoformat()

                    db_handler.add_component(data)
                    count_new += 1

                messagebox.showinfo(
                    "Import Complete",
                    f"{count_new} new component(s) imported.\n"
                    f"{count_skipped} duplicate(s) skipped."
                )
                self.refresh_treeview()

        except Exception as e:
            messagebox.showerror("Import Failed", f"An error occurred:\n{e}")

    def get_form_data(self):
        """Retrieves and validates data from the input form."""
        data = {key: entry.get().strip() for key, entry in self.entries.items()}
        
        if not data["name"] or not data["drawer_code"]:
            messagebox.showwarning("Missing Information", "Component Name and Drawer Code are required.")
            return None
        
        try:
            data["quantity"] = int(data["quantity"] or 0)
        except ValueError:
            messagebox.showerror("Invalid Input", "Quantity must be a valid number.")
            return None
            
        return data

    def adjust_quantity(self, amount):
        """
        Formdaki Quantity alanını amount (±1) kadar değiştirir,
        eğer bir satır seçiliyse veritabanını ve Treeview'u günceller,
        ve Chart penceresi açıksa grafiği yeniden çizer.
        """
        # 1) Yeni miktarı hesapla
        try:
            current = int(self.entries["quantity"].get() or 0)
            new_val = max(0, current + amount)
        except ValueError:
            new_val = max(0, amount)

        # 2) Formu güncelle
        self.entries["quantity"].delete(0, tk.END)
        self.entries["quantity"].insert(0, str(new_val))

        # 3) Seçili bir bileşen varsa veritabanına kaydet ve Treeview'u yenile
        if self.selected_item_data:
            self.update_component()

            # 4) Eğer grafik penceresi açıksa, grafiği yeniden çiz
            if self.chart_win and self.chart_win.winfo_exists():
                self._update_chart()



    def clear_form_and_selection(self):
        """Clears the form, the treeview selection, and the image preview."""
        self.clear_form_entries()
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
        self.selected_item_data = None
        self.update_image_preview(None)
        self.update_status("Form cleared. Ready to add a new component.")

    def clear_form_entries(self):
        """Just clears the text in the form's entry widgets."""
        for entry in self.entries.values():
            entry.delete(0, tk.END)

    def filter_and_search(self):
        """Filters treeview data based on search term and category."""
        search_term = self.search_var.get().lower()
        category = self.category_filter_var.get()
        filtered_data = db_handler.search_components(search_term, category)
        self.refresh_treeview(data=filtered_data)

    def sort_treeview_column(self, col, reverse):
        """Sorts the treeview by a specific column."""
        data = [(self.tree.set(child, col), child) for child in self.tree.get_children('')]
        
        # Attempt to sort numerically, fall back to string sort
        try:
            data.sort(key=lambda item: int(item[0]), reverse=reverse)
        except (ValueError, TypeError):
            data.sort(key=lambda item: str(item[0]).lower(), reverse=reverse)

        for index, (val, child) in enumerate(data):
            self.tree.move(child, '', index)

        # Toggle sort direction for the next click
        self.tree.heading(col, command=lambda: self.sort_treeview_column(col, not reverse))

    def browse_file(self, key):
        """Opens a file dialog to select a datasheet or image."""
        filetypes = {
            'datasheet': [("PDF Files", "*.pdf"), ("All files", "*.*")],
            'image_path': [("Image Files", "*.jpg *.jpeg *.png *.gif"), ("All files", "*.*")]
        }
        path = filedialog.askopenfilename(title=f"Select {key}", filetypes=filetypes.get(key))
        if path:
            self.entries[key].delete(0, tk.END)
            self.entries[key].insert(0, path)
            if key == "image_path":
                self.update_image_preview(path)
    
    # --- Helper Methods ---

    def update_image_preview(self, image_path):
        if image_path and os.path.exists(image_path):
            try:
                # Load
                img = Image.open(image_path)

                # Önce geometry güncellesin diye idletasks
                self.image_label.update_idletasks()

                # Label’ın şu anki boyutunu al
                max_w = self.image_label.winfo_width()
                max_h = self.image_label.winfo_height()

                # Eğer daha kurulmadıysa (0 dönerse) fallback olarak config
                if max_w <= 1 or max_h <= 1:
                    max_w, max_h = config.IMAGE_PREVIEW_SIZE

                # Oranları koruyarak yeni boyutları hesapla
                img_w, img_h = img.size
                img_ratio = img_w / img_h
                box_ratio = max_w / max_h

                if img_ratio > box_ratio:
                    # genişlik sınırı belirleyici
                    new_w = max_w
                    new_h = int(max_w / img_ratio)
                else:
                    # yükseklik sınırı belirleyici
                    new_h = max_h
                    new_w = int(max_h * img_ratio)

                # Yeniden boyutlandır
                img = img.resize((new_w, new_h), Image.LANCZOS)

                # Göster
                self.photo_image = ImageTk.PhotoImage(img)
                self.image_label.config(image=self.photo_image, text="")

            except Exception as e:
                # yüklenemezse metin göster
                print(f"Image preview error: {e}")
                self.image_label.config(image="", text="Error loading image")
        else:
            # geçersizse sıfırla
            self.image_label.config(image="", text="No Image")
            self.photo_image = None


    def update_category_filter(self):
        """Updates the category combobox with distinct categories from the DB."""
        current_selection = self.category_filter_var.get()
        categories = ["All"] + db_handler.get_distinct_categories()
        self.category_filter['values'] = categories
        # Preserve selection if it's still valid
        if current_selection in categories:
            self.category_filter_var.set(current_selection)
        else:
            self.category_filter_var.set("All")

    def apply_column_widths(self):
        """Applies saved column widths from settings."""
        settings = config.load_settings()
        for col, w in settings.get("column_widths", {}).items():
            if col in config.COLUMNS:
                self.tree.column(col, width=w)

    def get_selected_id(self):
        """Returns the ID of the currently selected treeview item."""
        return self.tree.selection()[0] if self.tree.selection() else None

    def update_status(self, text):
        """Updates the text in the status bar."""
        self.status_bar.config(text=text)

    def _update_chart(self):
        """Var olan chart penceresinde dilimleri günceller."""
        cats, counts = zip(*db_handler.get_category_counts())

        # Ekseni temizle
        self.chart_ax.clear()

        # Yeni pie çiz
        wedges, texts, autotexts = self.chart_ax.pie(
            counts,
            labels=cats,
            autopct="%1.1f%%",
            startangle=90,
            textprops={"color":"white"},
            wedgeprops={"edgecolor":"white"},
        )
        self.chart_ax.set_title("Category Distribution", color="white")

        # Legend’i güncelle
        self.chart_ax.legend(
            wedges,
            cats,
            title="Categories",
            loc="center left",
            bbox_to_anchor=(1, 0, 0.3, 1),
            facecolor='#2e2e2e',
            edgecolor='#2e2e2e',
        )

        # Çizimi ekrana yansıt
        self.chart_canvas.draw()



    def show_category_chart(self):
        """
        Category Chart penceresini açar ya da
        zaten açıksa sadece günceller.
        """
        # Eğer pencere hâlihazırda açıksa güncelle
        if self.chart_win and self.chart_win.winfo_exists():
            return self._update_chart()

        # Yoksa yeni pencere ve figür oluştur
        cats, counts = zip(*db_handler.get_category_counts())
        self.chart_win = tk.Toplevel(self.root)
        self.chart_win.title("Category Chart")
        self.chart_win.configure(bg='#2e2e2e')
        self.chart_win.geometry("900x600")
        self.chart_win.resizable(False, False)

        self.chart_fig, self.chart_ax = plt.subplots(
            figsize=(7,7), facecolor='#2e2e2e'
        )
        self.chart_canvas = FigureCanvasTkAgg(self.chart_fig, master=self.chart_win)
        self.chart_canvas.get_tk_widget().pack(fill="both", expand=True)

        # İlk çizimi yap
        self._update_chart()





def main():
    """Main function to initialize and run the application."""
    root = tk.Tk()
    
    # Set the theme before creating the app instance
    # This ensures all widgets are created with the correct theme from the start.
    settings = config.load_settings()
    initial_theme = settings.get("theme", "dark")
    sv_ttk.set_theme(initial_theme)
    
    # Apply dark title bar after the window is created but before it's drawn
    root.update_idletasks() 
    enable_windows_dark_titlebar(root)

    # Create and run the app
    app = ComponentTrackerApp(root)
    root.mainloop()

# --- Application Entry Point ---
if __name__ == "__main__":
    # The db_handler module is now expected to create the database and table
    # automatically if they don't exist when the first database operation is performed.
    main()
