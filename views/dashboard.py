import tkinter as tk
import customtkinter
import datetime
import models.product as product_model
import models.sale as sale_model
import models.expense as expense_model
import models.ledger as ledger_model
from utils.helpers import format_currency

class DashboardFrame(customtkinter.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        # Grid configuration
        self.grid_rowconfigure(0, weight=0) # Title
        self.grid_rowconfigure(1, weight=0) # Stat Cards Row
        self.grid_rowconfigure(2, weight=0) # Stock Alerts Title & Quick Actions
        self.grid_rowconfigure(3, weight=1) # Stock Alert Grid Scroll
        self.grid_columnconfigure(0, weight=1)

        # Title / Welcome Banner
        self.title_label = customtkinter.CTkLabel(
            self, text="PlywoodPro Dashboard",
            font=customtkinter.CTkFont(family="Inter", size=24, weight="bold"),
            text_color="#FFFFFF"
        )
        self.title_label.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        # 1. Stat Cards Frame Container
        self.cards_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.cards_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 15))
        self.cards_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="equal")

        # Create 4 beautiful stat cards
        self.revenue_card = self.create_stat_card(self.cards_frame, "Today's Revenue", "₹0.00", "#BA7517", 0)
        self.gross_profit_card = self.create_stat_card(self.cards_frame, "Today's Gross Profit", "₹0.00", "#2ECC71", 1)
        self.expenses_card = self.create_stat_card(self.cards_frame, "Today's Expenses", "₹0.00", "#E55039", 2)
        self.net_profit_card = self.create_stat_card(self.cards_frame, "Today's Net Profit", "₹0.00", "#3498DB", 3)

        # 2. Alerts Header + Quick Actions Row
        self.alerts_header_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.alerts_header_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(5, 5))
        self.alerts_header_frame.grid_columnconfigure(0, weight=1)
        self.alerts_header_frame.grid_columnconfigure((1, 2), weight=0)

        self.alerts_title = customtkinter.CTkLabel(
            self.alerts_header_frame, text="Active Inventory Stock Status",
            font=customtkinter.CTkFont(family="Inter", size=16, weight="bold"),
            text_color="#C9C5BC"
        )
        self.alerts_title.grid(row=0, column=0, sticky="w")

        # Quick Actions
        self.quick_sale_btn = customtkinter.CTkButton(
            self.alerts_header_frame, text="+ Record Sale", fg_color="#36322C", hover_color="#BA7517",
            text_color="#C9C5BC", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"),
            command=lambda: self.controller.switch_frame("sales")
        )
        self.quick_sale_btn.grid(row=0, column=1, padx=5, sticky="e")

        self.quick_pur_btn = customtkinter.CTkButton(
            self.alerts_header_frame, text="+ Log Intake", fg_color="#36322C", hover_color="#BA7517",
            text_color="#C9C5BC", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"),
            command=lambda: self.controller.switch_frame("purchase")
        )
        self.quick_pur_btn.grid(row=0, column=2, padx=5, sticky="e")

        # 3. Stock Table Frame Container
        self.table_container = customtkinter.CTkFrame(self, fg_color="#1F1E1B", border_width=1, border_color="#2D2C28")
        self.table_container.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.table_container.grid_rowconfigure(0, weight=0) # table headers
        self.table_container.grid_rowconfigure(1, weight=1) # table body scroll
        self.table_container.grid_columnconfigure(0, weight=1)

        # Columns Configuration
        self.headers_frame = customtkinter.CTkFrame(self.table_container, fg_color="#2D2C28", height=30, corner_radius=0)
        self.headers_frame.grid(row=0, column=0, sticky="ew")
        self._configure_table_columns(self.headers_frame)

        table_headers = ["Product Name", "Brand", "Thickness", "Dimensions Size", "Unit", "Alert Limit", "Current Stock", "Status Badge"]
        for idx, text in enumerate(table_headers):
            label = customtkinter.CTkLabel(
                self.headers_frame, text=text, font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#C9C5BC", anchor="w"
            )
            label.grid(row=0, column=idx, sticky="ew", padx=10, pady=5)

        # Scrollable Data body
        self.scroll_frame = customtkinter.CTkScrollableFrame(self.table_container, fg_color="transparent", corner_radius=0)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        self._configure_table_columns(self.scroll_frame)

    def create_stat_card(self, parent, label_text, value_text, accent_color, column_idx):
        card = customtkinter.CTkFrame(parent, fg_color="#1F1E1B", border_width=1, border_color="#2D2C28", height=100, corner_radius=8)
        card.grid(row=0, column=column_idx, padx=5, sticky="nsew")
        card.grid_propagate(False)

        # Left colorful indicator line
        indicator = customtkinter.CTkFrame(card, width=4, fg_color=accent_color, corner_radius=0)
        indicator.pack(side="left", fill="y")

        inner_frame = customtkinter.CTkFrame(card, fg_color="transparent")
        inner_frame.pack(side="left", fill="both", expand=True, padx=15, pady=12)

        lbl = customtkinter.CTkLabel(
            inner_frame, text=label_text, font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#8F8B83", anchor="w"
        )
        lbl.pack(fill="x")

        val = customtkinter.CTkLabel(
            inner_frame, text=value_text, font=customtkinter.CTkFont(family="Inter", size=20, weight="bold"), text_color="#FFFFFF", anchor="w"
        )
        val.pack(fill="x", pady=(5, 0))

        return {"card": card, "lbl": lbl, "val": val, "accent_color": accent_color}

    def _configure_table_columns(self, frame):
        frame.grid_columnconfigure(0, weight=3) # Product Name
        frame.grid_columnconfigure(1, weight=2) # Brand
        frame.grid_columnconfigure(2, weight=1) # Thickness
        frame.grid_columnconfigure(3, weight=1) # Size
        frame.grid_columnconfigure(4, weight=1) # Unit
        frame.grid_columnconfigure(5, weight=1) # Alert Limit
        frame.grid_columnconfigure(6, weight=1) # Stock Qty
        frame.grid_columnconfigure(7, weight=2) # Status Badge

    def on_show(self):
        """Called every time frame is switched to - updates stats and stock alerts."""
        self.refresh_dashboard_data()

    def refresh_dashboard_data(self):
        # 1. Update Financial KPI cards
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        
        # Calculate profits & revenues from sales table
        sales = sale_model.get_sales_by_date(today_str)
        revenue = sum(s['total_revenue'] for s in sales)
        gross_profit = sum(s['margin_profit'] for s in sales)

        # Calculate expenses from expenses table
        total_expenses = expense_model.get_total_expenses_by_date(today_str)

        # Calculate Net Profit
        net_profit = gross_profit - total_expenses

        # Configure display
        self.revenue_card['val'].configure(text=format_currency(revenue))
        self.gross_profit_card['val'].configure(text=format_currency(gross_profit))
        self.expenses_card['val'].configure(text=format_currency(total_expenses))

        # Dynamic color highlights for net profit card
        net_color = "#2ECC71" if net_profit >= 0 else "#E55039"
        self.net_profit_card['val'].configure(text=format_currency(net_profit), text_color=net_color)

        # 2. Reload Stock Table List
        for child in self.scroll_frame.winfo_children():
            child.destroy()

        products = product_model.get_active_products()
        if not products:
            no_data = customtkinter.CTkLabel(
                self.scroll_frame, text="No products found in the database. Please visit Products tab.",
                font=customtkinter.CTkFont(family="Inter", size=13, slant="italic"), text_color="#8F8B83"
            )
            no_data.grid(row=0, column=0, columnspan=8, pady=30, sticky="ew")
            return

        for idx, p in enumerate(products):
            current_stock = ledger_model.get_current_stock(p['id'])
            is_low_stock = current_stock <= p['low_stock_threshold']

            row_fg = "#282622" if idx % 2 == 0 else "#1F1E1B"
            row_frame = customtkinter.CTkFrame(self.scroll_frame, fg_color=row_fg, corner_radius=4)
            row_frame.grid(row=idx, column=0, columnspan=8, sticky="ew", pady=2, ipady=4)
            self._configure_table_columns(row_frame)

            # Row Text Color highlights
            text_color = "#E55039" if is_low_stock else "#E8E6E3"

            # Name
            n_lbl = customtkinter.CTkLabel(row_frame, text=p['name'], text_color=text_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"))
            n_lbl.grid(row=0, column=0, sticky="ew", padx=10)

            # Brand
            b_lbl = customtkinter.CTkLabel(row_frame, text=p['brand'] or "-", text_color=text_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=11))
            b_lbl.grid(row=0, column=1, sticky="ew", padx=10)

            # Thickness
            t_lbl = customtkinter.CTkLabel(row_frame, text=p['thickness'] or "-", text_color=text_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=11))
            t_lbl.grid(row=0, column=2, sticky="ew", padx=10)

            # Size
            s_lbl = customtkinter.CTkLabel(row_frame, text=p['size'] or "-", text_color=text_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=11))
            s_lbl.grid(row=0, column=3, sticky="ew", padx=10)

            # Unit
            u_lbl = customtkinter.CTkLabel(row_frame, text=p['unit'], text_color=text_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=11))
            u_lbl.grid(row=0, column=4, sticky="ew", padx=10)

            # Alert Limit
            l_lbl = customtkinter.CTkLabel(row_frame, text=str(p['low_stock_threshold']), text_color=text_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=11))
            l_lbl.grid(row=0, column=5, sticky="ew", padx=10)

            # Current Stock
            stock_text = f"{current_stock:.1f}" if current_stock % 1 != 0 else f"{int(current_stock)}"
            stock_color = "#E55039" if is_low_stock else "#2ECC71"
            st_lbl = customtkinter.CTkLabel(row_frame, text=stock_text, text_color=stock_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"))
            st_lbl.grid(row=0, column=6, sticky="ew", padx=10)

            # Status Badge
            badge_text = "LOW STOCK ALERT ⚠️" if is_low_stock else "HEALTHY STOCK"
            badge_color = "#E55039" if is_low_stock else "#2ECC71"
            badge_frame = customtkinter.CTkFrame(row_frame, fg_color="transparent")
            badge_frame.grid(row=0, column=7, sticky="w", padx=10)

            badge = customtkinter.CTkLabel(
                badge_frame, text=badge_text, text_color=badge_color, font=customtkinter.CTkFont(family="Inter", size=10, weight="bold")
            )
            badge.pack()
