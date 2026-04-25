"""
TallyChain — Invoicing Module
================================
Sales & purchase invoices with:
  - Auto tax computation (GST / generic)
  - Auto journal voucher generation
  - Invoice numbering
  - Payment tracking
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException

from database.engine import get_db
from database.models import Invoice, InvoiceCreate, InvoiceLineItem, VoucherCreate, VoucherLine
from modules.taxation import compute_gst_line, compute_generic_tax_line, compute_invoice_totals, is_interstate
from modules.ledger import create_voucher, get_account
from audit.trail import AuditTrail
from blockchain.chain import Blockchain


def _next_invoice_number(invoice_type: str, company_id: str) -> str:
    db = get_db()
    counter_key = f"inv_counter:{company_id}:{invoice_type}"
    n = db.get(counter_key, 0) + 1
    db.set(counter_key, n)
    prefix_map = {
        "SALES": "INV", "PURCHASE": "BILL",
        "CREDIT_NOTE": "CN", "DEBIT_NOTE": "DN",
    }
    prefix = prefix_map.get(invoice_type, "INV")
    year = datetime.now().year
    return f"{prefix}-{year}-{n:06d}"


def create_invoice(
    ic: InvoiceCreate,
    user_id: str = "system",
    username: str = "system",
    company_id: str = "default",
    company_state: str = "Maharashtra",
    tax_regime: str = "GST",
) -> Invoice:
    db = get_db()

    # Fetch party account
    party = get_account(ic.party_id, company_id)
    if not party:
        raise HTTPException(404, f"Party account {ic.party_id} not found")

    # Determine inter-state
    inter_state = is_interstate(company_state, ic.place_of_supply or company_state)

    # Compute tax for each line
    computed_items = []
    for item in ic.items:
        if tax_regime == "GST":
            item = compute_gst_line(item, ic.place_of_supply or "", company_state, inter_state)
        else:
            item = compute_generic_tax_line(item)
        computed_items.append(item)

    totals = compute_invoice_totals(computed_items)
    invoice_number = _next_invoice_number(ic.invoice_type, company_id)

    invoice = Invoice(
        invoice_number=invoice_number,
        invoice_type=ic.invoice_type,
        date=ic.date,
        due_date=ic.due_date,
        party_id=ic.party_id,
        party_name=party.name,
        party_gstin=party.gstin or "",
        place_of_supply=ic.place_of_supply or "",
        items=computed_items,
        notes=ic.notes,
        created_by=user_id,
        company_id=company_id,
        **totals,
    )

    # Auto-generate journal voucher
    voucher = _generate_voucher_for_invoice(invoice, company_id, user_id, username)
    invoice.voucher_id = voucher.id
    invoice.block_index = voucher.block_index

    db.col_insert("invoices", invoice.model_dump())
    AuditTrail.log(user_id=user_id, username=username, action="CREATE",
                   resource_type="Invoice", resource_id=invoice.id,
                   after=invoice.model_dump(), company_id=company_id)
    return invoice


def _generate_voucher_for_invoice(
    invoice: Invoice,
    company_id: str,
    user_id: str,
    username: str,
) -> object:
    """Auto-generate double-entry journal for an invoice."""
    db = get_db()

    # Resolve standard accounts
    def find_acc(code: str):
        accs = db.col_find("accounts", code=code, company_id=company_id)
        return accs[0]["id"] if accs else None

    lines = []

    if invoice.invoice_type == "SALES":
        # Dr: Sundry Debtors / Party
        lines.append(VoucherLine(
            account_id=invoice.party_id,
            account_name=invoice.party_name,
            debit=invoice.total_amount,
            narration=f"Sales Invoice {invoice.invoice_number}",
        ))
        # Cr: Sales account
        sales_id = find_acc("4000") or invoice.party_id
        lines.append(VoucherLine(
            account_id=sales_id,
            account_name="Sales",
            credit=invoice.total_taxable,
            narration=f"Sales Invoice {invoice.invoice_number}",
        ))
        # Cr: Tax accounts
        if invoice.total_cgst > 0:
            cgst_id = find_acc("2210")
            if cgst_id:
                lines.append(VoucherLine(account_id=cgst_id, account_name="CGST Payable",
                                         credit=invoice.total_cgst))
        if invoice.total_sgst > 0:
            sgst_id = find_acc("2220")
            if sgst_id:
                lines.append(VoucherLine(account_id=sgst_id, account_name="SGST Payable",
                                         credit=invoice.total_sgst))
        if invoice.total_igst > 0:
            igst_id = find_acc("2230")
            if igst_id:
                lines.append(VoucherLine(account_id=igst_id, account_name="IGST Payable",
                                         credit=invoice.total_igst))
        vtype = "SALES"

    elif invoice.invoice_type == "PURCHASE":
        # Dr: Purchase account
        purch_id = find_acc("5000") or invoice.party_id
        lines.append(VoucherLine(
            account_id=purch_id, account_name="Purchase",
            debit=invoice.total_taxable,
            narration=f"Purchase Invoice {invoice.invoice_number}",
        ))
        # Dr: ITC accounts
        if invoice.total_cgst > 0:
            itc_cgst = find_acc("2310")
            if itc_cgst:
                lines.append(VoucherLine(account_id=itc_cgst, account_name="CGST ITC",
                                         debit=invoice.total_cgst))
        if invoice.total_sgst > 0:
            itc_sgst = find_acc("2320")
            if itc_sgst:
                lines.append(VoucherLine(account_id=itc_sgst, account_name="SGST ITC",
                                         debit=invoice.total_sgst))
        if invoice.total_igst > 0:
            itc_igst = find_acc("2330")
            if itc_igst:
                lines.append(VoucherLine(account_id=itc_igst, account_name="IGST ITC",
                                         debit=invoice.total_igst))
        # Cr: Sundry Creditors / Party
        lines.append(VoucherLine(
            account_id=invoice.party_id,
            account_name=invoice.party_name,
            credit=invoice.total_amount,
            narration=f"Purchase Invoice {invoice.invoice_number}",
        ))
        vtype = "PURCHASE"
    else:
        vtype = "JOURNAL"
        # simple debit party for debit notes, credit for credit notes
        lines.append(VoucherLine(account_id=invoice.party_id,
                                 account_name=invoice.party_name,
                                 debit=invoice.total_amount if invoice.invoice_type == "DEBIT_NOTE" else 0,
                                 credit=invoice.total_amount if invoice.invoice_type == "CREDIT_NOTE" else 0))
        lines.append(VoucherLine(account_id=find_acc("4000") or invoice.party_id,
                                 account_name="Sales",
                                 debit=invoice.total_amount if invoice.invoice_type == "CREDIT_NOTE" else 0,
                                 credit=invoice.total_amount if invoice.invoice_type == "DEBIT_NOTE" else 0))

    vc = VoucherCreate(
        voucher_type=vtype,
        date=invoice.date,
        narration=f"{invoice.invoice_type} {invoice.invoice_number} — {invoice.party_name}",
        lines=lines,
        reference=invoice.invoice_number,
    )
    return create_voucher(vc, user_id=user_id, username=username, company_id=company_id)


def get_invoice(invoice_id: str, company_id: str = "default") -> Optional[Invoice]:
    db = get_db()
    data = db.col_get("invoices", invoice_id)
    if data and data.get("company_id") == company_id:
        return Invoice(**data)
    return None


def list_invoices(company_id: str = "default",
                  invoice_type: Optional[str] = None,
                  from_date: Optional[str] = None,
                  to_date: Optional[str] = None,
                  party_id: Optional[str] = None) -> list[Invoice]:
    db = get_db()
    records = db.col_find("invoices", company_id=company_id)
    invs = [Invoice(**r) for r in records]
    if invoice_type:
        invs = [i for i in invs if i.invoice_type == invoice_type]
    if from_date:
        invs = [i for i in invs if i.date >= from_date]
    if to_date:
        invs = [i for i in invs if i.date <= to_date]
    if party_id:
        invs = [i for i in invs if i.party_id == party_id]
    invs.sort(key=lambda i: i.date, reverse=True)
    return invs


def record_payment(invoice_id: str, amount: float,
                   payment_account_id: str,
                   user_id: str, username: str,
                   company_id: str = "default") -> Invoice:
    db = get_db()
    inv_data = db.col_get("invoices", invoice_id)
    if not inv_data:
        raise HTTPException(404, "Invoice not found")
    inv = Invoice(**inv_data)
    outstanding = inv.total_amount - inv.paid_amount
    if amount > outstanding + 0.01:
        raise HTTPException(400, f"Payment {amount} exceeds outstanding {outstanding:.2f}")

    inv.paid_amount = round(inv.paid_amount + amount, 2)
    inv.payment_status = "PAID" if inv.paid_amount >= inv.total_amount - 0.01 else "PARTIAL"

    # Journal entry for payment
    lines = []
    if inv.invoice_type == "SALES":
        lines.append(VoucherLine(account_id=payment_account_id, account_name="Bank/Cash", debit=amount))
        lines.append(VoucherLine(account_id=inv.party_id, account_name=inv.party_name, credit=amount))
        vtype = "RECEIPT"
    else:
        lines.append(VoucherLine(account_id=inv.party_id, account_name=inv.party_name, debit=amount))
        lines.append(VoucherLine(account_id=payment_account_id, account_name="Bank/Cash", credit=amount))
        vtype = "PAYMENT"

    vc = VoucherCreate(
        voucher_type=vtype, date=datetime.now().date().isoformat(),
        narration=f"Payment against {inv.invoice_number}",
        lines=lines, reference=inv.invoice_number,
    )
    create_voucher(vc, user_id=user_id, username=username, company_id=company_id)
    db.col_update("invoices", invoice_id, inv.model_dump())
    return inv
