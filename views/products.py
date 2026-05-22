import tkinter as tk
import customtkinter
from tkinter import messagebox
import models.product as product_model
import models.ledger as ledger_model
from utils.helpers import format_currency

class ProductsFrame(customtkinter.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        # Grid configuration
        self.grid_rowconfigure(0, weight=0) # Title header
        self.grid_rowconfigure(1, weight=1) # Main list table
        self.grid_columnconfigure(0, weight=1)

        # Header Frame
        self.header_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        self.header_frame.grid_columnconfigure(0, weight=1)
        self.header_frame.grid_columnconfigure(1, weight=0)

        # Title Label
        self.title_label = customtkinter.CTkLabel(
            self.header_frame,
            text="Products Registry",
            font=customtkinter.CTkFont(family="Inter", size=24, weight="bold"),
            text_color="#FFFFFF"
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        # Add Product Button
        self.add_btn = customtkinter.CTkButton(
            self.header_frame,
            text="+ Add New Product",
            fg_color="#BA7517",
            hover_color="#A06312",
            font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"),
            command=self.open_add_dialog
        )
        self.add_btn.grid(row=0, column=1, sticky="e")

        # Table Frame Container
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
        headers = ["Name", "Brand", "Type", "Specs", "Purchase Rate", "Sale Rate", "Unit", "Alert Limit", "In Stock", "Actions"]
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
        frame.grid_columnconfigure(0, weight=3) # Name
        frame.grid_columnconfigure(1, weight=2) # Brand
        frame.grid_columnconfigure(2, weight=1) # Type
        frame.grid_columnconfigure(3, weight=2) # Thickness/Size
        frame.grid_columnconfigure(4, weight=2) # Purchase Rate
        frame.grid_columnconfigure(5, weight=2) # Sale Rate
        frame.grid_columnconfigure(6, weight=1) # Unit
        frame.grid_columnconfigure(7, weight=1) # Limit
        frame.grid_columnconfigure(8, weight=1) # In Stock
        frame.grid_columnconfigure(9, weight=2) # Actions

    def on_show(self):
        """Loads and refreshes product records from database."""
        self.refresh_products()

    def refresh_products(self):
        # Clear existing rows
        for child in self.scroll_frame.winfo_children():
            child.destroy()

        products = product_model.get_active_products()
        
        if not products:
            no_data = customtkinter.CTkLabel(
                self.scroll_frame,
                text="No products in registry. Click '+ Add New Product' above to start.",
                font=customtkinter.CTkFont(family="Inter", size=13, slant="italic"),
                text_color="#8F8B83"
            )
            no_data.grid(row=0, column=0, columnspan=10, pady=40, sticky="ew")
            return

        for idx, p in enumerate(products):
            # Fetch current live stock
            current_stock = ledger_model.get_current_stock(p['id'])
            
            # Row Background styling (alternate color or warning highlighters)
            is_low_stock = current_stock <= p['low_stock_threshold']
            row_fg = "#282622" if idx % 2 == 0 else "#1F1E1B"
            if is_low_stock:
                text_color = "#E55039" # Crimson warning
            else:
                text_color = "#E8E6E3"

            # Create a subframe for row container to have hover colors or unified backgrounds
            row_frame = customtkinter.CTkFrame(self.scroll_frame, fg_color=row_fg, corner_radius=4)
            row_frame.grid(row=idx, column=0, columnspan=10, sticky="ew", pady=2, ipady=4)
            self._configure_table_columns(row_frame)

            # Name
            n_lbl = customtkinter.CTkLabel(row_frame, text=p['name'], text_color=text_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"))
            n_lbl.grid(row=0, column=0, sticky="ew", padx=10)

            # Brand
            b_lbl = customtkinter.CTkLabel(row_frame, text=p['brand'] or "-", text_color=text_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=12))
            b_lbl.grid(row=0, column=1, sticky="ew", padx=10)

            # Type
            t_lbl = customtkinter.CTkLabel(row_frame, text=p['type'] or "-", text_color=text_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=12))
            t_lbl.grid(row=0, column=2, sticky="ew", padx=10)

            # Specs (Size & Thickness)
            spec_text = f"{p['thickness'] or '-'} · {p['size'] or '-'}"
            s_lbl = customtkinter.CTkLabel(row_frame, text=spec_text, text_color=text_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=12))
            s_lbl.grid(row=0, column=3, sticky="ew", padx=10)

            # Purchase Rate
            pr_lbl = customtkinter.CTkLabel(row_frame, text=format_currency(p['purchase_price']), text_color=text_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=12))
            pr_lbl.grid(row=0, column=4, sticky="ew", padx=10)

            # Selling Rate
            sr_lbl = customtkinter.CTkLabel(row_frame, text=format_currency(p['selling_price']), text_color=text_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=12))
            sr_lbl.grid(row=0, column=5, sticky="ew", padx=10)

            # Unit
            u_lbl = customtkinter.CTkLabel(row_frame, text=p['unit'], text_color=text_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=12))
            u_lbl.grid(row=0, column=6, sticky="ew", padx=10)

            # Low Stock Limit
            l_lbl = customtkinter.CTkLabel(row_frame, text=str(p['low_stock_threshold']), text_color=text_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=12))
            l_lbl.grid(row=0, column=7, sticky="ew", padx=10)

            # In Stock Qty
            stock_text = f"{current_stock:.1f}" if current_stock % 1 != 0 else f"{int(current_stock)}"
            if is_low_stock:
                stock_text += " ⚠️"
            stock_lbl = customtkinter.CTkLabel(
                row_frame, 
                text=stock_text, 
                text_color="#E55039" if is_low_stock else "#2ECC71", 
                anchor="w", 
                font=customtkinter.CTkFont(family="Inter", size=12, weight="bold")
            )
            stock_lbl.grid(row=0, column=8, sticky="ew", padx=10)

            # Actions Button Frame
            actions_frame = customtkinter.CTkFrame(row_frame, fg_color="transparent")
            actions_frame.grid(row=0, column=9, sticky="ew", padx=10)

            edit_btn = customtkinter.CTkButton(
                actions_frame, text="Edit", width=45, height=22, fg_color="#36322C", hover_color="#BA7517", 
                text_color="#C9C5BC", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"),
                command=lambda prod=p: self.open_edit_dialog(prod)
            )
            edit_btn.pack(side="left", padx=2)

            del_btn = customtkinter.CTkButton(
                actions_frame, text="Del", width=45, height=22, fg_color="#4D1F1C", hover_color="#A93226", 
                text_color="#E6F2FF", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"),
                command=lambda pid=p['id'], pname=p['name']: self.delete_product_action(pid, pname)
            )
            del_btn.pack(side="left", padx=2)

    def open_add_dialog(self):
        ProductFormDialog(self, "Add New Product", callback=self.refresh_products)

    def open_edit_dialog(self, product_dict):
        ProductFormDialog(self, "Edit Product", product_dict, callback=self.refresh_products)

    def delete_product_action(self, product_id, name):
        confirm = messagebox.askyesno(
            "Confirm Soft Delete", 
            f"Are you sure you want to delete '{name}'?\nThis will hide the product but preserve historical records."
        )
        if confirm:
            product_model.soft_delete_product(product_id)
            self.controller.set_status(f"Deleted product: {name}")
            self.refresh_products()


class ProductFormDialog(customtkinter.CTkToplevel):
    def __init__(self, parent, title_text, product_dict=None, callback=None):
        super().__init__(parent)
        self.parent = parent
        self.callback = callback
        self.product = product_dict
        self.title(title_text)
        self.geometry("450x600")
        self.resizable(False, True)
        self.configure(fg_color="#201F1D")
        self.transient(parent)
        self.grab_set()

        # Title
        self.title_lbl = customtkinter.CTkLabel(
            self, text=title_text, font=customtkinter.CTkFont(family="Inter", size=18, weight="bold"), text_color="#BA7517"
        )
        self.title_lbl.pack(pady=(20, 15))

        # Buttons (packed first with side="bottom" so they are always visible)
        btn_container = customtkinter.CTkFrame(self, fg_color="transparent")
        btn_container.pack(fill="x", side="bottom", pady=20, padx=30)

        cancel_btn = customtkinter.CTkButton(
            btn_container, text="Cancel", fg_color="#36322C", hover_color="#4D4942", font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"),
            command=self.destroy
        )
        cancel_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        save_btn = customtkinter.CTkButton(
            btn_container, text="Save Product", fg_color="#BA7517", hover_color="#A06312", font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"),
            command=self.save_product
        )
        save_btn.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # Fields container (Scrollable Frame)
        form = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=30, pady=10)

        # Helper label generator
        def make_field(label_text, default_val=""):
            container = customtkinter.CTkFrame(form, fg_color="transparent")
            container.pack(fill="x", pady=5)
            
            lbl = customtkinter.CTkLabel(
                container, text=label_text, font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC", anchor="w"
            )
            lbl.pack(fill="x", pady=(0, 2))
            
            entry = customtkinter.CTkEntry(
                container, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=12)
            )
            entry.insert(0, str(default_val))
            entry.pack(fill="x")
            return entry

        # Fields inputs
        p = self.product or {}
        self.e_name = make_field("Product Name *", p.get('name', ''))
        self.e_brand = make_field("Brand / Manufacturer", p.get('brand', ''))
        self.e_type = make_field("Type (MR / BWR / BWP / Commercial)", p.get('type', 'MR'))
        self.e_thickness = make_field("Thickness (e.g. 6mm, 18mm)", p.get('thickness', '18mm'))
        self.e_size = make_field("Dimensions Size (e.g. 8x4, 7x4)", p.get('size', '8x4'))
        self.e_pur_price = make_field("Default Purchase Price (₹) *", p.get('purchase_price', '0.00'))
        self.e_sel_price = make_field("Default Selling Price (₹) *", p.get('selling_price', '0.00'))
        
        # Unit and Low-Stock fields side by side
        side_row = customtkinter.CTkFrame(form, fg_color="transparent")
        side_row.pack(fill="x", pady=5)
        side_row.grid_columnconfigure(0, weight=1)
        side_row.grid_columnconfigure(1, weight=1)

        # Unit dropdown
        u_box = customtkinter.CTkFrame(side_row, fg_color="transparent")
        u_box.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        u_lbl = customtkinter.CTkLabel(u_box, text="Unit *", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC", anchor="w")
        u_lbl.pack(fill="x", pady=(0, 2))
        self.e_unit = customtkinter.CTkComboBox(
            u_box, values=["sheets", "sqft"], fg_color="#181715", border_color="#36322C", button_color="#BA7517", button_hover_color="#A06312", dropdown_fg_color="#181715",
            state="readonly"
        )
        self.e_unit.set(p.get('unit', 'sheets'))
        self.e_unit.pack(fill="x")

        # Threshold limit
        t_box = customtkinter.CTkFrame(side_row, fg_color="transparent")
        t_box.grid(row=0, column=1, padx=(5, 0), sticky="ew")
        t_lbl = customtkinter.CTkLabel(t_box, text="Alert Limit *", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC", anchor="w")
        t_lbl.pack(fill="x", pady=(0, 2))
        self.e_limit = customtkinter.CTkEntry(t_box, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=12))
        self.e_limit.insert(0, str(p.get('low_stock_threshold', 10)))
        self.e_limit.pack(fill="x")

    def save_product(self):
        name = self.e_name.get().strip()
        brand = self.e_brand.get().strip()
        type_ = self.e_type.get().strip()
        thickness = self.e_thickness.get().strip()
        size = self.e_size.get().strip()
        pur_str = self.e_pur_price.get().strip()
        sel_str = self.e_sel_price.get().strip()
        unit = self.e_unit.get().strip()
        limit_str = self.e_limit.get().strip()

        # Validation
        if not name or not pur_str or not sel_str or not limit_str:
            messagebox.showerror("Validation Error", "All fields marked with '*' are required.")
            return

        try:
            purchase_price = float(pur_str)
            selling_price = float(sel_str)
            if purchase_price < 0 or selling_price < 0:
                raise ValueError("Rates cannot be negative.")
        except ValueError:
            messagebox.showerror("Validation Error", "Rates must be valid positive numbers.")
            return

        try:
            limit = int(limit_str)
            if limit < 0:
                raise ValueError("Limit cannot be negative.")
        except ValueError:
            messagebox.showerror("Validation Error", "Alert Limit must be a valid positive integer.")
            return

        # Insert or Update database
        try:
            if self.product:
                product_model.update_product(
                    self.product['id'], name, brand, type_, thickness, size, purchase_price, selling_price, unit, limit
                )
                self.parent.controller.set_status(f"Updated product: {name}")
            else:
                product_model.add_product(
                    name, brand, type_, thickness, size, purchase_price, selling_price, unit, limit
                )
                self.parent.controller.set_status(f"Added new product: {name}")
            
            if self.callback:
                self.callback()
            self.destroy()
        except Exception as ex:
            messagebox.showerror("Database Error", f"Failed to save product:\n{ex}")
