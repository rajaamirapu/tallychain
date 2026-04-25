"""
TallyChain -- User Management Panel
Create users, assign roles, deactivate accounts (admin only)
"""
import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.styles import *
from ui.widgets import DataTable, FormDialog, section_header


class UsersPanel(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        section_header(hdr, "User Management").pack(side="left")
        ttk.Button(hdr, text="+ New User", style="Accent.TButton",
                   command=self._add_user).pack(side="right", padx=(6, 0))
        ttk.Button(hdr, text="Edit Role", command=self._edit_role).pack(side="right", padx=(6, 0))
        ttk.Button(hdr, text="Deactivate", command=self._deactivate).pack(side="right")

        cols = [
            ("Username", 140, "w"),
            ("Full Name", 200, "w"),
            ("Email", 220, "w"),
            ("Role", 100, "center"),
            ("Company", 140, "w"),
            ("Active", 70, "center"),
            ("Created", 120, "center"),
        ]
        self.table = DataTable(self, cols, height=24)
        self.table.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self._users_cache = []
        self._load()

    def _load(self):
        try:
            from database.engine import get_db
            db = get_db()
            users = db.col_all("users")
            self._users_cache = users
            rows = []
            for u in users:
                rows.append((
                    u.get("username", ""),
                    u.get("full_name", ""),
                    u.get("email", ""),
                    u.get("role", ""),
                    u.get("company_id", ""),
                    "Yes" if u.get("is_active", True) else "No",
                    str(u.get("created_at", ""))[:10],
                ))
            self.table.set_rows(rows)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _add_user(self):
        fields = [
            ("username", "Username", "text", ""),
            ("full_name", "Full Name", "text", ""),
            ("email", "Email", "text", ""),
            ("role", "Role", "select", "accountant",
             ["admin", "accountant", "auditor", "viewer"]),
            ("password", "Password", "password", ""),
            ("confirm_password", "Confirm Password", "password", ""),
        ]
        dlg = FormDialog(self, "Create New User", fields)
        self.wait_window(dlg)
        if dlg.result:
            data = dlg.result
            if data.get("password") != data.get("confirm_password"):
                messagebox.showerror("Error", "Passwords do not match.")
                return
            try:
                from auth.rbac import create_user
                from database.models import UserCreate
                uc = UserCreate(
                    username=data["username"],
                    email=data["email"],
                    full_name=data["full_name"],
                    role=data["role"],
                    password=data["password"],
                )
                company_id = self.session.get("company_id", "default")
                create_user(uc, company_id=company_id)
                messagebox.showinfo("Success", f"User '{data['username']}' created successfully.")
                self._load()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _edit_role(self):
        idx = self.table.get_selected()
        if idx is None or idx < 0 or idx >= len(self._users_cache):
            messagebox.showwarning("Select User", "Please select a user to edit.")
            return
        user = self._users_cache[idx]
        if user.get("username") == "admin":
            messagebox.showwarning("Warning", "Cannot change the role of the admin user.")
            return
        fields = [
            ("username", "Username", "readonly", user.get("username", "")),
            ("role", "Role", "select", user.get("role", "viewer"),
             ["admin", "accountant", "auditor", "viewer"]),
        ]
        dlg = FormDialog(self, "Edit User Role", fields)
        self.wait_window(dlg)
        if dlg.result:
            try:
                from database.engine import get_db
                db = get_db()
                db.col_update("users", user["id"], {"role": dlg.result["role"]})
                messagebox.showinfo("Success", "Role updated successfully.")
                self._load()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _deactivate(self):
        idx = self.table.get_selected()
        if idx is None or idx < 0 or idx >= len(self._users_cache):
            messagebox.showwarning("Select User", "Please select a user to deactivate.")
            return
        user = self._users_cache[idx]
        if user.get("username") == self.session.get("username"):
            messagebox.showwarning("Warning", "You cannot deactivate your own account.")
            return
        if user.get("username") == "admin":
            messagebox.showwarning("Warning", "Cannot deactivate the main admin account.")
            return
        currently_active = user.get("is_active", True)
        action = "deactivate" if currently_active else "reactivate"
        if not messagebox.askyesno("Confirm", f"Are you sure you want to {action} '{user.get('username')}'?"):
            return
        try:
            from database.engine import get_db
            db = get_db()
            db.col_update("users", user["id"], {"is_active": not currently_active})
            messagebox.showinfo("Success", f"User {action}d successfully.")
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh(self):
        self._load()


class CompanyPanel(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        section_header(hdr, "Company Settings").pack(side="left")
        ttk.Button(hdr, text="Save", style="Accent.TButton",
                   command=self._save).pack(side="right")

        body = tk.Frame(self, bg=SURFACE)
        body.pack(fill="both", expand=True, padx=40, pady=10)

        self._vars = {}
        fields = [
            ("name", "Company Name"),
            ("gstin", "GSTIN"),
            ("pan", "PAN"),
            ("address", "Address"),
            ("city", "City"),
            ("state", "State"),
            ("pincode", "Pincode"),
            ("country", "Country"),
            ("phone", "Phone"),
            ("email", "Email"),
            ("financial_year_start", "FY Start (MM-DD)"),
        ]
        for i, (key, label) in enumerate(fields):
            tk.Label(body, text=label + ":", bg=SURFACE, fg=MUTED,
                     font=FONT_SMALL, anchor="e", width=22).grid(row=i, column=0, sticky="e", pady=6)
            var = tk.StringVar()
            tk.Entry(body, textvariable=var, width=36, bg=SURFACE2, fg=TEXT,
                     insertbackground=TEXT, relief="flat", font=FONT_BODY).grid(
                row=i, column=1, sticky="w", padx=(12, 0), pady=6)
            self._vars[key] = var

        self._load()

    def _load(self):
        try:
            from database.engine import get_db
            db = get_db()
            companies = db.col_all("companies")
            if companies:
                co = companies[0]
                for key, var in self._vars.items():
                    var.set(co.get(key, ""))
        except Exception:
            pass

    def _save(self):
        try:
            from database.engine import get_db
            from database.models import Company
            db = get_db()
            data = {k: v.get() for k, v in self._vars.items()}
            companies = db.col_all("companies")
            if companies:
                db.col_update("companies", companies[0]["id"], data)
            else:
                import uuid
                data["id"] = str(uuid.uuid4())
                db.col_insert("companies", data)
            messagebox.showinfo("Saved", "Company settings saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh(self):
        self._load()


class AdminPanel(ttk.Frame):
    """Tabbed container for user and company management."""
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)
        self.users_panel = UsersPanel(nb, self.session)
        self.company_panel = CompanyPanel(nb, self.session)
        nb.add(self.users_panel, text="Users")
        nb.add(self.company_panel, text="Company")

    def refresh(self):
        pass
