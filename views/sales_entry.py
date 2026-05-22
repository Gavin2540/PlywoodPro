import tkinter as tk
import customtkinter
import datetime
from tkinter import messagebox
import models.product as product_model
import models.sale as sale_model
import models.ledger as ledger_model
from utils.helpers import format_currency, parse_date, format_date

class SalesEntryFrame(customtkinter.CTkFrame):
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
            self, text="Log Plywood Dispatch (Sales)",
            font=customtkinter.CTkFont(family="Inter", size=24, weight="bold"),
            text_color="#FFFFFF"
        )
        self.title_label.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        # 1. Form Frame
        self.form_frame = customtkinter.CTkFrame(self, fg_color="#1F1E1B", border_width=1, border_color="#2D2C28")
        self.form_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 15))
        self._configure_form_grid()

        # Generate inputs
        # Col 0: Product Select + Stock Hint below it
        self.prod_container = customtkinter.CTkFrame(self.form_frame, fg_color="transparent")
        self.prod_container.grid(row=0, column=0, rowspan=2, sticky="ew", padx=15, pady=(15, 15))
        
        customtkinter.CTkLabel(self.prod_container, text="Select Product *", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC", anchor="w").pack(fill="x", pady=(0, 2))
        self.product_combo = customtkinter.CTkComboBox(
            self.prod_container, values=[], width=220, fg_color="#181715", border_color="#36322C", button_color="#BA7517", button_hover_color="#A06312", dropdown_fg_color="#181715",
            command=self.on_product_select, state="readonly"
        )
        self.product_combo.pack(fill="x")
        
        self.stock_hint_lbl = customtkinter.CTkLabel(
            self.prod_container, text="Available Stock: 0 units", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#2ECC71", anchor="w"
        )
        self.stock_hint_lbl.pack(fill="x", pady=(3, 0))

        # Col 1: Date
        customtkinter.CTkLabel(self.form_frame, text="Date (DD-MM-YYYY) *", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=0, column=1, sticky="w", padx=15, pady=(15, 2))
        self.e_date = customtkinter.CTkEntry(self.form_frame, width=120, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        self.e_date.grid(row=1, column=1, sticky="ew", padx=15, pady=(0, 15))

        # Col 2: Qty
        customtkinter.CTkLabel(self.form_frame, text="Quantity *", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=0, column=2, sticky="w", padx=15, pady=(15, 2))
        self.e_qty = customtkinter.CTkEntry(self.form_frame, width=100, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        self.e_qty.grid(row=1, column=2, sticky="ew", padx=15, pady=(0, 15))

        # Col 3: Selling Price
        customtkinter.CTkLabel(self.form_frame, text="Selling Rate (₹/unit) *", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=0, column=3, sticky="w", padx=15, pady=(15, 2))
        self.e_price = customtkinter.CTkEntry(self.form_frame, width=110, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        self.e_price.grid(row=1, column=3, sticky="ew", padx=15, pady=(0, 15))

        # Row 2 Inputs side side
        # Col 0-1: Customer
        customtkinter.CTkLabel(self.form_frame, text="Customer Name", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=2, column=0, sticky="w", padx=15, pady=(0, 2))
        self.e_customer = customtkinter.CTkEntry(self.form_frame, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        self.e_customer.grid(row=3, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 15))

        # Col 2-3: Notes
        customtkinter.CTkLabel(self.form_frame, text="Notes / Remarks", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=2, column=2, sticky="w", padx=15, pady=(0, 2))
        self.e_notes = customtkinter.CTkEntry(self.form_frame, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        self.e_notes.grid(row=3, column=2, columnspan=2, sticky="ew", padx=15, pady=(0, 15))

        # Submit button
        self.submit_btn = customtkinter.CTkButton(
            self.form_frame, text="Record Sale", fg_color="#BA7517", hover_color="#A06312", 
            font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"),
            command=self.submit_sale
        )
        self.submit_btn.grid(row=3, column=4, sticky="ew", padx=15, pady=(0, 15))

        # 2. Today's Log Title Header
        self.log_title = customtkinter.CTkLabel(
            self, text="Today's Dispatch (Sales) Log",
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

        log_headers = ["Product Name", "Customer", "Sale Date", "Quantity", "Rate (₹)", "Total Revenue", "Profit (Margin)", "Actions"]
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
        self.form_frame.grid_columnconfigure(0, weight=3) # Product Container
        self.form_frame.grid_columnconfigure(1, weight=2) # Date
        self.form_frame.grid_columnconfigure(2, weight=2) # Qty
        self.form_frame.grid_columnconfigure(3, weight=2) # Price
        self.form_frame.grid_columnconfigure(4, weight=2) # Button

    def _configure_table_columns(self, frame):
        frame.grid_columnconfigure(0, weight=3) # Name
        frame.grid_columnconfigure(1, weight=2) # Customer
        frame.grid_columnconfigure(2, weight=2) # Date
        frame.grid_columnconfigure(3, weight=1) # Qty
        frame.grid_columnconfigure(4, weight=2) # Rate
        frame.grid_columnconfigure(5, weight=2) # Total
        frame.grid_columnconfigure(6, weight=2) # Margin
        frame.grid_columnconfigure(7, weight=1) # Action

    def on_show(self):
        """Pre-fills fields, re-queries product options and updates stock limits."""
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
            self.stock_hint_lbl.configure(text="Available Stock: 0 units", text_color="#E55039")
            self.e_price.delete(0, tk.END)

        # 3. Refresh today's sales log
        self.refresh_today_log()

    def on_product_select(self, display_name):
        """Auto populates selling price and live stock level when a product is selected."""
        p = self.products_map.get(display_name)
        if p:
            self.e_price.delete(0, tk.END)
            self.e_price.insert(0, f"{p['selling_price']:.2f}")
            
            # Query stock level
            avail = ledger_model.get_current_stock(p['id'])
            unit = p['unit']
            
            # Stock color code: green if healthy, red if low
            is_low = avail <= p['low_stock_threshold']
            color = "#E55039" if is_low else "#2ECC71"
            avail_text = f"{avail:.1f}" if avail % 1 != 0 else f"{int(avail)}"
            
            self.stock_hint_lbl.configure(
                text=f"Available Stock: {avail_text} {unit}",
                text_color=color
            )

    def refresh_today_log(self):
        # Clear rows
        for child in self.scroll_frame.winfo_children():
            child.destroy()

        today_str = datetime.date.today().strftime("%Y-%m-%d")
        sales = sale_model.get_sales_by_date(today_str)

        if not sales:
            no_data = customtkinter.CTkLabel(
                self.scroll_frame, text="No sales recorded today.", font=customtkinter.CTkFont(family="Inter", size=12, slant="italic"), text_color="#8F8B83"
            )
            no_data.grid(row=0, column=0, columnspan=8, pady=20, sticky="ew")
            return

        for idx, item in enumerate(sales):
            row_fg = "#282622" if idx % 2 == 0 else "#1F1E1B"
            row_frame = customtkinter.CTkFrame(self.scroll_frame, fg_color=row_fg, corner_radius=4)
            row_frame.grid(row=idx, column=0, columnspan=8, sticky="ew", pady=2, ipady=4)
            self._configure_table_columns(row_frame)

            # Name
            n_text = f"{item['product_name']} ({item['product_brand']})"
            n_lbl = customtkinter.CTkLabel(row_frame, text=n_text, text_color="#E8E6E3", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"))
            n_lbl.grid(row=0, column=0, sticky="ew", padx=10)

            # Customer
            c_lbl = customtkinter.CTkLabel(row_frame, text=item['customer_name'] or "-", text_color="#C9C5BC", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11))
            c_lbl.grid(row=0, column=1, sticky="ew", padx=10)

            # Date
            d_lbl = customtkinter.CTkLabel(row_frame, text=format_date(item['date']), text_color="#C9C5BC", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11))
            d_lbl.grid(row=0, column=2, sticky="ew", padx=10)

            # Qty
            qty_text = f"{item['qty']:.1f} {item['product_unit']}" if item['qty'] % 1 != 0 else f"{int(item['qty'])} {item['product_unit']}"
            q_lbl = customtkinter.CTkLabel(row_frame, text=qty_text, text_color="#E55039", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"))
            q_lbl.grid(row=0, column=3, sticky="ew", padx=10)

            # Rate
            r_lbl = customtkinter.CTkLabel(row_frame, text=format_currency(item['unit_price']), text_color="#C9C5BC", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11))
            r_lbl.grid(row=0, column=4, sticky="ew", padx=10)

            # Total Revenue
            t_lbl = customtkinter.CTkLabel(row_frame, text=format_currency(item['total_revenue']), text_color="#E8E6E3", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"))
            t_lbl.grid(row=0, column=5, sticky="ew", padx=10)

            # Profit (Margin)
            p_color = "#2ECC71" if item['margin_profit'] >= 0 else "#E55039"
            p_lbl = customtkinter.CTkLabel(row_frame, text=format_currency(item['margin_profit']), text_color=p_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"))
            p_lbl.grid(row=0, column=6, sticky="ew", padx=10)

            # Action Delete
            actions_frame = customtkinter.CTkFrame(row_frame, fg_color="transparent")
            actions_frame.grid(row=0, column=7, sticky="ew", padx=10)

            del_btn = customtkinter.CTkButton(
                actions_frame, text="Delete", width=50, height=20, fg_color="#4D1F1C", hover_color="#A93226", text_color="#E6F2FF",
                font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"),
                command=lambda pid=item['id'], pname=n_text: self.delete_sale_action(pid, pname)
            )
            del_btn.pack(side="left")

    def submit_sale(self):
        disp_name = self.product_combo.get()
        p = self.products_map.get(disp_name)
        
        if not p:
            messagebox.showerror("Validation Error", "Please select a valid product first.")
            return

        date_input = self.e_date.get().strip()
        qty_str = self.e_qty.get().strip()
        rate_str = self.e_price.get().strip()
        customer = self.e_customer.get().strip()
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
            messagebox.showerror("Validation Error", "Selling rate must be a valid positive number.")
            return

        # Check stock capacity
        avail_stock = ledger_model.get_current_stock(p['id'])
        if qty > avail_stock:
            messagebox.showerror(
                "Out of Stock",
                f"Insufficient stock for this sale.\n\nProduct: {p['name']}\nAvailable: {avail_stock:.1f} {p['unit']}\nRequested: {qty:.1f} {p['unit']}"
            )
            return

        # Check ledger is not confirmed for this date
        ledger_row = ledger_model.get_or_create_ledger_row(p['id'], db_date)
        if ledger_row['is_confirmed'] == 1:
            messagebox.showerror("Locked Ledger", f"Stock Ledger has already been locked/confirmed for {date_input}. Cannot add transactions to locked days.")
            return

        # Add Sale
        try:
            sale_model.insert_sale(p['id'], db_date, qty, rate, customer, notes)
            self.controller.set_status(f"Added sale: {qty} {p['unit']} of {p['name']}")
            
            # Reset Qty
            self.e_qty.delete(0, tk.END)
            self.e_notes.delete(0, tk.END)
            self.on_product_select(disp_name) # update stock hint labels
            self.refresh_today_log()
        except Exception as ex:
            messagebox.showerror("Database Error", f"Failed to record sale:\n{ex}")

    def delete_sale_action(self, sale_id, name):
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete this sale entry for '{name}'?")
        if confirm:
            try:
                sale_model.delete_sale(sale_id)
                self.controller.set_status("Deleted sale record.")
                
                # Update stock hints
                disp_name = self.product_combo.get()
                self.on_product_select(disp_name)
                
                self.refresh_today_log()
            except PermissionError as pe:
                messagebox.showerror("Locked Ledger", str(pe))
            except Exception as ex:
                messagebox.showerror("Error", f"Failed to delete sale record:\n{ex}")
