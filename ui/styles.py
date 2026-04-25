"""TallyChain -- ttk Dark Theme"""
import tkinter as tk
from tkinter import ttk

BG        = "#0f1117"
SURFACE   = "#1a1d27"
SURFACE2  = "#21253a"
BORDER    = "#2e3348"
ACCENT    = "#4f8ef7"
ACCENT_H  = "#3b7de8"
SUCCESS   = "#34d399"
DANGER    = "#f87171"
WARNING   = "#fbbf24"
TEXT      = "#e2e8f0"
MUTED     = "#64748b"
WHITE     = "#ffffff"

FONT        = ("Segoe UI", 10)
FONT_SM     = ("Segoe UI", 9)
FONT_LG     = ("Segoe UI", 12)
FONT_XL     = ("Segoe UI", 16, "bold")
FONT_BOLD   = ("Segoe UI", 10, "bold")
FONT_MONO   = ("Courier New", 9)

# Aliases used by panel modules
FONT_SMALL  = FONT_SM
FONT_BODY   = FONT
FONT_TITLE  = FONT_LG
ACCENT_DARK = ACCENT_H


def apply_theme(root: tk.Tk):
    root.configure(bg=BG)
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".",
        background=SURFACE, foreground=TEXT,
        fieldbackground=SURFACE2, bordercolor=BORDER,
        troughcolor=SURFACE2, selectbackground=ACCENT,
        selectforeground=WHITE, font=FONT)

    style.configure("TFrame", background=SURFACE)
    style.configure("Dark.TFrame", background=BG)
    style.configure("Surface2.TFrame", background=SURFACE2)
    style.configure("Card.TFrame", background=SURFACE, relief="flat")

    style.configure("TLabel", background=SURFACE, foreground=TEXT, font=FONT)
    style.configure("Dark.TLabel", background=BG, foreground=TEXT, font=FONT)
    style.configure("Muted.TLabel", background=SURFACE, foreground=MUTED, font=FONT_SM)
    style.configure("Title.TLabel", background=SURFACE, foreground=TEXT, font=FONT_LG)
    style.configure("XL.TLabel", background=SURFACE, foreground=TEXT, font=FONT_XL)
    style.configure("Accent.TLabel", background=SURFACE, foreground=ACCENT, font=FONT_BOLD)
    style.configure("Success.TLabel", background=SURFACE, foreground=SUCCESS, font=FONT_BOLD)
    style.configure("Danger.TLabel", background=SURFACE, foreground=DANGER, font=FONT_BOLD)
    style.configure("Warning.TLabel", background=SURFACE, foreground=WARNING, font=FONT_BOLD)
    style.configure("Mono.TLabel", background=SURFACE, foreground=MUTED, font=FONT_MONO)

    style.configure("TButton", background=SURFACE2, foreground=TEXT, padding=(10, 6),
        bordercolor=BORDER, focusthickness=0, relief="flat", font=FONT)
    style.map("TButton",
        background=[("active", BORDER), ("pressed", BORDER)],
        foreground=[("disabled", MUTED)])

    style.configure("Accent.TButton", background=ACCENT, foreground=WHITE,
        padding=(12, 7), font=FONT_BOLD)
    style.map("Accent.TButton",
        background=[("active", ACCENT_H), ("pressed", ACCENT_H)])

    style.configure("Primary.TButton", background=ACCENT, foreground=WHITE,
        padding=(12, 7), font=FONT_BOLD)
    style.map("Primary.TButton",
        background=[("active", ACCENT_H), ("pressed", ACCENT_H)])

    style.configure("Danger.TButton", background=DANGER, foreground=WHITE, padding=(10, 6))
    style.map("Danger.TButton", background=[("active", "#e05555")])

    style.configure("Success.TButton", background=SUCCESS, foreground=BG, padding=(10, 6))
    style.map("Success.TButton", background=[("active", "#22c386")])

    style.configure("Nav.TButton", background=SURFACE, foreground=MUTED, padding=(8, 10),
        bordercolor=SURFACE, relief="flat", anchor="w", font=FONT)
    style.map("Nav.TButton",
        background=[("active", SURFACE2)],
        foreground=[("active", TEXT)])

    style.configure("NavActive.TButton", background=SURFACE2, foreground=ACCENT,
        padding=(8, 10), bordercolor=ACCENT, relief="flat", anchor="w", font=FONT_BOLD)

    style.configure("TEntry", fieldbackground=SURFACE2, foreground=TEXT,
        bordercolor=BORDER, insertcolor=TEXT, padding=(6, 5))
    style.map("TEntry", bordercolor=[("focus", ACCENT)])

    style.configure("TCombobox", fieldbackground=SURFACE2, foreground=TEXT,
        selectbackground=SURFACE2, selectforeground=TEXT, bordercolor=BORDER)
    style.map("TCombobox",
        fieldbackground=[("readonly", SURFACE2)],
        bordercolor=[("focus", ACCENT)])

    style.configure("Treeview",
        background=SURFACE, foreground=TEXT, fieldbackground=SURFACE,
        bordercolor=BORDER, rowheight=28, font=FONT)
    style.configure("Treeview.Heading",
        background=SURFACE2, foreground=MUTED, relief="flat",
        bordercolor=BORDER, font=("Segoe UI", 9, "bold"))
    style.map("Treeview",
        background=[("selected", ACCENT)],
        foreground=[("selected", WHITE)])
    style.map("Treeview.Heading",
        background=[("active", BORDER)])

    style.configure("TScrollbar", background=SURFACE2, troughcolor=SURFACE,
        bordercolor=BORDER, arrowcolor=MUTED)
    style.map("TScrollbar", background=[("active", BORDER)])

    style.configure("TLabelframe", background=SURFACE, bordercolor=BORDER, relief="solid")
    style.configure("TLabelframe.Label", background=SURFACE, foreground=MUTED, font=FONT_SM)

    style.configure("TNotebook", background=BG, bordercolor=BORDER, tabmargins=[0, 0, 0, 0])
    style.configure("TNotebook.Tab", background=SURFACE, foreground=MUTED, padding=(14, 8),
        bordercolor=BORDER, font=FONT)
    style.map("TNotebook.Tab",
        background=[("selected", SURFACE2)],
        foreground=[("selected", ACCENT)])

    style.configure("TSeparator", background=BORDER)

    style.configure("TCheckbutton", background=SURFACE, foreground=TEXT)
    style.map("TCheckbutton", background=[("active", SURFACE)])

    style.configure("TRadiobutton", background=SURFACE, foreground=TEXT)
    style.map("TRadiobutton", background=[("active", SURFACE)])

    return style
