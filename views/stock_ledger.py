import tkinter as tk
import customtkinter
import datetime
from tkinter import messagebox

import models.ledger as ledger_model
import utils.helpers as helpers

class StockLedgerFrame(customtkinter.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        # Grid configuration
        self.grid_rowconfigure(0, weight=0) # Title & date controls
        self.grid_rowconfigure(1, weight=1) # Main list table
        self.grid_columnconfigure(0, weight=1)

        # ----------------------------------------------------
        # ROW 0: Title and Controls Header
        # ----------------------------------------------------
        self.header_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        self.header_frame.grid_columnconfigure(0, weight=1)
        self.header_frame.grid_columnconfigure(1, weight=0)

        # Title Label
        self.title_label = customtkinter.CTkLabel(
            self.header_frame,
            text="Physical Stock Reconciliation Ledger",
            font=customtkinter.CTkFont(family="Inter", size=24, weight="bold"),
            text_color="#FFFFFF"
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        # Controls (Date entry, Refresh, Confirm All)
        self.controls_frame = customtkinter.CTkFrame(self.header_frame, fg_color="#181715", border_width=1, border_color="#2D2C28")
        self.controls_frame.grid(row=0, column=1, sticky="e")

        customtkinter.CTkLabel(
            self.controls_frame, text="Date: ", 
            font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), 
            text_color="#C9C5BC"
        ).pack(side="left", padx=(15, 5), pady=8)

        self.ledger_date_entry = customtkinter.CTkEntry(
            self.controls_frame, width=110, fg_color="#181715", border_color="#36322C",
            text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=12)
        )
        self.ledger_date_entry.pack(side="left", padx=5)
        self.ledger_date_entry.bind("<Return>", lambda e: self.refresh_ledger())

        self.refresh_btn = customtkinter.CTkButton(
            self.controls_frame, text="Refresh", width=70, height=28, fg_color="#36322C", hover_color="#BA7517",
            text_color="#C9C5BC", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"),
            command=self.refresh_ledger
        )
        self.refresh_btn.pack(side="left", padx=5)

        self.confirm_all_btn = customtkinter.CTkButton(
            self.controls_frame, text="Lock All Stocks 🔒", width=130, height=28, fg_color="#BA7517", hover_color="#A06312",
            text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"),
            command=self.confirm_all_stocks
        )
        self.confirm_all_btn.pack(side="left", padx=(5, 15))

        # ----------------------------------------------------
        # ROW 1: Table Frame Container
        # ----------------------------------------------------
        self.table_container = customtkinter.CTkFrame(self, fg_color="#1F1E1B", border_width=1, border_color="#2D2C28")
        self.table_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.table_container.grid_rowconfigure(0, weight=0) # Headers
        self.table_container.grid_rowconfigure(1, weight=1) # Scrollable area
        self.table_container.grid_columnconfigure(0, weight=1)

        # Table Column Headers
        self.headers_frame = customtkinter.CTkFrame(self.table_container, fg_color="#2D2C28", height=35, corner_radius=0)
        self.headers_frame.grid(row=0, column=0, sticky="ew")
        self._configure_table_columns(self.headers_frame)

        # Draw Header Labels
        headers = ["Product Specifications", "Opening Stock", "Purchases (+)", "Sales (-)", "Closing Stock", "Ledger Status", "Actions / Reconcile"]
        for idx, text in enumerate(headers):
            label = customtkinter.CTkLabel(
                self.headers_frame,
                text=text,
                font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"),
                text_color="#C9C5BC",
                anchor="w"
            )
            label.grid(row=0, column=idx, sticky="ew", padx=10, pady=6)

        # Scrollable Data Area
        self.scroll_frame = customtkinter.CTkScrollableFrame(self.table_container, fg_color="transparent", corner_radius=0)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        self._configure_table_columns(self.scroll_frame)

    def _configure_table_columns(self, frame):
        frame.grid_columnconfigure(0, weight=3) # Product Specifications
        frame.grid_columnconfigure(1, weight=1) # Opening Stock
        frame.grid_columnconfigure(2, weight=1) # Purchases
        frame.grid_columnconfigure(3, weight=1) # Sales
        frame.grid_columnconfigure(4, weight=1) # Closing Stock
        frame.grid_columnconfigure(5, weight=2) # Ledger Status
        frame.grid_columnconfigure(6, weight=3) # Actions

    def on_show(self):
        """Hook called when the frame is switched to. Sets today's date and refreshes."""
        today_str = datetime.date.today().strftime("%d-%m-%Y")
        self.ledger_date_entry.delete(0, tk.END)
        self.ledger_date_entry.insert(0, today_str)
        self.refresh_ledger()

    def refresh_ledger(self):
        # Validate and parse date
        date_input = self.ledger_date_entry.get().strip()
        try:
            db_date = helpers.parse_date(date_input)
        except ValueError:
            messagebox.showerror("Invalid Date", "Please enter a valid date in DD-MM-YYYY format.")
            return

        # Clear existing rows
        for child in self.scroll_frame.winfo_children():
            child.destroy()

        try:
            ledger_data = ledger_model.get_ledger_for_date(db_date)
        except Exception as ex:
            messagebox.showerror("Error", f"Failed to retrieve stock ledger:\n{ex}")
            return

        if not ledger_data:
            no_data = customtkinter.CTkLabel(
                self.scroll_frame,
                text="No active products in registry. Visit Products frame to register products.",
                font=customtkinter.CTkFont(family="Inter", size=13, slant="italic"),
                text_color="#8F8B83"
            )
            no_data.grid(row=0, column=0, columnspan=7, pady=40, sticky="ew")
            return

        for idx, row in enumerate(ledger_data):
            row_fg = "#282622" if idx % 2 == 0 else "#1F1E1B"
            
            # Create a subframe for row container
            row_frame = customtkinter.CTkFrame(self.scroll_frame, fg_color=row_fg, corner_radius=4)
            row_frame.grid(row=idx, column=0, columnspan=7, sticky="ew", pady=2, ipady=4)
            self._configure_table_columns(row_frame)

            # Product Specifications
            spec_text = f"{row['product_name']} ({row['product_brand']})\n{row['product_thickness']} • {row['product_size']}"
            p_lbl = customtkinter.CTkLabel(
                row_frame, text=spec_text, text_color="#E8E6E3", anchor="w", justify="left",
                font=customtkinter.CTkFont(family="Inter", size=11, weight="bold")
            )
            p_lbl.grid(row=0, column=0, sticky="ew", padx=10)

            # Opening Stock
            op_text = f"{row['opening_stock']:.1f}" if row['opening_stock'] % 1 != 0 else f"{int(row['opening_stock'])}"
            op_text += f" {row['product_unit']}"
            op_lbl = customtkinter.CTkLabel(row_frame, text=op_text, text_color="#C9C5BC", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11))
            op_lbl.grid(row=0, column=1, sticky="ew", padx=10)

            # Purchases
            pur_text = f"+{row['purchases_qty']:.1f}" if row['purchases_qty'] % 1 != 0 else f"+{int(row['purchases_qty'])}"
            pur_lbl = customtkinter.CTkLabel(
                row_frame, text=pur_text if row['purchases_qty'] > 0 else "-",
                text_color="#2ECC71" if row['purchases_qty'] > 0 else "#8F8B83",
                anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold" if row['purchases_qty'] > 0 else "normal")
            )
            pur_lbl.grid(row=0, column=2, sticky="ew", padx=10)

            # Sales
            sale_text = f"-{row['sales_qty']:.1f}" if row['sales_qty'] % 1 != 0 else f"-{int(row['sales_qty'])}"
            sale_lbl = customtkinter.CTkLabel(
                row_frame, text=sale_text if row['sales_qty'] > 0 else "-",
                text_color="#E55039" if row['sales_qty'] > 0 else "#8F8B83",
                anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold" if row['sales_qty'] > 0 else "normal")
            )
            sale_lbl.grid(row=0, column=3, sticky="ew", padx=10)

            # Closing Stock
            cls_text = f"{row['closing_stock']:.1f}" if row['closing_stock'] % 1 != 0 else f"{int(row['closing_stock'])}"
            cls_text += f" {row['product_unit']}"
            cls_lbl = customtkinter.CTkLabel(row_frame, text=cls_text, text_color="#FFFFFF", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"))
            cls_lbl.grid(row=0, column=4, sticky="ew", padx=10)

            # Ledger Status
            status_frame = customtkinter.CTkFrame(row_frame, fg_color="transparent")
            status_frame.grid(row=0, column=5, sticky="w", padx=10)

            if row['is_confirmed'] == 1:
                status_text = "LOCKED 🔒"
                status_color = "#2ECC71"  # green
            elif row['manual_override'] == 1:
                status_text = "ADJUSTED 🔍"
                status_color = "#3498DB"  # blue
                # Add note tooltip-like label
                if row['override_note']:
                    status_text += f"\n({row['override_note']})"
            else:
                status_text = "UNLOCKED 🔓"
                status_color = "#BA7517"  # amber

            status_lbl = customtkinter.CTkLabel(
                status_frame, text=status_text, text_color=status_color, justify="left",
                font=customtkinter.CTkFont(family="Inter", size=10, weight="bold")
            )
            status_lbl.pack(anchor="w")

            # Actions Column
            actions_frame = customtkinter.CTkFrame(row_frame, fg_color="transparent")
            actions_frame.grid(row=0, column=6, sticky="ew", padx=10)

            if row['is_confirmed'] == 1:
                # Locked: Actions disabled
                locked_lbl = customtkinter.CTkLabel(
                    actions_frame, text="Locked in History", font=customtkinter.CTkFont(family="Inter", size=10, slant="italic"), text_color="#8F8B83"
                )
                locked_lbl.pack(side="left")
            else:
                # Unlocked: Allow Confirm & Override
                confirm_btn = customtkinter.CTkButton(
                    actions_frame, text="Lock", width=50, height=22, fg_color="#27AE60", hover_color="#1E8449",
                    text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"),
                    command=lambda pid=row['product_id'], name=row['product_name']: self.confirm_product_stock(pid, db_date, name)
                )
                confirm_btn.pack(side="left", padx=2)

                override_btn = customtkinter.CTkButton(
                    actions_frame, text="Adjust / Override", width=110, height=22, fg_color="#36322C", hover_color="#BA7517",
                    text_color="#C9C5BC", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"),
                    command=lambda r=row: self.open_override_dialog(r, db_date)
                )
                override_btn.pack(side="left", padx=2)

    def confirm_product_stock(self, product_id, date_str, product_name):
        confirm = messagebox.askyesno(
            "Lock Day End Stock",
            f"Are you sure you want to Lock/Confirm the closing stock for:\n'{product_name}' on {helpers.format_date(date_str)}?\n\nThis will freeze today's Closing Stock and carry it forward as tomorrow's Opening Stock. Backdated changes to this product on this day will be locked."
        )
        if confirm:
            try:
                ledger_model.confirm_ledger_row(product_id, date_str)
                self.controller.set_status(f"Locked ledger for {product_name}")
                self.refresh_ledger()
            except Exception as ex:
                messagebox.showerror("Error", f"Failed to lock stock ledger row:\n{ex}")

    def confirm_all_stocks(self):
        date_input = self.ledger_date_entry.get().strip()
        try:
            db_date = helpers.parse_date(date_input)
        except ValueError:
            messagebox.showerror("Invalid Date", "Please enter a valid date in DD-MM-YYYY format.")
            return

        confirm = messagebox.askyesno(
            "Lock All Closing Stocks",
            f"Are you sure you want to lock the Closing Stock for ALL active products on {helpers.format_date(db_date)}?\n\nThis locks all inventory additions/deductions for this day and establishes tomorrow's opening stocks."
        )
        if confirm:
            try:
                self.controller.set_status("Locking all products...")
                ledger_model.confirm_all_ledger_rows(db_date)
                self.controller.set_status(f"Locked all stocks on {helpers.format_date(db_date)}")
                self.refresh_ledger()
                messagebox.showinfo("Success", f"All active stocks successfully locked for {helpers.format_date(db_date)}.")
            except Exception as ex:
                self.controller.set_status("Failed locking all stocks")
                messagebox.showerror("Error", f"Failed to lock stocks:\n{ex}")

    def open_override_dialog(self, ledger_row, date_str):
        OverrideLedgerDialog(self, ledger_row, date_str, callback=self.refresh_ledger)


class OverrideLedgerDialog(customtkinter.CTkToplevel):
    def __init__(self, parent, ledger_row, date_str, callback=None):
        super().__init__(parent)
        self.parent = parent
        self.ledger_row = ledger_row
        self.date_str = date_str
        self.callback = callback
        
        self.title("Reconcile Physical Stock Override")
        self.geometry("420x350")
        self.resizable(False, False)
        self.configure(fg_color="#201F1D")
        self.transient(parent)
        self.grab_set()

        # Title / Icon
        self.title_lbl = customtkinter.CTkLabel(
            self, text="Adjust / Override Stock Level",
            font=customtkinter.CTkFont(family="Inter", size=18, weight="bold"), text_color="#BA7517"
        )
        self.title_lbl.pack(pady=(20, 10))

        # Date sub-title
        self.date_lbl = customtkinter.CTkLabel(
            self, text=f"Date: {helpers.format_date(date_str)}",
            font=customtkinter.CTkFont(family="Inter", size=12, slant="italic"), text_color="#8F8B83"
        )
        self.date_lbl.pack(pady=(0, 15))

        # Buttons (packed first with side="bottom" so they are always visible)
        btn_container = customtkinter.CTkFrame(self, fg_color="transparent")
        btn_container.pack(fill="x", side="bottom", pady=20, padx=30)

        cancel_btn = customtkinter.CTkButton(
            btn_container, text="Cancel", fg_color="#36322C", hover_color="#4D4942", font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"),
            command=self.destroy
        )
        cancel_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        save_btn = customtkinter.CTkButton(
            btn_container, text="Save Adjustments", fg_color="#BA7517", hover_color="#A06312", font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"),
            command=self.save_override
        )
        save_btn.pack(side="right", fill="x", expand=True, padx=(8, 0))

        # Fields container (packed in the remaining space)
        form = customtkinter.CTkFrame(self, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=30, pady=5)

        # Product Info label (read-only specs)
        spec_text = f"Product: {ledger_row['product_name']} ({ledger_row['product_brand']})\nSpecs: {ledger_row['product_thickness']} · {ledger_row['product_size']}"
        self.p_info = customtkinter.CTkLabel(
            form, text=spec_text, font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"),
            text_color="#FFFFFF", anchor="w", justify="left"
        )
        self.p_info.pack(fill="x", pady=(0, 15))

        # Physical Quantity input
        customtkinter.CTkLabel(
            form, text=f"Actual Physical Stock Quantity ({ledger_row['product_unit']}) *",
            font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC", anchor="w"
        ).pack(fill="x", pady=(0, 2))
        
        self.e_qty = customtkinter.CTkEntry(
            form, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=13)
        )
        self.e_qty.insert(0, f"{ledger_row['closing_stock']:.1f}" if ledger_row['closing_stock'] % 1 != 0 else f"{int(ledger_row['closing_stock'])}")
        self.e_qty.pack(fill="x", pady=(0, 15))

        # Note / Reason explanation
        customtkinter.CTkLabel(
            form, text="Reconciliation Note / Reason for Adjustment *",
            font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC", anchor="w"
        ).pack(fill="x", pady=(0, 2))
        
        self.e_note = customtkinter.CTkEntry(
            form, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=12)
        )
        self.e_note.insert(0, ledger_row['override_note'] or "Physical stock count verification")
        self.e_note.pack(fill="x")

    def save_override(self):
        qty_str = self.e_qty.get().strip()
        note = self.e_note.get().strip()

        if not qty_str or not note:
            messagebox.showerror("Validation Error", "All fields marked with '*' are required.")
            return

        try:
            qty = float(qty_str)
            if qty < 0:
                raise ValueError("Quantity cannot be negative.")
        except ValueError:
            messagebox.showerror("Validation Error", "Quantity must be a valid positive number.")
            return

        try:
            ledger_model.override_ledger_row(self.ledger_row['product_id'], self.date_str, qty, note)
            self.parent.controller.set_status(f"Adjusted closing stock of {self.ledger_row['product_name']} to {qty_str}")
            if self.callback:
                self.callback()
            self.destroy()
        except Exception as ex:
            messagebox.showerror("Error", f"Failed to save manual override:\n{ex}")
