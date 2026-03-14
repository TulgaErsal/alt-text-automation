#!/usr/bin/env python3
"""
gui.py  –  CustomTkinter front-end for generate_alt_text.py

Usage:
    python gui.py
"""

import io
import sys
import threading
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

# ── import the backend ────────────────────────────────────────────────────────
try:
    from generate_alt_text import (
        PURPOSE_OPTIONS,
        INCLUDE_OPTIONS,
        TONE_OPTIONS,
        process_presentation,
        _LOCAL_GECKODRIVER,
    )
except ImportError as exc:
    import tkinter as _tk
    _tk.Tk().withdraw()
    messagebox.showerror("Import error", str(exc))
    sys.exit(1)

# ── appearance ────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

DEFAULT_URL = "https://aihelper.engin.umich.edu/alt-text-generator"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Alt Text Automation")
        self.geometry("820x760")
        self.minsize(640, 600)
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(6, weight=1)   # log area stretches

        PAD = {"padx": 16, "pady": (8, 0)}

        # ── Files section ─────────────────────────────────────────────────────
        files_frame = ctk.CTkFrame(self)
        files_frame.grid(row=0, column=0, sticky="ew", **PAD)
        files_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            files_frame, text="Files", font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 4))

        # Input PPTX
        ctk.CTkLabel(files_frame, text="Input PPTX:").grid(
            row=1, column=0, sticky="w", padx=12, pady=4
        )
        self.input_var = ctk.StringVar()
        ctk.CTkEntry(
            files_frame, textvariable=self.input_var,
            placeholder_text="Select a .pptx file…"
        ).grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        ctk.CTkButton(
            files_frame, text="Browse…", width=90, command=self._browse_input
        ).grid(row=1, column=2, padx=(0, 12), pady=4)

        # Output PPTX
        ctk.CTkLabel(files_frame, text="Output PPTX:").grid(
            row=2, column=0, sticky="w", padx=12, pady=4
        )
        self.output_var = ctk.StringVar()
        ctk.CTkEntry(
            files_frame, textvariable=self.output_var,
            placeholder_text="(auto: <name>_alt_text.pptx)"
        ).grid(row=2, column=1, sticky="ew", padx=8, pady=4)
        ctk.CTkButton(
            files_frame, text="Browse…", width=90, command=self._browse_output
        ).grid(row=2, column=2, padx=(0, 12), pady=4)

        # Tool URL
        ctk.CTkLabel(files_frame, text="Tool URL:").grid(
            row=3, column=0, sticky="w", padx=12, pady=(4, 12)
        )
        self.url_var = ctk.StringVar(value=DEFAULT_URL)
        ctk.CTkEntry(files_frame, textvariable=self.url_var).grid(
            row=3, column=1, columnspan=2, sticky="ew", padx=(8, 12), pady=(4, 12)
        )

        # ── Options section ───────────────────────────────────────────────────
        opts_frame = ctk.CTkFrame(self)
        opts_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(8, 0))
        opts_frame.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(
            opts_frame, text="Options", font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=12, pady=(10, 4))

        # Version
        ctk.CTkLabel(opts_frame, text="Alt text version:").grid(
            row=1, column=0, sticky="w", padx=12, pady=4
        )
        self.version_var = ctk.StringVar(value="long")
        ctk.CTkSegmentedButton(
            opts_frame, values=["short", "medium", "long"],
            variable=self.version_var
        ).grid(row=1, column=1, sticky="w", padx=8, pady=4)

        # Browser
        ctk.CTkLabel(opts_frame, text="Browser:").grid(
            row=1, column=2, sticky="w", padx=(16, 4), pady=4
        )
        self.browser_var = ctk.StringVar(value="auto")
        ctk.CTkOptionMenu(
            opts_frame, values=["auto", "firefox", "chrome", "edge"],
            variable=self.browser_var, width=120
        ).grid(row=1, column=3, sticky="w", padx=(0, 12), pady=4)

        # Purpose
        ctk.CTkLabel(opts_frame, text="Purpose:").grid(
            row=2, column=0, sticky="w", padx=12, pady=4
        )
        self.purpose_var = ctk.StringVar(value="(none)")
        ctk.CTkOptionMenu(
            opts_frame,
            values=["(none)"] + list(PURPOSE_OPTIONS),
            variable=self.purpose_var,
            width=210,
            dynamic_resizing=False,
        ).grid(row=2, column=1, sticky="w", padx=8, pady=4)

        # Tone
        ctk.CTkLabel(opts_frame, text="Tone:").grid(
            row=2, column=2, sticky="w", padx=(16, 4), pady=4
        )
        self.tone_var = ctk.StringVar(value="(none)")
        ctk.CTkOptionMenu(
            opts_frame,
            values=["(none)"] + list(TONE_OPTIONS),
            variable=self.tone_var,
            width=150,
            dynamic_resizing=False,
        ).grid(row=2, column=3, sticky="w", padx=(0, 12), pady=4)

        # Include checkboxes
        ctk.CTkLabel(opts_frame, text="Include:").grid(
            row=3, column=0, sticky="w", padx=12, pady=(4, 12)
        )
        self.include_data_var = ctk.BooleanVar(value=False)
        self.include_captions_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            opts_frame, text="Data Values", variable=self.include_data_var
        ).grid(row=3, column=1, sticky="w", padx=8, pady=(4, 12))
        ctk.CTkCheckBox(
            opts_frame, text="Captions / Labels", variable=self.include_captions_var
        ).grid(row=3, column=2, columnspan=2, sticky="w", padx=(16, 12), pady=(4, 12))

        # ── Advanced section ──────────────────────────────────────────────────
        adv_frame = ctk.CTkFrame(self)
        adv_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 0))
        adv_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            adv_frame, text="Advanced (for Firefox only)", font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 4))

        ctk.CTkLabel(adv_frame, text="Geckodriver path:").grid(
            row=1, column=0, sticky="w", padx=12, pady=(4, 12)
        )
        self.gecko_var = ctk.StringVar()
        ctk.CTkEntry(
            adv_frame, textvariable=self.gecko_var,
            placeholder_text="(auto-detect)"
        ).grid(row=1, column=1, sticky="ew", padx=8, pady=(4, 12))
        ctk.CTkButton(
            adv_frame, text="Browse…", width=90, command=self._browse_gecko
        ).grid(row=1, column=2, padx=(0, 12), pady=(4, 12))

        # ── Run / Stop buttons ────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, padx=16, pady=12, sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=0)

        self.run_btn = ctk.CTkButton(
            btn_frame, text="Run", height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._run,
        )
        self.run_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.stop_btn = ctk.CTkButton(
            btn_frame, text="Stop", height=42, width=100,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#c0392b", hover_color="#922b21",
            state="disabled",
            command=self._stop,
        )
        self.stop_btn.grid(row=0, column=1, sticky="e")

        # ── Progress bar ──────────────────────────────────────────────────────
        self.progress = ctk.CTkProgressBar(self, mode="indeterminate")
        self.progress.grid(row=4, column=0, padx=16, pady=(0, 4), sticky="ew")
        self.progress.set(0)

        # ── Log section ───────────────────────────────────────────────────────
        log_header = ctk.CTkFrame(self, fg_color="transparent")
        log_header.grid(row=5, column=0, sticky="ew", padx=16, pady=(4, 0))
        log_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_header, text="Log", font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            log_header, text="Clear", width=70, height=26,
            command=self._clear_log,
        ).grid(row=0, column=1, sticky="e")

        self.log_box = ctk.CTkTextbox(self, state="disabled", wrap="word")
        self.log_box.grid(row=6, column=0, sticky="nsew", padx=16, pady=(4, 16))

    # ── file dialogs ──────────────────────────────────────────────────────────

    def _browse_input(self):
        path = filedialog.askopenfilename(
            filetypes=[("PowerPoint files", "*.pptx"), ("All files", "*.*")]
        )
        if path:
            self.input_var.set(path)
            # Auto-fill output only if still blank
            if not self.output_var.get():
                p = Path(path)
                self.output_var.set(str(p.with_stem(p.stem + "_alt_text")))

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".pptx",
            filetypes=[("PowerPoint files", "*.pptx"), ("All files", "*.*")],
        )
        if path:
            self.output_var.set(path)

    def _browse_gecko(self):
        path = filedialog.askopenfilename(
            filetypes=[("Executables", "*.exe geckodriver"), ("All files", "*.*")]
        )
        if path:
            self.gecko_var.set(path)

    def _stop(self):
        self._stop_event.set()
        self.stop_btn.configure(state="disabled", text="Stopping…")

    # ── logging ───────────────────────────────────────────────────────────────

    def _log(self, text: str):
        """Append text to the log box. Must be called from the main thread."""
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    # ── run orchestration ─────────────────────────────────────────────────────

    def _run(self):
        # Validate input
        input_str = self.input_var.get().strip()
        if not input_str:
            messagebox.showwarning("Missing input", "Please select an input PPTX file.")
            return
        input_path = Path(input_str)
        if not input_path.exists():
            messagebox.showerror("File not found", f"File not found:\n{input_path}")
            return

        output_str = self.output_var.get().strip()
        output_path = (
            Path(output_str)
            if output_str
            else input_path.with_stem(input_path.stem + "_alt_text")
        )

        url     = self.url_var.get().strip() or DEFAULT_URL
        version = self.version_var.get()
        browser = self.browser_var.get()

        purpose = self.purpose_var.get()
        purpose = None if purpose == "(none)" else purpose

        includes = []
        if self.include_data_var.get():
            includes.append("data-values")
        if self.include_captions_var.get():
            includes.append("captions")

        tone = self.tone_var.get()
        tone = None if tone == "(none)" else tone

        gecko_str = self.gecko_var.get().strip()
        if gecko_str:
            geckodriver = Path(gecko_str)
        elif _LOCAL_GECKODRIVER.exists():
            geckodriver = _LOCAL_GECKODRIVER
        else:
            geckodriver = None

        # Clear log
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        self._stop_event = threading.Event()
        self.run_btn.configure(state="disabled", text="Running…")
        self.stop_btn.configure(state="normal")
        self.progress.start()

        threading.Thread(
            target=self._worker,
            args=(input_path, output_path, url, version, browser,
                  geckodriver, purpose, includes, tone),
            daemon=True,
        ).start()

    def _worker(self, input_path, output_path, url, version,
                browser, geckodriver, purpose, includes, tone):
        """Background thread: redirect stdout → log box, then run the backend."""

        class _GuiWriter(io.TextIOBase):
            def __init__(self_, app):
                self_._app = app

            def write(self_, text):
                if text:
                    self_._app.after(0, self_._app._log, text)
                return len(text)

            def flush(self_):
                pass

        old_stdout = sys.stdout
        sys.stdout = _GuiWriter(self)
        try:
            process_presentation(
                pptx_path=input_path,
                output_path=output_path,
                tool_url=url,
                version=version,
                browser=browser,
                geckodriver_path=geckodriver,
                purpose=purpose,
                includes=includes,
                tone=tone,
                stop_event=self._stop_event,
            )
            aborted = self._stop_event.is_set()
            self.after(0, self._on_done, None, aborted)
        except Exception as exc:
            self.after(0, self._on_done, str(exc), False)
        finally:
            sys.stdout = old_stdout

    def _on_done(self, error: str | None, aborted: bool = False):
        self.progress.stop()
        self.progress.set(0)
        self.run_btn.configure(state="normal", text="Run")
        self.stop_btn.configure(state="disabled", text="Stop")
        if error:
            messagebox.showerror("Error", error)
        elif aborted:
            messagebox.showwarning("Aborted", "Processing was stopped. Any completed slides have been saved.")
        else:
            messagebox.showinfo("Done", "Alt text generation complete!")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
