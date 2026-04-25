"""
TallyChain — FastAPI Application Entry Point
=============================================
All routes wired here. Run with:
    uvicorn main:app --reload --port 8000
"""
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import os

from config import settings
from auth.rbac import (
    authenticate_user, create_access_token, create_user,
    get_current_user, require_permission, ensure_admin_exists,
    hash_password,
)
from database.engine import get_db
from database.models import (
    UserCreate, UserLogin, Account, VoucherCreate, InvoiceCreate,
    BankStatement, TaxRate, Company,
)
from modules.ledger import (
    create_account, list_accounts, get_account, get_account_balance,
    get_ledger_statement, create_voucher, list_vouchers, get_voucher,
    seed_default_accounts, get_blockchain,
)
from modules.invoicing import (
    create_invoice, list_invoices, get_invoice, record_payment,
)
from modules.taxation import (
    list_tax_rates, seed_tax_rates,
    compute_gstr1, compute_gstr3b,
)
from modules.reporting import (
    trial_balance, profit_and_loss, balance_sheet,
    cash_flow, day_book, outstanding_report,
)
from audit.trail import AuditTrail, Reconciliation

# ─────────────────────────── App init ────────────────────────────────────────
app = FastAPI(
    title="TallyChain",
    description="Blockchain-powered enterprise accounting system",
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
frontend_dir = Path(__file__).parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.on_event("startup")
async def startup():
    """Bootstrap default data on first run."""
    ensure_admin_exists()
    seed_default_accounts()
    seed_tax_rates()
    # Ensure blockchain is initialised
    get_blockchain()


# ══════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════

@app.post("/api/auth/login")
async def login(creds: UserLogin):
    user = authenticate_user(creds.username, creds.password)
    if not user:
        AuditTrail.log(user_id="unknown", username=creds.username,
                       action="LOGIN", resource_type="User", resource_id="",
                       status="FAILED")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.id, "role": user.role,
                                  "company_id": user.company_id})
    AuditTrail.log(user_id=user.id, username=user.username,
                   action="LOGIN", resource_type="User", resource_id=user.id)
    return {"access_token": token, "token_type": "bearer",
            "role": user.role, "user_id": user.id,
            "username": user.username, "full_name": user.full_name}


@app.get("/api/auth/me")
async def me(current_user=Depends(get_current_user)):
    return current_user


# ══════════════════════════════════════════════════════════════
#  USER ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/api/users")
async def get_users(current_user=Depends(require_permission("users:read"))):
    db = get_db()
    users = db.col_all("users")
    return [{"id": u["id"], "username": u["username"], "email": u["email"],
             "full_name": u["full_name"], "role": u["role"],
             "is_active": u["is_active"]} for u in users]


@app.post("/api/users", status_code=201)
async def add_user(uc: UserCreate, current_user=Depends(require_permission("users:write"))):
    user = create_user(uc, company_id=current_user.company_id)
    AuditTrail.log(user_id=current_user.id, username=current_user.username,
                   action="CREATE", resource_type="User", resource_id=user.id,
                   company_id=current_user.company_id)
    return {"id": user.id, "username": user.username, "role": user.role}


@app.delete("/api/users/{user_id}")
async def delete_user(user_id: str, current_user=Depends(require_permission("users:delete"))):
    db = get_db()
    if not db.col_get("users", user_id):
        raise HTTPException(404, "User not found")
    db.col_update("users", user_id, {"is_active": False})
    AuditTrail.log(user_id=current_user.id, username=current_user.username,
                   action="DELETE", resource_type="User", resource_id=user_id,
                   company_id=current_user.company_id)
    return {"status": "deactivated"}


# ══════════════════════════════════════════════════════════════
#  COMPANY ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/api/company")
async def get_company(current_user=Depends(require_permission("company:read"))):
    db = get_db()
    companies = db.col_find("companies", id=current_user.company_id)
    if not companies:
        return {"id": "default", "name": "My Company", "tax_regime": "GST",
                "currency": "INR", "country": "India"}
    return companies[0]


@app.put("/api/company")
async def update_company(company: Company,
                          current_user=Depends(require_permission("company:write"))):
    db = get_db()
    company.id = current_user.company_id
    if db.col_get("companies", company.id):
        db.col_update("companies", company.id, company.model_dump())
    else:
        db.col_insert("companies", company.model_dump())
    return company


# ══════════════════════════════════════════════════════════════
#  ACCOUNT (COA) ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/api/accounts")
async def get_accounts(current_user=Depends(require_permission("accounts:read"))):
    return [a.model_dump() for a in list_accounts(current_user.company_id)]


@app.get("/api/accounts/{account_id}")
async def get_account_detail(account_id: str,
                              current_user=Depends(require_permission("accounts:read"))):
    acc = get_account(account_id, current_user.company_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    return acc


@app.post("/api/accounts", status_code=201)
async def create_account_route(account: Account,
                                current_user=Depends(require_permission("accounts:write"))):
    account.company_id = current_user.company_id
    return create_account(account, user_id=current_user.id)


@app.get("/api/accounts/{account_id}/balance")
async def account_balance(account_id: str, as_of: str = None,
                           current_user=Depends(require_permission("accounts:read"))):
    return get_account_balance(account_id, current_user.company_id, as_of)


@app.get("/api/accounts/{account_id}/ledger")
async def ledger_statement(account_id: str,
                            from_date: str = None, to_date: str = None,
                            current_user=Depends(require_permission("accounts:read"))):
    return get_ledger_statement(account_id, current_user.company_id, from_date, to_date)


# ══════════════════════════════════════════════════════════════
#  VOUCHER ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/api/vouchers")
async def get_vouchers(voucher_type: str = None, from_date: str = None,
                        to_date: str = None,
                        current_user=Depends(require_permission("vouchers:read"))):
    return [v.model_dump() for v in
            list_vouchers(current_user.company_id, voucher_type, from_date, to_date)]


@app.get("/api/vouchers/{voucher_id}")
async def get_voucher_detail(voucher_id: str,
                              current_user=Depends(require_permission("vouchers:read"))):
    v = get_voucher(voucher_id, current_user.company_id)
    if not v:
        raise HTTPException(404, "Voucher not found")
    return v


@app.post("/api/vouchers", status_code=201)
async def create_voucher_route(vc: VoucherCreate,
                                current_user=Depends(require_permission("vouchers:write"))):
    return create_voucher(vc, user_id=current_user.id,
                          username=current_user.username,
                          company_id=current_user.company_id)


# ══════════════════════════════════════════════════════════════
#  INVOICE ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/api/invoices")
async def get_invoices(invoice_type: str = None, from_date: str = None,
                        to_date: str = None, party_id: str = None,
                        current_user=Depends(require_permission("invoices:read"))):
    return [i.model_dump() for i in
            list_invoices(current_user.company_id, invoice_type, from_date, to_date, party_id)]


@app.get("/api/invoices/{invoice_id}")
async def get_invoice_detail(invoice_id: str,
                              current_user=Depends(require_permission("invoices:read"))):
    inv = get_invoice(invoice_id, current_user.company_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    return inv


@app.post("/api/invoices", status_code=201)
async def create_invoice_route(ic: InvoiceCreate,
                                current_user=Depends(require_permission("invoices:write"))):
    db = get_db()
    company_data = db.col_find("companies", id=current_user.company_id)
    company_state = company_data[0].get("state", "Maharashtra") if company_data else "Maharashtra"
    tax_regime = company_data[0].get("tax_regime", "GST") if company_data else "GST"
    return create_invoice(ic, user_id=current_user.id, username=current_user.username,
                          company_id=current_user.company_id,
                          company_state=company_state, tax_regime=tax_regime)


@app.post("/api/invoices/{invoice_id}/payment")
async def pay_invoice(invoice_id: str, amount: float, payment_account_id: str,
                       current_user=Depends(require_permission("invoices:write"))):
    return record_payment(invoice_id, amount, payment_account_id,
                          user_id=current_user.id, username=current_user.username,
                          company_id=current_user.company_id)


# ══════════════════════════════════════════════════════════════
#  TAX ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/api/tax/rates")
async def get_tax_rates(current_user=Depends(require_permission("tax:read"))):
    return [t.model_dump() for t in list_tax_rates(current_user.company_id)]


@app.post("/api/tax/rates", status_code=201)
async def add_tax_rate(rate: TaxRate, current_user=Depends(require_permission("tax:write"))):
    db = get_db()
    rate.company_id = current_user.company_id
    db.col_insert("tax_rates", rate.model_dump())
    return rate


@app.get("/api/tax/gstr1")
async def gstr1(period_from: str, period_to: str,
                current_user=Depends(require_permission("tax:read"))):
    return compute_gstr1(current_user.company_id, period_from, period_to)


@app.get("/api/tax/gstr3b")
async def gstr3b(period_from: str, period_to: str,
                 current_user=Depends(require_permission("tax:read"))):
    return compute_gstr3b(current_user.company_id, period_from, period_to)


# ══════════════════════════════════════════════════════════════
#  REPORTING ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/api/reports/trial-balance")
async def report_trial_balance(as_of: str = None,
                                current_user=Depends(require_permission("reports:read"))):
    return trial_balance(current_user.company_id, as_of)


@app.get("/api/reports/profit-loss")
async def report_pl(from_date: str = None, to_date: str = None,
                     current_user=Depends(require_permission("reports:read"))):
    return profit_and_loss(current_user.company_id, from_date, to_date)


@app.get("/api/reports/balance-sheet")
async def report_bs(as_of: str = None,
                     current_user=Depends(require_permission("reports:read"))):
    return balance_sheet(current_user.company_id, as_of)


@app.get("/api/reports/cash-flow")
async def report_cf(from_date: str = None, to_date: str = None,
                     current_user=Depends(require_permission("reports:read"))):
    return cash_flow(current_user.company_id, from_date, to_date)


@app.get("/api/reports/day-book")
async def report_daybook(date: str = None,
                          current_user=Depends(require_permission("reports:read"))):
    return day_book(current_user.company_id, date)


@app.get("/api/reports/outstanding")
async def report_outstanding(report_type: str = "RECEIVABLE",
                              current_user=Depends(require_permission("reports:read"))):
    return outstanding_report(current_user.company_id, report_type)


# ══════════════════════════════════════════════════════════════
#  BLOCKCHAIN ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/api/blockchain/stats")
async def bc_stats(current_user=Depends(require_permission("blockchain:read"))):
    bc = get_blockchain(current_user.company_id)
    return bc.get_chain_stats()


@app.get("/api/blockchain/blocks")
async def bc_recent(n: int = 20, current_user=Depends(require_permission("blockchain:read"))):
    bc = get_blockchain(current_user.company_id)
    return bc.get_recent_blocks(n)


@app.get("/api/blockchain/blocks/{index}")
async def bc_block(index: int, current_user=Depends(require_permission("blockchain:read"))):
    bc = get_blockchain(current_user.company_id)
    block = bc.get_block_by_index(index)
    if not block:
        raise HTTPException(404, "Block not found")
    return block.to_dict()


@app.get("/api/blockchain/verify")
async def bc_verify(current_user=Depends(require_permission("blockchain:verify"))):
    bc = get_blockchain(current_user.company_id)
    valid, msg = bc.validate_chain()
    AuditTrail.log(user_id=current_user.id, username=current_user.username,
                   action="VERIFY", resource_type="Blockchain", resource_id="chain",
                   after={"valid": valid, "message": msg},
                   company_id=current_user.company_id)
    return {"valid": valid, "message": msg, "blocks": len(bc.chain)}


@app.get("/api/blockchain/transaction/{tx_id}")
async def bc_find_tx(tx_id: str, current_user=Depends(require_permission("blockchain:read"))):
    bc = get_blockchain(current_user.company_id)
    result = bc.find_transaction(tx_id)
    if not result:
        raise HTTPException(404, "Transaction not found in blockchain")
    block, tx = result
    return {"block": block.to_dict(), "transaction": tx}


# ══════════════════════════════════════════════════════════════
#  AUDIT ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/api/audit")
async def get_audit_log(user_id: str = None, action: str = None,
                         resource_type: str = None, limit: int = 100,
                         current_user=Depends(require_permission("audit:read"))):
    entries = AuditTrail.query(current_user.company_id, user_id, action,
                                resource_type, limit=limit)
    return [e.model_dump() for e in entries]


# ══════════════════════════════════════════════════════════════
#  RECONCILIATION ROUTES
# ══════════════════════════════════════════════════════════════

@app.post("/api/reconciliation/import")
async def import_bank_statement(account_id: str, entries: list[dict],
                                 current_user=Depends(require_permission("reconciliation:write"))):
    saved = Reconciliation.import_bank_statement(
        entries, account_id, current_user.company_id,
        current_user.id, current_user.username
    )
    return {"imported": len(saved)}


@app.post("/api/reconciliation/auto-match")
async def auto_match(account_id: str,
                      current_user=Depends(require_permission("reconciliation:write"))):
    return Reconciliation.auto_match(account_id, current_user.company_id)


@app.get("/api/reconciliation/{account_id}")
async def get_bank_statement(account_id: str,
                              current_user=Depends(require_permission("reconciliation:read"))):
    stmts = Reconciliation.get_statement(account_id, current_user.company_id)
    return [s.model_dump() for s in stmts]


# ══════════════════════════════════════════════════════════════
#  DB STATS / HEALTH
# ══════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/api/db/stats")
async def db_stats(current_user=Depends(require_permission("audit:read"))):
    return get_db().db_stats()


# ══════════════════════════════════════════════════════════════
#  FRONTEND CATCH-ALL
# ══════════════════════════════════════════════════════════════

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    index = frontend_dir / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"message": "TallyChain API — frontend not found. Use /api/docs"},
                        status_code=200)
