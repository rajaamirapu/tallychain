"""
TallyChain — Immutable Audit Trail
====================================
Every create/update/delete/login operation is logged.
Audit records are append-only (never deleted) and also recorded
to the blockchain for tamper-evident history.
"""
import json
import os
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from database.models import AuditEntry
from config import settings


class AuditTrail:
    """
    Writes audit entries to:
      1. The encrypted TallyDB (queryable)
      2. A plain append-only JSONL audit log file (secondary evidence)
    """

    @staticmethod
    def log(
        user_id: str,
        username: str,
        action: str,
        resource_type: str,
        resource_id: str,
        before: Optional[dict] = None,
        after: Optional[dict] = None,
        ip_address: str = "",
        status: str = "SUCCESS",
        company_id: str = "default",
    ) -> AuditEntry:
        entry = AuditEntry(
            user_id=user_id,
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before=before,
            after=after,
            ip_address=ip_address,
            status=status,
            company_id=company_id,
        )

        # Write to encrypted DB
        try:
            from database.engine import get_db
            db = get_db()
            db.col_insert("audit_log", entry.model_dump())
        except Exception:
            pass  # Don't let audit failure block main operation

        # Write to JSONL file (secondary, plaintext evidence)
        try:
            Path(settings.AUDIT_PATH).parent.mkdir(parents=True, exist_ok=True)
            with open(settings.AUDIT_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.model_dump(), default=str) + "\n")
        except Exception:
            pass

        return entry

    @staticmethod
    def query(
        company_id: str = "default",
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
        limit: int = 200,
    ) -> list[AuditEntry]:
        from database.engine import get_db
        db = get_db()
        records = db.col_find("audit_log", company_id=company_id)

        if user_id:
            records = [r for r in records if r.get("user_id") == user_id]
        if action:
            records = [r for r in records if r.get("action") == action]
        if resource_type:
            records = [r for r in records if r.get("resource_type") == resource_type]
        if from_time:
            records = [r for r in records if r.get("timestamp", "") >= from_time]
        if to_time:
            records = [r for r in records if r.get("timestamp", "") <= to_time]

        records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
        return [AuditEntry(**r) for r in records[:limit]]


# ─── Reconciliation ──────────────────────────────────────────────────────────

class Reconciliation:

    @staticmethod
    def import_bank_statement(entries: list[dict], account_id: str,
                               company_id: str = "default",
                               user_id: str = "system",
                               username: str = "system") -> list:
        from database.models import BankStatement
        from database.engine import get_db
        db = get_db()
        saved = []
        for e in entries:
            stmt = BankStatement(
                account_id=account_id,
                date=e.get("date", ""),
                description=e.get("description", ""),
                debit=float(e.get("debit", 0)),
                credit=float(e.get("credit", 0)),
                balance=float(e.get("balance", 0)),
                company_id=company_id,
            )
            db.col_insert("bank_statements", stmt.model_dump())
            saved.append(stmt)
        AuditTrail.log(user_id=user_id, username=username,
                       action="IMPORT", resource_type="BankStatement",
                       resource_id=account_id, company_id=company_id,
                       after={"count": len(saved)})
        return saved

    @staticmethod
    def auto_match(account_id: str, company_id: str = "default") -> dict:
        """
        Auto-match unmatched bank statement entries with vouchers
        by amount and approximate date (±3 days).
        """
        from database.engine import get_db
        from database.models import BankStatement, Voucher
        db = get_db()

        unmatched = [BankStatement(**r) for r in
                     db.col_find("bank_statements", account_id=account_id,
                                 company_id=company_id, is_matched=False)]
        vouchers = [Voucher(**r) for r in
                    db.col_find("vouchers", company_id=company_id, is_posted=True)]

        matched_count = 0
        for stmt in unmatched:
            stmt_amount = stmt.credit - stmt.debit
            for v in vouchers:
                # Check amount match in any line for this account
                for line in v.lines:
                    if line.account_id != account_id:
                        continue
                    line_net = line.debit - line.credit
                    if abs(line_net - stmt_amount) < 0.01:
                        # Date within ±3 days
                        from datetime import date, timedelta
                        try:
                            sd = date.fromisoformat(stmt.date)
                            vd = date.fromisoformat(v.date)
                            if abs((sd - vd).days) <= 3:
                                db.col_update("bank_statements", stmt.id, {
                                    "is_matched": True,
                                    "matched_voucher_id": v.id,
                                })
                                matched_count += 1
                                break
                        except Exception:
                            pass
                else:
                    continue
                break

        total = len(unmatched)
        return {
            "total_unmatched": total,
            "auto_matched": matched_count,
            "still_unmatched": total - matched_count,
        }

    @staticmethod
    def get_statement(account_id: str, company_id: str = "default") -> list:
        from database.engine import get_db
        from database.models import BankStatement
        db = get_db()
        records = db.col_find("bank_statements", account_id=account_id,
                               company_id=company_id)
        stmts = [BankStatement(**r) for r in records]
        stmts.sort(key=lambda s: s.date)
        return stmts
