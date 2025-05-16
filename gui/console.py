import tkinter as tk
from tkinter import ttk
import queue                                           
class ConsolePanel(tk.Frame):
    """
    Panel for displaying script output and handling stdin requests.
    """
    def __init__(self, master, app_ref=None):                                 
        super().__init__(master)
        self.app_ref = app_ref                                                
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.scrollbar = ttk.Scrollbar(self, orient='vertical')
        self.text = tk.Text(
            self,
            bg='black',
            fg='lightgrey',
            insertbackground='white',                      
            wrap='word',
            yscrollcommand=self.scrollbar.set,
            undo=False,
            state='disabled',                 
        )
        self.scrollbar.config(command=self.text.yview)
        self.text.grid(row=0, column=0, sticky='nsew')
        self.scrollbar.grid(row=0, column=1, sticky='ns')
        self.context_menu = tk.Menu(self.text, tearoff=0)
        self.context_menu.add_command(label="Copy", accelerator="Ctrl+C",
                                       command=self._copy_selection)
        self.context_menu.add_command(label="Select All", accelerator="Ctrl+A",
                                       command=self._select_all)
        self.text.bind('<Button-3>', self._show_context_menu)
        self.text.bind('<Control-a>', self._select_all)                  
        self.text.bind('<Control-c>', self._copy_selection)              
    def _show_context_menu(self, event):
        try:
             has_selection = bool(self.text.tag_ranges(tk.SEL))
             self.context_menu.entryconfigure("Copy", state=tk.NORMAL if has_selection else tk.DISABLED)
        except tk.TclError: pass                            
        self.context_menu.tk_popup(event.x_root, event.y_root)
    def _copy_selection(self, event=None):
        if self.text.tag_ranges(tk.SEL):
             self.text.event_generate("<<Copy>>")
        return "break"                                          
    def _select_all(self, event=None):
        self.text.tag_add(tk.SEL, "1.0", tk.END)
        self.text.mark_set(tk.INSERT, "1.0")
        self.text.see(tk.INSERT)
        return "break"                          
    def write(self, msg: str):
        """Appends output message to the console."""
        if not self.winfo_exists(): return
        try:
            self.text.config(state='normal')
            self.text.insert(tk.END, msg)
            self.text.see(tk.END)
            self.text.config(state='disabled')                              
        except tk.TclError: pass
    def clear(self):
        """Clears the console."""
        if not self.winfo_exists(): return
        try:
            self.text.config(state='normal')
            self.text.delete('1.0', tk.END)
            self.text.config(state='disabled')
        except tk.TclError: pass
    def request_input(self, prompt=""):
        pass
    def _disable_input_mode(self):
        pass
    def _on_input_keypress(self, event):
        pass
    def _on_input_return(self, event):
        pass
