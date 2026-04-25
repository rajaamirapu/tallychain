"""
TallyChain -- Auth & RBAC (no web framework dependencies)
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

PERMISSIONS: dict = {
    "accounts:read":        {"admin","accountant","auditor","viewer"},
    "accounts:write":       {"admin","accountant"},
    "accounts:delete":      {"admin"},
    "vouchers:read":        {"admin","accountant","auditor","viewer"},
    "vouchers:write":       {"admin","accountant"},
    "vouchers:delete":      {"admin"},
    "invoices:read":        {"admin","accountant","auditor","viewer"},
    "invoices:write":       {"admin","accountant"},
    "invoices:delete":      {"admin"},
    "reports:read":         {"admin","accountant","auditor","viewer"},
    "tax:read":             {"admin","accountant","auditor","viewer"},
    "tax:write":            {"admin","accountant"},
    "audit:read":           {"admin","auditor"},
    "blockchain:read":      {"admin","accountant","auditor"},
    "blockchain:verify":    {"admin","auditor"},
    "users:read":           {"admin"},
    "users:write":          {"admin"},
    "users:delete":         {"admin"},
    "company:read":         {"admin","accountant","auditor","viewer"},
    "company:write":        {"admin"},
    "reconciliation:read":  {"admin","accountant","auditor"},
    "reconciliation:write": {"admin","accountant"},
}


def has_permission(role: str, permission: str) -> bool:
    return role in PERMISSIONS.get(permission, set())


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def authenticate_user(username: str, password: str):
    from database.engine import get_db
    from database.models import User
    db = get_db()
    users = db.col_find("users", username=username)
    if not users:
        return None
    user = User(**users[0])
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_user(user_create, company_id: str = "default"):
    from database.engine import get_db
    from database.models import User
    db = get_db()
    if db.col_find("users", username=user_create.username):
        raise ValueError("Username already exists")
    user = User(
        username=user_create.username,
        email=user_create.email,
        full_name=user_create.full_name,
        role=user_create.role,
        hashed_password=hash_password(user_create.password),
        company_id=company_id,
    )
    db.col_insert("users", user.model_dump())
    return user


def ensure_admin_exists():
    from database.engine import get_db
    from database.models import UserCreate
    db = get_db()
    if db.col_count("users") == 0:
        admin = UserCreate(
            username="admin", email="admin@tallychain.local",
            full_name="System Administrator", role="admin", password="Admin@123",
        )
        create_user(admin)
        return True
    return False
