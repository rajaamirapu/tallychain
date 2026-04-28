"""TallyChain -- Chart of Accounts & Ledger Statement Panel"""
import tkinter as tk
from tkinter import ttk, messagebox
from ui.styles import *
from ui.widgets import DataTable, FormDialog, section_header, card, fmt


ACCOUNT_TYPES = ["ASSET","LIABILITY","EQUITY","INCOME","EXPENSE","BANK","CASH",
                 "SUNDRY_DEBTOR","SUNDRY_CREDITOR","TAX_PAYABLE","TAX_RECEIVABLE",
                 "FIXED_ASSET","STOCK"]


class AccountsPanel(ttk.Frame):
    def __init__(self, parent, session, **kwargs):
        super().__init__(parent, style="Dark.TFrame", padding=20)
        self.session = session
        self._accounts = []
        self._build()
        self.refresh()

    def _build(self):
        # Header
        hdr = ttk.Frame(self, style="Dark.TFrame")
        hdr.pack(fill="x", pady=(0, 14))
        ttk.Label(hdr, text="Chart of Accounts", style="XL.TLabel",
                  background=BG).pack(side="left")
        ttk.Button(hdr, text="+ New Account", style="Primary.TButton",
                   command=self._new_account).pack(side="right")
        ttk.Button(hdr, text="View Ledger", command=self._view_ledger).pack(
            side="right", padx=(0,8))

        # Search bar
        sf = ttk.Frame(self, style="Dark.TFrame")
        sf.pack(fill="x", pady=(0,10))
        ttk.Label(sf, text="Search:", style="Muted.TLabel", background=BG).pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_filter())
        ttk.Entry(sf, textvariable=self._search_var, width=30).pack(side="left", padx=8)
        self._type_var = tk.StringVar(value="All Types")
        cb = ttk.Combobox(sf, textvariable=self._type_var,
                          values=["All Types"]+ACCOUNT_TYPES, width=20, state="readonly")
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _: self._apply_filter())

        # Table
        cols = ["code","name","account_type","opening_balance","is_active"]
        self.tbl = DataTable(self, cols, height=18)
        self.tbl.pack(fill="both", expand=True)
        self.tbl.on_double_click(self._on_row_dbl)

    def refresh(self):
        from modules.ledger import list_accounts
        cid = self.session.get("company_id","default")
        self._accounts = [a.model_dump() for a in list_accounts(cid)]
        self._apply_filter()

    def _apply_filter(self):
        q  = self._search_var.get().lower()
        tp = self._type_var.get()
        rows = []
        for a in self._accounts:
            if q and q not in a["name"].lower() and q not in a["code"]:
                continue
            if tp != "All Types" and a["account_type"] != tp:
                continue
            ob = f"₹{fmt(a['opening_balance'])} {a['opening_balance_type']}" if a.get("opening_balance") else "—"
            rows.append({
                "code": a["code"], "name": a["name"],
                "account_type": a["account_type"],
                "opening_balance": ob,
                "is_active": "Active" if a["is_active"] else "Inactive",
            })
        self.tbl.set_rows(rows)

    def _new_account(self):
        if not self.session.get("role") in ("admin","accountant"):
            messagebox.showwarning("Access Denied","Only Admin/Accountant can create accounts.")
            return
        fields = [
            {"key":"code",  "label":"Account Code"},
            {"key":"name",  "label":"Account Name"},
            {"key":"account_type","label":"Account Type","type":"select","options":ACCOUNT_TYPES,"default":"ASSET"},
            {"key":"opening_balance","label":"Opening Balance","type":"number","default":"0"},
            {"key":"opening_balance_type","label":"Balance Type","type":"select",
             "options":["Dr","Cr"],"default":"Dr"},
            {"key":"gstin","label":"GSTIN (optional)"},
        ]
        def submit(data):
            from database.models import Account
            from modules.ledger import create_account
            acc = Account(
                code=data["code"], name=data["name"],
                account_type=data["account_type"],
                opening_balance=float(data["opening_balance"] or 0),
                opening_balance_type=data["opening_balance_type"],
                gstin=data["gstin"] or None,
                company_id=self.session.get("company_id","default"),
            )
            create_account(acc, user_id=self.session.get("user_id","system"))
            messagebox.showinfo("Success", f"Account '{acc.name}' created.")
            self.refresh()

        FormDialog(self, "New Account", fields, submit, "Create Account")

    def _on_row_dbl(self, row):
        if row:
            self._view_ledger_for(row)

    def _view_ledger(self):
        sel = self.tbl.get_selected()
        if not sel:
            messagebox.showinfo("Select Account","Double-click or select an account first.")
            return
        self._view_ledger_for(sel)

    def _view_ledger_for(self, row):
        code = str(row.get("code",""))
        cid  = self.session.get("company_id","default")
        from database.engine import get_db
        from modules.ledger import get_ledger_statement
        db = get_db()
        accs = db.col_find("accounts", code=code, company_id=cid)
        if not accs:
            messagebox.showerror("Error","Account not found.")
            return
        acc_id = accs[0]["id"]

        win = tk.Toplevel(self)
        win.title(f"Ledger — {row.get('name','')} ({code})")
        win.configure(bg=SURFACE)
        win.geometry("960x600")

        top = ttk.Frame(win, padding=(16,12,16,8))
        top.pack(fill="x")
        ttk.Label(top, text=f"Ledger Statement: {row.get('name','')}",
                  style="Title.TLabel").pack(side="left")

        date_fr = ttk.Frame(top)
        date_fr.pack(side="right")
        ttk.Label(date_fr, text="From:", style="Muted.TLabel").pack(side="left")
        from_var = tk.StringVar()
        ttk.Entry(date_fr, textvariable=from_var, width=12).pack(side="left", padx=4)
        ttk.Label(date_fr, text="To:", style="Muted.TLabel").pack(side="left")
        to_var = tk.StringVar()
        ttk.Entry(date_fr, textvariable=to_var, width=12).pack(side="left", padx=4)

        cols = ["date","voucher_number","voucher_type","narration","debit","credit","balance"]
        tbl  = DataTable(win, cols, height=16)
        tbl.pack(fill="both", expand=True, padx=16, pady=8)

        info = ttk.Frame(win, padding=(16,4,16,12))
        info.pack(fill="x")
        open_lbl   = ttk.Label(info, text="Opening: —", style="Muted.TLabel")
        open_lbl.pack(side="left")
        close_lbl  = ttk.Label(info, text="Closing: —", style="Accent.TLabel")
        close_lbl.pack(side="right")

        def load():
            try:
                stmt = get_ledger_statement(acc_id, cid,
                                            from_var.get() or None,
                                            to_var.get()   or None)
                rows = []
                for e in stmt["entries"]:
                    rows.append({
                        "date":           e["date"],
                        "voucher_number": e["voucher_number"],
                        "voucher_type":   e["voucher_type"],
                        "narration":      e["narration"][:40],
                        "debit":          f"₹{fmt(e['debit'])}"  if e["debit"]  else "—",
                        "credit":         f"₹{fmt(e['credit'])}" if e["credit"] else "—",
                        "balance":        f"₹{fmt(e['balance'])} {e['balance_type']}",
                    })
                tbl.set_rows(rows)
                open_lbl.configure(text=
                    f"Opening: ₹{fmt(stmt['opening_balance'])} {stmt['opening_balance_type']}")
                close_lbl.configure(text=
                    f"Closing: ₹{fmt(stmt['closing_balance'])} {stmt['closing_balance_type']}")
            except Exception as ex:
                messagebox.showerror("Error", str(ex), parent=win)

        ttk.Button(top, text="Load", style="Primary.TButton", command=load).pack(side="right", padx=8)
        load()
