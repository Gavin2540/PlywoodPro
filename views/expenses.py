import tkinter as tk
import customtkinter
import datetime
from tkinter import messagebox
import models.expense as expense_model
import models.ledger as ledger_model
from utils.helpers import format_currency, parse_date, format_date

class ExpensesFrame(customtkinter.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        # Grid configuration
        self.grid_rowconfigure(0, weight=0) # Title
        self.grid_rowconfigure(1, weight=0) # Form Frame
        self.grid_rowconfigure(2, weight=0) # Log Title & Filter
        self.grid_rowconfigure(3, weight=1) # Scrollable Table
        self.grid_rowconfigure(4, weight=0) # Total Summary Bar
        self.grid_columnconfigure(0, weight=1)

        # Title
        self.title_label = customtkinter.CTkLabel(
            self, text="Log Business Expenses",
            font=customtkinter.CTkFont(family="Inter", size=24, weight="bold"),
            text_color="#FFFFFF"
        )
        self.title_label.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        # 1. Form Frame
        self.form_frame = customtkinter.CTkFrame(self, fg_color="#1F1E1B", border_width=1, border_color="#2D2C28")
        self.form_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 15))
        
        self.form_frame.grid_columnconfigure(0, weight=2) # Date
        self.form_frame.grid_columnconfigure(1, weight=2) # Category
        self.form_frame.grid_columnconfigure(2, weight=2) # Amount
        self.form_frame.grid_columnconfigure(3, weight=4) # Note
        self.form_frame.grid_columnconfigure(4, weight=2) # Button

        # Date input
        customtkinter.CTkLabel(self.form_frame, text="Date (DD-MM-YYYY) *", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=0, column=0, sticky="w", padx=15, pady=(15, 2))
        self.e_date = customtkinter.CTkEntry(self.form_frame, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        self.e_date.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 15))

        # Category dropdown
        customtkinter.CTkLabel(self.form_frame, text="Category *", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=0, column=1, sticky="w", padx=15, pady=(15, 2))
        self.e_category = customtkinter.CTkComboBox(
            self.form_frame, values=["Transport", "Labour", "Loading", "Rent", "Miscellaneous"], fg_color="#181715", border_color="#36322C", button_color="#BA7517", button_hover_color="#A06312", dropdown_fg_color="#181715",
            state="readonly"
        )
        self.e_category.grid(row=1, column=1, sticky="ew", padx=15, pady=(0, 15))

        # Amount
        customtkinter.CTkLabel(self.form_frame, text="Amount (₹) *", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=0, column=2, sticky="w", padx=15, pady=(15, 2))
        self.e_amount = customtkinter.CTkEntry(self.form_frame, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        self.e_amount.grid(row=1, column=2, sticky="ew", padx=15, pady=(0, 15))

        # Note
        customtkinter.CTkLabel(self.form_frame, text="Note / Description", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#C9C5BC").grid(row=0, column=3, sticky="w", padx=15, pady=(15, 2))
        self.e_note = customtkinter.CTkEntry(self.form_frame, fg_color="#181715", border_color="#36322C", text_color="#FFFFFF")
        self.e_note.grid(row=1, column=3, sticky="ew", padx=15, pady=(0, 15))

        # Submit button
        self.submit_btn = customtkinter.CTkButton(
            self.form_frame, text="Record Expense", fg_color="#BA7517", hover_color="#A06312", 
            font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"),
            command=self.submit_expense
        )
        self.submit_btn.grid(row=1, column=4, sticky="ew", padx=15, pady=(0, 15))

        # 2. Log Title & Date Filter Frame
        self.log_header = customtkinter.CTkFrame(self, fg_color="transparent")
        self.log_header.grid(row=2, column=0, sticky="ew", padx=20, pady=(5, 5))
        self.log_header.grid_columnconfigure(0, weight=1)
        self.log_header.grid_columnconfigure(1, weight=0)
        self.log_header.grid_columnconfigure(2, weight=0)

        self.log_title = customtkinter.CTkLabel(
            self.log_header, text="Operating Costs Log", font=customtkinter.CTkFont(family="Inter", size=16, weight="bold"), text_color="#C9C5BC"
        )
        self.log_title.grid(row=0, column=0, sticky="w")

        self.filter_lbl = customtkinter.CTkLabel(
            self.log_header, text="Filter Date: ", font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"), text_color="#8F8B83"
        )
        self.filter_lbl.grid(row=0, column=1, padx=5, sticky="e")

        self.filter_date_entry = customtkinter.CTkEntry(
            self.log_header, width=110, fg_color="#181715", border_color="#36322C", font=customtkinter.CTkFont(family="Inter", size=11)
        )
        self.filter_date_entry.grid(row=0, column=2, sticky="e")
        self.filter_date_entry.bind("<Return>", lambda e: self.refresh_expenses())
        self.filter_date_entry.bind("<FocusOut>", lambda e: self.refresh_expenses())

        # 3. Log Table Container
        self.table_container = customtkinter.CTkFrame(self, fg_color="#1F1E1B", border_width=1, border_color="#2D2C28")
        self.table_container.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 10))
        self.table_container.grid_rowconfigure(0, weight=0) # headers
        self.table_container.grid_rowconfigure(1, weight=1) # scroll
        self.table_container.grid_columnconfigure(0, weight=1)

        # Log Table Headers
        self.headers_frame = customtkinter.CTkFrame(self.table_container, fg_color="#2D2C28", height=30, corner_radius=0)
        self.headers_frame.grid(row=0, column=0, sticky="ew")
        self._configure_table_columns(self.headers_frame)

        log_headers = ["Category", "Amount (₹)", "Expense Date", "Note / Description", "Actions"]
        for idx, text in enumerate(log_headers):
            label = customtkinter.CTkLabel(
                self.headers_frame, text=text, font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#C9C5BC", anchor="w"
            )
            label.grid(row=0, column=idx, sticky="ew", padx=10, pady=5)

        # Log Scrollable rows
        self.scroll_frame = customtkinter.CTkScrollableFrame(self.table_container, fg_color="transparent", corner_radius=0)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        self._configure_table_columns(self.scroll_frame)

        # 4. Total Summary Bar
        self.total_frame = customtkinter.CTkFrame(self, fg_color="#181715", border_width=1, border_color="#2D2C28", height=40)
        self.total_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 20))
        
        self.total_lbl = customtkinter.CTkLabel(
            self.total_frame, text="Daily Total Expenditures: ", font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"), text_color="#8F8B83"
        )
        self.total_lbl.pack(side="left", padx=15)

        self.total_val = customtkinter.CTkLabel(
            self.total_frame, text="₹0.00", font=customtkinter.CTkFont(family="Inter", size=16, weight="bold"), text_color="#E55039"
        )
        self.total_val.pack(side="left")

    def _configure_table_columns(self, frame):
        frame.grid_columnconfigure(0, weight=2) # Category
        frame.grid_columnconfigure(1, weight=2) # Amount
        frame.grid_columnconfigure(2, weight=2) # Date
        frame.grid_columnconfigure(3, weight=4) # Note
        frame.grid_columnconfigure(4, weight=1) # Actions

    def on_show(self):
        """Pre-fills date fields and updates records."""
        today_str = datetime.date.today().strftime("%d-%m-%Y")
        
        self.e_date.delete(0, tk.END)
        self.e_date.insert(0, today_str)

        self.filter_date_entry.delete(0, tk.END)
        self.filter_date_entry.insert(0, today_str)
        
        self.e_category.set("Transport")
        self.e_amount.delete(0, tk.END)
        self.e_note.delete(0, tk.END)

        self.refresh_expenses()

    def refresh_expenses(self):
        # Clear rows
        for child in self.scroll_frame.winfo_children():
            child.destroy()

        date_input = self.filter_date_entry.get().strip()
        try:
            db_date = parse_date(date_input)
        except ValueError:
            # Fallback to today if invalid
            db_date = datetime.date.today().strftime("%Y-%m-%d")
            self.filter_date_entry.delete(0, tk.END)
            self.filter_date_entry.insert(0, format_date(db_date))

        expenses = expense_model.get_expenses_by_date(db_date)
        total = expense_model.get_total_expenses_by_date(db_date)

        # Update summary label
        self.total_val.configure(text=format_currency(total))

        if not expenses:
            no_data = customtkinter.CTkLabel(
                self.scroll_frame, text="No expenses recorded for this date.", font=customtkinter.CTkFont(family="Inter", size=12, slant="italic"), text_color="#8F8B83"
            )
            no_data.grid(row=0, column=0, columnspan=5, pady=20, sticky="ew")
            return

        for idx, item in enumerate(expenses):
            row_fg = "#282622" if idx % 2 == 0 else "#1F1E1B"
            row_frame = customtkinter.CTkFrame(self.scroll_frame, fg_color=row_fg, corner_radius=4)
            row_frame.grid(row=idx, column=0, columnspan=5, sticky="ew", pady=2, ipady=4)
            self._configure_table_columns(row_frame)

            # Category
            c_lbl = customtkinter.CTkLabel(row_frame, text=item['category'], text_color="#E8E6E3", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"))
            c_lbl.grid(row=0, column=0, sticky="ew", padx=10)

            # Amount
            a_lbl = customtkinter.CTkLabel(row_frame, text=format_currency(item['amount']), text_color="#E55039", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"))
            a_lbl.grid(row=0, column=1, sticky="ew", padx=10)

            # Date
            d_lbl = customtkinter.CTkLabel(row_frame, text=format_date(item['date']), text_color="#C9C5BC", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11))
            d_lbl.grid(row=0, column=2, sticky="ew", padx=10)

            # Note
            n_lbl = customtkinter.CTkLabel(row_frame, text=item['note'] or "-", text_color="#C9C5BC", anchor="w", font=customtkinter.CTkFont(family="Inter", size=11))
            n_lbl.grid(row=0, column=3, sticky="ew", padx=10)

            # Action Delete
            actions_frame = customtkinter.CTkFrame(row_frame, fg_color="transparent")
            actions_frame.grid(row=0, column=4, sticky="ew", padx=10)

            del_btn = customtkinter.CTkButton(
                actions_frame, text="Delete", width=50, height=20, fg_color="#4D1F1C", hover_color="#A93226", text_color="#E6F2FF",
                font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"),
                command=lambda pid=item['id'], pcat=item['category'], pamt=item['amount']: self.delete_expense_action(pid, pcat, pamt)
            )
            del_btn.pack(side="left")

    def submit_expense(self):
        date_input = self.e_date.get().strip()
        cat = self.e_category.get().strip()
        amt_str = self.e_amount.get().strip()
        note = self.e_note.get().strip()

        # Validations
        if not date_input or not amt_str or not cat:
            messagebox.showerror("Validation Error", "All fields marked with '*' are required.")
            return

        try:
            db_date = parse_date(date_input)
        except ValueError:
            messagebox.showerror("Validation Error", "Date must be in DD-MM-YYYY or YYYY-MM-DD format.")
            return

        try:
            amount = float(amt_str)
            if amount <= 0:
                raise ValueError("Amount must be greater than zero.")
        except ValueError:
            messagebox.showerror("Validation Error", "Amount must be a valid positive number.")
            return

        # Record Expense
        try:
            expense_model.insert_expense(db_date, cat, amount, note)
            self.controller.set_status(f"Added expense: ₹{amount:.2f} under '{cat}'")
            
            # Reset form fields
            self.e_amount.delete(0, tk.END)
            self.e_note.delete(0, tk.END)
            
            # Set filter date to matches insertion date and refresh list
            self.filter_date_entry.delete(0, tk.END)
            self.filter_date_entry.insert(0, format_date(db_date))
            
            self.refresh_expenses()
        except Exception as ex:
            messagebox.showerror("Database Error", f"Failed to record expense:\n{ex}")

    def delete_expense_action(self, expense_id, cat, amt):
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete this expense record: ₹{amt:.2f} under '{cat}'?")
        if confirm:
            try:
                expense_model.delete_expense(expense_id)
                self.controller.set_status("Deleted expense entry.")
                self.refresh_expenses()
            except Exception as ex:
                messagebox.showerror("Error", f"Failed to delete expense record:\n{ex}")
