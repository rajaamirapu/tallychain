"""
TallyChain — Financial Reporting Engine
=========================================
Reports generated live from ledger:
  • Trial Balance
  • Profit & Loss Statement
  • Balance Sheet
  • Cash Flow Statement
  • Day Book
  • Outstanding Receivables / Payables
"""
from typing import Optional
from database.engine import get_db
from database.models import Account, Voucher
from modules.ledger import list_accounts, get_account_balance


INCOME_TYPES = {"INCOME"}
EXPENSE_TYPES = {"EXPENSE"}
ASSET_TYPES = {"ASSET", "CASH", "BANK", "FIXED_ASSET", "STOCK", "SUNDRY_DEBTOR",
               "TAX_RECEIVABLE"}
LIABILITY_TYPES = {"LIABILITY", "SUNDRY_CREDITOR", "TAX_PAYABLE"}
EQUITY_TYPES = {"EQUITY"}


def _get_all_balances(company_id: str, as_of: Optional[str] = None) -> list[dict]:
    accounts = list_accounts(company_id)
    result = []
    for acc in accounts:
        bal = get_account_balance(acc.id, company_id, as_of)
        result.append({**acc.model_dump(), **bal})
    return result


# ─── Trial Balance ────────────────────────────────────────────────────────────

def trial_balance(company_id: str = "default", as_of: Optional[str] = None) -> dict:
    balances = _get_all_balances(company_id, as_of)
    rows = []
    total_dr = total_cr = 0.0
    for b in balances:
        if b["balance"] == 0:
            continue
        dr = b["balance"] if b["balance_type"] == "Dr" else 0.0
        cr = b["balance"] if b["balance_type"] == "Cr" else 0.0
        total_dr += dr
        total_cr += cr
        rows.append({
            "code": b["code"],
            "name": b["name"],
            "type": b["account_type"],
            "debit": dr,
            "credit": cr,
        })
    rows.sort(key=lambda r: r["code"])
    return {
        "report": "Trial Balance",
        "as_of": as_of,
        "rows": rows,
        "total_debit": round(total_dr, 2),
        "total_credit": round(total_cr, 2),
        "balanced": abs(total_dr - total_cr) < 0.01,
    }


# ─── P&L Statement ────────────────────────────────────────────────────────────

def profit_and_loss(company_id: str = "default",
                    from_date: Optional[str] = None,
                    to_date: Optional[str] = None) -> dict:
    """
    Compute P&L from voucher lines within date range.
    """
    db = get_db()
    accounts = {a.id: a for a in list_accounts(company_id)}
    vouchers_data = db.col_find("vouchers", company_id=company_id, is_posted=True)

    income_total = expense_total = 0.0
    income_detail: dict[str, float] = {}
    expense_detail: dict[str, float] = {}

    for vdata in vouchers_data:
        v = Voucher(**vdata)
        if from_date and v.date < from_date:
            continue
        if to_date and v.date > to_date:
            continue
        for line in v.lines:
            acc = accounts.get(line.account_id)
            if not acc:
                continue
            if acc.account_type in INCOME_TYPES:
                net = line.credit - line.debit
                income_detail[acc.name] = income_detail.get(acc.name, 0.0) + net
                income_total += net
            elif acc.account_type in EXPENSE_TYPES:
                net = line.debit - line.credit
                expense_detail[acc.name] = expense_detail.get(acc.name, 0.0) + net
                expense_total += net

    net_profit = income_total - expense_total
    return {
        "report": "Profit & Loss Statement",
        "period": f"{from_date or 'Inception'} to {to_date or 'Present'}",
        "income": [{"name": k, "amount": round(v, 2)} for k, v in sorted(income_detail.items())],
        "total_income": round(income_total, 2),
        "expenses": [{"name": k, "amount": round(v, 2)} for k, v in sorted(expense_detail.items())],
        "total_expenses": round(expense_total, 2),
        "net_profit": round(net_profit, 2),
        "is_profit": net_profit >= 0,
    }


# ─── Balance Sheet ────────────────────────────────────────────────────────────

def balance_sheet(company_id: str = "default", as_of: Optional[str] = None) -> dict:
    balances = _get_all_balances(company_id, as_of)

    assets = liabilities = equity = 0.0
    asset_rows = []
    liability_rows = []
    equity_rows = []

    for b in balances:
        amt = b["balance"] if b["balance_type"] == "Dr" else -b["balance"]
        row = {"name": b["name"], "code": b["code"],
               "type": b["account_type"], "amount": round(abs(b["balance"]), 2)}

        if b["account_type"] in ASSET_TYPES:
            asset_rows.append(row)
            assets += b["balance"] if b["balance_type"] == "Dr" else -b["balance"]
        elif b["account_type"] in LIABILITY_TYPES:
            liability_rows.append(row)
            liabilities += b["balance"] if b["balance_type"] == "Cr" else -b["balance"]
        elif b["account_type"] in EQUITY_TYPES:
            equity_rows.append(row)
            equity += b["balance"] if b["balance_type"] == "Cr" else -b["balance"]

    # Add net profit to retained earnings
    pl = profit_and_loss(company_id, to_date=as_of)
    equity += pl["net_profit"]
    equity_rows.append({"name": "Net Profit / (Loss)", "code": "RE",
                        "type": "EQUITY", "amount": round(pl["net_profit"], 2)})

    total_liab_equity = liabilities + equity
    return {
        "report": "Balance Sheet",
        "as_of": as_of,
        "assets": asset_rows,
        "total_assets": round(assets, 2),
        "liabilities": liability_rows,
        "equity": equity_rows,
        "total_liabilities_equity": round(total_liab_equity, 2),
        "balanced": abs(assets - total_liab_equity) < 0.01,
    }


# ─── Cash Flow Statement ──────────────────────────────────────────────────────

def cash_flow(company_id: str = "default",
              from_date: Optional[str] = None,
              to_date: Optional[str] = None) -> dict:
    db = get_db()
    accounts = {a.id: a for a in list_accounts(company_id)}
    vouchers_data = db.col_find("vouchers", company_id=company_id, is_posted=True)

    operating = investing = financing = 0.0
    op_rows = []
    inv_rows = []
    fin_rows = []

    for vdata in vouchers_data:
        v = Voucher(**vdata)
        if from_date and v.date < from_date:
            continue
        if to_date and v.date > to_date:
            continue
        for line in v.lines:
            acc = accounts.get(line.account_id)
            if not acc:
                continue
            net = line.debit - line.credit
            row = {"date": v.date, "narration": v.narration,
                   "voucher": v.voucher_number, "amount": round(net, 2)}
            if acc.account_type in {"INCOME", "EXPENSE", "SUNDRY_DEBTOR", "SUNDRY_CREDITOR"}:
                operating += net
                op_rows.append(row)
            elif acc.account_type in {"FIXED_ASSET"}:
                investing += net
                inv_rows.append(row)
            elif acc.account_type in {"EQUITY", "LIABILITY"}:
                financing += net
                fin_rows.append(row)

    net_change = operating + investing + financing
    return {
        "report": "Cash Flow Statement",
        "period": f"{from_date or 'Inception'} to {to_date or 'Present'}",
        "operating_activities": {"total": round(operating, 2), "items": op_rows},
        "investing_activities": {"total": round(investing, 2), "items": inv_rows},
        "financing_activities": {"total": round(financing, 2), "items": fin_rows},
        "net_cash_change": round(net_change, 2),
    }


# ─── Day Book ────────────────────────────────────────────────────────────────

def day_book(company_id: str = "default",
             from_date: Optional[str] = None,
             to_date: Optional[str] = None) -> dict:
    db = get_db()
    vouchers_data = db.col_find("vouchers", company_id=company_id, is_posted=True)
    if from_date:
        vouchers_data = [v for v in vouchers_data if v.get("date", "") >= from_date]
    if to_date:
        vouchers_data = [v for v in vouchers_data if v.get("date", "") <= to_date]
    vouchers = [Voucher(**v) for v in vouchers_data]
    vouchers.sort(key=lambda v: (v.date, v.voucher_number))
    period = f"{from_date or 'Inception'} to {to_date or 'Present'}"
    return {
        "report": "Day Book",
        "date": period,
        "total_entries": len(vouchers),
        "entries": [v.model_dump() for v in vouchers],
    }


# ─── Receivables / Payables ───────────────────────────────────────────────────

def outstanding_report(company_id: str = "default",
                       report_type: str = "RECEIVABLE") -> dict:
    """Outstanding receivables (debtors) or payables (creditors)."""
    db = get_db()
    from database.models import Invoice
    inv_type = "SALES" if report_type == "RECEIVABLE" else "PURCHASE"
    invoices_data = db.col_find("invoices", company_id=company_id, invoice_type=inv_type)
    rows = []
    total_outstanding = 0.0
    for idata in invoices_data:
        inv = Invoice(**idata)
        outstanding = round(inv.total_amount - inv.paid_amount, 2)
        if outstanding <= 0:
            continue
        rows.append({
            "invoice_number": inv.invoice_number,
            "date": inv.date,
            "due_date": inv.due_date,
            "party_name": inv.party_name,
            "total_amount": inv.total_amount,
            "paid_amount": inv.paid_amount,
            "outstanding": outstanding,
            "payment_status": inv.payment_status,
        })
        total_outstanding += outstanding

    rows.sort(key=lambda r: r["due_date"] or r["date"])
    return {
        "report": f"Outstanding {'Receivables' if report_type == 'RECEIVABLE' else 'Payables'}",
        "rows": rows,
        "total_outstanding": round(total_outstanding, 2),
    }
