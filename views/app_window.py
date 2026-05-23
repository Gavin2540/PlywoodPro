import tkinter as tk
import customtkinter
import datetime
import os
from tkinter import messagebox
from database.db import DatabaseManager
import utils.helpers
from utils.updater import check_for_updates_async, download_and_apply_update, CURRENT_VERSION
from utils.backup import export_database, import_database
from customtkinter import filedialog

# Import all view modules lazily or directly
from views.dashboard import DashboardFrame
from views.products import ProductsFrame
from views.purchase_entry import PurchaseEntryFrame
from views.sales_entry import SalesEntryFrame
from views.expenses import ExpensesFrame
from views.daily_report import DailyReportFrame
from views.stock_ledger import StockLedgerFrame

class AppWindow(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # Configure window settings
        self.title("Plywood Pro — Professional Inventory & Margins")
        self.geometry("1150x720")
        self.minimum_size = (1000, 650)
        self.minsize(1000, 650)
        
        # Set app icon
        try:
            icon_path = utils.helpers.get_resource_path("icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        # Set theme colors - custom beautiful dark/light combinations
        customtkinter.set_appearance_mode("dark")  # Default to premium dark mode
        customtkinter.set_default_color_theme("blue")  # Standard theme elements

        # Initialize database path
        DatabaseManager.initialize()

        # Grid configuration
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0) # status bar
        self.grid_columnconfigure(0, weight=0) # sidebar
        self.grid_columnconfigure(1, weight=1) # content

        # Sidebar Frame
        self.sidebar_frame = customtkinter.CTkFrame(self, width=200, corner_radius=0, fg_color="#181715")
        self.sidebar_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar_frame.grid_propagate(False)

        # App Logo / Header
        self.logo_label = customtkinter.CTkLabel(
            self.sidebar_frame, 
            text="Plywood Pro", 
            font=customtkinter.CTkFont(family="Inter", size=22, weight="bold"),
            text_color="#BA7517"
        )
        self.logo_label.pack(pady=(25, 5), padx=20)
        
        self.sub_logo = customtkinter.CTkLabel(
            self.sidebar_frame,
            text=f"SYSTEM v{CURRENT_VERSION}",
            font=customtkinter.CTkFont(family="Inter", size=9, weight="normal"),
            text_color="#8F8B83"
        )
        self.sub_logo.pack(pady=(0, 20))

        # Nav Buttons list
        self.nav_buttons = {}
        
        menu_items = [
            ("Dashboard", "dashboard"),
            ("Products", "products"),
            ("Purchase Entry", "purchase"),
            ("Sales Entry", "sales"),
            ("Expenses", "expenses"),
            ("Daily Report", "report"),
            ("Stock Ledger", "ledger")
        ]

        for display_name, key in menu_items:
            btn = customtkinter.CTkButton(
                self.sidebar_frame,
                text=display_name,
                fg_color="transparent",
                text_color="#C9C5BC",
                hover_color="#36322C",
                height=40,
                corner_radius=6,
                anchor="w",
                font=customtkinter.CTkFont(family="Inter", size=13, weight="normal"),
                command=lambda k=key: self.switch_frame(k)
            )
            btn.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[key] = btn

        # Data Management Buttons at bottom of sidebar
        self.restore_btn = customtkinter.CTkButton(
            self.sidebar_frame, text="⬇ Import Data", 
            fg_color="transparent", hover_color="#36322C", text_color="#C9C5BC", 
            anchor="w", corner_radius=6, command=self._import_data
        )
        self.restore_btn.pack(side="bottom", fill="x", padx=12, pady=(3, 20))

        self.backup_btn = customtkinter.CTkButton(
            self.sidebar_frame, text="⬆ Export Data", 
            fg_color="transparent", hover_color="#36322C", text_color="#C9C5BC", 
            anchor="w", corner_radius=6, command=self._export_data
        )
        self.backup_btn.pack(side="bottom", fill="x", padx=12, pady=3)

        # Content Area
        self.content_frame = customtkinter.CTkFrame(self, corner_radius=0, fg_color="#201F1D")
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Status Bar
        self.status_frame = customtkinter.CTkFrame(self, height=25, corner_radius=0, fg_color="#181715")
        self.status_frame.grid(row=1, column=1, sticky="ew")
        
        self.status_label = customtkinter.CTkLabel(
            self.status_frame,
            text="Ready",
            font=customtkinter.CTkFont(family="Inter", size=11),
            text_color="#8F8B83"
        )
        self.status_label.pack(side="left", padx=15, pady=2)

        self.time_label = customtkinter.CTkLabel(
            self.status_frame,
            text="",
            font=customtkinter.CTkFont(family="Inter", size=11),
            text_color="#8F8B83"
        )
        self.time_label.pack(side="right", padx=15, pady=2)
        self.update_time()

        # Frame Cache
        self.frames = {}
        
        # Default view
        self.switch_frame("dashboard")

        # ── Auto-updater: check for updates silently in background ────────
        # Uses .after() to safely marshal the callback onto the main thread
        check_for_updates_async(
            lambda ver, url: self.after(0, self._on_update_available, ver, url)
        )

    def update_time(self):
        """Dynamic clock inside the status bar."""
        now = datetime.datetime.now().strftime("%d-%b-%Y  %I:%M:%S %p")
        self.time_label.configure(text=now)
        self.after(1000, self.update_time)

    def set_status(self, message):
        """Updates the message in the status bar."""
        self.status_label.configure(text=message)

    def switch_frame(self, frame_key):
        """Swaps right hand views frame based on sidebar clicks."""
        # 1. Update button styling
        for key, btn in self.nav_buttons.items():
            if key == frame_key:
                btn.configure(fg_color="#BA7517", text_color="#FFFFFF")
            else:
                btn.configure(fg_color="transparent", text_color="#C9C5BC")

        # 2. Hide current frame
        if hasattr(self, 'current_frame') and self.current_frame:
            self.current_frame.grid_forget()

        # 3. Create or fetch frame
        if frame_key not in self.frames:
            if frame_key == "dashboard":
                self.frames[frame_key] = DashboardFrame(self.content_frame, self)
            elif frame_key == "products":
                self.frames[frame_key] = ProductsFrame(self.content_frame, self)
            elif frame_key == "purchase":
                self.frames[frame_key] = PurchaseEntryFrame(self.content_frame, self)
            elif frame_key == "sales":
                self.frames[frame_key] = SalesEntryFrame(self.content_frame, self)
            elif frame_key == "expenses":
                self.frames[frame_key] = ExpensesFrame(self.content_frame, self)
            elif frame_key == "report":
                self.frames[frame_key] = DailyReportFrame(self.content_frame, self)
            elif frame_key == "ledger":
                self.frames[frame_key] = StockLedgerFrame(self.content_frame, self)

        self.current_frame = self.frames[frame_key]
        self.current_frame.grid(row=0, column=0, sticky="nsew")

        # 4. Trigger on_show hook to refresh data
        if hasattr(self.current_frame, 'on_show'):
            self.current_frame.on_show()
            
        self.set_status(f"Viewing {frame_key.capitalize()} panel")

    # ── Auto-updater UI callbacks ─────────────────────────────────────────

    def _on_update_available(self, version, download_url):
        """Called on the main thread when a newer release is found."""
        self.set_status(f"🔔 Update available: {version}")
        result = messagebox.askyesno(
            "Update Available",
            f"A new version of PlywoodPro is available!\n\n"
            f"Current version:  v{CURRENT_VERSION}\n"
            f"Latest version:   {version}\n\n"
            f"Would you like to download and install it now?\n"
            f"(The app will restart automatically after updating.)",
            parent=self
        )
        if result:
            self._do_update(download_url)
        else:
            self.set_status(f"Update {version} skipped — you can update later.")

    def _do_update(self, download_url):
        """Downloads the update zip and launches the self-applying batch script."""
        self.set_status("⬇️ Downloading update… please wait.")
        self.update_idletasks()
        try:
            download_and_apply_update(download_url)
            # download_and_apply_update calls sys.exit(0) internally;
            # the lines below are only reached if something goes wrong.
        except Exception as e:
            messagebox.showerror(
                "Update Failed",
                f"Could not apply the update:\n\n{e}\n\n"
                f"You can download it manually from GitHub.",
                parent=self
            )
            self.set_status("Update failed. Continuing with current version.")

    # ── Backup & Restore Callbacks ────────────────────────────────────────

    def _export_data(self):
        filename = filedialog.asksaveasfilename(
            parent=self,
            title="Export Backup",
            defaultextension=".plypro",
            initialfile=f"PlywoodPro_Backup_{datetime.datetime.now().strftime('%Y%m%d')}.plypro",
            filetypes=[("PlywoodPro Backup", "*.plypro"), ("All Files", "*.*")]
        )
        if filename:
            try:
                export_database(filename)
                messagebox.showinfo("Export Successful", f"Backup successfully saved to:\n{filename}", parent=self)
            except Exception as e:
                messagebox.showerror("Export Failed", f"An error occurred while exporting data:\n{str(e)}", parent=self)

    def _import_data(self):
        filename = filedialog.askopenfilename(
            parent=self,
            title="Import Backup",
            filetypes=[("PlywoodPro Backup", "*.plypro"), ("All Files", "*.*")]
        )
        if filename:
            confirm = messagebox.askyesno(
                "Confirm Import",
                "WARNING: Importing a backup will overwrite ALL your current data.\n\nAre you sure you want to proceed?",
                parent=self,
                icon="warning"
            )
            if confirm:
                try:
                    import_database(filename)
                    # Reload all data in-place instead of restarting
                    # 1. Clear all cached frames so they are rebuilt with fresh data
                    for frame in list(self.frames.values()):
                        try:
                            frame.destroy()
                        except Exception:
                            pass
                    self.frames.clear()
                    self.current_frame = None
                    # 2. Re-initialize database connection
                    DatabaseManager.initialize()
                    # 3. Navigate back to dashboard (rebuilds it fresh)
                    self.switch_frame("dashboard")
                    messagebox.showinfo("Import Successful", "Backup imported successfully.\nAll data has been reloaded.", parent=self)
                    self.set_status("Data imported successfully.")
                except Exception as e:
                    messagebox.showerror("Import Failed", f"An error occurred while importing data:\n{str(e)}", parent=self)
