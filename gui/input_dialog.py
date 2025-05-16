import tkinter as tk
from tkinter import ttk
class InputDialog(tk.Toplevel):
    def __init__(self, parent, title="Input Request", prompt_text="Enter value:"):
        super().__init__(parent)
        self.transient(parent)
        self.title(title)
        self.attributes("-topmost", True)
        self.grab_set()
        self.result = None
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(expand=True, fill=tk.BOTH)
        ttk.Label(main_frame, text=prompt_text, wraplength=380).pack(pady=(0, 10))                       
        self.entry = ttk.Entry(main_frame, width=60)                  
        self.entry.pack(pady=5)
        self.entry.focus_set()
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(10, 0))
        try:
            ok_button = ttk.Button(button_frame, text="OK", command=self._on_ok, style="Accent.TButton")
        except tk.TclError: 
            ok_button = ttk.Button(button_frame, text="OK", command=self._on_ok)
        ok_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT, padx=5)
        self.entry.bind("<Return>", self._on_ok)
        self.bind("<Escape>", self._on_cancel)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.center_window()
        self.wait_window(self)
    def center_window(self):
        self.update_idletasks()
        parent_window = self.master if self.master else self.winfo_toplevel()
        parent_x = parent_window.winfo_x()
        parent_y = parent_window.winfo_y()
        parent_width = parent_window.winfo_width()
        parent_height = parent_window.winfo_height()
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()
        if dialog_width <= 1: dialog_width = max(400, self.winfo_reqwidth())                     
        if dialog_height <= 1: dialog_height = max(150, self.winfo_reqheight())
        x = parent_x + (parent_width // 2) - (dialog_width // 2)
        y = parent_y + (parent_height // 2) - (dialog_height // 2)
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        if x + dialog_width > screen_width: x = screen_width - dialog_width
        if y + dialog_height > screen_height: y = screen_height - dialog_height
        if x < 0: x = 0
        if y < 0: y = 0
        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
    def _on_ok(self, event=None):
        self.result = self.entry.get()
        self.destroy()
    def _on_cancel(self, event=None):
        self.result = None
        self.destroy()
