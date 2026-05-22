import tkinter as tk
import customtkinter
import datetime
from tkinter import messagebox
import models.product as product_model
import models.purchase as purchase_model
import models.ledger as ledger_model
from utils.helpers import format_currency, parse_date, format_date

class PurchaseEntryFrame(customtkinter.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.products_map = {} # maps display name -> product dict

        # Grid configuration
        self.grid_rowconfigure(0, weight=0) # Title
        self.grid_rowconfigure(1, weight=0) # Form Frame
        self.grid_rowconfigure(2, weight=0) # Today's Log Title
        self.grid_rowconfigure(3, weight=1) # Scrollable Log Table
        self.grid_columnconfigure(0, weight=1)

        # Title
        self.title_label = customtkinter.CTkLabel(
            self, text="Log Plywood Intake (Purchase)",
            font=customtkinter.CTkFont(family="Inter", size=24, weight="bold"),
            text_color="#FFFFFF"
        )
        self.title_label.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        # 1. Form Frame
        self.form_frame = customtkinter.CTkFrame(self, fg_color="#1F1E1B", border_width=1, border_color="#2D2C28")
        self.form_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 15))
        self._configure_form_grid()

        # Generate inputs
        # Col 0: Product Select
        customtkinter.CTkLabel(self.form_frame, text="Select Product *", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=0, column=0, sticky="w", padx=15, pady=(15, 2))
        self.product_combo = customtkinter.CTkComboBox(
            self.form_frame, values=[], width=220, fg_color="#181715", border_color="#36322C", button_color="#BA7517", button_hover_color="#A06312", dropdown_fg_color="#181715",
            command=self.on_product_select, state="readonly"
        )
        self.product_combo.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 15))

        # Col 1: Date
        customtkinter.CTkLabel(self.form_frame, text="Date (DD-MM-YYYY) *", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=0, column=1, sticky="w", padx=15, pady=(15, 2))
        self.e_date = customtkinter.CTkEntry(self.form_frame, width=120, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        self.e_date.grid(row=1, column=1, sticky="ew", padx=15, pady=(0, 15))

        # Col 2: Qty
        customtkinter.CTkLabel(self.form_frame, text="Quantity *", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=0, column=2, sticky="w", padx=15, pady=(15, 2))
        self.e_qty = customtkinter.CTkEntry(self.form_frame, width=100, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        self.e_qty.grid(row=1, column=2, sticky="ew", padx=15, pady=(0, 15))

        # Col 3: Price
        customtkinter.CTkLabel(self.form_frame, text="Purchase Rate (₹/unit) *", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=0, column=3, sticky="w", padx=15, pady=(15, 2))
        self.e_price = customtkinter.CTkEntry(self.form_frame, width=110, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        self.e_price.grid(row=1, column=3, sticky="ew", padx=15, pady=(0, 15))

        # Row 2 Inputs side side
        # Col 0-1: Supplier
        customtkinter.CTkLabel(self.form_frame, text="Supplier Name", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=2, column=0, sticky="w", padx=15, pady=(0, 2))
        self.e_supplier = customtkinter.CTkEntry(self.form_frame, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        self.e_supplier.grid(row=3, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 15))

        # Col 2-3: Notes
        customtkinter.CTkLabel(self.form_frame, text="Notes / Remarks", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=2, column=2, sticky="w", padx=15, pady=(0, 2))
        self.e_notes = customtkinter.CTkEntry(self.form_frame, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        self.e_notes.grid(row=3, column=2, columnspan=2, sticky="ew", padx=15, pady=(0, 15))

        # Submit button spanning right
        self.submit_btn = customtkinter.CTkButton(
            self.form_frame, text="Record Intake", fg_color="#BA7517", hover_color="#A06312", 
            font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"),
            command=self.submit_purchase
        )
        self.submit_btn.grid(row=3, column=4, sticky="ew", padx=15, pady=(0, 15))

        # 2. Today's Log Title Header
        self.log_title = customtkinter.CTkLabel(
            self, text="Today's Intake Log",
            font=customtkinter.CTkFont(family="Inter", size=16, weight="bold"),
            text_color="#C9C5BC"
        )
        self.log_title.grid(row=2, column=0, sticky="w", padx=20, pady=(5, 5))

        # 3. Log Table Container
        self.table_container = customtkinter.CTkFrame(self, fg_color="#1F1E1B", border_width=1, border_color="#2D2C28")
        self.table_container.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.table_container.grid_rowconfigure(0, weight=0) # headers
        self.table_container.grid_rowconfigure(1, weight=1) # scroll
        self.table_container.grid_columnconfigure(0, weight=1)

        # Log Table Headers
        self.headers_frame = customtkinter.CTkFrame(self.table_container, fg_color="#2D2C28", height=30, corner_radius=0)
        self.headers_frame.grid(row=0, column=0, sticky="ew")
        self._configure_table_columns(self.headers_frame)

        log_headers = ["Product Name", "Supplier", "Intake Date", "Quantity", "Rate (₹)", "Total Cost", "Actions"]
        for idx, text in enumerate(log_headers):
            label = customtkinter.CTkLabel(
                self.headers_frame, text=text, font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#C9C5BC", anchor="w"
            )
            label.grid(row=0, column=idx, sticky="ew", padx=10, pady=5)

        # Log Scrollable rows
        self.scroll_frame = customtkinter.CTkScrollableFrame(self.table_container, fg_color="transparent", corner_radius=0)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        self._configure_table_columns(self.scroll_frame)

    def _configure_form_grid(self):
        self.form_frame.grid_columnconfigure(0, weight=3) # Product Combo
        self.form_frame.grid_columnconfigure(1, weight=2) # Date
        self.form_frame.grid_columnconfigure(2, weight=2) # Qty
        self.form_frame.grid_columnconfigure(3, weight=2) # Unit Price
        self.form_frame.grid_columnconfigure(4, weight=2) # Button

    def _configure_table_columns(self, frame):
        frame.grid_columnconfigure(0, weight=3) # Name
        frame.grid_columnconfigure(1, weight=2) # Supplier
        frame.grid_columnconfigure(2, weight=2) # Date
        frame.grid_columnconfigure(3, weight=1) # Qty
        frame.grid_columnconfigure(4, weight=2) # Rate
        frame.grid_columnconfigure(5, weight=2) # Total
        frame.grid_columnconfigure(6, weight=1) # Action (Delete)

    def on_show(self):
        """Pre-fills fields and re-queries product options."""
        # 1. Reset date to today
        today_str = datetime.date.today().strftime("%d-%m-%Y")
        self.e_date.delete(0, tk.END)
        self.e_date.insert(0, today_str)

        # 2. Populate product list combo
        self.products = product_model.get_active_products()
        self.products_map.clear()
        
        display_names = []
        for p in self.products:
            name_str = f"{p['name']} ({p['brand']} · {p['thickness']} · {p['size']})"
            display_names.append(name_str)
            self.products_map[name_str] = p

        self.product_combo.configure(values=display_names)
        if display_names:
            self.product_combo.set(display_names[0])
            self.on_product_select(display_names[0])
        else:
            self.product_combo.set("No Products Available")
            self.e_price.delete(0, tk.END)

        # 3. Refresh today's purchase log
        self.refresh_today_log()

    def on_product_select(self, display_name):
        """Auto populates default purchase price when a product is selected."""
        p = self.products_map.get(display_name)
        if p:
            self.e_price.delete(0, tk.END)
            self.e_price.insert(0, f"{p['purchase_price']:.2f}")

    def refresh_today_log(self):
        # Clear rows
        for child in self.scroll_frame.winfo_children():
            child.destroy()

        today_str = datetime.date.today().strftime("%Y-%m-%d")
        purchases = purchase_model.get_purchases_by_date(today_str)

        if not purchases:
            no_data = customtkinter.CTkLabel(
                self.scroll_frame, text="No stock intake recorded today.", font=customtkinter.CTkFont(family="Inter", size=12, slant="italic"), text_color="#8F8B83"
            )
            no_data.grid(row=0, column=0, columnspan=7, pady=20, sticky="ew")
            return

        for idx, item in enumerate(purchases):
            row_fg = "#282622" if idx % 2 == 0 else "#1F1E1B"
            row_frame = customtkinter.CTkFrame(self.scroll_frame, fg_color=row_fg, corner_radius=4)
            row_frame.grid(row=idx, column=0, columnspan=7, sticky="ew", pady=2, ipady=4)
            self._configure_table_columns(row_frame)

            # Name
            n_text = f"{item['product_name']} ({item['product_brand']})"
            n_lbl = customtkinter.CTkLabel(row_frame, text=n_text, text_color="#E8E6E3", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"))
            n_lbl.grid(row=0, column=0, sticky="ew", padx=10)

            # Supplier
            s_lbl = customtkinter.CTkLabel(row_frame, text=item['supplier_name'] or "-", text_color="#C9C5BC", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11))
            s_lbl.grid(row=0, column=1, sticky="ew", padx=10)

            # Date
            d_lbl = customtkinter.CTkLabel(row_frame, text=format_date(item['date']), text_color="#C9C5BC", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11))
            d_lbl.grid(row=0, column=2, sticky="ew", padx=10)

            # Qty
            qty_text = f"{item['qty']:.1f} {item['product_unit']}" if item['qty'] % 1 != 0 else f"{int(item['qty'])} {item['product_unit']}"
            q_lbl = customtkinter.CTkLabel(row_frame, text=qty_text, text_color="#2ECC71", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"))
            q_lbl.grid(row=0, column=3, sticky="ew", padx=10)

            # Rate
            r_lbl = customtkinter.CTkLabel(row_frame, text=format_currency(item['unit_price']), text_color="#C9C5BC", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11))
            r_lbl.grid(row=0, column=4, sticky="ew", padx=10)

            # Total
            t_lbl = customtkinter.CTkLabel(row_frame, text=format_currency(item['total_cost']), text_color="#E8E6E3", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"))
            t_lbl.grid(row=0, column=5, sticky="ew", padx=10)

            # Action Delete
            actions_frame = customtkinter.CTkFrame(row_frame, fg_color="transparent")
            actions_frame.grid(row=0, column=6, sticky="ew", padx=10)

            del_btn = customtkinter.CTkButton(
                actions_frame, text="Delete", width=50, height=20, fg_color="#4D1F1C", hover_color="#A93226", text_color="#E6F2FF",
                font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"),
                command=lambda pid=item['id'], pname=n_text: self.delete_purchase_action(pid, pname)
            )
            del_btn.pack(side="left")

    def submit_purchase(self):
        disp_name = self.product_combo.get()
        p = self.products_map.get(disp_name)
        
        if not p:
            messagebox.showerror("Validation Error", "Please select a valid product first.")
            return

        date_input = self.e_date.get().strip()
        qty_str = self.e_qty.get().strip()
        rate_str = self.e_price.get().strip()
        supplier = self.e_supplier.get().strip()
        notes = self.e_notes.get().strip()

        # Validations
        if not date_input or not qty_str or not rate_str:
            messagebox.showerror("Validation Error", "All fields marked with '*' are required.")
            return

        try:
            db_date = parse_date(date_input)
        except ValueError:
            messagebox.showerror("Validation Error", "Date must be in DD-MM-YYYY or YYYY-MM-DD format.")
            return

        try:
            qty = float(qty_str)
            if qty <= 0:
                raise ValueError("Quantity must be greater than zero.")
        except ValueError:
            messagebox.showerror("Validation Error", "Quantity must be a valid positive number.")
            return

        try:
            rate = float(rate_str)
            if rate < 0:
                raise ValueError("Rate cannot be negative.")
        except ValueError:
            messagebox.showerror("Validation Error", "Purchase rate must be a valid positive number.")
            return

        # Check ledger is not confirmed for this date
        ledger_row = ledger_model.get_or_create_ledger_row(p['id'], db_date)
        if ledger_row['is_confirmed'] == 1:
            messagebox.showerror("Locked Ledger", f"Stock Ledger has already been locked/confirmed for {date_input}. Cannot add transactions to locked days.")
            return

        # Add Intake
        try:
            purchase_model.insert_purchase(p['id'], db_date, qty, rate, supplier, notes)
            self.controller.set_status(f"Added purchase: {qty} {p['unit']} of {p['name']}")
            
            # Reset Qty
            self.e_qty.delete(0, tk.END)
            self.e_notes.delete(0, tk.END)
            self.refresh_today_log()
        except Exception as ex:
            messagebox.showerror("Database Error", f"Failed to record purchase:\n{ex}")

    def delete_purchase_action(self, purchase_id, name):
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete this purchase entry for '{name}'?")
        if confirm:
            try:
                purchase_model.delete_purchase(purchase_id)
                self.controller.set_status("Deleted purchase record.")
                self.refresh_today_log()
            except PermissionError as pe:
                messagebox.showerror("Locked Ledger", str(pe))
            except Exception as ex:
                messagebox.showerror("Error", f"Failed to delete purchase record:\n{ex}")
