import tkinter as tk
from tkinter import ttk
import json
class VariablesPanel(tk.Frame):
    """
    Panel to display variables (e.g., Locals, Globals) using a Treeview.
    """
    def __init__(self, master):
        super().__init__(master)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        ttk.Label(self, text="Variables Inspector", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky='w', padx=5, pady=(5, 2))
        self.tree = ttk.Treeview(self, columns=('Value', 'Type'), show='tree headings')
        self.tree.heading('#0', text='Variable')                                    
        self.tree.heading('Value', text='Value')
        self.tree.heading('Type', text='Type')
        self.tree.column('#0', width=150, stretch=tk.YES, anchor='w')
        self.tree.column('Value', width=200, stretch=tk.YES, anchor='w')
        self.tree.column('Type', width=100, stretch=tk.NO, anchor='w')
        self.scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        self.tree.grid(row=1, column=0, sticky='nsew')
        self.scrollbar.grid(row=1, column=1, sticky='ns')
        self._create_base_nodes()
    def _create_base_nodes(self):
         """Creates the top-level 'Locals' and 'Globals' nodes."""
         if self.tree.exists('locals'): self.tree.delete('locals')
         self.tree.insert('', 'end', iid='locals', text='Locals', open=True)
         if self.tree.exists('globals'): self.tree.delete('globals')
         self.tree.insert('', 'end', iid='globals', text='Globals', open=False)                  
    def _safe_repr(self, value, max_len=100):
        """Safely get repr() of a value, handling potential errors and length limits."""
        try:
            s = repr(value)
        except Exception:
            try: s = str(value)
            except Exception as e: return f"<Error getting repr: {e}>"
        if isinstance(s, str) and len(s) > max_len: s = s[:max_len] + '...'
        return s
    def _clear_children(self, node_id):
        """Removes all children of a given node."""
        if self.tree.exists(node_id):
             for child in self.tree.get_children(node_id):
                  try:                                               
                       self.tree.delete(child)
                  except tk.TclError: pass
    def _insert_variable(self, parent_node_id, name, value_data):
        """
        Helper to insert a variable into the tree.
        value_data can be the actual value (for basic types) or its safe representation (for complex types).
        """
        value_repr = self._safe_repr(value_data)                                                         
        var_type = type(value_data).__name__
        item_id = f"{parent_node_id}_{name}"
        is_expandable = isinstance(value_data, (dict, list, tuple, set)) and value_data
        try:
             if self.tree.exists(item_id):
                  self.tree.item(item_id, text=str(name), values=(value_repr, var_type))
                  self._clear_children(item_id)
                  new_item_id = item_id
             else:
                  new_item_id = self.tree.insert(parent_node_id, 'end', iid=item_id,
                                                 text=str(name),
                                                 values=(value_repr, var_type),
                                                 open=False)
        except tk.TclError as e:
             print(f"Error inserting/updating tree item {item_id}: {e}")
             return                                                 
        if is_expandable:
             self._populate_children(new_item_id, value_data)
    def _populate_children(self, parent_id, data):
        """Recursively populates children for dicts, lists, tuples, sets."""
        try:
            if isinstance(data, dict):
                for key, value in sorted(data.items(), key=lambda item: str(item[0])):
                     self._insert_variable(parent_id, str(key), value)                                                   
            elif isinstance(data, (list, tuple)):
                 for i, value in enumerate(data):
                     self._insert_variable(parent_id, str(i), value)
            elif isinstance(data, set):
                 try:
                      sorted_items = sorted(list(data), key=repr)
                 except TypeError:
                      try: sorted_items = list(data)
                      except TypeError: sorted_items = []                                         
                 for i, value in enumerate(sorted_items):
                      self._insert_variable(parent_id, str(i), value)
            elif isinstance(data, str) and data.endswith("<Max depth>") or data == "<Recursion detected>":
                 pass
        except Exception as e:
             try: self.tree.insert(parent_id, 'end', text='<Error populating children>', values=(str(e), 'Error'))
             except tk.TclError: pass
    def update_variables(self, local_vars, global_vars):
        """Clears and repopulates the treeview with variable data received from backend."""
        if not self.winfo_exists(): return
        try:
             self._create_base_nodes()
             self._clear_children('locals')
             self._clear_children('globals')
             if isinstance(local_vars, dict):
                  for name, value_data in sorted(local_vars.items(), key=lambda item: item[0]):
                      self._insert_variable('locals', name, value_data)
             if isinstance(global_vars, dict):
                  for name, value_data in sorted(global_vars.items(), key=lambda item: item[0]):
                       self._insert_variable('globals', name, value_data)
        except tk.TclError: pass
        except Exception as e: print(f"Error updating variables panel: {e}")
