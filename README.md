# Component Library Tracker

**Component Library Tracker** is a powerful desktop application built with Python and Tkinter designed to help electronics enthusiasts, hobbyists, and professionals maintain and organize their component inventory with maximum efficiency. This README covers installation, configuration, usage, and development details.

---

## 📖 Table of Contents

1. [Introduction](#Introduction)
2. [Key Features](#key-features)
3. [Technology Stack](#technology-stack)
4. [Project Structure](#project-structure)
5. [Installation & Setup](#installation--setup)
6. [Configuration (`config.py`)](#configuration-configpy)
7. [Database Schema](#database-schema)
8. [User Interface Overview](#user-interface-overview)
9. [Import and Export](#import-and-export)
10. [Chart and Visualization](#chart-and-visualization)
11. [Theming and Dark Mode Support](#theming-and-dark-mode-support)
12. [Keyboard Shortcuts & Context Menu](#keyboard-shortcuts--context-menu)
13. [Error Handling and Validation](#error-handling-and-validation)
14. [Extending the Application](#extending-the-application)
15. [Contributing](#contributing)
16. [License](#license)

---

## 📝 Introduction

Component Library Tracker provides a user-friendly graphical interface for tracking electronic components. Each record can include:

* **Name** (required)
* **Category** (resistor, capacitor, MCU, etc.)
* **Drawer Code** (required, your physical storage label)
* **Quantity**
* **Datasheet** (URL or local PDF path)
* **Description**
* **Image Preview**
* **Date Added**

All data is stored in an SQLite database (`components.db`) that is automatically created and managed by the application. You can search, filter, import/export via CSV or PDF, and visualize your inventory distribution with an integrated pie chart.

---

## 🔑 Key Features

* **CRUD Operations**: Add, update, and delete components
* **Form Dirty-Check**: Warns before losing unsaved changes
* **Search & Filter**: Text search and category filter
* **Import CSV**: Auto-detects delimiter, normalizes headers, skips duplicates
* **Export**: CSV and PDF export via `csv` and `reportlab`
* **Image Preview**: Dynamic resizing with Pillow
* **Theming**: Light/dark themes via `sv_ttk` and Windows dark title bar support
* **Category Chart**: Live pie chart using Matplotlib
* **Keyboard Shortcuts**: Ctrl+N (New), Ctrl+S (Save), Delete (Remove)
* **Context Menu**: Right-click for Edit, Delete, Open Datasheet

---

## 🛠 Technology Stack

* **Python 3.8+**
* **Tkinter** for GUI
* **sv\_ttk** for modern theming
* **Pillow (PIL)** for image handling
* **Matplotlib** for charting
* **SQLite** for embedded database
* **ctypes + Windows DWM API** for dark title bar on Windows
* **pathlib** for cross-platform file paths
* **reportlab** for PDF generation

---

## 📂 Project Structure

```
component-library-tracker/
├── main_app.py        # Main application logic and UI
├── db_handler.py      # SQLite connection, schema creation, CRUD functions
├── export_utils.py    # CSV & PDF export utilities
├── config.py          # Load/save application settings
├── components.db      # SQLite database (auto-created)
├── requirements.txt   # Python dependencies
└── assets/            # Optional assets (icons, sample CSV, etc.)
```

---

## ⚙️ Installation & Setup

1. **Clone the repository**:

   ```bash
   git clone https://github.com/<your-username>/component-library-tracker.git
   cd component-library-tracker
   ```

2. **Create and activate a virtual environment**:

   ```bash
   python -m venv venv  # Create venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**:

   ```bash
   python main_app.py
   ```

> On first launch, `components.db` will be created automatically in the project directory.

---

## ⚙️ Configuration (`config.py`)

The `config.py` module manages persistent user settings in a JSON file (`settings.json`):

* **window\_size**: `(width, height)` of the main window
* **theme**: `'light'` or `'dark'`
* **column\_widths**: dictionary mapping each column to its width in pixels
* **IMAGE\_PREVIEW\_SIZE**: fallback size `(width, height)` for image preview

### Functions

* `load_settings()`: Returns a dict of settings or defaults if none exist
* `save_settings(settings)`: Writes the provided settings dict to disk

Modify defaults in `config.py` to customize behavior before first run.

---

## 🗄️ Database Schema

**Table: `components`**

| Column        | Type    | Description                          |
| ------------- | ------- | ------------------------------------ |
| `id`          | INTEGER | Primary key, auto-increment          |
| `name`        | TEXT    | Component name                       |
| `category`    | TEXT    | Category label                       |
| `drawer_code` | TEXT    | Physical drawer code                 |
| `quantity`    | INTEGER | Quantity in stock                    |
| `datasheet`   | TEXT    | URL or local path to datasheet (PDF) |
| `description` | TEXT    | User-provided description            |
| `image_path`  | TEXT    | Path to an image file                |
| `added_date`  | TEXT    | Date added (`YYYY-MM-DD`)            |

The table is created automatically on application start if it does not already exist.

---

## 🎨 User Interface Overview

* **Top Bar**: Search box, Category filter, Theme selector
* **Treeview**: Displays a list of components with columns for each field (except `id` and `image_path`)
* **Detail Form**: Editable fields for the selected component (or for adding new)
* **Image Preview**: Shows the component’s image scaled to fit
* **Buttons Bar**: Add, Update, Delete, Clear, Import CSV, Export CSV, Export PDF, Category Chart
* **Status Bar**: Displays informational messages and operation results

All elements resize and reposition gracefully using Tkinter layouts.

---

## 📑 Import and Export

### CSV Import

* **Delimiter Detection**: Uses `csv.Sniffer` to detect `, ; \t |`
* **Header Normalization**: Strips spaces, lowercases, replaces spaces with underscores
* **Required Columns**: `name`, `drawer_code`, `quantity` must be present in CSV
* **Duplicate Check**: Rows matching existing `(name, drawer_code)` are skipped
* **Data Conversion**: `quantity` parsed to integer, invalid values default to 0

### CSV Export

* Exports all components to a CSV file with header row

### PDF Export

* Generates a PDF table using `reportlab` with styling and pagination

Exported files are saved in the application directory or a user‑selected folder.

---

## 📊 Chart and Visualization

* **Category Distribution**: A live pie chart showing the percentage breakdown of components by category
* **Matplotlib**: Configured with a dark background (for dark theme) and white text
* **Embedding**: Chart is embedded in a Tkinter `Toplevel` window via `FigureCanvasTkAgg`
* The chart updates in real time when you add, update, or delete components

---

## 🌗 Theming and Dark Mode Support

* **sv\_ttk.set\_theme('light'/'dark')** applies consistent theme across widgets
* **Windows Dark Title Bar**: Uses ctypes to call DWM API and enable immersive dark mode on supported Windows builds
* Users can switch themes at runtime using the Theme dropdown
* Settings are persisted for next launch

---

## ⌨️ Keyboard Shortcuts & Context Menu

* **Ctrl + N**: Clear form and prepare for new component
* **Ctrl + S**: Save/update selected component
* **Delete**: Delete selected component

**Right‑Click Context Menu** on tree rows:

* ✏️ **Edit** (load into form)
* 🗑️ **Delete**
* 📄 **Open Datasheet** (URL or local file)

---

## 🚧 Error Handling and Validation

* **Required Fields**: Name & Drawer Code are enforced; missing fields trigger a warning dialog
* **Quantity Parsing**: Non-numeric entries display an error
* **Database Errors**: Shown via error dialogs on add/update/delete failures
* **Unsaved Changes**: Before clearing or switching selection, user is prompted to save or discard changes

All dialogs use Tkinter `messagebox` for consistent look-and-feel.

---

## 🧩 Extending the Application

To add new features or adapt behavior:

1. **db\_handler.py**: Add new queries or tables
2. **export\_utils.py**: Extend import/export formats (e.g., Excel)
3. **main\_app.py**:

   * Create additional buttons or menu items
   * Add custom validation or automation hooks
   * Integrate with external APIs (e.g., Octopart)
4. **config.py**: Define new settings and persist them

Follow PEP 8 style and include tests or sample data when contributing.

---

## 🤝 Contributing

1. Fork this repo
2. Create a branch: `git checkout -b feature/awesome`
3. Commit your changes: `git commit -m "Add awesome feature"`
4. Push: `git push origin feature/awesome`
5. Open a Pull Request against `main`

Please describe your changes clearly and reference any related issues.

---

## 📜 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

Feel free to use, modify, and distribute this software under the terms of the MIT License.

---

**Thank you for using Component Library Tracker!**

For support or questions, please open an issue on GitHub.
