# main_app.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import webbrowser
import platform  # Platforma özgü komutlar için eklendi

# Yeni ve modern tema için
import sv_ttk

# Import our separated modules
import db_handler
import export_utils
import config
from PIL import Image, ImageTk


class ComponentTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Component Library Tracker")

        # Holds the data of the currently selected Treeview item
        self.selected_item_data = None

        # Load settings and set window size
        settings = config.load_settings()
        w, h = settings.get("window_size", (1300, 750))
        self.root.geometry(f"{w}x{h}")

        # Save settings when the window is closed
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._create_widgets()
        self.refresh_treeview()

    def on_close(self):
        # Update settings with current window size
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        settings = config.load_settings()
        settings["window_size"] = (w, h)
        
        # Save column widths
        col_widths = {col: self.tree.column(col, option="width") for col in config.COLUMNS}
        settings["column_widths"] = col_widths
        config.save_settings(settings)
        self.root.destroy()

    def apply_column_widths(self):
        settings = config.load_settings()
        for col, w in settings.get("column_widths", {}).items():
            if col in config.COLUMNS:
                self.tree.column(col, width=w)

    def show_context_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.on_row_select()
            self.context_menu.post(event.x_root, event.y_root)

    def edit_via_context(self):
        if not self.selected_item_data:
            return
        self.update_status(f"Context Menu: Editing mode – {self.selected_item_data['name']}")

    def _create_widgets(self):
        """Creates the application's widgets."""
        # --- Main Layout Frames ---
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill="x")

        main_pane = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_pane.pack(fill="both", expand=True, padx=10, pady=5)

        tree_frame = ttk.Frame(main_pane, padding=(0, 0, 0, 5))
        bottom_container = ttk.Frame(main_pane)  # Container for form and image
        main_pane.add(tree_frame, weight=3)
        main_pane.add(bottom_container, weight=1)

        button_frame = ttk.Frame(self.root, padding="10")
        button_frame.pack(fill="x")
        
        status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor="w", padding=5)
        status_bar.pack(side="bottom", fill="x")
        self.status_bar = status_bar

        # --- Top Frame: Search and Filter ---
        ttk.Label(top_frame, text="🔎 Search:", font=("Arial", 10)).pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.filter_and_search())
        ttk.Entry(top_frame, textvariable=self.search_var, width=30).pack(side="left", padx=5)

        ttk.Label(top_frame, text="Category:", font=("Arial", 10)).pack(side="left", padx=(15, 5))
        self.category_filter_var = tk.StringVar(value="All")
        self.category_filter = ttk.Combobox(top_frame, textvariable=self.category_filter_var, state="readonly")
        self.category_filter.pack(side="left", padx=5)
        self.category_filter.bind("<<ComboboxSelected>>", lambda *args: self.filter_and_search())

        # --- Middle Frame: Treeview ---
        self.tree = ttk.Treeview(tree_frame, columns=config.COLUMNS, show='headings')
        for col in config.COLUMNS:
            if col == "image_path": continue
            self.tree.heading(col, text=config.COLUMN_TITLES[col], command=lambda c=col: self.sort_treeview_column(c, False))
            self.tree.column(col, width=config.COLUMN_WIDTHS.get(col, 100), anchor="w")
        
        self.tree.column("id", width=0, stretch=tk.NO)
        self.tree.column("image_path", width=0, stretch=tk.NO)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Event Bindings
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        self.tree.bind("<Double-1>", self.open_datasheet)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.tree.bind("<Button-3>", self.show_context_menu) # Bind right-click

        # Keyboard shortcuts
        self.root.bind("<Control-n>", lambda e: self.clear_form_and_selection())
        self.root.bind("<Control-s>", lambda e: self.update_component())
        self.root.bind("<Delete>", lambda e: self.delete_selected())

        # Create the context menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="✏️ Edit", command=self.edit_via_context)
        self.context_menu.add_command(label="🗑️ Delete", command=self.delete_selected)

        # --- Bottom Frame: Input Form & Image Preview ---
        form_frame = ttk.LabelFrame(bottom_container, text="Component Details", padding="10")
        form_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        image_frame = ttk.LabelFrame(bottom_container, text="Image Preview", padding="10")
        image_frame.pack(side="right", fill="y")
        self.image_label = ttk.Label(image_frame, text="No Image", anchor="center")
        self.image_label.pack(fill="both", expand=True)

        self.entries = {}
        for i, (key, text) in enumerate(config.FORM_LABELS.items()):
            ttk.Label(form_frame, text=text).grid(row=i, column=0, padx=5, pady=3, sticky="w")
            entry_frame = ttk.Frame(form_frame)
            entry_frame.grid(row=i, column=1, sticky="ew", padx=5, pady=3)

            if key == "datasheet" or key == "image_path":
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

        # --- Button Frame ---
        style = ttk.Style()
        style.configure("Success.TButton", foreground="white", background="#4CAF50")
        style.configure("Danger.TButton", foreground="white", background="#f44336")
        style.configure("Info.TButton", foreground="white", background="#2196F3")
        style.configure("Warning.TButton", foreground="white", background="#FF9800")
        style.configure("Primary.TButton", foreground="white", background="#9C27B0")
        
        ttk.Button(button_frame, text="➕ Add", command=self.add_component, style="Success.TButton").pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(button_frame, text="💾 Update", command=self.update_component, style="Info.TButton").pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(button_frame, text="🗑️ Delete", command=self.delete_selected, style="Danger.TButton").pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(button_frame, text="🧹 Clear Form", command=self.clear_form_and_selection).pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(button_frame, text="📤 Export CSV", command=export_utils.export_to_csv, style="Warning.TButton").pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(button_frame, text="📄 Export PDF", command=export_utils.export_to_pdf, style="Primary.TButton").pack(side="left", expand=True, fill="x", padx=5)

    def refresh_treeview(self, data=None):
        current_selection_id = self.get_selected_id()
        for row in self.tree.get_children():
            self.tree.delete(row)
        
        if data is None:
            data = db_handler.get_all_components()

        if data:
            for comp in data:
                self.tree.insert('', 'end', values=comp, iid=comp[0])
        
        self.update_category_filter()
        
        if current_selection_id and self.tree.exists(current_selection_id):
            self.tree.selection_set(current_selection_id)
            self.tree.focus(current_selection_id)
            self.tree.see(current_selection_id)

        self.update_status(f"Displayed {len(data or [])} components.")
        self.apply_column_widths()

    def update_category_filter(self):
        current_selection = self.category_filter_var.get()
        categories = ["All"] + db_handler.get_distinct_categories()
        self.category_filter['values'] = categories
        if current_selection in categories:
            self.category_filter_var.set(current_selection)
        else:
            self.category_filter_var.set("All")

    def get_form_data(self):
        data = {key: entry.get().strip() for key, entry in self.entries.items()}
        
        if not data["name"] or not data["drawer_code"] or not data["quantity"]:
            messagebox.showwarning("Missing Information", "Please fill in all required fields (*).")
            return None
        
        try:
            data["quantity"] = int(data["quantity"])
        except ValueError:
            messagebox.showerror("Invalid Input", "Quantity must be a valid number.")
            return None
        return data
    
    def update_image_preview(self, image_path):
        if image_path and os.path.exists(image_path):
            try:
                img = Image.open(image_path)
                # Use constant from config file
                img = img.resize(config.IMAGE_PREVIEW_SIZE, Image.LANCZOS)
                self.photo_image = ImageTk.PhotoImage(img)
                self.image_label.config(image=self.photo_image, text="")
            except Exception as e:
                self.image_label.config(image="", text="Error loading image")
                print(f"Image preview error: {e}")
        else:
            # if path is invalid or file not found
            self.image_label.config(image="", text="No Image")
            self.photo_image = None

    def add_component(self):
        data = self.get_form_data()
        if data is None: return

        if db_handler.add_component(data):
            messagebox.showinfo("Success", f"Component '{data['name']}' added successfully.")
            self.refresh_treeview()
            self.clear_form_and_selection()
        else:
            messagebox.showerror("Database Error", "Failed to add the component.")

    def update_component(self):
        if not self.selected_item_data:
            messagebox.showwarning("No Selection", "Please select a component to update.")
            return

        comp_id = self.selected_item_data['id']
        data = self.get_form_data()
        if data is None: return
        
        if db_handler.update_component(comp_id, data):
            # No popup on successful update to avoid interruption, just status update
            self.update_status(f"Component '{data['name']}' updated successfully.")
            self.refresh_treeview() 
        else:
            messagebox.showerror("Database Error", "Failed to update the component.")

    def delete_selected(self):
        if not self.selected_item_data:
            messagebox.showwarning("No Selection", "Please select a component to delete.")
            return
        
        comp_id = self.selected_item_data['id']
        comp_name = self.selected_item_data['name']

        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete '{comp_name}'?"):
            if db_handler.delete_component(comp_id):
                messagebox.showinfo("Success", f"Component '{comp_name}' deleted.")
                self.refresh_treeview()
                self.clear_form_and_selection()
            else:
                messagebox.showerror("Database Error", "Failed to delete component.")
    
    def on_row_select(self, event=None):
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

    def get_selected_id(self):
        if self.tree.selection():
            return self.tree.selection()[0]
        return None

    def clear_form_entries(self):
        for entry in self.entries.values():
            entry.delete(0, tk.END)

    def clear_form_and_selection(self):
        self.clear_form_entries()
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
        self.selected_item_data = None
        self.update_status("Form cleared. Ready to add a new component.")
        self.update_image_preview(None) # reset the image as well

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "nothing":
            # clicked on an empty area
            self.clear_form_and_selection()
        # otherwise (on heading, cell, item) on_row_select is already triggered

    def filter_and_search(self):
        search_term = self.search_var.get().lower()
        category = self.category_filter_var.get()
        filtered_data = db_handler.search_components(search_term, category)
        self.refresh_treeview(data=filtered_data)

    def sort_treeview_column(self, col, reverse):
        data = [(self.tree.set(child, col), child) for child in self.tree.get_children('')]
        
        try:
            data.sort(key=lambda item: int(item[0]), reverse=reverse)
        except (ValueError, TypeError):
            data.sort(key=lambda item: str(item[0]).lower(), reverse=reverse)

        for index, (val, child) in enumerate(data):
            self.tree.move(child, '', index)

        self.tree.heading(col, command=lambda: self.sort_treeview_column(col, not reverse))

    def browse_file(self, key):
        if key == 'datasheet':
            filetypes = [("PDF Files", "*.pdf"), ("All files", "*.*")]
        else:
            filetypes = [("Image Files", "*.jpg *.jpeg *.png *.gif"), ("All files", "*.*")]
        
        file_path = filedialog.askopenfilename(title=f"Select {key}", filetypes=filetypes)
        if file_path:
            self.entries[key].delete(0, tk.END)
            self.entries[key].insert(0, file_path)
            if key == "image_path":
                self.update_image_preview(file_path)
    
    # --- YENİ METOTLAR ---
    def adjust_quantity(self, amount):
        """Adjusts the quantity in the form by a given amount and auto-updates."""
        try:
            current_val = int(self.entries["quantity"].get() or 0)
            new_val = max(0, current_val + amount) # Prevent negative quantity
            self.entries["quantity"].delete(0, tk.END)
            self.entries["quantity"].insert(0, str(new_val))
        except (ValueError, KeyError):
            new_val = 1 if amount > 0 else 0
            self.entries["quantity"].delete(0, tk.END)
            self.entries["quantity"].insert(0, str(new_val))
        
        # Auto-save the change if an item is selected
        if self.selected_item_data:
            # Not: update_component fonksiyonunda başarılı güncelleme için 
            # açılır pencereyi kaldırmak, bu özelliği daha akıcı yapar.
            # update_component() içindeki messagebox.showinfo satırını 
            # self.update_status() ile değiştirdim.
            self.update_component()

    def open_datasheet(self, event=None):
        """Opens the selected component's datasheet cross-platform."""
        if not self.selected_item_data: return

        link = self.selected_item_data.get('datasheet', '')
        if not link:
            messagebox.showinfo("No Datasheet", "No datasheet provided for this component.")
            return

        try:
            if link.lower().startswith("http"):
                webbrowser.open(link)
            elif os.path.exists(link):
                # Use the correct command based on the operating system
                current_os = platform.system()
                if current_os == "Windows":
                    os.startfile(os.path.realpath(link))
                elif current_os == "Darwin":  # macOS
                    os.system(f'open "{link}"')
                else:  # Linux and others
                    os.system(f'xdg-open "{link}"')
            else:
                messagebox.showwarning("File Not Found", f"The path could not be found:\n{link}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open the datasheet.\nError: {e}")

    def update_status(self, text):
        self.status_bar.config(text=text)

# --- Application Entry Point ---
if __name__ == "__main__":
    root = tk.Tk()
    
    # Set the theme before creating the app instance
    # Options: "dark" or "light"
    sv_ttk.set_theme("dark")
    
    app = ComponentTrackerApp(root)
    root.mainloop()