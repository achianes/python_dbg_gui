import tkinter as tk
from tkinter import ttk

class VariablesPanel(tk.Frame):
    """Variables inspector with Locals/Globals and a Watch (pinned) group."""

    def __init__(self, master):
        super().__init__(master)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ttk.Label(self, text="Variables Inspector", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', padx=4, pady=(4,2))

        self.tree = ttk.Treeview(self, columns=("value",), show="tree headings")
        self.tree.heading("#0", text="Name")
        self.tree.heading("value", text="Value")
        self.tree.column("#0", width=170, stretch=True)
        self.tree.column("value", width=280, stretch=True)

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")

        # Root groups
        self._watch_root = self.tree.insert("", "end", text="Watch", values=("",), open=True)
        self._locals_root = self.tree.insert("", "end", text="Locals", values=("",), open=True)
        self._globals_root = self.tree.insert("", "end", text="Globals", values=("",), open=True)

        self._watch_items = {}  # expr -> item_id

        # Context menu for watch items
        self._menu = tk.Menu(self, tearoff=0)
        self._menu.add_command(label="Remove from Watch", command=self._remove_selected_watch)
        self.tree.bind("<Button-3>", self._on_right_click)

    def _on_right_click(self, event):
        try:
            item = self.tree.identify_row(event.y)
            if not item:
                return
            # show only for watch subtree
            if self._is_under_watch(item):
                self.tree.selection_set(item)
                self._menu.tk_popup(event.x_root, event.y_root)
        except Exception:
            pass

    def _is_under_watch(self, item_id):
        try:
            parent = self.tree.parent(item_id)
            while parent:
                if parent == self._watch_root:
                    return True
                parent = self.tree.parent(parent)
        except Exception:
            return False
        return False

    def _remove_selected_watch(self):
        try:
            sel = self.tree.selection()
            if not sel:
                return
            item = sel[0]
            # find expr by reverse map
            expr = None
            for k,v in list(self._watch_items.items()):
                if v == item:
                    expr = k
                    break
            if expr:
                self.remove_watch(expr)
        except Exception:
            pass

    def _clear_group(self, root_id):
        try:
            for child in self.tree.get_children(root_id):
                self.tree.delete(child)
        except Exception:
            pass

    def update_variables(self, locals_dict, globals_dict):
        """Update Locals/Globals groups."""
        self._clear_group(self._locals_root)
        self._clear_group(self._globals_root)
        self._populate_dict(self._locals_root, locals_dict or {})
        self._populate_dict(self._globals_root, globals_dict or {})

    def _populate_dict(self, root, data):
        try:
            for k in sorted(data.keys(), key=str):
                v = data[k]
                self._insert_value(root, str(k), v)
        except Exception:
            # fallback non-sort
            try:
                for k,v in (data or {}).items():
                    self._insert_value(root, str(k), v)
            except Exception:
                pass

    def _insert_value(self, parent, name, value):
        # flatten primitives; for dict/list show as nested
        if isinstance(value, dict):
            node = self.tree.insert(parent, "end", text=name, values=("{...}",), open=False)
            for kk, vv in value.items():
                self._insert_value(node, str(kk), vv)
        elif isinstance(value, (list, tuple, set)):
            node = self.tree.insert(parent, "end", text=name, values=(f"{type(value).__name__}[{len(value)}]",), open=False)
            for idx, item in enumerate(list(value)):
                self._insert_value(node, f"[{idx}]", item)
        else:
            self.tree.insert(parent, "end", text=name, values=(str(value),))

    # --- Watch API ---

    def add_watch(self, expr: str):
        expr = (expr or "").strip()
        if not expr:
            return False
        if expr in self._watch_items:
            # keep it visible
            try: self.tree.see(self._watch_items[expr])
            except Exception: pass
            return True
        try:
            item = self.tree.insert(self._watch_root, "end", text=expr, values=("<pending>",), open=False)
            self._watch_items[expr] = item
            self.tree.see(item)
            return True
        except Exception:
            return False

    def remove_watch(self, expr: str):
        expr = (expr or "").strip()
        if not expr:
            return False
        item = self._watch_items.pop(expr, None)
        if item:
            try: self.tree.delete(item)
            except Exception: pass
            return True
        return False

    def get_watch_expressions(self):
        return list(self._watch_items.keys())

    def update_watch_value(self, expr: str, value_str: str, success: bool = True):
        expr = (expr or "").strip()
        if expr not in self._watch_items:
            return
        item = self._watch_items[expr]
        try:
            display = value_str if success else f"<error> {value_str}"
            self.tree.item(item, values=(display,))
        except Exception:
            pass
