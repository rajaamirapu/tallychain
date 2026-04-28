"""
TallyChain — Ledger & Voucher Engine
=====================================
Implements:
  • Chart of Accounts management
  • Double-entry journal validation (debits == credits)
  • Voucher creation with automatic blockchain recording
  • Account balance computation
  • Ledger statement generation
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException

from database.engine import get_db
from database.models import Account, Voucher, VoucherCreate, VoucherLine
from audit.trail import AuditTrail
from blockchain.chain import Blockchain


_blockchain: Optional[Blockchain] = None


def get_blockchain(company_id: str = "default") -> Blockchain:
    global _blockchain
    if _blockchain is None:
        _blockchain = Blockchain(company_id=company_id)
    return _blockchain


def _next_voucher_number(voucher_type: str, company_id: str) -> str:
    db = get_db()
    counter_key = f"counter:{company_id}:{voucher_type}"
    n = db.get(counter_key, 0) + 1
    db.set(counter_key, n)
    prefix_map = {
        "PAYMENT": "PMT", "RECEIPT": "RCP", "JOURNAL": "JNL",
        "SALES": "SAL", "PURCHASE": "PUR", "CONTRA": "CTR",
        "DEBIT_NOTE": "DN", "CREDIT_NOTE": "CN", "OPENING_BALANCE": "OB",
    }
    prefix = prefix_map.get(voucher_type, "VCH")
    year = datetime.now().year
    return f"{prefix}-{year}-{n:06d}"


# ══════════════════════════════════════════════════════════════
#  ACCOUNTS
# ══════════════════════════════════════════════════════════════

DEFAULT_COA = [
    # code, name, type, is_system
    ("1000", "Cash & Bank", "ASSET", True),
    ("1001", "Cash in Hand", "CASH", True),
    ("1002", "Bank Account", "BANK", True),
    ("1100", "Sundry Debtors", "SUNDRY_DEBTOR", True),
    ("1200", "Stock in Trade", "STOCK", True),
    ("1300", "Fixed Assets", "FIXED_ASSET", True),
    ("1400", "Other Current Assets", "ASSET", True),
    ("2000", "Sundry Creditors", "SUNDRY_CREDITOR", True),
    ("2100", "Loans & Liabilities", "LIABILITY", True),
    ("2200", "GST Payable", "TAX_PAYABLE", True),
    ("2210", "CGST Payable", "TAX_PAYABLE", True),
    ("2220", "SGST Payable", "TAX_PAYABLE", True),
    ("2230", "IGST Payable", "TAX_PAYABLE", True),
    ("2300", "Input Tax Credit", "TAX_RECEIVABLE", True),
    ("2310", "CGST ITC", "TAX_RECEIVABLE", True),
    ("2320", "SGST ITC", "TAX_RECEIVABLE", True),
    ("2330", "IGST ITC", "TAX_RECEIVABLE", True),
    ("2400", "TDS Payable", "TAX_PAYABLE", True),
    ("3000", "Capital Account", "EQUITY", True),
    ("3100", "Retained Earnings", "EQUITY", True),
    ("4000", "Sales", "INCOME", True),
    ("4100", "Service Income", "INCOME", True),
    ("4200", "Other Income", "INCOME", True),
    ("5000", "Purchase", "EXPENSE", True),
    ("5100", "Direct Expenses", "EXPENSE", True),
    ("5200", "Indirect Expenses", "EXPENSE", True),
    ("5300", "Salaries", "EXPENSE", True),
    ("5400", "Rent", "EXPENSE", True),
    ("5500", "Depreciation", "EXPENSE", True),
]


def seed_default_accounts(company_id: str = "default") -> int:
    db = get_db()
    existing = db.col_find("accounts", company_id=company_id, is_system=True)
    if existing:
        return 0
    count = 0
    for code, name, atype, is_sys in DEFAULT_COA:
        acc = Account(
            code=code, name=name, account_type=atype,
            is_system=is_sys, company_id=company_id
        )
        db.col_insert("accounts", acc.model_dump())
        count += 1
    return count


def create_account(account: Account, user_id: str = "system") -> Account:
    db = get_db()
    existing = db.col_find("accounts", code=account.code, company_id=account.company_id)
    if existing:
        raise HTTPException(400, f"Account code {account.code} already exists")
    db.col_insert("accounts", account.model_dump())
    AuditTrail.log(user_id=user_id, username="", action="CREATE",
                   resource_type="Account", resource_id=account.id,
                   after=account.model_dump(), company_id=account.company_id)
    return account


def update_account(account_id: str, updates: dict, company_id: str = "default",
                   user_id: str = "system") -> Account:
    db = get_db()
    data = db.col_get("accounts", account_id)
    if not data or data.get("company_id") != company_id:
        raise HTTPException(404, "Account not found")
    before = dict(data)
    if "code" in updates and updates["code"] != data["code"]:
        clash = db.col_find("accounts", code=updates["code"], company_id=company_id)
        if clash:
            raise HTTPException(400, f"Account code {updates['code']} already exists")
    allowed = {"name", "account_type", "opening_balance", "opening_balance_type",
               "gstin", "pan", "credit_limit", "is_active", "code"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    data.update(filtered)
    db.col_update("accounts", account_id, data)
    AuditTrail.log(user_id=user_id, username="", action="UPDATE",
                   resource_type="Account", resource_id=account_id,
                   before=before, after=data, company_id=company_id)
    return Account(**data)


def get_account(account_id: str, company_id: str = "default") -> Optional[Account]:
    db = get_db()
    data = db.col_get("accounts", account_id)
    if data and data.get("company_id") == company_id:
        return Account(**data)
    return None


def list_accounts(company_id: str = "default") -> list[Account]:
    db = get_db()
    records = db.col_find("accounts", company_id=company_id)
    return [Account(**r) for r in records]


def get_account_balance(account_id: str, company_id: str = "default",
                        as_of: Optional[str] = None) -> dict:
    """
    Compute running balance for an account from all posted vouchers.
    Returns {"debit_total": float, "credit_total": float, "balance": float, "balance_type": "Dr|Cr"}
    """
    db = get_db()
    account = get_account(account_id, company_id)
    if not account:
        raise HTTPException(404, "Account not found")

    vouchers = db.col_find("vouchers", company_id=company_id, is_posted=True)
    debit_total = account.opening_balance if account.opening_balance_type == "Dr" else 0.0
    credit_total = account.opening_balance if account.opening_balance_type == "Cr" else 0.0

    for vdata in vouchers:
        v = Voucher(**vdata)
        if as_of and v.date > as_of:
            continue
        for line in v.lines:
            if line.account_id == account_id:
                debit_total += line.debit
                credit_total += line.credit

    # Asset/Expense: Dr-normal; Liability/Equity/Income: Cr-normal
    dr_types = {"ASSET", "CASH", "BANK", "FIXED_ASSET", "STOCK",
                "SUNDRY_DEBTOR", "TAX_RECEIVABLE", "EXPENSE"}
    if account.account_type in dr_types:
        balance = debit_total - credit_total
        btype = "Dr" if balance >= 0 else "Cr"
    else:
        balance = credit_total - debit_total
        btype = "Cr" if balance >= 0 else "Dr"

    return {
        "account_id": account_id,
        "account_name": account.name,
        "account_type": account.account_type,
        "debit_total": round(debit_total, 2),
        "credit_total": round(credit_total, 2),
        "balance": round(abs(balance), 2),
        "balance_type": btype,
    }


# ══════════════════════════════════════════════════════════════
#  VOUCHERS
# ══════════════════════════════════════════════════════════════

def _validate_double_entry(lines: list[VoucherLine]):
    total_dr = sum(l.debit for l in lines)
    total_cr = sum(l.credit for l in lines)
    if abs(total_dr - total_cr) > 0.005:  # 0.5 paisa tolerance
        raise HTTPException(
            400,
            f"Double-entry imbalance: debits={total_dr:.2f} ≠ credits={total_cr:.2f}"
        )


def create_voucher(vc: VoucherCreate, user_id: str = "system",
                   username: str = "system", company_id: str = "default") -> Voucher:
    _validate_double_entry(vc.lines)
    db = get_db()
    bc = get_blockchain(company_id)

    voucher_number = _next_voucher_number(vc.voucher_type, company_id)
    voucher = Voucher(
        **vc.model_dump(),
        voucher_number=voucher_number,
        created_by=user_id,
        company_id=company_id,
    )

    # Record to blockchain first
    tx_payload = {
        "id": voucher.id,
        "type": "VOUCHER",
        "voucher_type": voucher.voucher_type,
        "voucher_number": voucher_number,
        "date": voucher.date,
        "narration": voucher.narration,
        "lines": [l.model_dump() for l in voucher.lines],
        "created_by": user_id,
        "company_id": company_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    block = bc.add_block([tx_payload], created_by=user_id)
    voucher.block_index = block.index
    voucher.block_hash = block.hash

    db.col_insert("vouchers", voucher.model_dump())
    AuditTrail.log(user_id=user_id, username=username, action="CREATE",
                   resource_type="Voucher", resource_id=voucher.id,
                   after=voucher.model_dump(), company_id=company_id)
    return voucher


def get_voucher(voucher_id: str, company_id: str = "default") -> Optional[Voucher]:
    db = get_db()
    data = db.col_get("vouchers", voucher_id)
    if data and data.get("company_id") == company_id:
        return Voucher(**data)
    return None


def list_vouchers(company_id: str = "default", voucher_type: Optional[str] = None,
                  from_date: Optional[str] = None, to_date: Optional[str] = None,
                  limit: int = 200) -> list[Voucher]:
    db = get_db()
    records = db.col_find("vouchers", company_id=company_id)
    vouchers = [Voucher(**r) for r in records]
    if voucher_type:
        vouchers = [v for v in vouchers if v.voucher_type == voucher_type]
    if from_date:
        vouchers = [v for v in vouchers if v.date >= from_date]
    if to_date:
        vouchers = [v for v in vouchers if v.date <= to_date]
    vouchers.sort(key=lambda v: (v.date, v.voucher_number), reverse=True)
    return vouchers[:limit]


def get_ledger_statement(account_id: str, company_id: str = "default",
                         from_date: Optional[str] = None,
                         to_date: Optional[str] = None) -> dict:
    """Full ledger statement with running balance."""
    db = get_db()
    account = get_account(account_id, company_id)
    if not account:
        raise HTTPException(404, "Account not found")

    opening = account.opening_balance
    op_type = account.opening_balance_type

    # Opening balance as of from_date
    op_balance = opening if op_type == "Dr" else -opening

    vouchers_all = db.col_find("vouchers", company_id=company_id, is_posted=True)
    entries = []
    for vdata in vouchers_all:
        v = Voucher(**vdata)
        for line in v.lines:
            if line.account_id != account_id:
                continue
            if from_date and v.date < from_date:
                op_balance += line.debit - line.credit
                continue
            if to_date and v.date > to_date:
                continue
            entries.append({
                "date": v.date,
                "voucher_number": v.voucher_number,
                "voucher_type": v.voucher_type,
                "narration": line.narration or v.narration,
                "debit": line.debit,
                "credit": line.credit,
                "voucher_id": v.id,
                "block_hash": v.block_hash,
            })

    entries.sort(key=lambda e: (e["date"], e["voucher_number"]))
    running = op_balance
    for e in entries:
        running += e["debit"] - e["credit"]
        e["balance"] = round(abs(running), 2)
        e["balance_type"] = "Dr" if running >= 0 else "Cr"

    closing = running
    return {
        "account": account.model_dump(),
        "from_date": from_date,
        "to_date": to_date,
        "opening_balance": round(abs(op_balance), 2),
        "opening_balance_type": "Dr" if op_balance >= 0 else "Cr",
        "entries": entries,
        "closing_balance": round(abs(closing), 2),
        "closing_balance_type": "Dr" if closing >= 0 else "Cr",
        "total_debits": round(sum(e["debit"] for e in entries), 2),
        "total_credits": round(sum(e["credit"] for e in entries), 2),
    }
