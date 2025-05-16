import os
import tkinter as tk
from tkinter import ttk, messagebox
class RunConfigDialog(tk.Toplevel):
    def __init__(self, parent, script_path, current_args=""):
        super().__init__(parent)
        self.title(f"Run Configuration: {os.path.basename(script_path)}")
        self.transient(parent)
        self.attributes("-topmost", True)
        self.script_path = script_path
        self.result_args = None                                        
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(main_frame, text="Arguments:").grid(row=0, column=0, padx=(0,5), pady=5, sticky="w")
        self.args_entry = ttk.Entry(main_frame, width=50)
        self.args_entry.insert(0, current_args)
        self.args_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(10,0))                     
        ttk.Button(btn_frame, text="OK", command=self.on_ok).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.on_cancel).pack(side="left", padx=5)
        main_frame.grid_columnconfigure(1, weight=1)                                   
        self.args_entry.focus_set()
        self.bind("<Return>", lambda e: self.on_ok())
        self.bind("<Escape>", lambda e: self.on_cancel())
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)                            
        self.center_window()
        self.grab_set()                                          
        self.wait_window(self)
    def center_window(self):
        self.update_idletasks()                                             
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 10: width = 450                    
        if height <= 10: height = 120                    
        parent_window = self.master
        parent_x = parent_window.winfo_x()
        parent_y = parent_window.winfo_y()
        parent_width = parent_window.winfo_width()
        parent_height = parent_window.winfo_height()
        x = parent_x + (parent_width // 2) - (width // 2)
        y = parent_y + (parent_height // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    def on_ok(self):
        self.result_args = self.args_entry.get()
        self.destroy()
    def on_cancel(self):
        self.result_args = None                                       
        self.destroy()
