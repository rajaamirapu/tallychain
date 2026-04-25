"""
TallyChain -- Reports Panel
Financial reports: Trial Balance, P&L, Balance Sheet, Cash Flow, Day Book, Outstanding
"""
import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.styles import *
from ui.widgets import DataTable, section_header, separator, fmt, scrolled_text


def _date_range_frame(parent, default_from="2024-04-01", default_to="2025-03-31"):
    """Returns a frame with from/to date entries and their StringVar."""
    frm = tk.Frame(parent, bg=SURFACE)
    tk.Label(frm, text="From:", bg=SURFACE, fg=TEXT, font=FONT_SMALL).pack(side="left", padx=(0,4))
    from_var = tk.StringVar(value=default_from)
    tk.Entry(frm, textvariable=from_var, width=12, bg=SURFACE2, fg=TEXT,
             insertbackground=TEXT, relief="flat").pack(side="left", padx=(0,12))
    tk.Label(frm, text="To:", bg=SURFACE, fg=TEXT, font=FONT_SMALL).pack(side="left", padx=(0,4))
    to_var = tk.StringVar(value=default_to)
    tk.Entry(frm, textvariable=to_var, width=12, bg=SURFACE2, fg=TEXT,
             insertbackground=TEXT, relief="flat").pack(side="left")
    return frm, from_var, to_var


class TrialBalancePanel(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        section_header(hdr, "Trial Balance").pack(side="left")
        self.dr_frm, self.from_var, self.to_var = _date_range_frame(hdr)
        self.dr_frm.pack(side="left", padx=20)
        ttk.Button(hdr, text="Generate", style="Accent.TButton",
                   command=self._generate).pack(side="left")

        cols = [
            ("Account", 260, "w"),
            ("Type", 120, "center"),
            ("Debit (₹)", 130, "e"),
            ("Credit (₹)", 130, "e"),
        ]
        self.table = DataTable(self, cols, height=20)
        self.table.pack(fill="both", expand=True, padx=20, pady=(0,10))

        self.totals = tk.Label(self, text="", bg=SURFACE, fg=MUTED, font=FONT_SMALL)
        self.totals.pack(padx=20, pady=(0,12), anchor="e")

    def _generate(self):
        try:
            from modules.reporting import trial_balance
            rows = trial_balance(self.from_var.get(), self.to_var.get())
            table_rows = []
            total_dr = total_cr = 0.0
            for r in rows:
                dr = r.get("debit", 0) or 0
                cr = r.get("credit", 0) or 0
                total_dr += dr
                total_cr += cr
                table_rows.append((
                    r.get("account_name", ""),
                    r.get("account_type", ""),
                    fmt(dr) if dr else "",
                    fmt(cr) if cr else "",
                ))
            self.table.set_rows(table_rows)
            status = "✓ Balanced" if abs(total_dr - total_cr) < 0.01 else "✗ Unbalanced"
            color = SUCCESS if abs(total_dr - total_cr) < 0.01 else DANGER
            self.totals.config(
                text=f"Total Debit: {fmt(total_dr)}   Total Credit: {fmt(total_cr)}   {status}",
                fg=color)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh(self):
        pass


class ProfitLossPanel(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        section_header(hdr, "Profit & Loss Statement").pack(side="left")
        self.dr_frm, self.from_var, self.to_var = _date_range_frame(hdr)
        self.dr_frm.pack(side="left", padx=20)
        ttk.Button(hdr, text="Generate", style="Accent.TButton",
                   command=self._generate).pack(side="left")

        self.text_area = scrolled_text(self, height=30)
        self.text_area.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.text_area.config(state="disabled")

    def _generate(self):
        try:
            from modules.reporting import profit_and_loss
            data = profit_and_loss(self.from_var.get(), self.to_var.get())
            lines = []
            lines.append("=" * 60)
            lines.append("           PROFIT & LOSS STATEMENT")
            lines.append(f"   Period: {self.from_var.get()} to {self.to_var.get()}")
            lines.append("=" * 60)

            lines.append("\nINCOME")
            lines.append("-" * 60)
            total_income = 0.0
            for item in data.get("income", []):
                amt = item.get("amount", 0)
                total_income += amt
                lines.append(f"  {item.get('name',''):<40} {fmt(amt):>15}")
            lines.append(f"  {'TOTAL INCOME':<40} {fmt(total_income):>15}")

            lines.append("\nEXPENSES")
            lines.append("-" * 60)
            total_exp = 0.0
            for item in data.get("expenses", []):
                amt = item.get("amount", 0)
                total_exp += amt
                lines.append(f"  {item.get('name',''):<40} {fmt(amt):>15}")
            lines.append(f"  {'TOTAL EXPENSES':<40} {fmt(total_exp):>15}")

            net = total_income - total_exp
            lines.append("")
            lines.append("=" * 60)
            label = "NET PROFIT" if net >= 0 else "NET LOSS"
            lines.append(f"  {label:<40} {fmt(abs(net)):>15}")
            lines.append("=" * 60)

            self.text_area.config(state="normal")
            self.text_area.delete("1.0", "end")
            self.text_area.insert("1.0", "\n".join(lines))
            self.text_area.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh(self):
        pass


class BalanceSheetPanel(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        section_header(hdr, "Balance Sheet").pack(side="left")
        self.dr_frm, self.from_var, self.to_var = _date_range_frame(hdr)
        self.dr_frm.pack(side="left", padx=20)
        ttk.Button(hdr, text="Generate", style="Accent.TButton",
                   command=self._generate).pack(side="left")

        self.text_area = scrolled_text(self, height=30)
        self.text_area.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.text_area.config(state="disabled")

    def _generate(self):
        try:
            from modules.reporting import balance_sheet
            data = balance_sheet(self.from_var.get(), self.to_var.get())
            lines = []
            lines.append("=" * 60)
            lines.append("               BALANCE SHEET")
            lines.append(f"   As on: {self.to_var.get()}")
            lines.append("=" * 60)

            lines.append("\nASSETS")
            lines.append("-" * 60)
            total_assets = 0.0
            for item in data.get("assets", []):
                amt = item.get("amount", 0)
                total_assets += amt
                lines.append(f"  {item.get('name',''):<40} {fmt(amt):>15}")
            lines.append(f"  {'TOTAL ASSETS':<40} {fmt(total_assets):>15}")

            lines.append("\nLIABILITIES & EQUITY")
            lines.append("-" * 60)
            total_liab = 0.0
            for item in data.get("liabilities", []):
                amt = item.get("amount", 0)
                total_liab += amt
                lines.append(f"  {item.get('name',''):<40} {fmt(amt):>15}")
            for item in data.get("equity", []):
                amt = item.get("amount", 0)
                total_liab += amt
                lines.append(f"  {item.get('name',''):<40} {fmt(amt):>15}")
            lines.append(f"  {'TOTAL LIABILITIES & EQUITY':<40} {fmt(total_liab):>15}")

            lines.append("")
            lines.append("=" * 60)
            balanced = abs(total_assets - total_liab) < 0.01
            lines.append(f"  {'STATUS':<40} {'BALANCED ✓' if balanced else 'UNBALANCED ✗':>15}")
            lines.append("=" * 60)

            self.text_area.config(state="normal")
            self.text_area.delete("1.0", "end")
            self.text_area.insert("1.0", "\n".join(lines))
            self.text_area.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh(self):
        pass


class CashFlowPanel(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        section_header(hdr, "Cash Flow Statement").pack(side="left")
        self.dr_frm, self.from_var, self.to_var = _date_range_frame(hdr)
        self.dr_frm.pack(side="left", padx=20)
        ttk.Button(hdr, text="Generate", style="Accent.TButton",
                   command=self._generate).pack(side="left")

        self.text_area = scrolled_text(self, height=30)
        self.text_area.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.text_area.config(state="disabled")

    def _generate(self):
        try:
            from modules.reporting import cash_flow
            data = cash_flow(self.from_var.get(), self.to_var.get())
            lines = []
            lines.append("=" * 60)
            lines.append("            CASH FLOW STATEMENT")
            lines.append(f"   Period: {self.from_var.get()} to {self.to_var.get()}")
            lines.append("=" * 60)

            for section_key, section_label in [
                ("operating", "OPERATING ACTIVITIES"),
                ("investing", "INVESTING ACTIVITIES"),
                ("financing", "FINANCING ACTIVITIES"),
            ]:
                lines.append(f"\n{section_label}")
                lines.append("-" * 60)
                section_total = 0.0
                for item in data.get(section_key, []):
                    amt = item.get("amount", 0)
                    section_total += amt
                    lines.append(f"  {item.get('name',''):<40} {fmt(amt):>15}")
                lines.append(f"  {'Net ' + section_label:<40} {fmt(section_total):>15}")

            net_change = data.get("net_change", 0)
            opening = data.get("opening_balance", 0)
            closing = data.get("closing_balance", opening + net_change)
            lines.append("")
            lines.append("=" * 60)
            lines.append(f"  {'Opening Cash Balance':<40} {fmt(opening):>15}")
            lines.append(f"  {'Net Change in Cash':<40} {fmt(net_change):>15}")
            lines.append(f"  {'Closing Cash Balance':<40} {fmt(closing):>15}")
            lines.append("=" * 60)

            self.text_area.config(state="normal")
            self.text_area.delete("1.0", "end")
            self.text_area.insert("1.0", "\n".join(lines))
            self.text_area.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh(self):
        pass


class DayBookPanel(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        section_header(hdr, "Day Book").pack(side="left")
        self.dr_frm, self.from_var, self.to_var = _date_range_frame(hdr)
        self.dr_frm.pack(side="left", padx=20)
        ttk.Button(hdr, text="Generate", style="Accent.TButton",
                   command=self._generate).pack(side="left")

        cols = [
            ("Date", 100, "center"),
            ("Voucher No.", 120, "center"),
            ("Type", 100, "center"),
            ("Narration", 260, "w"),
            ("Debit (₹)", 120, "e"),
            ("Credit (₹)", 120, "e"),
        ]
        self.table = DataTable(self, cols, height=22)
        self.table.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        self.totals = tk.Label(self, text="", bg=SURFACE, fg=MUTED, font=FONT_SMALL)
        self.totals.pack(padx=20, pady=(0, 12), anchor="e")

    def _generate(self):
        try:
            from modules.reporting import day_book
            entries = day_book(self.from_var.get(), self.to_var.get())
            rows = []
            total_dr = total_cr = 0.0
            for e in entries:
                dr = e.get("debit", 0) or 0
                cr = e.get("credit", 0) or 0
                total_dr += dr
                total_cr += cr
                rows.append((
                    e.get("date", "")[:10],
                    e.get("voucher_no", ""),
                    e.get("voucher_type", ""),
                    e.get("narration", "")[:50],
                    fmt(dr) if dr else "",
                    fmt(cr) if cr else "",
                ))
            self.table.set_rows(rows)
            self.totals.config(
                text=f"Total Debit: {fmt(total_dr)}   Total Credit: {fmt(total_cr)}",
                fg=MUTED)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh(self):
        pass


class OutstandingPanel(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        section_header(hdr, "Receivables & Payables").pack(side="left")
        self.type_var = tk.StringVar(value="receivable")
        ttk.Radiobutton(hdr, text="Receivables", variable=self.type_var,
                        value="receivable", style="TRadiobutton").pack(side="left", padx=(20, 6))
        ttk.Radiobutton(hdr, text="Payables", variable=self.type_var,
                        value="payable", style="TRadiobutton").pack(side="left", padx=(0, 20))
        ttk.Button(hdr, text="Generate", style="Accent.TButton",
                   command=self._generate).pack(side="left")

        cols = [
            ("Invoice No.", 130, "center"),
            ("Party", 200, "w"),
            ("Invoice Date", 110, "center"),
            ("Due Date", 110, "center"),
            ("Amount (₹)", 130, "e"),
            ("Paid (₹)", 130, "e"),
            ("Outstanding (₹)", 150, "e"),
            ("Status", 90, "center"),
        ]
        self.table = DataTable(self, cols, height=22)
        self.table.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        self.totals = tk.Label(self, text="", bg=SURFACE, fg=MUTED, font=FONT_SMALL)
        self.totals.pack(padx=20, pady=(0, 12), anchor="e")

    def _generate(self):
        try:
            from modules.reporting import outstanding_report
            report = outstanding_report(self.type_var.get())
            rows = []
            total_amt = total_paid = total_outstanding = 0.0
            for r in report:
                amt = r.get("total_amount", 0) or 0
                paid = r.get("paid_amount", 0) or 0
                outstanding = r.get("outstanding", amt - paid)
                total_amt += amt
                total_paid += paid
                total_outstanding += outstanding
                rows.append((
                    r.get("invoice_number", ""),
                    r.get("party_name", ""),
                    r.get("invoice_date", "")[:10],
                    r.get("due_date", "")[:10] if r.get("due_date") else "",
                    fmt(amt),
                    fmt(paid),
                    fmt(outstanding),
                    r.get("status", ""),
                ))
            self.table.set_rows(rows)
            self.totals.config(
                text=f"Total: {fmt(total_amt)}   Paid: {fmt(total_paid)}   Outstanding: {fmt(total_outstanding)}",
                fg=MUTED)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh(self):
        pass


class ReportsPanel(ttk.Frame):
    """Tabbed container for all financial reports."""
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.panels = {
            "Trial Balance": TrialBalancePanel(nb, self.session),
            "Profit & Loss": ProfitLossPanel(nb, self.session),
            "Balance Sheet": BalanceSheetPanel(nb, self.session),
            "Cash Flow": CashFlowPanel(nb, self.session),
            "Day Book": DayBookPanel(nb, self.session),
            "Outstanding": OutstandingPanel(nb, self.session),
        }
        for label, panel in self.panels.items():
            nb.add(panel, text=label)

    def refresh(self):
        pass
