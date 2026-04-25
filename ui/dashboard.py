"""TallyChain -- Dashboard Panel"""
import tkinter as tk
from tkinter import ttk
from ui.styles import *
from ui.widgets import StatCard, DataTable, card, fmt


class DashboardPanel(ttk.Frame):
    def __init__(self, parent, session, **kwargs):
        super().__init__(parent, style="Dark.TFrame", padding=20)
        self.session = session
        self._build()
        self.refresh()

    def _build(self):
        ttk.Label(self, text="Dashboard", style="XL.TLabel",
                  background=BG).pack(anchor="w", pady=(0, 18))

        # Stat cards row
        self.cards_row = ttk.Frame(self, style="Dark.TFrame")
        self.cards_row.pack(fill="x", pady=(0, 20))
        self.cards_row.columnconfigure((0,1,2,3), weight=1)

        self.stat_blocks  = StatCard(self.cards_row, "Blockchain Blocks", "—", "transactions", ACCENT)
        self.stat_income  = StatCard(self.cards_row, "Total Income",  "—", "all time", SUCCESS)
        self.stat_expense = StatCard(self.cards_row, "Total Expenses","—", "all time", DANGER)
        self.stat_profit  = StatCard(self.cards_row, "Net Profit",    "—", "", SUCCESS)
        for i, c in enumerate([self.stat_blocks, self.stat_income,
                                self.stat_expense, self.stat_profit]):
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i==0 else 12, 0))

        # Two-column lower area
        lower = ttk.Frame(self, style="Dark.TFrame")
        lower.pack(fill="both", expand=True)
        lower.columnconfigure(0, weight=1)
        lower.columnconfigure(1, weight=1)

        # Blockchain info card
        bc_card = card(lower, "Blockchain Status")
        bc_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.bc_text = tk.Text(bc_card, height=8, bg=SURFACE2, fg=TEXT,
                               font=FONT_MONO, relief="flat", bd=0,
                               padx=8, pady=8, state="disabled")
        self.bc_text.pack(fill="both", expand=True)

        # Recent vouchers card
        rv_card = card(lower, "Recent Vouchers")
        rv_card.grid(row=0, column=1, sticky="nsew")
        cols = ["voucher_number","voucher_type","date","amount"]
        self.recent_tbl = DataTable(rv_card, cols, height=7)
        self.recent_tbl.pack(fill="both", expand=True)

    def refresh(self):
        try:
            from modules.ledger import get_blockchain, list_vouchers
            from modules.reporting import profit_and_loss
            cid = self.session.get("company_id", "default")

            bc = get_blockchain(cid)
            stats = bc.get_chain_stats()
            self.stat_blocks.update_value(stats["total_blocks"], ACCENT)

            pl = profit_and_loss(cid)
            self.stat_income.update_value(f"₹{fmt(pl['total_income'],0)}", SUCCESS)
            self.stat_expense.update_value(f"₹{fmt(pl['total_expenses'],0)}", DANGER)
            net = pl["net_profit"]
            self.stat_profit.update_value(
                f"₹{fmt(abs(net),0)}",
                SUCCESS if net >= 0 else DANGER
            )
            self.stat_profit._val_lbl.master.children
            # re-label
            for w in self.stat_profit.winfo_children():
                if isinstance(w, ttk.Label) and w.cget("text") in ("Net Profit","Net Loss"):
                    w.configure(text="Net Profit" if net >= 0 else "Net Loss")

            # BC text
            self.bc_text.configure(state="normal")
            self.bc_text.delete("1.0","end")
            status = "✓ INTACT" if stats["is_valid"] else "✗ TAMPERED"
            color  = SUCCESS if stats["is_valid"] else DANGER
            self.bc_text.insert("end",
                f"Status    : {status}\n"
                f"Blocks    : {stats['total_blocks']}\n"
                f"Txns      : {stats['total_transactions']}\n"
                f"Latest #  : {stats['latest_index']}\n\n"
                f"Latest Hash:\n{stats['latest_hash']}\n\n"
                f"Genesis Hash:\n{stats['genesis_hash']}"
            )
            self.bc_text.configure(state="disabled")

            # Recent vouchers
            vouchers = list_vouchers(cid)[:8]
            rows = []
            for v in vouchers:
                amt = sum(l.debit for l in v.lines)
                rows.append({
                    "voucher_number": v.voucher_number,
                    "voucher_type":   v.voucher_type,
                    "date":           v.date,
                    "amount":         f"₹{fmt(amt)}",
                })
            self.recent_tbl.set_rows(rows)
        except Exception as e:
            pass
