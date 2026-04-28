"""TallyChain -- Invoice Panel"""
import tkinter as tk
from tkinter import ttk, messagebox
import datetime
from ui.styles import *
from ui.widgets import DataTable, fmt

INV_TYPES = ["SALES","PURCHASE","CREDIT_NOTE","DEBIT_NOTE"]


class InvoicesPanel(ttk.Frame):
    def __init__(self, parent, session, **kwargs):
        super().__init__(parent, style="Dark.TFrame", padding=20)
        self.session  = session
        self._parties = []
        self._party_map = {}
        self._tax_rates = []
        self._build()
        self._load_lookups()
        self.refresh()

    def _load_lookups(self):
        from modules.ledger import list_accounts
        from modules.taxation import list_tax_rates
        cid = self.session.get("company_id","default")
        party_types = {"SUNDRY_DEBTOR","SUNDRY_CREDITOR","ASSET","LIABILITY"}
        accs = [a for a in list_accounts(cid) if a.account_type in party_types]
        self._parties    = [f"{a.code} — {a.name}" for a in accs]
        self._party_map  = {f"{a.code} — {a.name}": a.id for a in accs}
        rates = list_tax_rates(cid)
        self._tax_rates  = [r.name for r in rates if r.tax_type == "GST"]
        self._tax_rate_map = {r.name: r.rate for r in rates}

    def _build(self):
        hdr = ttk.Frame(self, style="Dark.TFrame")
        hdr.pack(fill="x", pady=(0,14))
        ttk.Label(hdr, text="Invoices", style="XL.TLabel", background=BG).pack(side="left")
        ttk.Button(hdr, text="+ New Invoice", style="Primary.TButton",
                   command=self._new_invoice).pack(side="right")
        ttk.Button(hdr, text="Record Payment",
                   command=self._record_payment).pack(side="right", padx=(0,8))

        # Tab bar
        self.tab_var = tk.StringVar(value="SALES")
        tab_bar = ttk.Frame(self, style="Dark.TFrame")
        tab_bar.pack(fill="x", pady=(0,10))
        for t in INV_TYPES:
            ttk.Radiobutton(tab_bar, text=t, variable=self.tab_var, value=t,
                            command=self.refresh).pack(side="left", padx=(0,4))

        cols = ["invoice_number","date","due_date","party_name",
                "total_taxable","total_tax","total_amount","payment_status"]
        self.tbl = DataTable(self, cols, height=17)
        self.tbl.pack(fill="both", expand=True)
        self.tbl.on_double_click(self._view_detail)

        self.status = ttk.Label(self, text="", style="Muted.TLabel", background=BG)
        self.status.pack(anchor="w", pady=(6,0))

    def refresh(self):
        from modules.invoicing import list_invoices
        cid  = self.session.get("company_id","default")
        invs = list_invoices(cid, invoice_type=self.tab_var.get())
        rows = []
        for i in invs:
            rows.append({
                "invoice_number": i.invoice_number,
                "date":           i.date,
                "due_date":       i.due_date or "—",
                "party_name":     i.party_name,
                "total_taxable":  f"₹{fmt(i.total_taxable)}",
                "total_tax":      f"₹{fmt(i.total_tax)}",
                "total_amount":   f"₹{fmt(i.total_amount)}",
                "payment_status": i.payment_status,
            })
        self.tbl.set_rows(rows)
        self.status.configure(text=f"{len(invs)} invoices")

    def _new_invoice(self):
        if self.session.get("role","viewer") not in ("admin","accountant"):
            messagebox.showwarning("Access Denied","Only Admin/Accountant can create invoices.")
            return
        InvoiceEntryDialog(self, self.session, self._parties, self._party_map,
                           self._tax_rates, self._tax_rate_map, on_done=self.refresh)

    def _record_payment(self):
        sel = self.tbl.get_selected()
        if not sel:
            messagebox.showinfo("Select","Select an invoice first."); return
        inv_num = str(sel.get("invoice_number",""))
        if sel.get("payment_status") == "PAID":
            messagebox.showinfo("Paid","This invoice is already fully paid."); return
        PaymentDialog(self, self.session, inv_num, on_done=self.refresh)

    def _view_detail(self, row):
        if not row: return
        from database.engine import get_db
        cid = self.session.get("company_id","default")
        db = get_db()
        invs = db.col_find("invoices", invoice_number=str(row.get("invoice_number","")),
                           company_id=cid)
        if not invs: return
        inv = invs[0]
        win = tk.Toplevel(self)
        win.title(f"Invoice — {inv['invoice_number']}")
        win.configure(bg=SURFACE)
        win.geometry("860x580")
        pad = ttk.Frame(win, padding=20)
        pad.pack(fill="both", expand=True)

        info = [("Invoice #",inv["invoice_number"]),("Type",inv["invoice_type"]),
                ("Date",inv["date"]),("Due Date",inv.get("due_date","—")),
                ("Party",inv["party_name"]),("GSTIN",inv.get("party_gstin","—")),
                ("Place of Supply",inv.get("place_of_supply","—"))]
        top2 = ttk.Frame(pad)
        top2.pack(fill="x", pady=(0,10))
        for i,(lbl,val) in enumerate(info):
            c = ttk.Frame(top2)
            c.grid(row=i//4, column=i%4, sticky="w", padx=16, pady=3)
            ttk.Label(c,text=lbl+":",style="Muted.TLabel").pack(anchor="w")
            ttk.Label(c,text=str(val),style="TLabel").pack(anchor="w")

        ttk.Separator(pad).pack(fill="x",pady=8)
        ttk.Label(pad,text="Line Items",style="Title.TLabel").pack(anchor="w",pady=(0,6))
        cols = ["description","hsn_sac","qty","rate","taxable","cgst","sgst","igst","total"]
        tbl = DataTable(pad, cols, height=8)
        tbl.pack(fill="both", expand=True)
        rows = []
        for item in inv.get("items",[]):
            rows.append({"description":item.get("description",""),
                "hsn_sac":item.get("hsn_sac",""),
                "qty":fmt(item.get("quantity",0),0),
                "rate":f"₹{fmt(item.get('rate',0))}",
                "taxable":f"₹{fmt(item.get('taxable_amount',0))}",
                "cgst":f"₹{fmt(item.get('cgst_amount',0))}",
                "sgst":f"₹{fmt(item.get('sgst_amount',0))}",
                "igst":f"₹{fmt(item.get('igst_amount',0))}",
                "total":f"₹{fmt(item.get('total',0))}"})
        tbl.set_rows(rows)
        summary = ttk.Frame(pad)
        summary.pack(fill="x", pady=8)
        for lbl, val in [("Subtotal",inv["total_taxable"]),("Total Tax",inv["total_tax"]),
                         ("Grand Total",inv["total_amount"]),("Paid",inv["paid_amount"])]:
            r = ttk.Frame(summary)
            r.pack(side="right", padx=16)
            ttk.Label(r,text=lbl,style="Muted.TLabel").pack(anchor="e")
            ttk.Label(r,text=f"₹{fmt(val)}",style="Accent.TLabel").pack(anchor="e")


class InvoiceEntryDialog(tk.Toplevel):
    def __init__(self, parent, session, parties, party_map,
                 tax_rates, tax_rate_map, on_done=None):
        super().__init__(parent)
        self.title("New Invoice")
        self.configure(bg=SURFACE)
        self.geometry("940x680")
        self.grab_set()
        self.session      = session
        self.parties      = parties
        self.party_map    = party_map
        self.tax_rates    = tax_rates
        self.tax_rate_map = tax_rate_map
        self.on_done      = on_done
        self.item_rows    = []
        self._build()
        self._add_item()

    def _build(self):
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)
        hdr = ttk.Frame(self, padding=(20,14,20,8))
        hdr.grid(row=0, column=0, sticky="ew")
        ttk.Label(hdr, text="New Invoice", style="XL.TLabel").pack(side="left")

        top = ttk.Frame(self, padding=(20,0,20,8))
        top.grid(row=1, column=0, sticky="ew")
        top.columnconfigure((1,3,5), weight=1)

        self._itype   = tk.StringVar(value="SALES")
        self._party   = tk.StringVar()
        self._date    = tk.StringVar(value=datetime.date.today().isoformat())
        self._due     = tk.StringVar()
        self._pos     = tk.StringVar()
        self._notes   = tk.StringVar()

        specs = [
            ("Type",        self._itype, "select", INV_TYPES),
            ("Party",       self._party, "combo",  self.parties),
            ("Date",        self._date,  "entry",  None),
            ("Due Date",    self._due,   "entry",  None),
            ("Place Supply",self._pos,   "entry",  None),
            ("Notes",       self._notes, "entry",  None),
        ]
        for i,(lbl,var,wtype,opts) in enumerate(specs):
            c,r = (i%2)*3, i//2
            ttk.Label(top,text=lbl+":",style="Muted.TLabel").grid(
                row=r,column=c,sticky="w",padx=(0,6),pady=3)
            if wtype=="select":
                ttk.Combobox(top,textvariable=var,values=opts,state="readonly",width=18
                             ).grid(row=r,column=c+1,sticky="ew",padx=(0,18),pady=3)
            elif wtype=="combo":
                ttk.Combobox(top,textvariable=var,values=opts,width=26
                             ).grid(row=r,column=c+1,sticky="ew",padx=(0,18),pady=3)
            else:
                ttk.Entry(top,textvariable=var,width=22
                          ).grid(row=r,column=c+1,sticky="ew",padx=(0,18),pady=3)

        # Items
        ilf = ttk.LabelFrame(self, text="Line Items", padding=(12,8))
        ilf.grid(row=2, column=0, sticky="nsew", padx=20, pady=4)
        ilf.columnconfigure(0, weight=1)
        ihdr = ttk.Frame(ilf)
        ihdr.pack(fill="x")
        for txt,w in [("Description",28),("HSN/SAC",8),("Qty",6),("Rate",10),
                      ("Disc%",5),("GST%",10),("Total",10),("",3)]:
            ttk.Label(ihdr,text=txt,style="Muted.TLabel",width=w,anchor="w"
                      ).pack(side="left",padx=2)
        self.items_frame = ttk.Frame(ilf)
        self.items_frame.pack(fill="x")
        ib = ttk.Frame(ilf)
        ib.pack(fill="x", pady=(8,0))
        ttk.Button(ib, text="+ Item", command=self._add_item).pack(side="left")
        self.total_lbl = ttk.Label(ib, text="Grand Total: ₹0.00", style="Accent.TLabel")
        self.total_lbl.pack(side="right")

        ftr = ttk.Frame(self, padding=(20,8,20,14))
        ftr.grid(row=3, column=0, sticky="ew")
        ttk.Button(ftr, text="Cancel", command=self.destroy).pack(side="right",padx=(8,0))
        ttk.Button(ftr, text="Create Invoice & Post Journal",
                   style="Primary.TButton", command=self._submit).pack(side="right")

    def _add_item(self):
        f = ttk.Frame(self.items_frame)
        f.pack(fill="x", pady=2)
        desc  = tk.StringVar()
        hsn   = tk.StringVar()
        qty   = tk.StringVar(value="1")
        rate  = tk.StringVar(value="0")
        disc  = tk.StringVar(value="0")
        gst   = tk.StringVar(value=self.tax_rates[0] if self.tax_rates else "")
        total_lbl = ttk.Label(f, text="₹0.00", style="Accent.TLabel", width=10)

        ttk.Entry(f,textvariable=desc,width=28).pack(side="left",padx=2)
        ttk.Entry(f,textvariable=hsn,width=8).pack(side="left",padx=2)
        ttk.Entry(f,textvariable=qty,width=6).pack(side="left",padx=2)
        ttk.Entry(f,textvariable=rate,width=10).pack(side="left",padx=2)
        ttk.Entry(f,textvariable=disc,width=5).pack(side="left",padx=2)
        ttk.Combobox(f,textvariable=gst,values=self.tax_rates,width=10,state="readonly"
                     ).pack(side="left",padx=2)
        total_lbl.pack(side="left",padx=2)

        entry = {"desc":desc,"hsn":hsn,"qty":qty,"rate":rate,"disc":disc,"gst":gst,"lbl":total_lbl,"frame":f}
        self.item_rows.append(entry)

        def update(*_):
            try:
                q  = float(qty.get() or 0)
                r  = float(rate.get() or 0)
                d  = float(disc.get() or 0)
                gr = self.tax_rate_map.get(gst.get(), 0)
                taxable = q * r * (1 - d/100)
                tot = taxable * (1 + gr/100)
                total_lbl.configure(text=f"₹{fmt(tot)}")
                self._update_grand()
            except Exception:
                pass

        def del_item():
            self.item_rows.remove(entry)
            f.destroy()
            self._update_grand()

        for v in (qty, rate, disc, gst):
            v.trace_add("write", update)
        ttk.Button(f, text="×", width=3, command=del_item).pack(side="left",padx=2)

    def _update_grand(self):
        total = 0
        for row in self.item_rows:
            try:
                q = float(row["qty"].get() or 0)
                r = float(row["rate"].get() or 0)
                d = float(row["disc"].get() or 0)
                g = self.tax_rate_map.get(row["gst"].get(), 0)
                total += q * r * (1 - d/100) * (1 + g/100)
            except Exception:
                pass
        self.total_lbl.configure(text=f"Grand Total: ₹{fmt(total)}")

    def _submit(self):
        from database.models import InvoiceCreate, InvoiceLineItem
        from modules.invoicing import create_invoice
        party_str = self._party.get().strip()
        party_id  = self.party_map.get(party_str)
        if not party_id:
            messagebox.showerror("Error","Select a valid party.", parent=self); return
        items = []
        for row in self.item_rows:
            gst_name = row["gst"].get()
            gst_rate = self.tax_rate_map.get(gst_name, 0)
            items.append(InvoiceLineItem(
                description=row["desc"].get(),
                hsn_sac=row["hsn"].get(),
                quantity=float(row["qty"].get() or 1),
                rate=float(row["rate"].get() or 0),
                discount_pct=float(row["disc"].get() or 0),
                tax_rate=gst_rate, cgst_rate=gst_rate/2,
                sgst_rate=gst_rate/2, igst_rate=0,
                taxable_amount=0, cgst_amount=0, sgst_amount=0,
                igst_amount=0, total=0,
            ))
        if not items:
            messagebox.showerror("Error","Add at least one line item.", parent=self); return
        try:
            ic = InvoiceCreate(
                invoice_type=self._itype.get(),
                date=self._date.get(),
                due_date=self._due.get() or "",
                party_id=party_id,
                place_of_supply=self._pos.get(),
                items=items,
                notes=self._notes.get(),
            )
            inv = create_invoice(ic,
                user_id=self.session.get("user_id","system"),
                username=self.session.get("username","system"),
                company_id=self.session.get("company_id","default"))
            messagebox.showinfo("Created",
                f"Invoice {inv.invoice_number}\nTotal: ₹{fmt(inv.total_amount)}\n"
                f"Journal entry auto-posted to blockchain.", parent=self)
            self.destroy()
            if self.on_done: self.on_done()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)


class PaymentDialog(tk.Toplevel):
    def __init__(self, parent, session, invoice_number, on_done=None):
        super().__init__(parent)
        self.title(f"Record Payment — {invoice_number}")
        self.configure(bg=SURFACE)
        self.geometry("420x280")
        self.grab_set()
        self.session = session
        self.inv_num = invoice_number
        self.on_done = on_done
        self._build()

    def _build(self):
        from database.engine import get_db
        from modules.ledger import list_accounts
        cid = self.session.get("company_id","default")
        db = get_db()
        invs = db.col_find("invoices", invoice_number=self.inv_num, company_id=cid)
        self._inv = invs[0] if invs else {}
        outstanding = self._inv.get("total_amount",0) - self._inv.get("paid_amount",0)

        pad = ttk.Frame(self, padding=24)
        pad.pack(fill="both", expand=True)
        ttk.Label(pad, text=f"Invoice: {self.inv_num}", style="Title.TLabel").pack(anchor="w")
        ttk.Label(pad, text=f"Outstanding: ₹{fmt(outstanding)}", style="Danger.TLabel").pack(anchor="w",pady=4)

        ttk.Separator(pad).pack(fill="x", pady=10)
        r1 = ttk.Frame(pad); r1.pack(fill="x", pady=4)
        ttk.Label(r1,text="Amount (₹):",style="Muted.TLabel",width=16).pack(side="left")
        self._amt = tk.StringVar(value=str(round(outstanding,2)))
        ttk.Entry(r1, textvariable=self._amt, width=20).pack(side="left")

        banks = [a for a in list_accounts(cid) if a.account_type in ("BANK","CASH")]
        bank_names = [f"{a.code} — {a.name}" for a in banks]
        self._bank_map = {f"{a.code} — {a.name}": a.id for a in banks}
        r2 = ttk.Frame(pad); r2.pack(fill="x", pady=4)
        ttk.Label(r2,text="Account:",style="Muted.TLabel",width=16).pack(side="left")
        self._bank = tk.StringVar(value=bank_names[0] if bank_names else "")
        ttk.Combobox(r2, textvariable=self._bank, values=bank_names,
                     state="readonly", width=24).pack(side="left")

        ftr = ttk.Frame(pad)
        ftr.pack(fill="x", pady=(14,0))
        ttk.Button(ftr, text="Cancel", command=self.destroy).pack(side="right",padx=(8,0))
        ttk.Button(ftr, text="Record Payment", style="Primary.TButton",
                   command=self._submit).pack(side="right")

    def _submit(self):
        from modules.invoicing import record_payment
        from database.engine import get_db
        cid = self.session.get("company_id","default")
        db  = get_db()
        inv_id = self._inv.get("id","")
        bank_id = self._bank_map.get(self._bank.get())
        if not bank_id:
            messagebox.showerror("Error","Select a bank/cash account.", parent=self); return
        try:
            inv = record_payment(inv_id, float(self._amt.get()),
                bank_id, self.session.get("user_id","system"),
                self.session.get("username","system"), cid)
            messagebox.showinfo("Done",
                f"Payment recorded. Status: {inv.payment_status}", parent=self)
            self.destroy()
            if self.on_done: self.on_done()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)
