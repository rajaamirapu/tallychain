"""
TallyChain -- Blockchain Explorer Panel
View chain blocks, verify integrity, inspect block data
"""
import tkinter as tk
from tkinter import ttk, messagebox
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.styles import *
from ui.widgets import DataTable, section_header, scrolled_text


class BlockchainPanel(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._build()

    def _build(self):
        # Top: stats bar
        stats_bar = tk.Frame(self, bg=SURFACE2, pady=10)
        stats_bar.pack(fill="x", padx=0, pady=(0, 2))

        self.stat_labels = {}
        for key, label in [("blocks", "Total Blocks"), ("valid", "Chain Valid"),
                            ("last_hash", "Latest Hash")]:
            f = tk.Frame(stats_bar, bg=SURFACE2)
            f.pack(side="left", padx=28)
            tk.Label(f, text=label, bg=SURFACE2, fg=MUTED, font=FONT_SMALL).pack()
            lbl = tk.Label(f, text="—", bg=SURFACE2, fg=TEXT, font=FONT_BODY)
            lbl.pack()
            self.stat_labels[key] = lbl

        # Control bar
        ctrl = tk.Frame(self, bg=SURFACE)
        ctrl.pack(fill="x", padx=20, pady=(10, 6))
        section_header(ctrl, "Block Explorer").pack(side="left")
        ttk.Button(ctrl, text="Verify Chain Integrity", style="Accent.TButton",
                   command=self._verify).pack(side="right", padx=(6, 0))
        ttk.Button(ctrl, text="Refresh", command=self._load).pack(side="right")

        # Main split: block list left, detail right
        split = tk.Frame(self, bg=SURFACE)
        split.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Left: block list
        left = tk.Frame(split, bg=SURFACE, width=420)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        cols = [
            ("#", 50, "center"),
            ("Hash (short)", 150, "center"),
            ("Transactions", 100, "center"),
            ("Timestamp", 150, "center"),
        ]
        self.block_table = DataTable(left, cols, height=24)
        self.block_table.pack(fill="both", expand=True)
        self.block_table.on_select(self._on_block_select)

        # Right: block detail
        right = tk.Frame(split, bg=SURFACE)
        right.pack(side="left", fill="both", expand=True, padx=(16, 0))

        tk.Label(right, text="Block Detail", bg=SURFACE, fg=TEXT, font=FONT_TITLE).pack(anchor="w", pady=(0, 6))
        self.detail_text = scrolled_text(right, height=30)
        self.detail_text.pack(fill="both", expand=True)
        self.detail_text.config(state="disabled")

        self._blocks_cache = []
        self._load()

    def _load(self):
        try:
            from blockchain.chain import get_blockchain
            chain = get_blockchain()
            blocks = chain.blocks
            self._blocks_cache = blocks
            stats = chain.get_chain_stats()

            self.stat_labels["blocks"].config(text=str(stats.get("length", len(blocks))))
            self.stat_labels["valid"].config(
                text="✓ Valid" if stats.get("is_valid", False) else "✗ Invalid",
                fg=SUCCESS if stats.get("is_valid", False) else DANGER)
            if blocks:
                last_hash = blocks[-1].hash or ""
                self.stat_labels["last_hash"].config(text=last_hash[:20] + "..." if len(last_hash) > 20 else last_hash)
            else:
                self.stat_labels["last_hash"].config(text="—")

            rows = []
            for i, blk in enumerate(blocks):
                h = blk.hash or ""
                rows.append((
                    str(i),
                    h[:16] + "..." if len(h) > 16 else h,
                    str(len(blk.transactions)) if blk.transactions else "0",
                    str(blk.timestamp)[:19] if blk.timestamp else "",
                ))
            self.block_table.set_rows(rows)
        except Exception as e:
            messagebox.showerror("Error loading blockchain", str(e))

    def _on_block_select(self, idx):
        if idx < 0 or idx >= len(self._blocks_cache):
            return
        blk = self._blocks_cache[idx]
        lines = []
        lines.append(f"Block #{idx}")
        lines.append("=" * 56)
        lines.append(f"  Index         : {blk.index}")
        lines.append(f"  Timestamp     : {blk.timestamp}")
        lines.append(f"  Hash          : {blk.hash}")
        lines.append(f"  Previous Hash : {blk.previous_hash}")
        lines.append(f"  Merkle Root   : {blk.merkle_root}")
        lines.append(f"  Nonce         : {blk.nonce}")

        txns = blk.transactions or []
        lines.append(f"\nTransactions ({len(txns)}):")
        lines.append("-" * 56)
        for i, tx in enumerate(txns):
            lines.append(f"\n  [{i+1}] {tx.get('voucher_type', tx.get('type', 'UNKNOWN'))}")
            lines.append(f"       ID       : {tx.get('id', 'N/A')}")
            lines.append(f"       Amount   : {tx.get('total_amount', tx.get('amount', 'N/A'))}")
            lines.append(f"       Date     : {tx.get('date', 'N/A')}")
            narr = tx.get("narration", "")
            if narr:
                lines.append(f"       Narration: {narr[:60]}")
            # Show debit/credit lines if present
            for line in tx.get("lines", []):
                dr = line.get("debit_amount", 0)
                cr = line.get("credit_amount", 0)
                acct = line.get("account_name", line.get("account_id", ""))
                if dr:
                    lines.append(f"         Dr {acct:<30} {dr:>12.2f}")
                if cr:
                    lines.append(f"         Cr {acct:<30} {cr:>12.2f}")

        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", "\n".join(lines))
        self.detail_text.config(state="disabled")

    def _verify(self):
        try:
            from blockchain.chain import get_blockchain
            chain = get_blockchain()
            is_valid, _msg = chain.validate_chain()
            if is_valid:
                messagebox.showinfo("Chain Verification",
                    "✓ Blockchain integrity verified!\n\nAll blocks are valid and properly chained.\nNo tampering detected.")
            else:
                messagebox.showerror("Chain Verification",
                    "✗ BLOCKCHAIN INTEGRITY COMPROMISED!\n\nOne or more blocks have been tampered with.\nPlease contact your system administrator immediately.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh(self):
        self._load()
