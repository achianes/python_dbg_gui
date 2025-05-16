import tkinter as tk
from tkinter import ttk
import os
class StackPanel(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        ttk.Label(self, text="Call Stack", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky='w', padx=5, pady=2)
        self.tree = ttk.Treeview(self, columns=('Function', 'Location'), show='headings', selectmode='browse')
        self.tree.heading('Function', text='Function')
        self.tree.heading('Location', text='File:Line')
        self.tree.column('Function', width=150, stretch=tk.YES, anchor='w')
        self.tree.column('Location', width=200, stretch=tk.YES, anchor='w')
        self.scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        self.tree.grid(row=1, column=0, sticky='nsew')
        self.scrollbar.grid(row=1, column=1, sticky='ns')
        self.tree.tag_configure('current_frame', background='#cceeff')
        self.item_to_frame_map = {}
        self.tree.bind('<Double-1>', self.on_frame_double_click)
    def update_stack(self, simple_stack_data):
        if not self.winfo_exists(): return
        self.item_to_frame_map = {}
        try:
            self.tree.delete(*self.tree.get_children())
            if not simple_stack_data: return
            for i, (filename, lineno, func_name) in enumerate(reversed(simple_stack_data)):
                location = f"{os.path.basename(filename or '?')}:{lineno or '?'}"
                func_display = func_name or "<module>"
                item_id = f"frame_{len(simple_stack_data) - 1 - i}"
                self.tree.insert('', 'end', iid=item_id, values=(func_display, location))
                self.item_to_frame_map[item_id] = {'file': filename, 'line': lineno, 'func': func_name}
                if i == 0:
                      self.tree.selection_set(item_id)
                      self.tree.focus(item_id)
                      self.tree.item(item_id, tags=('current_frame',))
        except tk.TclError: pass
        except Exception as e:
             print(f"Error updating stack panel: {e}")
    def on_frame_double_click(self, event):
         selected_item_id = self.tree.focus()
         if not selected_item_id: return
         frame_info = self.item_to_frame_map.get(selected_item_id)
         if frame_info:
              print(f"Stack frame double-clicked: {frame_info}")
         else:
              print(f"Could not find frame info for item: {selected_item_id}")
