import tkinter as tk
from tkinter import ttk, messagebox
import re
class SearchReplaceDialog:
    def __init__(self, parent, app):
        self.app = app                            
        self.top = tk.Toplevel(parent)
        self.top.title("Find and Replace")
        self.top.transient(parent)                                         
        self.top.attributes("-topmost", True)                                     
        self.top.lift()                                                   
        self.matches = []                                                                     
        self.current_match_index = -1
        self.tag_name = "search_highlight"
        self.tag_current = "search_current"
        self.create_widgets()
        self.center_window()
        self.top.bind("<Destroy>", lambda _: self.clear_highlights())
    def center_window(self):
        w=300
        h=200
        parent = self.top.master
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.top.geometry(f"{w}x{h}+{x}+{y}")
    def create_widgets(self):
        frame = ttk.Frame(self.top, padding=10)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text="Find:").grid(row=0, column=0, sticky='w')
        self.find_entry = ttk.Entry(frame, width=40)
        self.find_entry.grid(row=0, column=1, padx=5, pady=5)
        self.match_case = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Match case", variable=self.match_case).grid(
            row=1, column=0, columnspan=2, sticky='w')
        self.whole_word = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Whole word", variable=self.whole_word).grid(
            row=2, column=0, columnspan=2, sticky='w')
        self.search_current = tk.BooleanVar(value=True)
        ttk.Radiobutton(frame, text="Search in current tab", variable=self.search_current, value=True).grid(
            row=3, column=0, columnspan=2, sticky='w')
        ttk.Radiobutton(frame, text="Search in all open tabs", variable=self.search_current, value=False).grid(
            row=4, column=0, columnspan=2, sticky='w')
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Find Next", command=self.find_next).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Find All", command=self.find_all).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Cancel", command=self.top.destroy).pack(side='left', padx=2)
    def find_all(self):
        query = self.find_entry.get().strip()
        if not query:
            return
        self.clear_highlights()
        self._gather_matches(query)
        if not self.matches:
            messagebox.showinfo("Not found", "Nessuna occorrenza trovata.")
            return
        editors_taggati = set()
        for editor, start, end in self.matches:
            editor.text.tag_add(self.tag_name, start, end)
            editors_taggati.add(editor)
        for editor in editors_taggati:
            editor.text.tag_configure(self.tag_name, background="#aaccee")
    def find_next(self):
        query = self.find_entry.get().strip()
        if not query:
            return
        if not self.matches:
            self._gather_matches(query)
            if not self.matches:
                messagebox.showinfo("Not found", "Nessuna occorrenza trovata.")
                return
        self.current_match_index = (self.current_match_index + 1) % len(self.matches)
        self.clear_highlights()
        self.highlight_current_match()
    def _gather_matches(self, query):
        match_case = self.match_case.get()
        whole_word = self.whole_word.get()
        flags = 0 if match_case else re.IGNORECASE
        pat = rf"\b{re.escape(query)}\b" if whole_word else re.escape(query)
        self.matches.clear()
        self.current_match_index = -1
        for _, editor in self.app.open_tabs.items():
            text = editor.text.get("1.0", tk.END)
            for m in re.finditer(pat, text, flags):
                start = f"1.0+{m.start()}c"
                end   = f"1.0+{m.end()}c"
                self.matches.append((editor, start, end))
    def highlight_current_match(self):
        editor, start, end = self.matches[self.current_match_index]
        editor.text.tag_add(self.tag_current, start, end)
        editor.text.tag_configure(self.tag_current, background="#aaccee")
        editor.text.mark_set("insert", start)
        editor.text.see(start)
    def clear_highlights(self):
        for _, editor in self.app.open_tabs.items():
            editor.text.tag_remove(self.tag_name, "1.0", tk.END)
            editor.text.tag_remove(self.tag_current, "1.0", tk.END)
