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
        build_driver,
        wait_for_auth,
        run_batch,
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

# Status display values
_S_LAUNCHING     = ("Launching browser…",    "gray")
_S_WAITING       = ("Waiting for sign-in…",  "orange")
_S_READY         = ("Signed in ✓",           "green")
_S_DISCONNECTED  = ("Not connected",         "gray")
_S_LOST          = ("Connection lost",       "#c0392b")
_S_TIMEOUT       = ("Sign-in timed out",     "#c0392b")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Alt Text Automation")
        self.geometry("820x800")
        self.minsize(640, 640)

        self._driver = None
        self._connecting = False
        self._stop_event = threading.Event()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Auto-connect once the event loop is running
        self.after(300, self._connect)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(7, weight=1)   # log area stretches

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

        # ── Browser status row ────────────────────────────────────────────────
        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(8, 0))
        status_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            status_frame, text="Browser:", font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=12, pady=10)

        self.status_label = ctk.CTkLabel(status_frame, text=_S_DISCONNECTED[0],
                                         text_color=_S_DISCONNECTED[1])
        self.status_label.grid(row=0, column=1, sticky="w", padx=4, pady=10)

        self.reconnect_btn = ctk.CTkButton(
            status_frame, text="Reconnect", width=110,
            command=self._connect,
        )
        self.reconnect_btn.grid(row=0, column=2, padx=(0, 12), pady=10)

        # ── Run / Stop buttons ────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, padx=16, pady=12, sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=0)

        self.run_btn = ctk.CTkButton(
            btn_frame, text="Run", height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            state="disabled",
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
        self.progress.grid(row=5, column=0, padx=16, pady=(0, 4), sticky="ew")
        self.progress.set(0)

        # ── Log section ───────────────────────────────────────────────────────
        log_header = ctk.CTkFrame(self, fg_color="transparent")
        log_header.grid(row=6, column=0, sticky="ew", padx=16, pady=(4, 0))
        log_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_header, text="Log", font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            log_header, text="Clear", width=70, height=26,
            command=self._clear_log,
        ).grid(row=0, column=1, sticky="e")

        self.log_box = ctk.CTkTextbox(self, state="disabled", wrap="word")
        self.log_box.grid(row=7, column=0, sticky="nsew", padx=16, pady=(4, 16))

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

    # ── browser connect / disconnect ──────────────────────────────────────────

    def _geckodriver_path(self) -> Path | None:
        gecko_str = self.gecko_var.get().strip()
        if gecko_str:
            return Path(gecko_str)
        if _LOCAL_GECKODRIVER.exists():
            return _LOCAL_GECKODRIVER
        return None

    def _connect(self):
        if self._connecting:
            return
        self._connecting = True

        # Close any existing browser first
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

        self._set_status(*_S_LAUNCHING)
        self.reconnect_btn.configure(state="disabled")
        self.run_btn.configure(state="disabled")

        browser    = self.browser_var.get()
        geckodriver = self._geckodriver_path()
        url        = self.url_var.get().strip() or DEFAULT_URL

        threading.Thread(
            target=self._connect_worker,
            args=(browser, geckodriver, url),
            daemon=True,
        ).start()

    def _connect_worker(self, browser, geckodriver, url):
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
            driver = build_driver(browser, geckodriver)
            self._driver = driver
            self.after(0, self._set_status, *_S_WAITING)
            wait_for_auth(driver, url, raise_on_timeout=True)
            self.after(0, self._on_connect_done, None)
        except TimeoutError as exc:
            self._driver = None
            self.after(0, self._on_connect_done, str(exc), True)
        except Exception as exc:
            self._driver = None
            self.after(0, self._on_connect_done, str(exc))
        finally:
            sys.stdout = old_stdout

    def _on_connect_done(self, error: str | None, timed_out: bool = False):
        self._connecting = False
        self.reconnect_btn.configure(state="normal")
        if error:
            status = _S_TIMEOUT if timed_out else _S_LOST
            self._set_status(*status)
        else:
            self._set_status(*_S_READY)
            self.run_btn.configure(state="normal")

    def _set_status(self, text: str, color: str):
        self.status_label.configure(text=text, text_color=color)

    # ── stop ──────────────────────────────────────────────────────────────────

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

        purpose = self.purpose_var.get()
        purpose = None if purpose == "(none)" else purpose

        includes = []
        if self.include_data_var.get():
            includes.append("data-values")
        if self.include_captions_var.get():
            includes.append("captions")

        tone = self.tone_var.get()
        tone = None if tone == "(none)" else tone

        self._stop_event = threading.Event()
        self.run_btn.configure(state="disabled", text="Running…")
        self.stop_btn.configure(state="normal")
        self.reconnect_btn.configure(state="disabled")
        self.progress.start()

        threading.Thread(
            target=self._worker,
            args=(input_path, output_path, url, version, purpose, includes, tone),
            daemon=True,
        ).start()

    def _worker(self, input_path, output_path, url, version, purpose, includes, tone):
        """Background thread: redirect stdout → log box, then run the batch."""

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
            run_batch(
                driver=self._driver,
                pptx_path=input_path,
                output_path=output_path,
                tool_url=url,
                version=version,
                purpose=purpose,
                includes=includes,
                tone=tone,
                stop_event=self._stop_event,
            )
            aborted = self._stop_event.is_set()
            self.after(0, self._on_done, None, aborted)
        except Exception as exc:
            err = str(exc)
            lost = type(exc).__name__ in ("InvalidSessionIdException", "NoSuchWindowException")
            self.after(0, self._on_done, err, False, lost)
        finally:
            sys.stdout = old_stdout

    def _on_done(self, error: str | None, aborted: bool = False, connection_lost: bool = False):
        self.progress.stop()
        self.progress.set(0)
        self.stop_btn.configure(state="disabled", text="Stop")
        self.reconnect_btn.configure(state="normal")

        if connection_lost:
            self._driver = None
            self._set_status(*_S_LOST)
            self.run_btn.configure(state="disabled", text="Run")
            messagebox.showerror(
                "Connection lost",
                "The browser session was lost.\n\nClick Reconnect to sign in again."
            )
        elif error:
            self.run_btn.configure(state="normal", text="Run")
            messagebox.showerror("Error", error)
        elif aborted:
            self.run_btn.configure(state="normal", text="Run")
            messagebox.showwarning(
                "Aborted",
                "Processing was stopped. Any completed slides have been saved."
            )
        else:
            self.run_btn.configure(state="normal", text="Run")
            messagebox.showinfo("Done", "Alt text generation complete!")

    # ── window close ──────────────────────────────────────────────────────────

    def _on_close(self):
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
        self.destroy()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
