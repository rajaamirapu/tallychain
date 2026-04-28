"""
TallyChain -- GST Assistant Panel
Chat-style UI for querying GST information via a local Ollama LLM.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.styles import *
from ui.widgets import section_header


class GSTAssistantPanel(ttk.Frame):
    """Chat interface for GST queries powered by local Ollama LLM."""

    def __init__(self, parent, session):
        super().__init__(parent, style="Card.TFrame")
        self.session = session
        self._history = []  # conversation history for context
        self._streaming = False
        self._cancel_stream = False
        self._model = "llama3.2"
        self._build()

    def _build(self):
        # ── Header ──
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        section_header(hdr, "GST Assistant (AI)").pack(side="left")

        # Model selector and status
        right_hdr = tk.Frame(hdr, bg=SURFACE)
        right_hdr.pack(side="right")

        tk.Label(right_hdr, text="Model:", bg=SURFACE, fg=MUTED,
                 font=FONT_SMALL).pack(side="left", padx=(0, 4))
        self._model_var = tk.StringVar(value=self._model)
        self._model_combo = ttk.Combobox(right_hdr, textvariable=self._model_var,
                                         width=18, state="readonly")
        self._model_combo.pack(side="left", padx=(0, 10))
        self._model_combo.bind("<<ComboboxSelected>>", self._on_model_change)

        self._status_label = tk.Label(right_hdr, text="", bg=SURFACE,
                                      fg=MUTED, font=FONT_SMALL)
        self._status_label.pack(side="left", padx=(0, 10))

        ttk.Button(right_hdr, text="Check Connection",
                   command=self._check_connection).pack(side="left")

        # ── Quick queries ──
        quick_frame = tk.Frame(self, bg=SURFACE)
        quick_frame.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(quick_frame, text="Quick:", bg=SURFACE, fg=MUTED,
                 font=FONT_SMALL).pack(side="left", padx=(0, 6))

        from modules.gst_assistant import QUICK_QUERIES
        for label, query in QUICK_QUERIES:
            btn = tk.Button(
                quick_frame, text=label,
                bg=SURFACE2, fg=ACCENT, relief="flat",
                font=FONT_SMALL, cursor="hand2", padx=8, pady=2,
                activebackground=ACCENT, activeforeground="white",
                command=lambda q=query, l=label: self._send_quick(l, q),
            )
            btn.pack(side="left", padx=(0, 6))

        # ── Chat display ──
        chat_container = tk.Frame(self, bg=SURFACE2)
        chat_container.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        self._chat_text = tk.Text(
            chat_container, bg=SURFACE2, fg=TEXT,
            font=FONT_MONO, relief="flat", bd=0,
            padx=12, pady=12, wrap="word",
            state="disabled", cursor="arrow",
        )
        vsb = ttk.Scrollbar(chat_container, command=self._chat_text.yview)
        self._chat_text.configure(yscrollcommand=vsb.set)
        self._chat_text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Tags for styling
        self._chat_text.tag_configure("user", foreground=ACCENT,
                                      font=(FONT_MONO[0], FONT_MONO[1], "bold"))
        self._chat_text.tag_configure("assistant", foreground=TEXT)
        self._chat_text.tag_configure("system", foreground=MUTED,
                                      font=FONT_SMALL)
        self._chat_text.tag_configure("error", foreground=DANGER)

        # Welcome message
        self._append_system(
            "Welcome to GST Assistant! Ask any GST-related question or "
            "use the quick query buttons above.\n"
            "Powered by Ollama (local LLM) -- your data stays on your machine.\n"
            "Make sure Ollama is running: ollama serve\n"
        )

        # ── Input area ──
        input_frame = tk.Frame(self, bg=SURFACE)
        input_frame.pack(fill="x", padx=20, pady=(0, 16))

        self._input_text = tk.Text(
            input_frame, height=3, bg=SURFACE2, fg=TEXT,
            font=FONT_BODY, insertbackground=TEXT,
            relief="flat", bd=0, padx=10, pady=8, wrap="word",
        )
        self._input_text.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._input_text.bind("<Return>", self._on_enter)
        self._input_text.bind("<Shift-Return>", lambda e: None)  # allow newlines

        btn_frame = tk.Frame(input_frame, bg=SURFACE)
        btn_frame.pack(side="right", fill="y")

        self._send_btn = tk.Button(
            btn_frame, text="Send", bg=ACCENT, fg="white",
            font=("Segoe UI", 11, "bold"), relief="flat",
            cursor="hand2", padx=16, pady=8,
            activebackground=ACCENT_DARK, activeforeground="white",
            command=self._send_message,
        )
        self._send_btn.pack(side="top", pady=(0, 4))

        tk.Button(
            btn_frame, text="Clear Chat", bg=SURFACE2, fg=MUTED,
            font=FONT_SMALL, relief="flat", cursor="hand2",
            padx=10, pady=4, command=self._clear_chat,
        ).pack(side="top")

        # Initial connection check
        self.after(500, self._check_connection)

    def _on_enter(self, event):
        if not event.state & 0x1:  # not Shift
            self._send_message()
            return "break"
        return None

    def _on_model_change(self, event=None):
        self._model = self._model_var.get()

    def _check_connection(self):
        """Check Ollama connectivity in a background thread to avoid blocking the UI."""
        self._status_label.config(text="Checking...", fg=MUTED)

        def _worker():
            from modules.gst_assistant import check_ollama
            result = check_ollama()
            self.after(0, self._update_connection_status, result)

        threading.Thread(target=_worker, daemon=True).start()

    def _update_connection_status(self, result):
        """Update UI with connection check results (runs on main thread)."""
        if result["status"] == "ok":
            models = result["models"]
            self._model_combo["values"] = models
            if models and self._model_var.get() not in models:
                self._model_var.set(models[0])
                self._model = models[0]
            self._status_label.config(
                text=f"Connected ({len(models)} model{'s' if len(models) != 1 else ''})",
                fg=SUCCESS,
            )
        else:
            self._model_combo["values"] = []
            self._status_label.config(text="Disconnected", fg=DANGER)
            self._append_system(
                f"[Connection] {result.get('message', 'Cannot reach Ollama')}\n"
            )

    def _send_quick(self, label, query):
        """Send a pre-defined quick query."""
        if self._streaming:
            return
        self._input_text.delete("1.0", "end")
        self._append_user(label)
        self._stream_response(query)

    def _send_message(self):
        """Send user's typed message."""
        if self._streaming:
            return
        text = self._input_text.get("1.0", "end").strip()
        if not text:
            return
        self._input_text.delete("1.0", "end")
        self._append_user(text)
        self._stream_response(text)

    def _stream_response(self, prompt):
        """Run the LLM query in a background thread and stream tokens."""
        self._streaming = True
        self._cancel_stream = False
        self._send_btn.config(state="disabled", text="...")

        self._history.append({"role": "user", "content": prompt})
        history_snapshot = list(self._history[:-1])
        self._append_text("\nAssistant:\n", "system")

        def _worker():
            from modules.gst_assistant import query_stream
            full_response = []
            try:
                for token in query_stream(prompt, self._model, history_snapshot):
                    if self._cancel_stream:
                        break
                    full_response.append(token)
                    self.after(0, self._append_text, token, "assistant")
            except Exception as e:
                if not self._cancel_stream:
                    self.after(0, self._append_text, f"\n[Error] {e}\n", "error")
            finally:
                response_text = "".join(full_response)
                self.after(0, self._finish_worker, response_text)

        threading.Thread(target=_worker, daemon=True).start()

    def _finish_worker(self, response_text):
        """Handle history updates on the main thread after streaming ends."""
        if not self._cancel_stream:
            self._history.append({"role": "assistant", "content": response_text})
            if len(self._history) > 20:
                self._history = self._history[-20:]
        self._finish_stream()

    def _finish_stream(self):
        self._append_text("\n\n", "assistant")
        self._streaming = False
        self._send_btn.config(state="normal", text="Send")
        self._chat_text.see("end")

    def _append_user(self, text):
        self._append_text(f"\nYou: {text}\n", "user")

    def _append_system(self, text):
        self._append_text(text, "system")

    def _append_text(self, text, tag):
        self._chat_text.config(state="normal")
        self._chat_text.insert("end", text, tag)
        self._chat_text.config(state="disabled")
        self._chat_text.see("end")

    def _clear_chat(self):
        if self._streaming:
            self._cancel_stream = True
        self._history.clear()
        self._chat_text.config(state="normal")
        self._chat_text.delete("1.0", "end")
        self._chat_text.config(state="disabled")
        self._append_system(
            "Chat cleared. Ask a new GST question to get started.\n"
        )

    def refresh(self):
        pass
