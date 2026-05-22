import tkinter as tk
import customtkinter
import datetime
from tkinter import messagebox
from tkinter import filedialog
import os

import models.sale as sale_model
import models.expense as expense_model
import utils.helpers as helpers
import utils.export as export_utils

class DailyReportFrame(customtkinter.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        # Grid configuration
        self.grid_rowconfigure(0, weight=0) # Title and Date Filter Frame
        self.grid_rowconfigure(1, weight=0) # Stat Cards Row
        self.grid_rowconfigure(2, weight=1) # Double tables side-by-side
        self.grid_columnconfigure(0, weight=1)

        # ----------------------------------------------------
        # ROW 0: Title and Controls Header
        # ----------------------------------------------------
        self.header_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        self.header_frame.grid_columnconfigure(0, weight=1)
        self.header_frame.grid_columnconfigure(1, weight=0)

        # Title
        self.title_label = customtkinter.CTkLabel(
            self.header_frame, text="Daily Performance & Profit Report",
            font=customtkinter.CTkFont(family="Inter", size=24, weight="bold"),
            text_color="#FFFFFF"
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        # Controls (Date entry, Refresh, Exports)
        self.controls_frame = customtkinter.CTkFrame(self.header_frame, fg_color="#181715", border_width=1, border_color="#2D2C28")
        self.controls_frame.grid(row=0, column=1, sticky="e")

        customtkinter.CTkLabel(
            self.controls_frame, text="Date: ", 
            font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), 
            text_color="#C9C5BC"
        ).pack(side="left", padx=(15, 5), pady=8)

        self.report_date_entry = customtkinter.CTkEntry(
            self.controls_frame, width=110, fg_color="#181715", border_color="#36322C",
            text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=12)
        )
        self.report_date_entry.pack(side="left", padx=5)
        self.report_date_entry.bind("<Return>", lambda e: self.refresh_report())

        # Buttons
        self.refresh_btn = customtkinter.CTkButton(
            self.controls_frame, text="Refresh", width=70, height=28, fg_color="#36322C", hover_color="#BA7517",
            text_color="#C9C5BC", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"),
            command=self.refresh_report
        )
        self.refresh_btn.pack(side="left", padx=5)

        self.pdf_btn = customtkinter.CTkButton(
            self.controls_frame, text="Export PDF 📄", width=100, height=28, fg_color="#BA7517", hover_color="#A06312",
            text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"),
            command=self.export_pdf
        )
        self.pdf_btn.pack(side="left", padx=5)

        self.excel_btn = customtkinter.CTkButton(
            self.controls_frame, text="Export Excel 📊", width=110, height=28, fg_color="#2ECC71", hover_color="#27AE60",
            text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"),
            command=self.export_excel
        )
        self.excel_btn.pack(side="left", padx=(5, 15))

        # ----------------------------------------------------
        # ROW 1: 5 beautiful dynamic stats cards
        # ----------------------------------------------------
        self.cards_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.cards_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 15))
        self.cards_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="equal")

        self.vol_card = self.create_stat_card(self.cards_frame, "Volume Sold (Sheets)", "0 Sheets", "#BA7517", 0)
        self.rev_card = self.create_stat_card(self.cards_frame, "Total Revenue", "₹0.00", "#F1C40F", 1)
        self.gp_card = self.create_stat_card(self.cards_frame, "Gross Margin Profit", "₹0.00", "#2ECC71", 2)
        self.exp_card = self.create_stat_card(self.cards_frame, "Operating Costs", "₹0.00", "#E55039", 3)
        self.np_card = self.create_stat_card(self.cards_frame, "Net Business Profit", "₹0.00", "#3498DB", 4)

        # ----------------------------------------------------
        # ROW 2: Double Detail Tables (Side-by-Side)
        # ----------------------------------------------------
        self.details_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.details_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.details_frame.grid_rowconfigure(0, weight=1)
        self.details_frame.grid_columnconfigure(0, weight=6)  # Sales Breakdown (60%)
        self.details_frame.grid_columnconfigure(1, weight=4)  # Operating Expenses (40%)

        # --- LEFT PANEL: Sales breakdown ---
        self.sales_panel = customtkinter.CTkFrame(self.details_frame, fg_color="#1F1E1B", border_width=1, border_color="#2D2C28")
        self.sales_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.sales_panel.grid_rowconfigure(0, weight=0) # title
        self.sales_panel.grid_rowconfigure(1, weight=0) # headers
        self.sales_panel.grid_rowconfigure(2, weight=1) # scroll list
        self.sales_panel.grid_columnconfigure(0, weight=1)

        self.sales_title_lbl = customtkinter.CTkLabel(
            self.sales_panel, text="Itemized Sales & Profit Margins",
            font=customtkinter.CTkFont(family="Inter", size=14, weight="bold"),
            text_color="#C9C5BC"
        )
        self.sales_title_lbl.grid(row=0, column=0, sticky="w", padx=15, pady=10)

        # Sales headers
        self.sales_headers_frame = customtkinter.CTkFrame(self.sales_panel, fg_color="#2D2C28", height=28, corner_radius=0)
        self.sales_headers_frame.grid(row=1, column=0, sticky="ew")
        self._configure_sales_columns(self.sales_headers_frame)

        sales_headers = ["Item Description", "Qty", "Sale Rate", "Cost Rate", "Margin Profit", "Customer"]
        for idx, text in enumerate(sales_headers):
            lbl = customtkinter.CTkLabel(
                self.sales_headers_frame, text=text,
                font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"),
                text_color="#C9C5BC", anchor="w"
            )
            lbl.grid(row=0, column=idx, sticky="ew", padx=8, pady=4)

        # Sales scrollable list
        self.sales_scroll = customtkinter.CTkScrollableFrame(self.sales_panel, fg_color="transparent", corner_radius=0)
        self.sales_scroll.grid(row=2, column=0, sticky="nsew")
        self._configure_sales_columns(self.sales_scroll)

        # --- RIGHT PANEL: Expenses breakdown ---
        self.expenses_panel = customtkinter.CTkFrame(self.details_frame, fg_color="#1F1E1B", border_width=1, border_color="#2D2C28")
        self.expenses_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.expenses_panel.grid_rowconfigure(0, weight=0) # title
        self.expenses_panel.grid_rowconfigure(1, weight=0) # headers
        self.expenses_panel.grid_rowconfigure(2, weight=1) # scroll list
        self.expenses_panel.grid_columnconfigure(0, weight=1)

        self.expenses_title_lbl = customtkinter.CTkLabel(
            self.expenses_panel, text="Categorized Daily Expenditures",
            font=customtkinter.CTkFont(family="Inter", size=14, weight="bold"),
            text_color="#C9C5BC"
        )
        self.expenses_title_lbl.grid(row=0, column=0, sticky="w", padx=15, pady=10)

        # Expenses headers
        self.exp_headers_frame = customtkinter.CTkFrame(self.expenses_panel, fg_color="#2D2C28", height=28, corner_radius=0)
        self.exp_headers_frame.grid(row=1, column=0, sticky="ew")
        self._configure_exp_columns(self.exp_headers_frame)

        exp_headers = ["Category", "Amount", "Note / Description"]
        for idx, text in enumerate(exp_headers):
            lbl = customtkinter.CTkLabel(
                self.exp_headers_frame, text=text,
                font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"),
                text_color="#C9C5BC", anchor="w"
            )
            lbl.grid(row=0, column=idx, sticky="ew", padx=8, pady=4)

        # Expenses scrollable list
        self.exp_scroll = customtkinter.CTkScrollableFrame(self.expenses_panel, fg_color="transparent", corner_radius=0)
        self.exp_scroll.grid(row=2, column=0, sticky="nsew")
        self._configure_exp_columns(self.exp_scroll)

    def create_stat_card(self, parent, label_text, value_text, accent_color, column_idx):
        card = customtkinter.CTkFrame(parent, fg_color="#1F1E1B", border_width=1, border_color="#2D2C28", height=90, corner_radius=6)
        card.grid(row=0, column=column_idx, padx=4, sticky="nsew")
        card.grid_propagate(False)

        # Left colorful indicator line
        indicator = customtkinter.CTkFrame(card, width=3, fg_color=accent_color, corner_radius=0)
        indicator.pack(side="left", fill="y")

        inner_frame = customtkinter.CTkFrame(card, fg_color="transparent")
        inner_frame.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        lbl = customtkinter.CTkLabel(
            inner_frame, text=label_text, font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"), text_color="#8F8B83", anchor="w"
        )
        lbl.pack(fill="x")

        val = customtkinter.CTkLabel(
            inner_frame, text=value_text, font=customtkinter.CTkFont(family="Inter", size=16, weight="bold"), text_color="#FFFFFF", anchor="w"
        )
        val.pack(fill="x", pady=(3, 0))

        return {"card": card, "lbl": lbl, "val": val, "accent_color": accent_color}

    def _configure_sales_columns(self, frame):
        frame.grid_columnconfigure(0, weight=3) # Item Description
        frame.grid_columnconfigure(1, weight=1) # Qty
        frame.grid_columnconfigure(2, weight=1) # Sale rate
        frame.grid_columnconfigure(3, weight=1) # Cost rate
        frame.grid_columnconfigure(4, weight=2) # Margin profit
        frame.grid_columnconfigure(5, weight=2) # Customer

    def _configure_exp_columns(self, frame):
        frame.grid_columnconfigure(0, weight=2) # Category
        frame.grid_columnconfigure(1, weight=2) # Amount
        frame.grid_columnconfigure(2, weight=3) # Note

    def on_show(self):
        """Hook called when the frame is switched to. Sets today's date and refreshes."""
        today_str = datetime.date.today().strftime("%d-%m-%Y")
        self.report_date_entry.delete(0, tk.END)
        self.report_date_entry.insert(0, today_str)
        self.refresh_report()

    def refresh_report(self):
        # Validate and parse date
        date_input = self.report_date_entry.get().strip()
        try:
            db_date = helpers.parse_date(date_input)
        except ValueError:
            messagebox.showerror("Invalid Date", "Please enter a valid date in DD-MM-YYYY format.")
            return

        # Fetch Sales
        sales = sale_model.get_sales_by_date(db_date)
        # Fetch Expenses
        expenses = expense_model.get_expenses_by_date(db_date)
        total_expenses = expense_model.get_total_expenses_by_date(db_date)

        # ----------------------------------------------------
        # 1. Update KPI Card Sums
        # ----------------------------------------------------
        total_qty = sum(s['qty'] for s in sales)
        total_rev = sum(s['total_revenue'] for s in sales)
        total_gp = sum(s['margin_profit'] for s in sales)
        net_profit = total_gp - total_expenses

        # Volume
        self.vol_card['val'].configure(text=f"{total_qty:.1f} Units" if total_qty % 1 != 0 else f"{int(total_qty)} Units")
        # Revenue
        self.vol_card['lbl'].configure(text="Volume Sold")
        self.rev_card['val'].configure(text=helpers.format_currency(total_rev))
        # Gross profit
        self.gp_card['val'].configure(text=helpers.format_currency(total_gp))
        # Expenses
        self.exp_card['val'].configure(text=helpers.format_currency(total_expenses))
        # Net Profit
        np_color = "#2ECC71" if net_profit >= 0 else "#E55039"
        self.np_card['val'].configure(text=helpers.format_currency(net_profit), text_color=np_color)

        # ----------------------------------------------------
        # 2. Populate Sales Breakdown List
        # ----------------------------------------------------
        for child in self.sales_scroll.winfo_children():
            child.destroy()

        if not sales:
            no_sales = customtkinter.CTkLabel(
                self.sales_scroll, text="No sales transactions on this date.",
                font=customtkinter.CTkFont(family="Inter", size=11, slant="italic"), text_color="#8F8B83"
            )
            no_sales.grid(row=0, column=0, columnspan=6, pady=30, sticky="ew")
        else:
            for idx, s in enumerate(sales):
                row_fg = "#282622" if idx % 2 == 0 else "#1F1E1B"
                row_frame = customtkinter.CTkFrame(self.sales_scroll, fg_color=row_fg, corner_radius=4)
                row_frame.grid(row=idx, column=0, columnspan=6, sticky="ew", pady=1, ipady=3)
                self._configure_sales_columns(row_frame)

                # Item Description
                desc_text = f"{s['product_name']} ({s['product_brand']})\n{s['product_thickness']} • {s['product_size']}"
                desc_lbl = customtkinter.CTkLabel(row_frame, text=desc_text, text_color="#E8E6E3", anchor="w", justify="left", font=customtkinter.CTkFont(family="Inter", size=10, weight="normal"))
                desc_lbl.grid(row=0, column=0, sticky="ew", padx=8)

                # Qty
                qty_text = f"{s['qty']:.1f}" if s['qty'] % 1 != 0 else f"{int(s['qty'])}"
                qty_lbl = customtkinter.CTkLabel(row_frame, text=qty_text, text_color="#C9C5BC", anchor="w", font=customtkinter.CTkFont(family="Inter", size=10))
                qty_lbl.grid(row=0, column=1, sticky="ew", padx=8)

                # Sale Rate
                s_rate_lbl = customtkinter.CTkLabel(row_frame, text=helpers.format_currency(s['unit_price']), text_color="#C9C5BC", anchor="w", font=customtkinter.CTkFont(family="Inter", size=10))
                s_rate_lbl.grid(row=0, column=2, sticky="ew", padx=8)

                # Cost Rate
                c_rate_lbl = customtkinter.CTkLabel(row_frame, text=helpers.format_currency(s['purchase_price_at_time']), text_color="#8F8B83", anchor="w", font=customtkinter.CTkFont(family="Inter", size=10))
                c_rate_lbl.grid(row=0, column=3, sticky="ew", padx=8)

                # Profit Margin
                prof_color = "#2ECC71" if s['margin_profit'] >= 0 else "#E55039"
                prof_lbl = customtkinter.CTkLabel(row_frame, text=helpers.format_currency(s['margin_profit']), text_color=prof_color, anchor="w", font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"))
                prof_lbl.grid(row=0, column=4, sticky="ew", padx=8)

                # Customer
                cust_text = s['customer_name'] or "-"
                if s['notes']:
                    cust_text += f"\n({s['notes']})"
                cust_lbl = customtkinter.CTkLabel(row_frame, text=cust_text, text_color="#C9C5BC", anchor="w", justify="left", font=customtkinter.CTkFont(family="Inter", size=9))
                cust_lbl.grid(row=0, column=5, sticky="ew", padx=8)

        # ----------------------------------------------------
        # 3. Populate Expenses Breakdown List
        # ----------------------------------------------------
        for child in self.exp_scroll.winfo_children():
            child.destroy()

        if not expenses:
            no_exp = customtkinter.CTkLabel(
                self.exp_scroll, text="No expenses recorded on this date.",
                font=customtkinter.CTkFont(family="Inter", size=11, slant="italic"), text_color="#8F8B83"
            )
            no_exp.grid(row=0, column=0, columnspan=3, pady=30, sticky="ew")
        else:
            for idx, e in enumerate(expenses):
                row_fg = "#282622" if idx % 2 == 0 else "#1F1E1B"
                row_frame = customtkinter.CTkFrame(self.exp_scroll, fg_color=row_fg, corner_radius=4)
                row_frame.grid(row=idx, column=0, columnspan=3, sticky="ew", pady=1, ipady=3)
                self._configure_exp_columns(row_frame)

                # Category
                cat_lbl = customtkinter.CTkLabel(row_frame, text=e['category'], text_color="#E8E6E3", anchor="w", font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"))
                cat_lbl.grid(row=0, column=0, sticky="ew", padx=8)

                # Amount
                amt_lbl = customtkinter.CTkLabel(row_frame, text=helpers.format_currency(e['amount']), text_color="#E55039", anchor="w", font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"))
                amt_lbl.grid(row=0, column=1, sticky="ew", padx=8)

                # Note
                note_lbl = customtkinter.CTkLabel(row_frame, text=e['note'] or "-", text_color="#C9C5BC", anchor="w", justify="left", font=customtkinter.CTkFont(family="Inter", size=10))
                note_lbl.grid(row=0, column=2, sticky="ew", padx=8)

    def export_pdf(self):
        date_input = self.report_date_entry.get().strip()
        try:
            db_date = helpers.parse_date(date_input)
        except ValueError:
            messagebox.showerror("Invalid Date", "Please enter a valid date in DD-MM-YYYY format.")
            return

        # Request file location to save
        filename = f"PlywoodPro_DailyReport_{db_date}.pdf"
        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Documents", "*.pdf")],
            initialfile=filename,
            title="Save Daily Report PDF"
        )
        if not filepath:
            return

        try:
            self.controller.set_status("Generating PDF Report...")
            # Trigger export
            export_utils.export_daily_pdf(db_date, filepath)
            self.controller.set_status(f"PDF exported successfully: {os.path.basename(filepath)}")
            messagebox.showinfo("Export Success", f"Report saved successfully as PDF:\n{filepath}")
        except Exception as ex:
            self.controller.set_status("PDF export failed")
            messagebox.showerror("Export Failed", f"An error occurred while generating PDF:\n{ex}")

    def export_excel(self):
        date_input = self.report_date_entry.get().strip()
        try:
            db_date = helpers.parse_date(date_input)
        except ValueError:
            messagebox.showerror("Invalid Date", "Please enter a valid date in DD-MM-YYYY format.")
            return

        # Request file location to save
        filename = f"PlywoodPro_DailyReport_{db_date}.xlsx"
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Spreadsheets", "*.xlsx")],
            initialfile=filename,
            title="Save Daily Report Excel"
        )
        if not filepath:
            return

        try:
            self.controller.set_status("Generating Excel Report...")
            # Trigger export
            export_utils.export_daily_excel(db_date, filepath)
            self.controller.set_status(f"Excel exported successfully: {os.path.basename(filepath)}")
            messagebox.showinfo("Export Success", f"Report saved successfully as Excel:\n{filepath}")
        except Exception as ex:
            self.controller.set_status("Excel export failed")
            messagebox.showerror("Export Failed", f"An error occurred while generating Excel:\n{ex}")
