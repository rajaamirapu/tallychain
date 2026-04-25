"""
TallyChain Desktop Application
Main entry point: login window + main window with sidebar navigation
"""
import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.styles import *


# ─── Bootstrap ────────────────────────────────────────────────────────────────

def bootstrap():
    """Seed DB with defaults on first run."""
    from auth.rbac import ensure_admin_exists
    from modules.ledger import seed_default_accounts
    from modules.taxation import seed_tax_rates
    ensure_admin_exists()
    seed_default_accounts()
    seed_tax_rates()


# ─── Login Window ─────────────────────────────────────────────────────────────

class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TallyChain — Login")
        self.resizable(False, False)
        self.configure(bg=BG)
        apply_theme(self)
        self._center(420, 500)
        self._build()
        self.session = None

    def _center(self, w, h):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(expand=True, fill="both")

        # Logo / header
        logo_frame = tk.Frame(outer, bg=BG)
        logo_frame.pack(pady=(50, 0))
        tk.Label(logo_frame, text="⛓", font=("Segoe UI", 48), bg=BG, fg=ACCENT).pack()
        tk.Label(logo_frame, text="TallyChain", font=("Segoe UI", 24, "bold"),
                 bg=BG, fg=TEXT).pack()
        tk.Label(logo_frame, text="Blockchain-Powered Accounting",
                 font=FONT_SMALL, bg=BG, fg=MUTED).pack(pady=(4, 0))

        # Card
        card = tk.Frame(outer, bg=SURFACE, padx=32, pady=28)
        card.pack(padx=40, pady=30)

        tk.Label(card, text="Username", bg=SURFACE, fg=MUTED, font=FONT_SMALL,
                 anchor="w").pack(fill="x")
        self.username_var = tk.StringVar()
        user_entry = tk.Entry(card, textvariable=self.username_var, width=28,
                              bg=SURFACE2, fg=TEXT, insertbackground=TEXT,
                              relief="flat", font=FONT_BODY)
        user_entry.pack(fill="x", ipady=8, pady=(2, 14))
        user_entry.focus()

        tk.Label(card, text="Password", bg=SURFACE, fg=MUTED, font=FONT_SMALL,
                 anchor="w").pack(fill="x")
        self.password_var = tk.StringVar()
        pwd_entry = tk.Entry(card, textvariable=self.password_var, show="●", width=28,
                             bg=SURFACE2, fg=TEXT, insertbackground=TEXT,
                             relief="flat", font=FONT_BODY)
        pwd_entry.pack(fill="x", ipady=8, pady=(2, 20))
        pwd_entry.bind("<Return>", lambda e: self._login())

        self.error_label = tk.Label(card, text="", bg=SURFACE, fg=DANGER,
                                    font=FONT_SMALL)
        self.error_label.pack()

        btn = tk.Button(card, text="Sign In", command=self._login,
                        bg=ACCENT, fg="white", font=("Segoe UI", 11, "bold"),
                        relief="flat", cursor="hand2", padx=20, pady=10,
                        activebackground=ACCENT_DARK, activeforeground="white")
        btn.pack(fill="x", pady=(8, 0))

        tk.Label(outer, text="Default: admin / Admin@123",
                 bg=BG, fg=MUTED, font=FONT_SMALL).pack(pady=(0, 12))

    def _login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()
        if not username or not password:
            self.error_label.config(text="Please enter username and password.")
            return
        try:
            from auth.rbac import authenticate_user
            user = authenticate_user(username, password)
            if user is None:
                self.error_label.config(text="Invalid username or password.")
                return
            if not getattr(user, "is_active", True):
                self.error_label.config(text="Your account has been deactivated.")
                return
            self.session = {
                "user_id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "role": user.role,
                "company_id": user.company_id,
            }
            self.destroy()
        except Exception as e:
            self.error_label.config(text=f"Login error: {e}")


# ─── Main Application Window ──────────────────────────────────────────────────

class MainApp(tk.Tk):
    MENU_ITEMS = [
        ("Dashboard",   "🏠", "dashboard"),
        ("Accounts",    "📒", "accounts"),
        ("Vouchers",    "📝", "vouchers"),
        ("Invoices",    "🧾", "invoices"),
        ("Reports",     "📊", "reports"),
        ("Taxation",    "🧮", "tax"),
        ("Blockchain",  "⛓", "blockchain"),
        ("Audit",       "🔍", "audit"),
        ("Admin",       "⚙", "admin"),
    ]

    # Maps that require specific permissions to show
    PERM_MAP = {
        "admin":      "users:read",
        "audit":      "audit:read",
        "blockchain": "blockchain:read",
    }

    def __init__(self, session: dict):
        super().__init__()
        self.session = session
        self.title(f"TallyChain — {session.get('full_name', '')} ({session.get('role', '')})")
        self.state("zoomed")
        self.configure(bg=BG)
        apply_theme(self)
        self._panels: dict = {}
        self._active_key = None
        self._sidebar_btns: dict = {}
        self._build()
        self._navigate("dashboard")

    def _build(self):
        # Sidebar
        self.sidebar = tk.Frame(self, bg=SURFACE2, width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo in sidebar
        logo = tk.Frame(self.sidebar, bg=SURFACE2, pady=18)
        logo.pack(fill="x")
        tk.Label(logo, text="⛓ TallyChain", font=("Segoe UI", 14, "bold"),
                 bg=SURFACE2, fg=ACCENT).pack()
        tk.Label(logo, text="Blockchain Accounting",
                 font=FONT_SMALL, bg=SURFACE2, fg=MUTED).pack()

        sep = tk.Frame(self.sidebar, bg=BORDER, height=1)
        sep.pack(fill="x", padx=16, pady=(0, 8))

        # Nav buttons
        for label, icon, key in self.MENU_ITEMS:
            if key in self.PERM_MAP:
                from auth.rbac import has_permission
                if not has_permission(self.session.get("role", ""), self.PERM_MAP[key]):
                    continue
            btn = tk.Button(
                self.sidebar,
                text=f"  {icon}  {label}",
                anchor="w",
                bg=SURFACE2, fg=TEXT,
                activebackground=ACCENT, activeforeground="white",
                relief="flat", font=FONT_BODY,
                cursor="hand2", padx=16, pady=10,
                command=lambda k=key: self._navigate(k),
            )
            btn.pack(fill="x")
            self._sidebar_btns[key] = btn

        # Bottom: user info + logout
        bottom = tk.Frame(self.sidebar, bg=SURFACE2)
        bottom.pack(side="bottom", fill="x", pady=12, padx=12)
        sep2 = tk.Frame(self.sidebar, bg=BORDER, height=1)
        sep2.pack(side="bottom", fill="x", padx=16, pady=(0, 4))
        tk.Label(bottom, text=self.session.get("full_name", ""),
                 bg=SURFACE2, fg=TEXT, font=FONT_SMALL).pack(anchor="w")
        tk.Label(bottom, text=self.session.get("role", "").capitalize(),
                 bg=SURFACE2, fg=MUTED, font=FONT_SMALL).pack(anchor="w")
        tk.Button(bottom, text="Sign Out", bg=SURFACE2, fg=DANGER,
                  relief="flat", cursor="hand2", font=FONT_SMALL,
                  command=self._logout).pack(anchor="w", pady=(6, 0))

        # Main content area
        self.content = tk.Frame(self, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)

        # Status bar
        self.status_bar = tk.Label(self, text="Ready", bg=SURFACE2, fg=MUTED,
                                   font=FONT_SMALL, anchor="w", padx=12)
        self.status_bar.pack(side="bottom", fill="x", ipady=3)

    def _get_panel(self, key):
        if key in self._panels:
            return self._panels[key]
        # Lazy-load panels
        panel = None
        if key == "dashboard":
            from ui.dashboard import DashboardPanel
            panel = DashboardPanel(self.content, self.session)
        elif key == "accounts":
            from ui.accounts import AccountsPanel
            panel = AccountsPanel(self.content, self.session)
        elif key == "vouchers":
            from ui.vouchers import VouchersPanel
            panel = VouchersPanel(self.content, self.session)
        elif key == "invoices":
            from ui.invoices import InvoicesPanel
            panel = InvoicesPanel(self.content, self.session)
        elif key == "reports":
            from ui.reports import ReportsPanel
            panel = ReportsPanel(self.content, self.session)
        elif key == "tax":
            from ui.tax import TaxPanel
            panel = TaxPanel(self.content, self.session)
        elif key == "blockchain":
            from ui.blockchain_view import BlockchainPanel
            panel = BlockchainPanel(self.content, self.session)
        elif key == "audit":
            from ui.audit import AuditTabPanel
            panel = AuditTabPanel(self.content, self.session)
        elif key == "admin":
            from ui.users import AdminPanel
            panel = AdminPanel(self.content, self.session)

        if panel is not None:
            self._panels[key] = panel
        return panel

    def _navigate(self, key):
        if self._active_key == key:
            return

        # Hide current panel
        if self._active_key and self._active_key in self._panels:
            self._panels[self._active_key].pack_forget()

        # Highlight sidebar button
        for k, btn in self._sidebar_btns.items():
            btn.config(bg=SURFACE2, fg=TEXT)
        if key in self._sidebar_btns:
            self._sidebar_btns[key].config(bg=ACCENT, fg="white")

        # Show/create new panel
        try:
            panel = self._get_panel(key)
            if panel:
                panel.pack(fill="both", expand=True)
                panel.refresh()
                self._active_key = key
                label = next((lbl for lbl, _, k in self.MENU_ITEMS if k == key), key.title())
                self.status_bar.config(text=f"  {label}")
        except Exception as e:
            messagebox.showerror("Panel Error", f"Could not load panel '{key}':\n{e}")

    def _logout(self):
        if messagebox.askyesno("Sign Out", "Are you sure you want to sign out?"):
            self.destroy()
            main()  # Re-launch login


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    try:
        bootstrap()
    except Exception as e:
        import traceback
        traceback.print_exc()
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Startup Error", f"Failed to initialise TallyChain:\n\n{e}")
        root.destroy()
        return

    login = LoginWindow()
    login.mainloop()

    if login.session is None:
        return  # User closed login window

    app = MainApp(login.session)
    app.mainloop()


if __name__ == "__main__":
    main()
