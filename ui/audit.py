"""
TallyChain -- Audit Trail Panel
View, filter and export the immutable audit log
"""
import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.styles import *
from ui.widgets import DataTable, section_header, scrolled_text


class AuditPanel(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        section_header(hdr, "Audit Trail").pack(side="left")
        ttk.Button(hdr, text="Refresh", command=self._load).pack(side="right")

        # Filter bar
        flt = tk.Frame(self, bg=SURFACE)
        flt.pack(fill="x", padx=20, pady=(0, 8))

        tk.Label(flt, text="User:", bg=SURFACE, fg=MUTED, font=FONT_SMALL).pack(side="left", padx=(0,4))
        self.user_var = tk.StringVar()
        tk.Entry(flt, textvariable=self.user_var, width=14, bg=SURFACE2, fg=TEXT,
                 insertbackground=TEXT, relief="flat").pack(side="left", padx=(0,14))

        tk.Label(flt, text="Action:", bg=SURFACE, fg=MUTED, font=FONT_SMALL).pack(side="left", padx=(0,4))
        self.action_var = tk.StringVar()
        tk.Entry(flt, textvariable=self.action_var, width=16, bg=SURFACE2, fg=TEXT,
                 insertbackground=TEXT, relief="flat").pack(side="left", padx=(0,14))

        tk.Label(flt, text="From:", bg=SURFACE, fg=MUTED, font=FONT_SMALL).pack(side="left", padx=(0,4))
        self.from_var = tk.StringVar()
        tk.Entry(flt, textvariable=self.from_var, width=12, bg=SURFACE2, fg=TEXT,
                 insertbackground=TEXT, relief="flat").pack(side="left", padx=(0,14))

        tk.Label(flt, text="To:", bg=SURFACE, fg=MUTED, font=FONT_SMALL).pack(side="left", padx=(0,4))
        self.to_var = tk.StringVar()
        tk.Entry(flt, textvariable=self.to_var, width=12, bg=SURFACE2, fg=TEXT,
                 insertbackground=TEXT, relief="flat").pack(side="left", padx=(0,14))

        ttk.Button(flt, text="Filter", command=self._load).pack(side="left")

        # Split: table top, detail bottom
        split = tk.Frame(self, bg=SURFACE)
        split.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        cols = [
            ("Timestamp", 160, "center"),
            ("User", 120, "w"),
            ("Action", 180, "w"),
            ("Entity Type", 120, "center"),
            ("Entity ID", 160, "center"),
            ("IP / Source", 130, "center"),
        ]
        self.table = DataTable(split, cols, height=16)
        self.table.pack(fill="x")
        self.table.on_select(self._on_select)

        tk.Label(split, text="Detail", bg=SURFACE, fg=MUTED, font=FONT_SMALL).pack(anchor="w", pady=(10, 2))
        self.detail = scrolled_text(split, height=8)
        self.detail.pack(fill="x")
        self.detail.config(state="disabled")

        self._entries_cache = []
        self._load()

    def _load(self):
        try:
            from audit.trail import AuditTrail
            kwargs = {}
            if self.user_var.get().strip():
                kwargs["user_id"] = self.user_var.get().strip()
            if self.action_var.get().strip():
                kwargs["action"] = self.action_var.get().strip()
            if self.from_var.get().strip():
                kwargs["from_time"] = self.from_var.get().strip()
            if self.to_var.get().strip():
                kwargs["to_time"] = self.to_var.get().strip()
            entries = AuditTrail.query(**kwargs)
            # entries is a list of AuditEntry pydantic models
            self._entries_cache = [e.model_dump() for e in entries]
            rows = []
            for e in self._entries_cache:
                rows.append((
                    str(e.get("timestamp", ""))[:19],
                    e.get("username", e.get("user_id", "")),
                    e.get("action", ""),
                    e.get("resource_type", e.get("entity_type", "")),
                    str(e.get("resource_id", e.get("entity_id", "")))[:30],
                    e.get("ip_address", e.get("source", "")),
                ))
            self.table.set_rows(rows)
        except Exception as ex:
            messagebox.showerror("Error", str(ex))

    def _on_select(self, idx):
        if idx < 0 or idx >= len(self._entries_cache):
            return
        entry = self._entries_cache[idx]
        import json
        detail_str = json.dumps(entry, indent=2, default=str)
        self.detail.config(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", detail_str)
        self.detail.config(state="disabled")

    def refresh(self):
        self._load()


class ReconciliationPanel(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        section_header(hdr, "Bank Reconciliation").pack(side="left")

        ctrl = tk.Frame(self, bg=SURFACE)
        ctrl.pack(fill="x", padx=20, pady=(0, 10))
        tk.Label(ctrl, text="Bank Account:", bg=SURFACE, fg=TEXT, font=FONT_SMALL).pack(side="left", padx=(0,6))
        self.account_var = tk.StringVar()
        self.account_cb = ttk.Combobox(ctrl, textvariable=self.account_var, width=28, state="readonly")
        self.account_cb.pack(side="left", padx=(0, 14))
        ttk.Button(ctrl, text="Auto-Match", style="Accent.TButton",
                   command=self._auto_match).pack(side="left", padx=(0, 8))
        ttk.Button(ctrl, text="Refresh", command=self._load_accounts).pack(side="left")

        cols = [
            ("Date", 100, "center"),
            ("Bank Ref.", 130, "center"),
            ("Description", 220, "w"),
            ("Amount (₹)", 120, "e"),
            ("Type", 80, "center"),
            ("Matched Voucher", 160, "center"),
            ("Status", 90, "center"),
        ]
        self.table = DataTable(self, cols, height=22)
        self.table.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self._load_accounts()

    def _load_accounts(self):
        try:
            from modules.ledger import list_accounts
            accounts = list_accounts()
            bank_accounts = [a for a in accounts
                             if "bank" in a.get("name", "").lower() or
                                a.get("account_type", "").lower() in ("bank", "cash")]
            names = [f"{a.get('account_code','')} - {a.get('name','')}" for a in bank_accounts]
            self.account_cb["values"] = names
            self._accounts_map = {
                f"{a.get('account_code','')} - {a.get('name','')}": a.get("id")
                for a in bank_accounts
            }
            if names:
                self.account_cb.current(0)
            self._load_statements()
        except Exception:
            pass

    def _load_statements(self):
        try:
            from database.engine import get_db
            db = get_db()
            statements = db.col_all("bank_statements")
            rows = []
            for s in statements:
                rows.append((
                    str(s.get("date", ""))[:10],
                    s.get("reference", ""),
                    s.get("description", "")[:40],
                    str(s.get("amount", "")),
                    s.get("transaction_type", ""),
                    s.get("matched_voucher_id", "")[:16] if s.get("matched_voucher_id") else "",
                    s.get("status", "unmatched"),
                ))
            self.table.set_rows(rows)
        except Exception:
            pass

    def _auto_match(self):
        try:
            acc_name = self.account_var.get()
            acc_id = self._accounts_map.get(acc_name)
            if not acc_id:
                messagebox.showwarning("Warning", "Please select a bank account first.")
                return
            from audit.trail import Reconciliation
            recon = Reconciliation()
            result = recon.auto_match(acc_id)
            matched = result.get("matched", 0)
            messagebox.showinfo("Auto-Match Complete",
                f"Reconciliation complete.\n\nMatched: {matched} transactions")
            self._load_statements()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh(self):
        self._load_accounts()


class AuditTabPanel(ttk.Frame):
    """Tabbed container for audit and reconciliation."""
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)
        self.audit = AuditPanel(nb, self.session)
        self.recon = ReconciliationPanel(nb, self.session)
        nb.add(self.audit, text="Audit Trail")
        nb.add(self.recon, text="Reconciliation")

    def refresh(self):
        pass
