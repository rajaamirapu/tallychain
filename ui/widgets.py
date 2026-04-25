"""TallyChain -- Reusable Tkinter Widgets"""
import tkinter as tk
from tkinter import ttk, messagebox
from ui.styles import *


def fmt(n, dec=2):
    if n is None: return "—"
    try:
        return f"{float(n):,.{dec}f}"
    except Exception:
        return str(n)


def card(parent, title="", **kwargs):
    """Card frame with optional title label."""
    f = ttk.Frame(parent, style="Card.TFrame", padding=16)
    if title:
        ttk.Label(f, text=title, style="Title.TLabel").pack(anchor="w", pady=(0, 10))
    return f


class DataTable(ttk.Frame):
    """Scrollable Treeview table."""
    def __init__(self, parent, columns: list, show_index=False, height=14, **kwargs):
        super().__init__(parent, style="Card.TFrame")
        self.columns = columns
        self._build(height)

    def _build(self, height):
        self.tree = ttk.Treeview(self, columns=self.columns,
                                  show="headings", height=height)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for col in self.columns:
            txt = col.replace("_", " ").title()
            self.tree.heading(col, text=txt)
            w = 120
            if col in ("id",): w = 0
            elif col in ("narration","description","name"): w = 200
            elif col in ("hash","merkle_root","previous_hash"): w = 280
            elif col in ("code","date","type","status"): w = 90
            self.tree.column(col, width=w, minwidth=60,
                             stretch=(col not in ("id","code","date","type","status")))

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def set_rows(self, rows: list[dict]):
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            vals = [row.get(c, "") for c in self.columns]
            self.tree.insert("", "end", values=vals)

    def get_selected(self) -> dict | None:
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0])["values"]
        return dict(zip(self.columns, vals))

    def on_select(self, callback):
        self.tree.bind("<<TreeviewSelect>>", lambda e: callback(self.get_selected()))

    def on_double_click(self, callback):
        self.tree.bind("<Double-1>", lambda e: callback(self.get_selected()))


class FormDialog(tk.Toplevel):
    """Modal form dialog."""
    def __init__(self, parent, title: str, fields: list, on_submit,
                 submit_label="Save", width=460):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=SURFACE)
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)
        self._fields = fields
        self._vars = {}
        self._on_submit = on_submit
        self._build(title, submit_label)
        self.geometry(f"{width}x{len(fields)*62+120}")
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width()//2
        py = parent.winfo_rooty() + parent.winfo_height()//2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px-w//2}+{py-h//2}")

    def _build(self, title, submit_label):
        ttk.Label(self, text=title, style="XL.TLabel").pack(
            anchor="w", padx=20, pady=(18, 12))
        ttk.Separator(self).pack(fill="x", padx=20)

        body = ttk.Frame(self, padding=(20, 12))
        body.pack(fill="both", expand=True)

        for field in self._fields:
            key    = field["key"]
            label  = field.get("label", key.replace("_", " ").title())
            ftype  = field.get("type", "text")
            opts   = field.get("options", [])
            defval = field.get("default", "")

            row = ttk.Frame(body)
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="Muted.TLabel", width=18,
                      anchor="w").pack(side="left")

            if ftype == "select":
                var = tk.StringVar(value=str(defval))
                cb = ttk.Combobox(row, textvariable=var, values=opts,
                                  state="readonly", width=26)
                cb.pack(side="left", fill="x", expand=True)
            elif ftype == "password":
                var = tk.StringVar(value=str(defval))
                ttk.Entry(row, textvariable=var, show="*", width=28).pack(
                    side="left", fill="x", expand=True)
            elif ftype == "number":
                var = tk.StringVar(value=str(defval))
                ttk.Entry(row, textvariable=var, width=28).pack(
                    side="left", fill="x", expand=True)
            elif ftype == "date":
                var = tk.StringVar(value=str(defval))
                ttk.Entry(row, textvariable=var, width=28).pack(
                    side="left", fill="x", expand=True)
                ttk.Label(row, text="YYYY-MM-DD", style="Muted.TLabel").pack(side="left", padx=4)
            elif ftype == "readonly":
                var = tk.StringVar(value=str(defval))
                e = ttk.Entry(row, textvariable=var, width=28, state="readonly")
                e.pack(side="left", fill="x", expand=True)
            else:
                var = tk.StringVar(value=str(defval))
                ttk.Entry(row, textvariable=var, width=28).pack(
                    side="left", fill="x", expand=True)
            self._vars[key] = var

        ttk.Separator(self).pack(fill="x", padx=20, pady=8)
        btns = ttk.Frame(self, padding=(20, 0, 20, 16))
        btns.pack(fill="x")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text=submit_label, style="Primary.TButton",
                   command=self._submit).pack(side="right")

    def _submit(self):
        data = {k: v.get() for k, v in self._vars.items()}
        try:
            self._on_submit(data)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def set_values(self, data: dict):
        for k, var in self._vars.items():
            if k in data:
                var.set(str(data[k]) if data[k] is not None else "")


class StatCard(ttk.Frame):
    def __init__(self, parent, label, value, sub="", color=None, **kwargs):
        super().__init__(parent, style="Card.TFrame", padding=16)
        c = color or ACCENT
        ttk.Label(self, text=label, style="Muted.TLabel").pack(anchor="w")
        lbl = ttk.Label(self, text=str(value), font=("Segoe UI", 22, "bold"),
                        background=SURFACE, foreground=c)
        lbl.pack(anchor="w", pady=(4, 2))
        if sub:
            ttk.Label(self, text=sub, style="Muted.TLabel").pack(anchor="w")
        self._val_lbl = lbl

    def update_value(self, value, color=None):
        self._val_lbl.configure(text=str(value))
        if color:
            self._val_lbl.configure(foreground=color)


def badge(parent, text, color=ACCENT, bg=None):
    bg = bg or SURFACE2
    lbl = tk.Label(parent, text=f" {text} ",
                   font=("Segoe UI", 8, "bold"),
                   fg=color, bg=bg, padx=4, pady=2,
                   relief="flat", bd=0)
    return lbl


def separator(parent, orient="horizontal"):
    return ttk.Separator(parent, orient=orient)


def scrolled_text(parent, height=8, **kwargs):
    frame = ttk.Frame(parent)
    txt = tk.Text(frame, height=height, bg=SURFACE2, fg=TEXT,
                  font=FONT_MONO, insertbackground=TEXT,
                  relief="flat", bd=0, padx=8, pady=8, wrap="word", **kwargs)
    vsb = ttk.Scrollbar(frame, command=txt.yview)
    txt.configure(yscrollcommand=vsb.set)
    txt.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    return frame, txt


def section_header(parent, title, button_text=None, button_cmd=None):
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=(0, 10))
    ttk.Label(row, text=title, style="Title.TLabel").pack(side="left")
    if button_text and button_cmd:
        ttk.Button(row, text=button_text, style="Primary.TButton",
                   command=button_cmd).pack(side="right")
    return row
