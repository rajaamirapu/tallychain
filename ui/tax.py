"""
TallyChain -- Tax Panel
GST Rates management, GSTR-1, GSTR-3B computation
"""
import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.styles import *
from ui.widgets import DataTable, FormDialog, section_header, fmt, scrolled_text


class TaxRatesPanel(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        section_header(hdr, "Tax Rates").pack(side="left")
        ttk.Button(hdr, text="+ Add Rate", style="Accent.TButton",
                   command=self._add_rate).pack(side="right")

        cols = [
            ("Name", 180, "w"),
            ("Tax Type", 100, "center"),
            ("Rate (%)", 100, "e"),
            ("CGST %", 90, "e"),
            ("SGST %", 90, "e"),
            ("IGST %", 90, "e"),
            ("HSN/SAC", 120, "center"),
            ("Active", 70, "center"),
        ]
        self.table = DataTable(self, cols, height=20)
        self.table.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self._load()

    def _load(self):
        try:
            from database.engine import get_db
            db = get_db()
            rates = db.col_all("tax_rates")
            rows = []
            for r in rates:
                rows.append((
                    r.get("name", ""),
                    r.get("tax_type", ""),
                    f"{r.get('rate', 0):.1f}",
                    f"{r.get('cgst', 0):.1f}",
                    f"{r.get('sgst', 0):.1f}",
                    f"{r.get('igst', 0):.1f}",
                    r.get("hsn_code", "") or r.get("sac_code", ""),
                    "Yes" if r.get("is_active", True) else "No",
                ))
            self.table.set_rows(rows)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _add_rate(self):
        fields = [
            ("name", "Tax Rate Name", "text", ""),
            ("tax_type", "Tax Type", "select", "GST", ["GST", "IGST", "VAT", "NONE"]),
            ("rate", "Total Rate (%)", "number", "18"),
            ("cgst", "CGST Rate (%)", "number", "9"),
            ("sgst", "SGST Rate (%)", "number", "9"),
            ("igst", "IGST Rate (%)", "number", "18"),
            ("hsn_code", "HSN Code", "text", ""),
            ("description", "Description", "text", ""),
        ]
        dlg = FormDialog(self, "Add Tax Rate", fields)
        self.wait_window(dlg)
        if dlg.result:
            try:
                from modules.taxation import seed_tax_rates
                from database.engine import get_db
                import uuid
                from database.models import TaxRate
                db = get_db()
                data = dlg.result
                tr = TaxRate(
                    name=data["name"],
                    rate=float(data.get("rate", 0)),
                    tax_type=data.get("tax_type", "GST"),
                    cgst=float(data.get("cgst", 0)),
                    sgst=float(data.get("sgst", 0)),
                    igst=float(data.get("igst", 0)),
                    hsn_code=data.get("hsn_code", ""),
                    description=data.get("description", ""),
                )
                db.col_insert("tax_rates", tr.model_dump())
                self._load()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def refresh(self):
        self._load()


class GSTR1Panel(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        section_header(hdr, "GSTR-1 (Outward Supplies)").pack(side="left")

        ctrl = tk.Frame(self, bg=SURFACE)
        ctrl.pack(fill="x", padx=20, pady=(0, 10))
        tk.Label(ctrl, text="Month:", bg=SURFACE, fg=TEXT, font=FONT_SMALL).pack(side="left", padx=(0,4))
        self.month_var = tk.StringVar(value="2024-12")
        tk.Entry(ctrl, textvariable=self.month_var, width=10, bg=SURFACE2, fg=TEXT,
                 insertbackground=TEXT, relief="flat").pack(side="left", padx=(0,16))
        tk.Label(ctrl, text="(YYYY-MM)", bg=SURFACE, fg=MUTED, font=FONT_SMALL).pack(side="left", padx=(0,20))
        ttk.Button(ctrl, text="Compute GSTR-1", style="Accent.TButton",
                   command=self._compute).pack(side="left")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # B2B tab
        b2b_frame = ttk.Frame(nb, style="Card.TFrame")
        nb.add(b2b_frame, text="B2B Invoices")
        b2b_cols = [
            ("GSTIN/Party", 180, "w"),
            ("Invoice No.", 120, "center"),
            ("Date", 100, "center"),
            ("Taxable (₹)", 130, "e"),
            ("IGST (₹)", 110, "e"),
            ("CGST (₹)", 110, "e"),
            ("SGST (₹)", 110, "e"),
            ("Total (₹)", 120, "e"),
        ]
        self.b2b_table = DataTable(b2b_frame, b2b_cols, height=14)
        self.b2b_table.pack(fill="both", expand=True, padx=10, pady=10)

        # Summary tab
        sum_frame = ttk.Frame(nb, style="Card.TFrame")
        nb.add(sum_frame, text="Summary")
        summary_frame, self.summary_text = scrolled_text(sum_frame, height=20)
        summary_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.summary_text.config(state="disabled")

    def _compute(self):
        try:
            from modules.taxation import compute_gstr1
            month = self.month_var.get().strip()
            data = compute_gstr1(month)

            b2b_rows = []
            for inv in data.get("b2b", []):
                b2b_rows.append((
                    inv.get("party_gstin", inv.get("party_name", "")),
                    inv.get("invoice_number", ""),
                    inv.get("invoice_date", "")[:10],
                    fmt(inv.get("taxable_amount", 0)),
                    fmt(inv.get("igst", 0)),
                    fmt(inv.get("cgst", 0)),
                    fmt(inv.get("sgst", 0)),
                    fmt(inv.get("total_amount", 0)),
                ))
            self.b2b_table.set_rows(b2b_rows)

            summary = data.get("summary", {})
            lines = []
            lines.append("=" * 50)
            lines.append(f"  GSTR-1 Summary for {month}")
            lines.append("=" * 50)
            lines.append(f"  Total B2B Invoices   : {summary.get('b2b_count', 0)}")
            lines.append(f"  Total B2C Invoices   : {summary.get('b2c_count', 0)}")
            lines.append(f"  Total Taxable Value  : {fmt(summary.get('total_taxable', 0))}")
            lines.append(f"  Total IGST           : {fmt(summary.get('total_igst', 0))}")
            lines.append(f"  Total CGST           : {fmt(summary.get('total_cgst', 0))}")
            lines.append(f"  Total SGST           : {fmt(summary.get('total_sgst', 0))}")
            lines.append(f"  Total Tax            : {fmt(summary.get('total_tax', 0))}")
            lines.append(f"  Grand Total          : {fmt(summary.get('grand_total', 0))}")
            lines.append("=" * 50)

            self.summary_text.config(state="normal")
            self.summary_text.delete("1.0", "end")
            self.summary_text.insert("1.0", "\n".join(lines))
            self.summary_text.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh(self):
        pass


class GSTR3BPanel(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        section_header(hdr, "GSTR-3B (Monthly Summary Return)").pack(side="left")

        ctrl = tk.Frame(self, bg=SURFACE)
        ctrl.pack(fill="x", padx=20, pady=(0, 10))
        tk.Label(ctrl, text="Month:", bg=SURFACE, fg=TEXT, font=FONT_SMALL).pack(side="left", padx=(0,4))
        self.month_var = tk.StringVar(value="2024-12")
        tk.Entry(ctrl, textvariable=self.month_var, width=10, bg=SURFACE2, fg=TEXT,
                 insertbackground=TEXT, relief="flat").pack(side="left", padx=(0,16))
        tk.Label(ctrl, text="(YYYY-MM)", bg=SURFACE, fg=MUTED, font=FONT_SMALL).pack(side="left", padx=(0,20))
        ttk.Button(ctrl, text="Compute GSTR-3B", style="Accent.TButton",
                   command=self._compute).pack(side="left")

        text_frame, self.text_area = scrolled_text(self, height=30)
        text_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.text_area.config(state="disabled")

    def _compute(self):
        try:
            from modules.taxation import compute_gstr3b
            month = self.month_var.get().strip()
            data = compute_gstr3b(month)
            lines = []
            lines.append("=" * 60)
            lines.append(f"   GSTR-3B Return for {month}")
            lines.append("=" * 60)

            lines.append("\n3.1 OUTWARD SUPPLIES & TAX")
            lines.append("-" * 60)
            outward = data.get("outward_supplies", {})
            lines.append(f"  (a) Taxable Outward Supplies     : {fmt(outward.get('taxable_value', 0))}")
            lines.append(f"      IGST                         : {fmt(outward.get('igst', 0))}")
            lines.append(f"      CGST                         : {fmt(outward.get('cgst', 0))}")
            lines.append(f"      SGST                         : {fmt(outward.get('sgst', 0))}")
            lines.append(f"  (b) Zero-Rated Supplies          : {fmt(outward.get('zero_rated', 0))}")
            lines.append(f"  (c) Exempted/Nil Rated Supplies  : {fmt(outward.get('exempted', 0))}")

            lines.append("\n4. ELIGIBLE ITC")
            lines.append("-" * 60)
            itc = data.get("input_tax_credit", {})
            lines.append(f"  (A) ITC Available IGST           : {fmt(itc.get('igst', 0))}")
            lines.append(f"      ITC Available CGST           : {fmt(itc.get('cgst', 0))}")
            lines.append(f"      ITC Available SGST           : {fmt(itc.get('sgst', 0))}")

            lines.append("\n6. PAYMENT OF TAX")
            lines.append("-" * 60)
            payment = data.get("tax_payment", {})
            lines.append(f"  IGST Payable                     : {fmt(payment.get('igst_payable', 0))}")
            lines.append(f"  CGST Payable                     : {fmt(payment.get('cgst_payable', 0))}")
            lines.append(f"  SGST Payable                     : {fmt(payment.get('sgst_payable', 0))}")
            lines.append(f"  Net Tax Payable                  : {fmt(payment.get('net_payable', 0))}")
            lines.append("=" * 60)

            self.text_area.config(state="normal")
            self.text_area.delete("1.0", "end")
            self.text_area.insert("1.0", "\n".join(lines))
            self.text_area.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh(self):
        pass


class TaxPanel(ttk.Frame):
    """Tabbed container for all tax panels."""
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        from ui.gst_assistant import GSTAssistantPanel
        self.panels = {
            "Tax Rates": TaxRatesPanel(nb, self.session),
            "GSTR-1": GSTR1Panel(nb, self.session),
            "GSTR-3B": GSTR3BPanel(nb, self.session),
            "GST Assistant": GSTAssistantPanel(nb, self.session),
        }
        for label, panel in self.panels.items():
            nb.add(panel, text=label)

    def refresh(self):
        pass
