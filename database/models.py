"""
TallyChain — Pydantic Data Models
All entities that flow through the application layer.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, List
from datetime import date, datetime
from decimal import Decimal
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


# ══════════════════════════════════════════════════════════════
#  AUTH & USERS
# ══════════════════════════════════════════════════════════════

class UserRole(str):
    ADMIN = "admin"
    ACCOUNTANT = "accountant"
    AUDITOR = "auditor"
    VIEWER = "viewer"

ROLES = ["admin", "accountant", "auditor", "viewer"]

class User(BaseModel):
    id: str = Field(default_factory=new_id)
    username: str
    email: str
    full_name: str
    role: str = "viewer"
    is_active: bool = True
    hashed_password: str
    company_id: str = "default"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class UserCreate(BaseModel):
    username: str
    email: str
    full_name: str
    role: str = "viewer"
    password: str
    company_id: str = "default"

class UserLogin(BaseModel):
    username: str
    password: str


# ══════════════════════════════════════════════════════════════
#  COMPANY
# ══════════════════════════════════════════════════════════════

class Company(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    gstin: Optional[str] = None          # India GST
    pan: Optional[str] = None
    ein: Optional[str] = None            # US EIN
    address: str = ""
    city: str = ""
    state: str = ""
    country: str = "India"
    pincode: str = ""
    phone: str = ""
    email: str = ""
    fiscal_year_start: str = "04-01"     # MM-DD
    currency: str = "INR"
    tax_regime: str = "GST"              # GST | GAAP | GENERIC
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ══════════════════════════════════════════════════════════════
#  CHART OF ACCOUNTS
# ══════════════════════════════════════════════════════════════

AccountType = Literal[
    "ASSET", "LIABILITY", "EQUITY", "INCOME", "EXPENSE",
    "BANK", "CASH", "SUNDRY_DEBTOR", "SUNDRY_CREDITOR",
    "TAX_PAYABLE", "TAX_RECEIVABLE", "FIXED_ASSET", "STOCK"
]

class Account(BaseModel):
    id: str = Field(default_factory=new_id)
    code: str                            # e.g. "1001"
    name: str                            # e.g. "Cash in Hand"
    account_type: AccountType
    parent_id: Optional[str] = None      # for hierarchical CoA
    opening_balance: float = 0.0
    opening_balance_type: Literal["Dr", "Cr"] = "Dr"
    is_active: bool = True
    is_system: bool = False              # system accounts cannot be deleted
    gstin: Optional[str] = None          # party GSTIN
    pan: Optional[str] = None
    credit_limit: float = 0.0
    company_id: str = "default"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ══════════════════════════════════════════════════════════════
#  VOUCHERS (journal entries)
# ══════════════════════════════════════════════════════════════

VoucherType = Literal[
    "PAYMENT", "RECEIPT", "JOURNAL", "SALES", "PURCHASE",
    "CONTRA", "DEBIT_NOTE", "CREDIT_NOTE", "OPENING_BALANCE"
]

class VoucherLine(BaseModel):
    account_id: str
    account_name: str = ""
    debit: float = 0.0
    credit: float = 0.0
    narration: str = ""
    cost_center: str = ""

class Voucher(BaseModel):
    id: str = Field(default_factory=new_id)
    voucher_number: str = ""
    voucher_type: VoucherType
    date: str                            # ISO date string YYYY-MM-DD
    narration: str = ""
    lines: List[VoucherLine]
    reference: str = ""                  # cheque no, invoice ref, etc.
    is_posted: bool = True
    block_index: Optional[int] = None   # blockchain block where this was recorded
    block_hash: Optional[str] = None
    created_by: str = "system"
    company_id: str = "default"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    tags: List[str] = []


class VoucherCreate(BaseModel):
    voucher_type: VoucherType
    date: str
    narration: str = ""
    lines: List[VoucherLine]
    reference: str = ""
    tags: List[str] = []


# ══════════════════════════════════════════════════════════════
#  INVOICE
# ══════════════════════════════════════════════════════════════

class InvoiceLineItem(BaseModel):
    description: str
    hsn_sac: str = ""                   # HSN/SAC code (India)
    quantity: float = 1.0
    unit: str = "Nos"
    rate: float = 0.0
    discount_pct: float = 0.0
    taxable_amount: float = 0.0
    tax_rate: float = 0.0               # combined GST %
    cgst_rate: float = 0.0
    sgst_rate: float = 0.0
    igst_rate: float = 0.0
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    igst_amount: float = 0.0
    total: float = 0.0

class Invoice(BaseModel):
    id: str = Field(default_factory=new_id)
    invoice_number: str = ""
    invoice_type: Literal["SALES", "PURCHASE", "CREDIT_NOTE", "DEBIT_NOTE"] = "SALES"
    date: str
    due_date: str = ""
    party_id: str                        # Account ID of customer/supplier
    party_name: str = ""
    party_gstin: str = ""
    place_of_supply: str = ""
    items: List[InvoiceLineItem]
    subtotal: float = 0.0
    total_discount: float = 0.0
    total_taxable: float = 0.0
    total_cgst: float = 0.0
    total_sgst: float = 0.0
    total_igst: float = 0.0
    total_tax: float = 0.0
    total_amount: float = 0.0
    payment_status: Literal["UNPAID", "PARTIAL", "PAID"] = "UNPAID"
    paid_amount: float = 0.0
    voucher_id: Optional[str] = None     # linked journal voucher
    block_index: Optional[int] = None
    notes: str = ""
    company_id: str = "default"
    created_by: str = "system"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class InvoiceCreate(BaseModel):
    invoice_type: Literal["SALES", "PURCHASE", "CREDIT_NOTE", "DEBIT_NOTE"] = "SALES"
    date: str
    due_date: str = ""
    party_id: str
    place_of_supply: str = ""
    items: List[InvoiceLineItem]
    notes: str = ""


# ══════════════════════════════════════════════════════════════
#  TAX
# ══════════════════════════════════════════════════════════════

class TaxRate(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str                            # e.g. "GST 18%"
    rate: float                          # total %
    cgst: float = 0.0
    sgst: float = 0.0
    igst: float = 0.0
    tax_type: str = "GST"               # GST | SALES_TAX | VAT | GENERIC
    is_active: bool = True
    company_id: str = "default"


# ══════════════════════════════════════════════════════════════
#  AUDIT
# ══════════════════════════════════════════════════════════════

class AuditEntry(BaseModel):
    id: str = Field(default_factory=new_id)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    user_id: str
    username: str
    action: str                          # CREATE | UPDATE | DELETE | LOGIN | VERIFY
    resource_type: str                   # Account | Voucher | Invoice | User …
    resource_id: str
    before: Optional[dict] = None
    after: Optional[dict] = None
    ip_address: str = ""
    status: str = "SUCCESS"
    company_id: str = "default"


# ══════════════════════════════════════════════════════════════
#  RECONCILIATION
# ══════════════════════════════════════════════════════════════

class BankStatement(BaseModel):
    id: str = Field(default_factory=new_id)
    account_id: str
    date: str
    description: str
    debit: float = 0.0
    credit: float = 0.0
    balance: float = 0.0
    is_matched: bool = False
    matched_voucher_id: Optional[str] = None
    company_id: str = "default"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
