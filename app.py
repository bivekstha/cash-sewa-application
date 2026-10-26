import calendar as cal_module
import sqlite3
from datetime import date, datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

DB_PATH = Path(__file__).with_name("cash_sewa.db")
CURRENCIES = {
    "INR (₹)": {"code": "INR", "symbol": "₹"},
    "NPR (रू)": {"code": "NPR", "symbol": "रू"},
}
CATEGORIES = ["Food", "Travel", "Education", "Shopping", "Bills",
              "Entertainment", "Health", "Other"]

BG = "#0b1020"
PANEL = "#11182b"
CARD = "#151f36"
TEXT = "#edf2ff"
MUTED = "#aab8d4"
ACCENT = "#7c5cff"
GREEN = "#34d399"
RED = "#fb7185"
YELLOW = "#fbbf24"


def get_connection():
    return sqlite3.connect(DB_PATH)


def setup_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL CHECK(amount > 0),
                currency TEXT NOT NULL,
                category TEXT NOT NULL,
                expense_date TEXT NOT NULL,
                description TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month TEXT NOT NULL,
                currency TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount >= 0),
                UNIQUE(month, currency)
            )
        """)


def add_expense(amount, currency, category, expense_date, description):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO expenses
               (amount, currency, category, expense_date, description)
               VALUES (?, ?, ?, ?, ?)""",
            (amount, currency, category, expense_date.isoformat(), description.strip())
        )


def update_expense(expense_id, amount, currency, category, expense_date, description):
    """Update an existing transaction, preserving its ID."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE expenses
               SET amount = ?, currency = ?, category = ?,
                   expense_date = ?, description = ?
               WHERE id = ?""",
            (amount, currency, category, expense_date.isoformat(),
             description.strip(), int(expense_id))
        )


def delete_expense(expense_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (int(expense_id),))


def delete_expenses_for_month(currency, month):
    """Remove all expenses for a currency and month (YYYY-MM). Returns count deleted."""
    with get_connection() as conn:
        cur = conn.execute(
            """DELETE FROM expenses
               WHERE currency = ? AND substr(expense_date, 1, 7) = ?""",
            (currency, month),
        )
        return cur.rowcount


def delete_all_expenses(currency):
    """Remove every expense for a currency (all months). Returns count deleted."""
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM expenses WHERE currency = ?",
            (currency,),
        )
        return cur.rowcount


def get_expense(expense_id):
    """Return a single expense row by ID, or None."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT id, amount, currency, category, expense_date, description
               FROM expenses WHERE id = ?""",
            (int(expense_id),)
        ).fetchone()
    return row


def save_budget(month, currency, amount):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO budgets (month, currency, amount)
            VALUES (?, ?, ?)
            ON CONFLICT(month, currency) DO UPDATE SET amount = excluded.amount
        """, (month, currency, amount))


def load_expenses(currency, month):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, amount, currency, category, expense_date, description
               FROM expenses
               WHERE currency = ? AND substr(expense_date, 1, 7) = ?
               ORDER BY expense_date DESC, id DESC""",
            (currency, month)
        ).fetchall()
    return rows


def load_budget(month, currency):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT amount FROM budgets WHERE month = ? AND currency = ?",
            (month, currency)
        ).fetchone()
    return float(row[0]) if row else 0.0


def money(value, symbol):
    return f"{symbol}{value:,.2f}"


def make_saving_tips(spent, budget, category_totals, symbol):
    tips = []
    if budget <= 0:
        tips.append("Set a monthly budget to start tracking your spending limit.")
    else:
        ratio = spent / budget
        if ratio >= 1:
            tips.append(f"You have exceeded your budget by {money(spent - budget, symbol)}. Pause non-essential purchases if possible.")
        elif ratio >= 0.8:
            tips.append(f"You have used {ratio:.0%} of your budget. Review optional purchases before spending more.")
        else:
            tips.append(f"You have used {ratio:.0%} of your budget. Keep checking your spending.")
    if category_totals:
        top_category = max(category_totals.items(), key=lambda item: item[1])
        if top_category[1] > 0:
            tips.append(f"Your highest-spending category is {top_category[0]} ({money(top_category[1], symbol)}). See whether you can reduce it next month.")
    if spent == 0:
        tips.append("No expenses recorded for this month yet. Add your first expense.")
    return tips


class DatePickerPopup(tk.Toplevel):
    """Simple calendar popup built with pure Tkinter (no extra packages)."""

    def __init__(self, parent, initial_date, on_select):
        super().__init__(parent)
        self.title("Select date")
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.on_select = on_select

        try:
            self.view_year = initial_date.year
            self.view_month = initial_date.month
            self.selected = initial_date
        except Exception:
            today = date.today()
            self.view_year = today.year
            self.view_month = today.month
            self.selected = today

        header = tk.Frame(self, bg=PANEL, padx=10, pady=8)
        header.pack(fill="x")
        tk.Button(header, text="◀", command=self._prev_month, bg=CARD, fg=TEXT,
                  relief="flat", width=3, cursor="hand2").pack(side="left")
        self.month_label = tk.Label(header, text="", bg=PANEL, fg=TEXT,
                                    font=("Segoe UI", 12, "bold"))
        self.month_label.pack(side="left", expand=True)
        tk.Button(header, text="▶", command=self._next_month, bg=CARD, fg=TEXT,
                  relief="flat", width=3, cursor="hand2").pack(side="right")

        days_frame = tk.Frame(self, bg=PANEL, padx=10)
        days_frame.pack()
        for i, day_name in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
            tk.Label(days_frame, text=day_name, bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 9, "bold"), width=4).grid(row=0, column=i, padx=1, pady=2)

        self.grid_frame = tk.Frame(self, bg=PANEL, padx=10, pady=4)
        self.grid_frame.pack()

        footer = tk.Frame(self, bg=PANEL, padx=10, pady=8)
        footer.pack(fill="x")
        tk.Button(footer, text="Today", command=self._pick_today, bg=ACCENT, fg="white",
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(footer, text="Cancel", command=self.destroy, bg="#334155", fg="white",
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  font=("Segoe UI", 9, "bold")).pack(side="right")

        self._build_days()
        self.update_idletasks()
        # Center near parent
        try:
            px = parent.winfo_rootx() + 40
            py = parent.winfo_rooty() + 80
            self.geometry(f"+{px}+{py}")
        except Exception:
            pass

    def _build_days(self):
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        self.month_label.configure(
            text=f"{cal_module.month_name[self.view_month]} {self.view_year}"
        )
        weeks = cal_module.Calendar(firstweekday=0).monthdayscalendar(
            self.view_year, self.view_month
        )
        today = date.today()
        for r, week in enumerate(weeks):
            for c, day in enumerate(week):
                if day == 0:
                    tk.Label(self.grid_frame, text="", bg=PANEL, width=4).grid(
                        row=r, column=c, padx=1, pady=1
                    )
                    continue
                d = date(self.view_year, self.view_month, day)
                is_selected = d == self.selected
                is_today = d == today
                bg = ACCENT if is_selected else (CARD if is_today else PANEL)
                fg = "white" if is_selected else (YELLOW if is_today else TEXT)
                btn = tk.Button(
                    self.grid_frame, text=str(day), width=4, bg=bg, fg=fg,
                    relief="flat", cursor="hand2", font=("Segoe UI", 9),
                    command=lambda dd=d: self._choose(dd),
                )
                btn.grid(row=r, column=c, padx=1, pady=1)

    def _prev_month(self):
        if self.view_month == 1:
            self.view_month = 12
            self.view_year -= 1
        else:
            self.view_month -= 1
        self._build_days()

    def _next_month(self):
        if self.view_month == 12:
            self.view_month = 1
            self.view_year += 1
        else:
            self.view_month += 1
        self._build_days()

    def _pick_today(self):
        self._choose(date.today())

    def _choose(self, d):
        self.on_select(d)
        self.destroy()


class CashSewaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cash Sewa | Student Money Manager")
        self.root.geometry("1180x800")
        self.root.minsize(950, 680)
        self.root.configure(bg=BG)
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Treeview", background=CARD, foreground=TEXT,
                             fieldbackground=CARD, rowheight=29, borderwidth=0)
        self.style.configure("Treeview.Heading", background=PANEL, foreground=TEXT,
                             font=("Segoe UI", 10, "bold"), padding=8)
        self.style.map("Treeview", background=[("selected", ACCENT)])
        self.style.configure("TCombobox", fieldbackground=CARD, background=PANEL,
                             foreground=TEXT, padding=5)
        self.style.configure("TEntry", fieldbackground=CARD, foreground=TEXT, padding=6)

        today = date.today()
        self.month = today.strftime("%Y-%m")
        self.currency_label = tk.StringVar(value="INR (₹)")
        self.budget_var = tk.StringVar(value="0")
        self.amount_var = tk.StringVar(value="100")
        self.category_var = tk.StringVar(value=CATEGORIES[0])
        self.date_var = tk.StringVar(value=today.isoformat())
        self.description_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready • Your data is stored on this computer")
        self.editing_id = None  # None = add mode; int = edit mode

        self._build_ui()
        setup_database()
        self.refresh()
        self.root.bind("<Delete>", lambda _e: self.delete_selected())

    def make_button(self, parent, text, command, color=ACCENT):
        return tk.Button(parent, text=text, command=command, bg=color, fg="white",
                         activebackground=color, activeforeground="white",
                         relief="flat", bd=0, padx=13, pady=8,
                         font=("Segoe UI", 10, "bold"), cursor="hand2")

    def _build_ui(self):
        header = tk.Frame(self.root, bg=BG, padx=24, pady=18)
        header.pack(fill="x")
        title_row = tk.Frame(header, bg=BG)
        title_row.pack(fill="x")
        tk.Label(title_row, text="💸 Cash Sewa", bg=BG, fg=TEXT,
                 font=("Segoe UI", 24, "bold")).pack(side="left")
        tk.Label(title_row, text="Built by BIVEK SHRESTHA", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).pack(side="right", pady=(8, 0))
        tk.Label(header, text="Your money. Your plan. Your progress.  •  Offline desktop edition",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 0))

        controls = tk.Frame(self.root, bg=PANEL, padx=18, pady=12)
        controls.pack(fill="x", padx=24, pady=(0, 14))
        tk.Label(controls, text="Currency", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 8))
        currency_box = ttk.Combobox(controls, textvariable=self.currency_label,
                                    values=list(CURRENCIES.keys()), state="readonly", width=14)
        currency_box.pack(side="left")
        currency_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        tk.Label(controls, text="Month", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=(24, 8))
        self.month_display = tk.Label(
            controls,
            text=datetime.strptime(self.month, "%Y-%m").strftime("%B %Y"),
            bg=PANEL, fg=MUTED, font=("Segoe UI", 10),
        )
        self.month_display.pack(side="left")

        budget_frame = tk.Frame(controls, bg=PANEL)
        budget_frame.pack(side="right")
        tk.Label(budget_frame, text="Monthly budget", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 8))
        ttk.Entry(budget_frame, textvariable=self.budget_var, width=13).pack(side="left", padx=(0, 8))
        self.make_button(budget_frame, "Save budget", self.save_budget_clicked).pack(side="left")

        self.metrics_frame = tk.Frame(self.root, bg=BG)
        self.metrics_frame.pack(fill="x", padx=24, pady=(0, 14))
        self.metric_labels = []
        for title in ("Monthly budget", "Total spent", "Remaining", "Transactions"):
            card = tk.Frame(self.metrics_frame, bg=CARD, padx=16, pady=14,
                            highlightbackground="#2b3858", highlightthickness=1)
            card.pack(side="left", fill="both", expand=True, padx=(0, 10))
            tk.Label(card, text=title, bg=CARD, fg=MUTED,
                     font=("Segoe UI", 10)).pack(anchor="w")
            value = tk.Label(card, text="—", bg=CARD, fg=TEXT,
                             font=("Segoe UI", 18, "bold"))
            value.pack(anchor="w", pady=(7, 0))
            self.metric_labels.append(value)

        content = tk.Frame(self.root, bg=BG)
        content.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        left = tk.Frame(content, bg=PANEL, padx=15, pady=15)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        right = tk.Frame(content, bg=PANEL, padx=15, pady=15)
        right.pack(side="right", fill="both", expand=True)

        tk.Label(left, text="🧾 Recent transactions", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))
        tree_wrap = tk.Frame(left, bg=PANEL)
        tree_wrap.pack(fill="both", expand=True)
        columns = ("id", "date", "category", "description", "amount")
        self.tree = ttk.Treeview(tree_wrap, columns=columns, show="headings", height=11)
        for col, label, width in [
            ("id", "ID", 45), ("date", "Date", 95), ("category", "Category", 100),
            ("description", "Description", 170), ("amount", "Amount", 105)
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, minwidth=40, anchor="w")
        tree_scroll = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        # Mouse-wheel scroll over the table
        self.tree.bind("<MouseWheel>", lambda e: self.tree.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        self.tree.bind("<Button-4>", lambda e: self.tree.yview_scroll(-1, "units"))
        self.tree.bind("<Button-5>", lambda e: self.tree.yview_scroll(1, "units"))
        actions = tk.Frame(left, bg=PANEL)
        actions.pack(fill="x", pady=(10, 0))
        self.make_button(actions, "Edit selected", self.edit_selected, ACCENT).pack(side="left")
        self.make_button(actions, "Delete selected", self.delete_selected, RED).pack(side="left", padx=8)
        self.make_button(actions, "Clear this month", self.clear_month_transactions, RED).pack(side="left", padx=8)
        self.make_button(actions, "Clear all history", self.clear_all_transactions, "#7f1d1d").pack(side="left", padx=8)
        self.make_button(actions, "Refresh", self.refresh, "#334155").pack(side="left")

        self.form_title = tk.Label(right, text="➕ Add an expense", bg=PANEL, fg=TEXT,
                                   font=("Segoe UI", 14, "bold"))
        self.form_title.pack(anchor="w", pady=(0, 12))

        self._form_label(right, "Amount")
        ttk.Entry(right, textvariable=self.amount_var).pack(fill="x", pady=(0, 9))

        self._form_label(right, "Category")
        ttk.Combobox(right, textvariable=self.category_var, values=CATEGORIES,
                     state="readonly").pack(fill="x", pady=(0, 9))

        self._form_label(right, "Date (YYYY-MM-DD)")
        date_row = tk.Frame(right, bg=PANEL)
        date_row.pack(fill="x", pady=(0, 9))
        ttk.Entry(date_row, textvariable=self.date_var).pack(side="left", fill="x", expand=True)
        self.make_button(date_row, "📅", self.open_calendar, ACCENT).pack(side="left", padx=(6, 0))
        self.make_button(date_row, "Today", self.set_today_date, "#334155").pack(side="left", padx=(6, 0))

        self._form_label(right, "Description")
        ttk.Entry(right, textvariable=self.description_var).pack(fill="x", pady=(0, 12))

        form_actions = tk.Frame(right, bg=PANEL)
        form_actions.pack(fill="x")
        self.save_btn = self.make_button(form_actions, "Add expense", self.save_expense_clicked, GREEN)
        self.save_btn.pack(side="left", fill="x", expand=True)
        self.clear_btn = self.make_button(form_actions, "Clear form", self.clear_form, "#334155")
        self.clear_btn.pack(side="left", padx=(8, 0))

        tk.Label(right, text="💡 Saving tips", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(18, 8))
        tips_wrap = tk.Frame(right, bg=PANEL)
        tips_wrap.pack(fill="both", expand=True)
        self.tips_text = tk.Text(tips_wrap, height=6, wrap="word", bg=CARD, fg=TEXT,
                                 insertbackground=TEXT, relief="flat", font=("Segoe UI", 10),
                                 padx=10, pady=8)
        tips_scroll = ttk.Scrollbar(tips_wrap, orient="vertical", command=self.tips_text.yview)
        self.tips_text.configure(yscrollcommand=tips_scroll.set)
        self.tips_text.pack(side="left", fill="both", expand=True)
        tips_scroll.pack(side="right", fill="y")
        self.tips_text.configure(state="disabled")

        status = tk.Frame(self.root, bg="#080c18")
        status.pack(fill="x")
        tk.Label(status, textvariable=self.status_var, bg="#080c18",
                 fg=MUTED, anchor="w", padx=24, pady=8, font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True)
        tk.Label(status, text="Built by BIVEK SHRESTHA", bg="#080c18",
                 fg=ACCENT, anchor="e", padx=24, pady=8, font=("Segoe UI", 9, "bold")).pack(side="right")

    def _form_label(self, parent, text):
        tk.Label(parent, text=text, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))

    def selected_currency(self):
        info = CURRENCIES[self.currency_label.get()]
        return info["code"], info["symbol"]

    def set_today_date(self):
        self.date_var.set(date.today().isoformat())

    def open_calendar(self):
        try:
            initial = date.fromisoformat(self.date_var.get().strip())
        except ValueError:
            initial = date.today()

        def on_select(d):
            self.date_var.set(d.isoformat())

        DatePickerPopup(self.root, initial, on_select)

    def clear_form(self):
        """Cancel editing and reset the form for a new expense."""
        self.editing_id = None
        self.amount_var.set("100")
        self.category_var.set(CATEGORIES[0])
        self.date_var.set(date.today().isoformat())
        self.description_var.set("")
        self.form_title.configure(text="➕ Add an expense")
        self.save_btn.configure(text="Add expense", bg=GREEN, activebackground=GREEN)
        self.clear_btn.configure(text="Clear form")
        self.status_var.set("Form cleared • Ready to add a new expense")

    def _enter_edit_mode(self, expense_id):
        row = get_expense(expense_id)
        if not row:
            messagebox.showerror("Not found", f"Transaction ID {expense_id} no longer exists.")
            self.clear_form()
            self.refresh()
            return
        self.editing_id = int(row[0])
        amount = float(row[1])
        if amount == int(amount):
            self.amount_var.set(str(int(amount)))
        else:
            self.amount_var.set(f"{amount:g}")
        self.category_var.set(row[3] if row[3] in CATEGORIES else CATEGORIES[0])
        self.date_var.set(row[4])
        self.description_var.set(row[5] or "")
        for label, info in CURRENCIES.items():
            if info["code"] == row[2]:
                self.currency_label.set(label)
                break
        self.form_title.configure(text=f"✏️ Edit expense #{self.editing_id}")
        self.save_btn.configure(text="Save changes", bg=YELLOW, activebackground=YELLOW)
        self.clear_btn.configure(text="Cancel edit")
        self.status_var.set(f"Editing transaction #{self.editing_id} • Change any field and click Save changes")

    def _on_tree_double_click(self, _event):
        self.edit_selected()

    def edit_selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select a transaction", "Select a transaction in the table first.")
            return
        values = self.tree.item(selection[0], "values")
        self._enter_edit_mode(values[0])

    def save_budget_clicked(self):
        currency, _symbol = self.selected_currency()
        try:
            amount = float(self.budget_var.get())
            if amount < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid budget", "Enter a valid budget amount (zero or greater).")
            return
        save_budget(self.month, currency, amount)
        self.status_var.set("Budget saved locally.")
        self.refresh()

    def save_expense_clicked(self):
        currency, _symbol = self.selected_currency()
        try:
            amount = float(self.amount_var.get().replace(",", "").strip())
            if amount <= 0:
                raise ValueError
            expense_date = date.fromisoformat(self.date_var.get().strip())
        except ValueError:
            messagebox.showerror(
                "Invalid input",
                "Enter an amount greater than zero and a valid date such as 2026-10-26."
            )
            return

        if expense_date.strftime("%Y-%m") != self.month:
            messagebox.showinfo(
                "Different month",
                "This version displays the current month only. The expense will be saved, "
                "but may not appear in the current list."
            )

        description = self.description_var.get()
        category = self.category_var.get()

        if self.editing_id is not None:
            update_expense(self.editing_id, amount, currency, category, expense_date, description)
            self.status_var.set(f"Transaction #{self.editing_id} updated and saved locally.")
            self.clear_form()
        else:
            add_expense(amount, currency, category, expense_date, description)
            self.description_var.set("")
            self.status_var.set("Expense added and saved locally.")

        self.refresh()

    def delete_selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select a transaction", "Select a transaction in the table first.")
            return
        values = self.tree.item(selection[0], "values")
        expense_id = values[0]
        if messagebox.askyesno("Delete transaction", f"Delete transaction ID {expense_id}?"):
            if self.editing_id is not None and int(expense_id) == self.editing_id:
                self.clear_form()
            delete_expense(expense_id)
            self.status_var.set(f"Transaction #{expense_id} deleted.")
            self.refresh()

    def clear_month_transactions(self):
        """Remove all saved transactions for the current month and currency."""
        currency, _symbol = self.selected_currency()
        month_label = datetime.strptime(self.month, "%Y-%m").strftime("%B %Y")
        count = len(load_expenses(currency, self.month))
        if count == 0:
            messagebox.showinfo("Nothing to clear", f"No {currency} transactions for {month_label}.")
            return
        ok = messagebox.askyesno(
            "Clear this month",
            f"Delete all {count} {currency} transaction(s) for {month_label}?\n\n"
            "This cannot be undone.",
        )
        if not ok:
            return
        deleted = delete_expenses_for_month(currency, self.month)
        self.clear_form()
        self.status_var.set(f"Cleared {deleted} transaction(s) for {month_label}.")
        self.refresh()

    def clear_all_transactions(self):
        """Remove every saved transaction for the selected currency (all months)."""
        currency, _symbol = self.selected_currency()
        with get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM expenses WHERE currency = ?", (currency,)
            ).fetchone()[0]
        if total == 0:
            messagebox.showinfo("Nothing to clear", f"No saved {currency} transactions.")
            return
        ok = messagebox.askyesno(
            "Clear all history",
            f"Delete ALL {total} saved {currency} transaction(s) from every month?\n\n"
            "This removes old history permanently and cannot be undone.",
        )
        if not ok:
            return
        deleted = delete_all_expenses(currency)
        self.clear_form()
        self.status_var.set(f"Cleared all history: {deleted} {currency} transaction(s) removed.")
        self.refresh()

    def refresh(self):
        currency, symbol = self.selected_currency()
        budget = load_budget(self.month, currency)
        rows = load_expenses(currency, self.month)
        spent = sum(float(row[1]) for row in rows)
        remaining = budget - spent
        self.budget_var.set(f"{budget:g}")
        for label in self.tree.get_children():
            self.tree.delete(label)
        for row in rows:
            try:
                display_date = date.fromisoformat(row[4]).strftime("%d %b %Y")
            except ValueError:
                display_date = row[4]
            self.tree.insert("", "end", values=(
                row[0], display_date, row[3], row[5] or "—", money(float(row[1]), symbol)
            ))
        for label, value in zip(self.metric_labels, (
            money(budget, symbol), money(spent, symbol), money(remaining, symbol), str(len(rows))
        )):
            label.configure(text=value)
        category_totals = {}
        for row in rows:
            category_totals[row[3]] = category_totals.get(row[3], 0.0) + float(row[1])
        tips = make_saving_tips(spent, budget, category_totals, symbol)
        self.tips_text.configure(state="normal")
        self.tips_text.delete("1.0", "end")
        self.tips_text.insert("1.0", "\n\n".join("• " + tip for tip in tips))
        self.tips_text.configure(state="disabled")


def main():
    setup_database()
    root = tk.Tk()
    CashSewaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
