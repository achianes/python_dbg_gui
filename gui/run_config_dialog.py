import os
import tkinter as tk
from tkinter import ttk, filedialog

class RunConfigDialog(tk.Toplevel):
    """
    Retro-compatibile:
      - accetta sia parametri posizionali che keyword (current_args, current_cwd, args, cwd, initial_args, initial_cwd)
      - espone result_args e result_cwd (None se annullato)

    Uso tipico (vecchio):
      RunConfigDialog(root, script_path, current_args="--foo 1")

    Uso tipico (nuovo):
      RunConfigDialog(root, script_path, current_args="--foo 1", current_cwd="D:/proj")
    """

    def __init__(self, parent, script_path, *positional, **kwargs):
        super().__init__(parent)

        self.parent = parent
        self.script_path = script_path

        # --- Retro-compat parsing ---
        # positional: (current_args?, current_cwd?)
        current_args = ""
        current_cwd = ""

        if len(positional) >= 1:
            current_args = positional[0] if positional[0] is not None else ""
        if len(positional) >= 2:
            current_cwd = positional[1] if positional[1] is not None else ""

        # keyword overrides / aliases
        if "current_args" in kwargs and kwargs["current_args"] is not None:
            current_args = kwargs["current_args"]
        if "args" in kwargs and kwargs["args"] is not None:
            current_args = kwargs["args"]
        if "initial_args" in kwargs and kwargs["initial_args"] is not None:
            current_args = kwargs["initial_args"]

        if "current_cwd" in kwargs and kwargs["current_cwd"] is not None:
            current_cwd = kwargs["current_cwd"]
        if "cwd" in kwargs and kwargs["cwd"] is not None:
            current_cwd = kwargs["cwd"]
        if "initial_cwd" in kwargs and kwargs["initial_cwd"] is not None:
            current_cwd = kwargs["initial_cwd"]

        # Default cwd fallback (non invasivo)
        if not current_cwd:
            try:
                current_cwd = os.path.dirname(os.path.abspath(script_path))
            except Exception:
                current_cwd = ""

        # Results
        self.result_args = None
        self.result_cwd = None

        self.title("Run Configuration")
        self.resizable(False, False)

        # Make modal and topmost
        try:
            self.transient(parent)
        except Exception:
            pass
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass

        # --- UI ---
        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        # Script label (basename)
        script_name = os.path.basename(script_path) if script_path else "Script"
        ttk.Label(frm, text=script_name, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        # Args
        ttk.Label(frm, text="Arguments:").grid(row=1, column=0, sticky="w")
        self._args_var = tk.StringVar(value=str(current_args) if current_args is not None else "")
        args_entry = ttk.Entry(frm, textvariable=self._args_var, width=60)
        args_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(8, 0))

        # CWD
        ttk.Label(frm, text="Working dir (cwd):").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self._cwd_var = tk.StringVar(value=str(current_cwd) if current_cwd is not None else "")
        cwd_entry = ttk.Entry(frm, textvariable=self._cwd_var, width=50)
        cwd_entry.grid(row=2, column=1, sticky="ew", padx=(8, 8), pady=(10, 0))

        browse_btn = ttk.Button(frm, text="Browse...", command=self._browse_cwd)
        browse_btn.grid(row=2, column=2, sticky="e", pady=(10, 0))

        # Buttons
        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, columnspan=3, sticky="e", pady=(14, 0))

        ok_btn = ttk.Button(btns, text="OK", command=self._on_ok)
        ok_btn.grid(row=0, column=0, padx=(0, 8))
        cancel_btn = ttk.Button(btns, text="Cancel", command=self._on_cancel)
        cancel_btn.grid(row=0, column=1)

        # Key bindings
        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())

        # Layout config
        frm.columnconfigure(1, weight=1)

        # Center relative to parent and show
        self.update_idletasks()
        self._center_over_parent()
        try:
            self.grab_set()
        except Exception:
            pass

        args_entry.focus_set()
        self.wait_window(self)

    def _browse_cwd(self):
        initial = self._cwd_var.get().strip()
        if not initial:
            try:
                initial = os.path.dirname(os.path.abspath(self.script_path))
            except Exception:
                initial = ""
        folder = filedialog.askdirectory(parent=self, initialdir=initial or None, title="Select working directory")
        if folder:
            self._cwd_var.set(folder)

    def _on_ok(self):
        self.result_args = self._args_var.get()
        self.result_cwd = self._cwd_var.get()
        self.destroy()

    def _on_cancel(self):
        self.result_args = None
        self.result_cwd = None
        self.destroy()

    def _center_over_parent(self):
        try:
            self.update_idletasks()
            pw = self.parent.winfo_width()
            ph = self.parent.winfo_height()
            px = self.parent.winfo_rootx()
            py = self.parent.winfo_rooty()

            w = self.winfo_width()
            h = self.winfo_height()

            x = px + (pw - w) // 2
            y = py + (ph - h) // 2

            # keep on-screen
            if x < 0: x = 0
            if y < 0: y = 0

            self.geometry(f"+{x}+{y}")
        except Exception:
            # Fallback: let WM decide
            pass
