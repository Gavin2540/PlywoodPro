import tkinter as tk
import customtkinter
import datetime
from tkinter import messagebox
import models.product as product_model
import models.purchase as purchase_model
import models.ledger as ledger_model
from utils.helpers import format_currency, parse_date, format_date
from views.products import ProductFormDialog

class PurchaseEntryFrame(customtkinter.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.products_map = {} # maps display name -> product dict
        self.item_rows = []

        # Grid configuration
        self.grid_rowconfigure(0, weight=0) # Title
        self.grid_rowconfigure(1, weight=0) # Shared Form (Date, Supplier, Notes)
        self.grid_rowconfigure(2, weight=1) # Dynamic Items Container (Scrollable)
        self.grid_rowconfigure(3, weight=0) # Action Buttons
        self.grid_rowconfigure(4, weight=0) # Today's Log Title
        self.grid_rowconfigure(5, weight=1) # Today's Log Scrollable
        self.grid_columnconfigure(0, weight=1)

        # Title
        self.title_label = customtkinter.CTkLabel(
            self, text="Log Plywood Intake (Purchase)",
            font=customtkinter.CTkFont(family="Inter", size=24, weight="bold"),
            text_color="#FFFFFF"
        )
        self.title_label.grid(row=0, column=0, sticky="w", padx=20, pady=(15, 5))

        # 1. Shared Fields Frame
        self.shared_frame = customtkinter.CTkFrame(self, fg_color="#1F1E1B", border_width=1, border_color="#2D2C28")
        self.shared_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        self.shared_frame.grid_columnconfigure(0, weight=1)
        self.shared_frame.grid_columnconfigure(1, weight=1)
        self.shared_frame.grid_columnconfigure(2, weight=2)

        # Date
        customtkinter.CTkLabel(self.shared_frame, text="Intake Date (DD-MM-YYYY) *", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=0, column=0, sticky="w", padx=15, pady=(10, 2))
        self.e_date = customtkinter.CTkEntry(self.shared_frame, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        self.e_date.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))

        # Supplier
        customtkinter.CTkLabel(self.shared_frame, text="Supplier Name", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=0, column=1, sticky="w", padx=15, pady=(10, 2))
        self.e_supplier = customtkinter.CTkEntry(self.shared_frame, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        self.e_supplier.grid(row=1, column=1, sticky="ew", padx=15, pady=(0, 10))

        # Notes
        customtkinter.CTkLabel(self.shared_frame, text="Batch Notes / Remarks", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=0, column=2, sticky="w", padx=15, pady=(10, 2))
        self.e_notes = customtkinter.CTkEntry(self.shared_frame, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        self.e_notes.grid(row=1, column=2, sticky="ew", padx=15, pady=(0, 10))

        # 2. Dynamic Items Scrollable Frame
        self.items_container = customtkinter.CTkScrollableFrame(self, fg_color="#1F1E1B", border_width=1, border_color="#2D2C28", height=180)
        self.items_container.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
        
        # Headers for dynamic items
        headers_frame = customtkinter.CTkFrame(self.items_container, fg_color="transparent")
        headers_frame.pack(fill="x", pady=(0, 5))
        headers_frame.grid_columnconfigure(0, weight=4) # Product
        headers_frame.grid_columnconfigure(1, weight=1) # + New
        headers_frame.grid_columnconfigure(2, weight=2) # Qty
        headers_frame.grid_columnconfigure(3, weight=2) # Rate
        headers_frame.grid_columnconfigure(4, weight=1) # Remove
        
        customtkinter.CTkLabel(headers_frame, text="Product *", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#C9C5BC", anchor="w").grid(row=0, column=0, sticky="w", padx=5)
        customtkinter.CTkLabel(headers_frame, text="Quantity *", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#C9C5BC", anchor="w").grid(row=0, column=2, sticky="w", padx=5)
        customtkinter.CTkLabel(headers_frame, text="Rate (₹) *", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#C9C5BC", anchor="w").grid(row=0, column=3, sticky="w", padx=5)

        # 3. Actions Frame
        self.actions_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.actions_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 15))
        
        self.add_row_btn = customtkinter.CTkButton(
            self.actions_frame, text="+ Add Another Product", fg_color="#36322C", hover_color="#4D4942", 
            font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), command=self.add_item_row
        )
        self.add_row_btn.pack(side="left")

        self.submit_btn = customtkinter.CTkButton(
            self.actions_frame, text="Record Intake (All Items)", fg_color="#BA7517", hover_color="#A06312", 
            font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"), command=self.submit_purchase
        )
        self.submit_btn.pack(side="right")

        # 4. Today's Log
        self.log_title = customtkinter.CTkLabel(
            self, text="Today's Intake Log",
            font=customtkinter.CTkFont(family="Inter", size=16, weight="bold"), text_color="#C9C5BC"
        )
        self.log_title.grid(row=4, column=0, sticky="w", padx=20, pady=(0, 5))

        self.log_container = customtkinter.CTkFrame(self, fg_color="#1F1E1B", border_width=1, border_color="#2D2C28")
        self.log_container.grid(row=5, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.log_container.grid_rowconfigure(0, weight=0)
        self.log_container.grid_rowconfigure(1, weight=1)
        self.log_container.grid_columnconfigure(0, weight=1)

        log_headers_frame = customtkinter.CTkFrame(self.log_container, fg_color="#2D2C28", height=30, corner_radius=0)
        log_headers_frame.grid(row=0, column=0, sticky="ew")
        self._configure_log_columns(log_headers_frame)

        for idx, text in enumerate(["Product Name", "Supplier", "Intake Date", "Quantity", "Rate (₹)", "Total Cost", "Actions"]):
            customtkinter.CTkLabel(log_headers_frame, text=text, font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#C9C5BC", anchor="w").grid(row=0, column=idx, sticky="ew", padx=10, pady=5)

        self.log_scroll = customtkinter.CTkScrollableFrame(self.log_container, fg_color="transparent", corner_radius=0)
        self.log_scroll.grid(row=1, column=0, sticky="nsew")
        self._configure_log_columns(self.log_scroll)

        # Initialize with one empty row
        self.add_item_row()

    def _configure_log_columns(self, frame):
        frame.grid_columnconfigure(0, weight=3) # Name
        frame.grid_columnconfigure(1, weight=2) # Supplier
        frame.grid_columnconfigure(2, weight=2) # Date
        frame.grid_columnconfigure(3, weight=1) # Qty
        frame.grid_columnconfigure(4, weight=2) # Rate
        frame.grid_columnconfigure(5, weight=2) # Total
        frame.grid_columnconfigure(6, weight=1) # Action

    def add_item_row(self):
        row_frame = customtkinter.CTkFrame(self.items_container, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)
        row_frame.grid_columnconfigure(0, weight=4) # Product combo
        row_frame.grid_columnconfigure(1, weight=1) # New btn
        row_frame.grid_columnconfigure(2, weight=2) # Qty
        row_frame.grid_columnconfigure(3, weight=2) # Rate
        row_frame.grid_columnconfigure(4, weight=1) # Remove

        row_obj = {'frame': row_frame}

        def on_prod_select(choice, r=row_obj):
            p = self.products_map.get(choice)
            if p:
                r['price'].delete(0, tk.END)
                r['price'].insert(0, f"{p['purchase_price']:.2f}")

        # Product Combo
        combo = customtkinter.CTkComboBox(
            row_frame, values=list(self.products_map.keys()), fg_color="#181715", border_color="#36322C", 
            button_color="#BA7517", button_hover_color="#A06312", dropdown_fg_color="#181715",
            state="readonly", command=on_prod_select
        )
        combo.grid(row=0, column=0, sticky="ew", padx=(5, 2))
        if self.products_map:
            first_val = list(self.products_map.keys())[0]
            combo.set(first_val)
        else:
            combo.set("No Products")
        row_obj['combo'] = combo

        # + New Button
        new_btn = customtkinter.CTkButton(
            row_frame, text="+ New", width=50, fg_color="#453d33", hover_color="#5a5144", text_color="#FFFFFF",
            font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"),
            command=lambda r=row_obj: self.open_new_product_dialog(r)
        )
        new_btn.grid(row=0, column=1, sticky="w", padx=2)

        # Qty
        qty = customtkinter.CTkEntry(row_frame, width=80, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        qty.grid(row=0, column=2, sticky="ew", padx=5)
        row_obj['qty'] = qty

        # Rate
        price = customtkinter.CTkEntry(row_frame, width=90, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        price.grid(row=0, column=3, sticky="ew", padx=5)
        row_obj['price'] = price
        
        if self.products_map and combo.get() in self.products_map:
            on_prod_select(combo.get())

        # Remove
        rem_btn = customtkinter.CTkButton(
            row_frame, text="✕", width=30, fg_color="#4D1F1C", hover_color="#A93226", text_color="#FFFFFF",
            command=lambda r=row_obj: self.remove_item_row(r)
        )
        rem_btn.grid(row=0, column=4, sticky="e", padx=(2, 5))

        self.item_rows.append(row_obj)
        self.update_remove_buttons()

    def remove_item_row(self, row_obj):
        if len(self.item_rows) > 1:
            row_obj['frame'].destroy()
            self.item_rows.remove(row_obj)
            self.update_remove_buttons()

    def update_remove_buttons(self):
        # Disable remove button if only 1 row exists
        state = "normal" if len(self.item_rows) > 1 else "disabled"
        for row in self.item_rows:
            btns = [w for w in row['frame'].winfo_children() if isinstance(w, customtkinter.CTkButton) and w.cget("text") == "✕"]
            if btns:
                btns[0].configure(state=state)

    def refresh_products_list(self, auto_select_combo=None):
        self.products = product_model.get_active_products()
        self.products_map.clear()
        display_names = []
        for p in self.products:
            name_str = f"{p['name']} ({p['brand']} · {p['thickness']} · {p['size']})"
            display_names.append(name_str)
            self.products_map[name_str] = p

        # Update all combos in all rows
        for row in self.item_rows:
            current_val = row['combo'].get()
            row['combo'].configure(values=display_names)
            if display_names:
                if current_val not in display_names:
                    # Select last added (assuming it's new) for the active combo if requested
                    if auto_select_combo and row['combo'] == auto_select_combo:
                        row['combo'].set(display_names[-1])
                        # Trigger rate update
                        p = self.products_map[display_names[-1]]
                        row['price'].delete(0, tk.END)
                        row['price'].insert(0, f"{p['purchase_price']:.2f}")
                    else:
                        row['combo'].set(display_names[0])
            else:
                row['combo'].set("No Products")

    def open_new_product_dialog(self, target_row):
        def on_added():
            self.refresh_products_list(auto_select_combo=target_row['combo'])
        
        ProductFormDialog(self, "Add New Product", callback=on_added)

    def on_show(self):
        # Reset date to today
        self.e_date.delete(0, tk.END)
        self.e_date.insert(0, datetime.date.today().strftime("%d-%m-%Y"))
        self.refresh_products_list()
        self.refresh_today_log()

    def refresh_today_log(self):
        for child in self.log_scroll.winfo_children():
            child.destroy()

        today_str = datetime.date.today().strftime("%Y-%m-%d")
        purchases = purchase_model.get_purchases_by_date(today_str)

        if not purchases:
            no_data = customtkinter.CTkLabel(
                self.log_scroll, text="No stock intake recorded today.", font=customtkinter.CTkFont(family="Inter", size=12, slant="italic"), text_color="#8F8B83"
            )
            no_data.grid(row=0, column=0, columnspan=7, pady=20, sticky="ew")
            return

        for idx, item in enumerate(purchases):
            row_fg = "#282622" if idx % 2 == 0 else "#1F1E1B"
            row_frame = customtkinter.CTkFrame(self.log_scroll, fg_color=row_fg, corner_radius=4)
            row_frame.grid(row=idx, column=0, columnspan=7, sticky="ew", pady=2, ipady=4)
            self._configure_log_columns(row_frame)

            n_text = f"{item['product_name']} ({item['product_brand']})"
            customtkinter.CTkLabel(row_frame, text=n_text, text_color="#E8E6E3", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold")).grid(row=0, column=0, sticky="ew", padx=10)
            customtkinter.CTkLabel(row_frame, text=item['supplier_name'] or "-", text_color="#C9C5BC", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11)).grid(row=0, column=1, sticky="ew", padx=10)
            customtkinter.CTkLabel(row_frame, text=format_date(item['date']), text_color="#C9C5BC", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11)).grid(row=0, column=2, sticky="ew", padx=10)
            
            qty_text = f"{item['qty']:.1f} {item['product_unit']}" if item['qty'] % 1 != 0 else f"{int(item['qty'])} {item['product_unit']}"
            customtkinter.CTkLabel(row_frame, text=qty_text, text_color="#2ECC71", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold")).grid(row=0, column=3, sticky="ew", padx=10)
            customtkinter.CTkLabel(row_frame, text=format_currency(item['unit_price']), text_color="#C9C5BC", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11)).grid(row=0, column=4, sticky="ew", padx=10)
            customtkinter.CTkLabel(row_frame, text=format_currency(item['total_cost']), text_color="#E8E6E3", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold")).grid(row=0, column=5, sticky="ew", padx=10)

            actions_frame = customtkinter.CTkFrame(row_frame, fg_color="transparent")
            actions_frame.grid(row=0, column=6, sticky="ew", padx=10)
            del_btn = customtkinter.CTkButton(
                actions_frame, text="Delete", width=50, height=20, fg_color="#4D1F1C", hover_color="#A93226", text_color="#E6F2FF",
                font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"),
                command=lambda pid=item['id'], pname=n_text: self.delete_purchase_action(pid, pname)
            )
            del_btn.pack(side="left")

    def submit_purchase(self):
        date_input = self.e_date.get().strip()
        supplier = self.e_supplier.get().strip()
        notes = self.e_notes.get().strip()

        if not date_input:
            messagebox.showerror("Validation Error", "Date is required.")
            return

        try:
            db_date = parse_date(date_input)
        except ValueError:
            messagebox.showerror("Validation Error", "Date must be in DD-MM-YYYY or YYYY-MM-DD format.")
            return

        # Validate all rows first
        valid_items = []
        for i, row in enumerate(self.item_rows):
            disp_name = row['combo'].get()
            p = self.products_map.get(disp_name)
            if not p:
                messagebox.showerror("Validation Error", f"Row {i+1}: Please select a valid product.")
                return

            qty_str = row['qty'].get().strip()
            rate_str = row['price'].get().strip()

            if not qty_str or not rate_str:
                messagebox.showerror("Validation Error", f"Row {i+1}: Quantity and Rate are required.")
                return

            try:
                qty = float(qty_str)
                if qty <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Validation Error", f"Row {i+1}: Quantity must be a positive number.")
                return

            try:
                rate = float(rate_str)
                if rate < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Validation Error", f"Row {i+1}: Rate must be a positive number.")
                return

            # Check ledger lock
            ledger_row = ledger_model.get_or_create_ledger_row(p['id'], db_date)
            if ledger_row['is_confirmed'] == 1:
                messagebox.showerror("Locked Ledger", f"Stock Ledger locked for {date_input} for product '{p['name']}'.")
                return
            
            valid_items.append({
                'product_id': p['id'],
                'qty': qty,
                'rate': rate,
                'name': p['name'],
                'unit': p['unit']
            })

        if not valid_items:
            messagebox.showerror("Validation Error", "Add at least one product.")
            return

        # Add all valid items
        try:
            for item in valid_items:
                purchase_model.insert_purchase(item['product_id'], db_date, item['qty'], item['rate'], supplier, notes)
            
            self.controller.set_status(f"Added {len(valid_items)} purchase records.")
            
            # Reset UI
            for row in self.item_rows[1:]:
                row['frame'].destroy()
            self.item_rows = [self.item_rows[0]]
            self.item_rows[0]['qty'].delete(0, tk.END)
            # keep the rate as is or update it via selection
            self.e_notes.delete(0, tk.END)
            self.update_remove_buttons()
            self.refresh_today_log()
        except Exception as ex:
            messagebox.showerror("Database Error", f"Failed to record purchases:\n{ex}")

    def delete_purchase_action(self, purchase_id, name):
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete purchase entry for '{name}'?")
        if confirm:
            try:
                purchase_model.delete_purchase(purchase_id)
                self.controller.set_status("Deleted purchase record.")
                self.refresh_today_log()
            except PermissionError as pe:
                messagebox.showerror("Locked Ledger", str(pe))
            except Exception as ex:
                messagebox.showerror("Error", f"Failed to delete purchase record:\n{ex}")
