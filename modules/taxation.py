"""
TallyChain — Taxation Engine
==============================
Supports:
  • India GST (CGST/SGST/IGST, HSN/SAC, inter/intra-state)
  • US Sales Tax / GAAP compliance
  • Generic configurable tax rates

GST logic:
  - Intra-state supply → CGST + SGST (equal split)
  - Inter-state supply → IGST
  - Exempt / NIL rated items
"""
from database.models import InvoiceLineItem, TaxRate
from database.engine import get_db

# Standard GST slabs (India)
GST_SLABS = [0, 3, 5, 12, 18, 28]

DEFAULT_TAX_RATES = [
    {"name": "GST 0%",   "rate": 0.0,  "cgst": 0.0,  "sgst": 0.0,  "igst": 0.0,  "tax_type": "GST"},
    {"name": "GST 5%",   "rate": 5.0,  "cgst": 2.5,  "sgst": 2.5,  "igst": 5.0,  "tax_type": "GST"},
    {"name": "GST 12%",  "rate": 12.0, "cgst": 6.0,  "sgst": 6.0,  "igst": 12.0, "tax_type": "GST"},
    {"name": "GST 18%",  "rate": 18.0, "cgst": 9.0,  "sgst": 9.0,  "igst": 18.0, "tax_type": "GST"},
    {"name": "GST 28%",  "rate": 28.0, "cgst": 14.0, "sgst": 14.0, "igst": 28.0, "tax_type": "GST"},
    {"name": "US Tax 6%",  "rate": 6.0,  "cgst": 0.0, "sgst": 0.0, "igst": 0.0,  "tax_type": "SALES_TAX"},
    {"name": "US Tax 8%",  "rate": 8.0,  "cgst": 0.0, "sgst": 0.0, "igst": 0.0,  "tax_type": "SALES_TAX"},
    {"name": "VAT 10%",    "rate": 10.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0,  "tax_type": "VAT"},
    {"name": "Generic 5%", "rate": 5.0,  "cgst": 0.0, "sgst": 0.0, "igst": 0.0,  "tax_type": "GENERIC"},
]


def seed_tax_rates(company_id: str = "default") -> int:
    db = get_db()
    existing = db.col_find("tax_rates", company_id=company_id)
    if existing:
        return 0
    count = 0
    for t in DEFAULT_TAX_RATES:
        rate = TaxRate(company_id=company_id, **t)
        db.col_insert("tax_rates", rate.model_dump())
        count += 1
    return count


def list_tax_rates(company_id: str = "default") -> list[TaxRate]:
    db = get_db()
    records = db.col_find("tax_rates", company_id=company_id)
    return [TaxRate(**r) for r in records]


def is_interstate(supplier_state: str, buyer_state: str) -> bool:
    return supplier_state.strip().lower() != buyer_state.strip().lower()


def compute_gst_line(
    item: InvoiceLineItem,
    place_of_supply: str,
    company_state: str,
    inter_state: bool = False,
) -> InvoiceLineItem:
    """
    Compute GST amounts for a single invoice line.
    Modifies and returns the item with populated tax fields.
    """
    qty = item.quantity
    rate = item.rate
    gross = qty * rate
    discount = gross * (item.discount_pct / 100.0)
    taxable = round(gross - discount, 2)

    item.taxable_amount = taxable

    if inter_state:
        item.igst_rate = item.tax_rate
        item.cgst_rate = 0.0
        item.sgst_rate = 0.0
        item.igst_amount = round(taxable * item.igst_rate / 100.0, 2)
        item.cgst_amount = 0.0
        item.sgst_amount = 0.0
    else:
        item.cgst_rate = round(item.tax_rate / 2.0, 2)
        item.sgst_rate = round(item.tax_rate / 2.0, 2)
        item.igst_rate = 0.0
        item.cgst_amount = round(taxable * item.cgst_rate / 100.0, 2)
        item.sgst_amount = round(taxable * item.sgst_rate / 100.0, 2)
        item.igst_amount = 0.0

    item.total = round(taxable + item.cgst_amount + item.sgst_amount + item.igst_amount, 2)
    return item


def compute_generic_tax_line(item: InvoiceLineItem) -> InvoiceLineItem:
    """Generic / US tax — single rate, no split."""
    qty = item.quantity
    gross = qty * item.rate
    discount = gross * (item.discount_pct / 100.0)
    taxable = round(gross - discount, 2)
    item.taxable_amount = taxable
    tax_amount = round(taxable * item.tax_rate / 100.0, 2)
    item.igst_amount = tax_amount       # store in igst_amount as catch-all
    item.total = round(taxable + tax_amount, 2)
    return item


def compute_invoice_totals(items: list[InvoiceLineItem]) -> dict:
    subtotal = sum(i.quantity * i.rate for i in items)
    total_discount = sum(i.quantity * i.rate * i.discount_pct / 100.0 for i in items)
    total_taxable = sum(i.taxable_amount for i in items)
    total_cgst = sum(i.cgst_amount for i in items)
    total_sgst = sum(i.sgst_amount for i in items)
    total_igst = sum(i.igst_amount for i in items)
    total_tax = total_cgst + total_sgst + total_igst
    total_amount = total_taxable + total_tax
    return {
        "subtotal": round(subtotal, 2),
        "total_discount": round(total_discount, 2),
        "total_taxable": round(total_taxable, 2),
        "total_cgst": round(total_cgst, 2),
        "total_sgst": round(total_sgst, 2),
        "total_igst": round(total_igst, 2),
        "total_tax": round(total_tax, 2),
        "total_amount": round(total_amount, 2),
    }


# ─── GSTR-1 / GSTR-3B Computation ────────────────────────────────────────────

def compute_gstr1(company_id: str, period_from: str, period_to: str) -> dict:
    """
    Compute GSTR-1 summary from sales invoices in a date range.
    Returns B2B, B2C, HSN-summary buckets.
    """
    db = get_db()
    invoices_data = db.col_find("invoices", company_id=company_id, invoice_type="SALES")
    from database.models import Invoice
    invoices = [Invoice(**i) for i in invoices_data
                if period_from <= i.get("date", "") <= period_to]

    b2b = []          # GST-registered buyers
    b2c_large = []    # unregistered, taxable > 2.5L
    b2c_small = []    # unregistered, taxable <= 2.5L
    hsn_summary: dict[str, dict] = {}
    total_taxable = total_cgst = total_sgst = total_igst = 0.0

    for inv in invoices:
        row = {
            "invoice_number": inv.invoice_number,
            "date": inv.date,
            "party_name": inv.party_name,
            "party_gstin": inv.party_gstin,
            "place_of_supply": inv.place_of_supply,
            "taxable": inv.total_taxable,
            "cgst": inv.total_cgst,
            "sgst": inv.total_sgst,
            "igst": inv.total_igst,
            "total": inv.total_amount,
        }
        total_taxable += inv.total_taxable
        total_cgst += inv.total_cgst
        total_sgst += inv.total_sgst
        total_igst += inv.total_igst

        if inv.party_gstin:
            b2b.append(row)
        elif inv.total_taxable > 250000:
            b2c_large.append(row)
        else:
            b2c_small.append(row)

        for item in inv.items:
            if item.hsn_sac:
                k = item.hsn_sac
                if k not in hsn_summary:
                    hsn_summary[k] = {"hsn": k, "taxable": 0, "cgst": 0, "sgst": 0, "igst": 0}
                hsn_summary[k]["taxable"] += item.taxable_amount
                hsn_summary[k]["cgst"] += item.cgst_amount
                hsn_summary[k]["sgst"] += item.sgst_amount
                hsn_summary[k]["igst"] += item.igst_amount

    return {
        "period": f"{period_from} to {period_to}",
        "b2b": b2b,
        "b2c_large": b2c_large,
        "b2c_small": b2c_small,
        "hsn_summary": list(hsn_summary.values()),
        "totals": {
            "taxable": round(total_taxable, 2),
            "cgst": round(total_cgst, 2),
            "sgst": round(total_sgst, 2),
            "igst": round(total_igst, 2),
            "total_tax": round(total_cgst + total_sgst + total_igst, 2),
        },
    }


def compute_gstr3b(company_id: str, period_from: str, period_to: str) -> dict:
    """Compute GSTR-3B: outward supplies, ITC, net tax payable."""
    db = get_db()
    from database.models import Invoice

    sales = [Invoice(**i) for i in db.col_find("invoices", company_id=company_id, invoice_type="SALES")
             if period_from <= i.get("date", "") <= period_to]
    purchases = [Invoice(**i) for i in db.col_find("invoices", company_id=company_id, invoice_type="PURCHASE")
                 if period_from <= i.get("date", "") <= period_to]

    out_taxable = sum(i.total_taxable for i in sales)
    out_cgst = sum(i.total_cgst for i in sales)
    out_sgst = sum(i.total_sgst for i in sales)
    out_igst = sum(i.total_igst for i in sales)

    itc_cgst = sum(i.total_cgst for i in purchases)
    itc_sgst = sum(i.total_sgst for i in purchases)
    itc_igst = sum(i.total_igst for i in purchases)

    net_cgst = max(out_cgst - itc_cgst, 0)
    net_sgst = max(out_sgst - itc_sgst, 0)
    net_igst = max(out_igst - itc_igst, 0)

    return {
        "period": f"{period_from} to {period_to}",
        "3_1_outward_supplies": {
            "taxable_value": round(out_taxable, 2),
            "cgst": round(out_cgst, 2),
            "sgst": round(out_sgst, 2),
            "igst": round(out_igst, 2),
        },
        "4_itc_available": {
            "cgst": round(itc_cgst, 2),
            "sgst": round(itc_sgst, 2),
            "igst": round(itc_igst, 2),
        },
        "6_1_net_tax_payable": {
            "cgst": round(net_cgst, 2),
            "sgst": round(net_sgst, 2),
            "igst": round(net_igst, 2),
            "total": round(net_cgst + net_sgst + net_igst, 2),
        },
    }
