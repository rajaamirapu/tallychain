"""TallyChain -- Voucher Entry Panel"""
import tkinter as tk
from tkinter import ttk, messagebox
from ui.styles import *
from ui.widgets import DataTable, fmt

VOUCHER_TYPES = ["PAYMENT","RECEIPT","JOURNAL","SALES","PURCHASE","CONTRA",
                 "DEBIT_NOTE","CREDIT_NOTE","OPENING_BALANCE"]


class VouchersPanel(ttk.Frame):
    def __init__(self, parent, session, **kwargs):
        super().__init__(parent, style="Dark.TFrame", padding=20)
        self.session = session
        self._accounts = []
        self._account_map = {}   # name -> id
        self._build()
        self._load_accounts()
        self.refresh()

    def _load_accounts(self):
        from modules.ledger import list_accounts
        cid = self.session.get("company_id","default")
        accs = list_accounts(cid)
        self._accounts = [f"{a.code} — {a.name}" for a in accs]
        self._account_map = {f"{a.code} — {a.name}": a.id for a in accs}
        self._account_id_to_name = {a.id: f"{a.code} — {a.name}" for a in accs}

    def _build(self):
        # Header
        hdr = ttk.Frame(self, style="Dark.TFrame")
        hdr.pack(fill="x", pady=(0,14))
        ttk.Label(hdr, text="Voucher Entry", style="XL.TLabel",
                  background=BG).pack(side="left")
        ttk.Button(hdr, text="+ New Voucher", style="Primary.TButton",
                   command=self._new_voucher).pack(side="right")

        # Filters
        ff = ttk.Frame(self, style="Dark.TFrame")
        ff.pack(fill="x", pady=(0,10))
        ttk.Label(ff, text="Type:", style="Muted.TLabel", background=BG).pack(side="left")
        self._ftype = tk.StringVar(value="All")
        ttk.Combobox(ff, textvariable=self._ftype,
                     values=["All"]+VOUCHER_TYPES, width=16, state="readonly"
                     ).pack(side="left", padx=(4,12))
        ttk.Label(ff, text="From:", style="Muted.TLabel", background=BG).pack(side="left")
        self._ffrom = tk.StringVar()
        ttk.Entry(ff, textvariable=self._ffrom, width=12).pack(side="left", padx=4)
        ttk.Label(ff, text="To:", style="Muted.TLabel", background=BG).pack(side="left")
        self._fto = tk.StringVar()
        ttk.Entry(ff, textvariable=self._fto, width=12).pack(side="left", padx=4)
        ttk.Button(ff, text="Filter", command=self.refresh).pack(side="left", padx=8)
        ttk.Button(ff, text="Clear",  command=self._clear_filter).pack(side="left")

        # Table
        cols = ["voucher_number","voucher_type","date","narration","total_dr","total_cr","block"]
        self.tbl = DataTable(self, cols, height=16)
        self.tbl.pack(fill="both", expand=True)
        self.tbl.on_double_click(self._view_detail)

        # Status bar
        self.status = ttk.Label(self, text="", style="Muted.TLabel", background=BG)
        self.status.pack(anchor="w", pady=(6,0))

    def _clear_filter(self):
        self._ftype.set("All"); self._ffrom.set(""); self._fto.set("")
        self.refresh()

    def refresh(self):
        from modules.ledger import list_vouchers
        cid = self.session.get("company_id","default")
        vtype = self._ftype.get() if self._ftype.get() != "All" else None
        fr = self._ffrom.get() or None
        to = self._fto.get()   or None
        vouchers = list_vouchers(cid, vtype, fr, to)
        rows = []
        for v in vouchers:
            dr = sum(l.debit  for l in v.lines)
            cr = sum(l.credit for l in v.lines)
            rows.append({
                "voucher_number": v.voucher_number,
                "voucher_type":   v.voucher_type,
                "date":           v.date,
                "narration":      (v.narration or "")[:50],
                "total_dr":       f"₹{fmt(dr)}",
                "total_cr":       f"₹{fmt(cr)}",
                "block":          f"#{v.block_index}" if v.block_index is not None else "—",
            })
        self.tbl.set_rows(rows)
        self.status.configure(text=f"{len(vouchers)} vouchers")

    def _new_voucher(self):
        role = self.session.get("role","viewer")
        if role not in ("admin","accountant"):
            messagebox.showwarning("Access Denied","Only Admin/Accountant can post vouchers.")
            return
        VoucherEntryDialog(self, self.session, self._accounts,
                           self._account_map, on_done=self.refresh)

    def _view_detail(self, row):
        if not row: return
        from modules.ledger import list_vouchers
        from database.engine import get_db
        cid = self.session.get("company_id","default")
        db = get_db()
        vnum = row.get("voucher_number","")
        vouchers = db.col_find("vouchers", voucher_number=vnum, company_id=cid)
        if not vouchers: return
        v_data = vouchers[0]
        win = tk.Toplevel(self)
        win.title(f"Voucher — {vnum}")
        win.configure(bg=SURFACE)
        win.geometry("720x500")
        pad = ttk.Frame(win, padding=20)
        pad.pack(fill="both", expand=True)
        fields = [
            ("Voucher #",  v_data.get("voucher_number","")),
            ("Type",       v_data.get("voucher_type","")),
            ("Date",       v_data.get("date","")),
            ("Narration",  v_data.get("narration","")),
            ("Reference",  v_data.get("reference","")),
            ("Block #",    str(v_data.get("block_index","—"))),
            ("Block Hash", (v_data.get("block_hash","") or "")[:48]+"…"),
        ]
        for lbl, val in fields:
            r = ttk.Frame(pad)
            r.pack(fill="x", pady=3)
            ttk.Label(r, text=lbl+":", style="Muted.TLabel", width=14, anchor="w").pack(side="left")
            ttk.Label(r, text=val, style="TLabel").pack(side="left")
        ttk.Separator(pad).pack(fill="x", pady=10)
        ttk.Label(pad, text="Ledger Entries", style="Title.TLabel").pack(anchor="w", pady=(0,6))
        cols = ["account","debit","credit","narration"]
        tbl  = DataTable(pad, cols, height=8)
        tbl.pack(fill="both", expand=True)
        lines = v_data.get("lines",[])
        rows  = []
        for l in lines:
            aname = self._account_id_to_name.get(l.get("account_id",""), l.get("account_id",""))
            rows.append({
                "account":   aname,
                "debit":     f"₹{fmt(l.get('debit',0))}" if l.get("debit") else "—",
                "credit":    f"₹{fmt(l.get('credit',0))}" if l.get("credit") else "—",
                "narration": l.get("narration",""),
            })
        tbl.set_rows(rows)


class VoucherEntryDialog(tk.Toplevel):
    """Full voucher entry form with dynamic lines."""
    def __init__(self, parent, session, accounts, account_map, on_done=None):
        super().__init__(parent)
        self.title("New Voucher Entry")
        self.configure(bg=SURFACE)
        self.geometry("820x620")
        self.grab_set()
        self.session   = session
        self.accounts  = accounts
        self.acc_map   = account_map
        self.on_done   = on_done
        self.line_rows = []
        self._build()
        self._add_line()
        self._add_line()

    def _build(self):
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        # Top form
        top = ttk.Frame(self, padding=(20,16,20,8))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure((1,3,5), weight=1)

        labels = ["Voucher Type","Date","Reference","Narration"]
        self._vtype = tk.StringVar(value="JOURNAL")
        self._date  = tk.StringVar(value=__import__("datetime").date.today().isoformat())
        self._ref   = tk.StringVar()
        self._narr  = tk.StringVar()
        vars_ = [self._vtype, self._date, self._ref, self._narr]

        for i, (lbl, var) in enumerate(zip(labels, vars_)):
            col = (i % 2) * 3
            row = i // 2
            ttk.Label(top, text=lbl+":", style="Muted.TLabel").grid(
                row=row, column=col, sticky="w", padx=(0,6), pady=4)
            if lbl == "Voucher Type":
                cb = ttk.Combobox(top, textvariable=var, values=VOUCHER_TYPES,
                                   state="readonly", width=18)
                cb.grid(row=row, column=col+1, sticky="ew", padx=(0,20), pady=4)
            else:
                ttk.Entry(top, textvariable=var, width=22).grid(
                    row=row, column=col+1, sticky="ew", padx=(0,20), pady=4)

        # Lines section
        lf = ttk.LabelFrame(self, text="Ledger Entries (Dr must = Cr)",
                             padding=(12,8))
        lf.grid(row=1, column=0, sticky="ew", padx=20, pady=8)
        lf.columnconfigure(0, weight=1)

        hdr = ttk.Frame(lf)
        hdr.pack(fill="x")
        for txt, w in [("Account",34),("Debit",12),("Credit",12),("Narration",20),("",4)]:
            ttk.Label(hdr, text=txt, style="Muted.TLabel", width=w,
                      anchor="w").pack(side="left", padx=2)

        self.lines_frame = ttk.Frame(lf)
        self.lines_frame.pack(fill="x")

        btn_row = ttk.Frame(lf)
        btn_row.pack(fill="x", pady=(8,0))
        ttk.Button(btn_row, text="+ Add Line", command=self._add_line).pack(side="left")
        self.balance_lbl = ttk.Label(btn_row, text="Diff: ₹0.00",
                                      style="Success.TLabel")
        self.balance_lbl.pack(side="right")

        # Footer
        ftr = ttk.Frame(self, padding=(20,8,20,16))
        ftr.grid(row=3, column=0, sticky="ew")
        ttk.Button(ftr, text="Cancel", command=self.destroy).pack(side="right", padx=(8,0))
        ttk.Button(ftr, text="Post to Blockchain", style="Primary.TButton",
                   command=self._submit).pack(side="right")

    def _add_line(self):
        row_f = ttk.Frame(self.lines_frame)
        row_f.pack(fill="x", pady=2)

        acc_var = tk.StringVar()
        dr_var  = tk.StringVar(value="0")
        cr_var  = tk.StringVar(value="0")
        nr_var  = tk.StringVar()

        cb = ttk.Combobox(row_f, textvariable=acc_var, values=self.accounts,
                          width=33, font=FONT_SM)
        cb.pack(side="left", padx=2)
        ttk.Entry(row_f, textvariable=dr_var, width=12).pack(side="left", padx=2)
        ttk.Entry(row_f, textvariable=cr_var, width=12).pack(side="left", padx=2)
        ttk.Entry(row_f, textvariable=nr_var, width=20).pack(side="left", padx=2)

        def del_line():
            self.line_rows.remove(entry)
            row_f.destroy()
            self._update_balance()

        ttk.Button(row_f, text="×", width=3, command=del_line).pack(side="left", padx=2)

        entry = {"acc": acc_var, "dr": dr_var, "cr": cr_var, "nr": nr_var}
        self.line_rows.append(entry)

        for var in (dr_var, cr_var):
            var.trace_add("write", lambda *_: self._update_balance())

    def _update_balance(self):
        try:
            total_dr = sum(float(r["dr"].get() or 0) for r in self.line_rows)
            total_cr = sum(float(r["cr"].get() or 0) for r in self.line_rows)
            diff = abs(total_dr - total_cr)
            balanced = diff < 0.005
            self.balance_lbl.configure(
                text=f"Dr ₹{fmt(total_dr)} | Cr ₹{fmt(total_cr)} | Diff ₹{fmt(diff)}",
                foreground=SUCCESS if balanced else DANGER
            )
        except Exception:
            pass

    def _submit(self):
        total_dr = sum(float(r["dr"].get() or 0) for r in self.line_rows)
        total_cr = sum(float(r["cr"].get() or 0) for r in self.line_rows)
        if abs(total_dr - total_cr) > 0.005:
            messagebox.showerror("Imbalance",
                f"Debits ₹{fmt(total_dr)} ≠ Credits ₹{fmt(total_cr)}\n"
                "Voucher must balance before posting.", parent=self)
            return
        lines = []
        for r in self.line_rows:
            acc_str = r["acc"].get().strip()
            acc_id  = self.acc_map.get(acc_str)
            if not acc_id:
                messagebox.showerror("Error", f"Unknown account: '{acc_str}'", parent=self)
                return
            dr = float(r["dr"].get() or 0)
            cr = float(r["cr"].get() or 0)
            if dr == 0 and cr == 0:
                continue
            lines.append({"account_id": acc_id, "account_name": acc_str,
                          "debit": dr, "credit": cr, "narration": r["nr"].get()})
        if not lines:
            messagebox.showerror("Error","No ledger lines entered.", parent=self)
            return
        try:
            from database.models import VoucherCreate, VoucherLine
            from modules.ledger import create_voucher
            vc = VoucherCreate(
                voucher_type=self._vtype.get(),
                date=self._date.get(),
                narration=self._narr.get(),
                reference=self._ref.get(),
                lines=[VoucherLine(**l) for l in lines],
            )
            v = create_voucher(vc,
                    user_id=self.session.get("user_id","system"),
                    username=self.session.get("username","system"),
                    company_id=self.session.get("company_id","default"))
            messagebox.showinfo("Posted",
                f"Voucher {v.voucher_number} posted to blockchain block #{v.block_index}",
                parent=self)
            self.destroy()
            if self.on_done:
                self.on_done()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)
