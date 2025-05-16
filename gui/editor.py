import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import keyword
import re
import sys
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 24
class CodeEditor(tk.Frame):
    def __init__(self, master, main_app_ref=None):
        super().__init__(master)
        self.main_app_ref = main_app_ref
        self.font_family = 'Consolas'
        self.font_size = 11
        self.current_font = tkfont.Font(family=self.font_family, size=self.font_size)
        self.line_height = self.current_font.metrics('linespace')
        self.gutter_width = 45
        self.completion_listbox = None
        self.completion_active = False
        self.potential_completions = []
        self.completion_word_start_index = None
        self.python_keywords = keyword.kwlist + keyword.softkwlist
        self.python_builtins = [b for b in dir(__builtins__) if not b.startswith('_')]
        self._base_known_words = sorted(list(set(self.python_keywords + self.python_builtins)))
        self.document_words = set()
        self.all_known_words = list(self._base_known_words)
        self.bg_color = "white"
        self.fg_color = "black"
        self.insert_bg_color = "black"
        self.gutter_bg_color = "#f0f0f0"
        self.gutter_fg_color = "#606060"
        self.syntax_colors = {
            'keyword': '#0000ff', 'comment': '#008000', 'string': '#a31515',
            'number': '#098658', 'function': '#795E26', 'class': '#267f99',
            'decorator': '#800080', 'builtin': '#0000ff', 'self': '#aa00aa',
        }
        self.theme_colors_cache = None
        self.gutter = tk.Canvas(self, width=self.gutter_width, bg=self.gutter_bg_color, highlightthickness=0)
        self.vsb = ttk.Scrollbar(self, orient='vertical', command=self._on_vscroll)
        self.hsb = ttk.Scrollbar(self, orient='horizontal', command=self._on_hscroll)
        self.text = tk.Text(self,
                            wrap='none',
                            font=self.current_font,
                            tabs=(self.current_font.measure(' ' * 4),),
                            undo=True, maxundo=-1,
                            yscrollcommand=self._on_yscroll,
                            xscrollcommand=self.hsb.set,
                            borderwidth=0, highlightthickness=0,
                            padx=5, pady=2,
                            background=self.bg_color,
                            foreground=self.fg_color,
                            insertbackground=self.insert_bg_color)
        self.gutter.pack(side='left', fill='y')
        self.vsb.pack(side='right', fill='y')
        self.hsb.pack(side='bottom', fill='x')
        self.text.pack(side='right', fill='both', expand=True)
        self.text.bind('<KeyPress>', self._on_key_press, add='+')
        self.text.bind('<<Modified>>', self._on_text_change, add='+')
        self.text.bind('<Configure>', self._on_widget_configure, add='+')
        self.text.bind('<ButtonRelease-1>', self._on_release_1, add='+')
        self.text.bind('<MouseWheel>', lambda e: self._on_mousewheel(e, 'y'), add='+')
        self.text.bind('<Control-MouseWheel>', lambda e: self._on_zoom(e), add='+')
        self.text.bind('<Shift-MouseWheel>', lambda e: self._on_mousewheel(e, 'x'), add='+')
        self.gutter.bind('<Button-1>', self._on_gutter_click)
        self.gutter.bind('<Double-Button-1>', self._on_gutter_double_click)
        self._compile_syntax_patterns()
        self._apply_default_syntax_colors()
        self.text.tag_configure('current_line', background='#e6e6e6')
        self.text.tag_configure('breakpoint_line', background='#ffdddd')
        self._breakpoints = set()
        self.dirty = False
        self.filepath = None
        self._temp_name = None
        self.opened_by_debugger = False
        self._create_context_menu()
        self.text.bind('<Button-3>', self._show_context_menu)
        self.text.bind("<Control-f>", self._trigger_find_dialog_from_editor)
        self.text.bind("<KeyRelease>", self._on_key_release_for_completion, add='+')                            
        self.text.bind("<KeyPress-Escape>", self._on_escape_for_completion, add='+')
        self.text.bind("<KeyPress-Up>", self._on_arrow_key_for_completion, add='+')
        self.text.bind("<KeyPress-Down>", self._on_arrow_key_for_completion, add='+')
        self.text.bind("<Button-1>", self._on_click_for_completion, add='+')
        self._highlight_job = None
        self._debugger_active_line = None                                 
        self.after(50, self._update_gutter_and_highlight)
        self.after(5000, lambda: self._update_document_words_safely())
    def _apply_default_syntax_colors(self):
        for tag, color in self.syntax_colors.items():
            font_config = self.current_font
            if tag == 'class':
                 font_config = (self.current_font.cget('family'), self.current_font.cget('size'), 'bold')
            try:
                self.text.tag_configure(tag, foreground=color, font=font_config)
            except tk.TclError: pass
    def set_font_size(self, size):
        new_size = max(MIN_FONT_SIZE, min(size, MAX_FONT_SIZE))
        if new_size == self.font_size and self.current_font.cget('size') == new_size: return
        self.font_size = new_size
        self.current_font.configure(size=self.font_size)
        self.line_height = self.current_font.metrics('linespace')
        new_tab_width = self.current_font.measure(' ' * 4)
        self.text.config(font=self.current_font, tabs=(new_tab_width,))
        if self.theme_colors_cache:
            self.apply_theme(self.theme_colors_cache, force_syntax_update=True)
        else:
            self._apply_default_syntax_colors()
        self._update_gutter_and_highlight()
    def apply_theme(self, theme_colors_dict, force_syntax_update=False):
        self.theme_colors_cache = theme_colors_dict
        self.bg_color = theme_colors_dict.get("editor_bg", "white")
        self.fg_color = theme_colors_dict.get("editor_fg", "black")
        self.insert_bg_color = theme_colors_dict.get("editor_insert_bg", self.fg_color)
        self.gutter_bg_color = theme_colors_dict.get("gutter_bg", "#f0f0f0")
        self.gutter_fg_color = theme_colors_dict.get("gutter_fg", "#606060")
        current_line_bg = theme_colors_dict.get("current_line_editor_bg", "#e6e6e6")
        self.text.tag_configure('current_line', background=current_line_bg)
        breakpoint_line_bg = theme_colors_dict.get("breakpoint_line_editor_bg", "#ffdddd")
        self.text.tag_configure('breakpoint_line', background=breakpoint_line_bg)
        self.text.config(background=self.bg_color, foreground=self.fg_color, insertbackground=self.insert_bg_color)
        self.gutter.config(bg=self.gutter_bg_color)
        merged_syntax_colors = self.syntax_colors.copy() 
        theme_syntax = theme_colors_dict.get("syntax", {})
        if isinstance(theme_syntax, dict): merged_syntax_colors.update(theme_syntax)
        self.syntax_colors = merged_syntax_colors
        self._apply_default_syntax_colors()
        if force_syntax_update or self.winfo_exists():
            self._update_gutter_and_highlight()
    def _on_widget_configure(self, event=None):
        self._update_gutter_and_highlight()                                  
    def _on_release_1(self, event=None):
        self.after_idle(self._update_gutter) 
    def _compile_syntax_patterns(self):
        kwlist = keyword.kwlist + keyword.softkwlist
        builtins_list = dir(__builtins__)
        self._syntax_patterns_ordered = [
            ('string', r'("""(?:.|\n)*?""")|(\'\'\'(?:.|\n)*?\'\'\')|(".*?")|(\'.*?\')'),
            ('function', r'\bdef\s+([a-zA-Z_]\w*)'), 
            ('class', r'\bclass\s+([a-zA-Z_]\w*)'),
            ('decorator', r'@\w+'),
            ('keyword', r'\b(' + '|'.join(kwlist) + r')\b'),
            ('builtin', r'\b(' + '|'.join(b for b in builtins_list if not b.startswith('_')) + r')\b'),
            ('self', r'\b(self|cls)\b'), 
            ('number', r'\b-?\d+\.?\d*(?:[eE][-+]?\d+)?\b'), 
            ('comment', r'#.*'), 
        ]
        self._compiled_patterns = {}
        for tag, pattern_str in self._syntax_patterns_ordered:
            flags = re.DOTALL if tag == 'string' else 0
            self._compiled_patterns[tag] = re.compile(pattern_str, flags)
        self._highlight_order = ['comment'] +\
                                [tag for tag, _ in self._syntax_patterns_ordered if tag != 'comment']
    def _on_text_change(self, event=None):
        if self.text.edit_modified():
            if not self.dirty:
                self.dirty = True
                if self.main_app_ref and hasattr(self.main_app_ref, '_mark_dirty'):
                    self.main_app_ref._mark_dirty(self)
            self._trigger_highlight_update()
        self.text.edit_modified(False)
    def _on_key_release_for_completion(self, event):                                                             
        if event.keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Caps_Lock", "Num_Lock", "Scroll_Lock", "Insert", "Pause", "Print", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"): return
        if event.keysym in ("Up", "Down", "Return", "Tab", "Escape"): return
        if event.keysym in ("BackSpace", "Delete", "Left", "Right", "Home", "End", "Prior", "Next"):
            self._hide_completion_listbox(); return
        self._handle_completion_check()
    def _trigger_highlight_update(self):
        if self._highlight_job: self.after_cancel(self._highlight_job)
        self._highlight_job = self.after(150, self._highlight_syntax_visible_wrapper)                     
    def _highlight_syntax_visible_wrapper(self):
        self._highlight_job = None
        if self.winfo_exists():
            self._update_gutter() 
            self._highlight_syntax_visible()
            self._ensure_debugger_line_is_current() 
    def _ensure_debugger_line_is_current(self):
        if self._debugger_active_line is not None:
            self.highlight_current_line(self._debugger_active_line, from_debugger_call=True)
    def _hide_completion_listbox(self):
        if self.completion_listbox: self.completion_listbox.destroy(); self.completion_listbox = None
        self.completion_active = False; self.potential_completions = []
    def _apply_completion(self, from_keyboard=True):
        if not self.completion_active or not self.completion_listbox: return False
        try:
            selected_indices = self.completion_listbox.curselection()
            selected_completion = ""
            if not selected_indices:
                if from_keyboard and self.completion_listbox.size() > 0: selected_completion = self.potential_completions[0]
                else: self._hide_completion_listbox(); return False
            else: selected_completion = self.potential_completions[selected_indices[0]]
            current_word_typed_len = len(self.text.get(self.completion_word_start_index, tk.INSERT))
            self.text.edit_separator()
            self.text.delete(self.completion_word_start_index, f"{self.completion_word_start_index} + {current_word_typed_len}c")
            self.text.insert(self.completion_word_start_index, selected_completion)
            self.text.edit_separator()
            self._hide_completion_listbox(); return True
        except tk.TclError: self._hide_completion_listbox(); return False
        except Exception: self._hide_completion_listbox(); return False
    def _on_escape_for_completion(self, event):
        if self.completion_active: self._hide_completion_listbox(); return "break"
        return None
    def _on_arrow_key_for_completion(self, event):
        if self.completion_active and self.completion_listbox:
            current_selection_tuple = self.completion_listbox.curselection(); current_idx = -1
            if current_selection_tuple: current_idx = current_selection_tuple[0]
            max_idx = self.completion_listbox.size() - 1
            if max_idx < 0: return "break"
            next_idx = current_idx
            if event.keysym == "Up": next_idx = current_idx - 1 if current_idx > 0 else max_idx
            elif event.keysym == "Down": next_idx = current_idx + 1 if current_idx < max_idx else 0
            if next_idx != current_idx:
                if current_idx != -1: self.completion_listbox.select_clear(current_idx)
                self.completion_listbox.select_set(next_idx); self.completion_listbox.activate(next_idx); self.completion_listbox.see(next_idx)
            return "break"
        return None
    def _on_click_for_completion(self, event):
        if self.completion_active and self.completion_listbox:
            try:
                lb_x, lb_y = self.completion_listbox.winfo_x(), self.completion_listbox.winfo_y()
                lb_w, lb_h = self.completion_listbox.winfo_width(), self.completion_listbox.winfo_height()
                if not (lb_x <= event.x < lb_x + lb_w and lb_y <= event.y < lb_y + lb_h):
                    self._hide_completion_listbox()
            except tk.TclError: self._hide_completion_listbox()
        return None 
    def _on_completion_select_mouse(self, event):
        self._apply_completion(from_keyboard=False); self.text.focus_set(); return "break"
    def _handle_completion_check(self):
        if not hasattr(self, 'all_known_words'): return
        try:
            if self.text.tag_ranges("sel"): self._hide_completion_listbox(); return
            cursor_index = self.text.index(tk.INSERT)
            line_start = self.text.index(f"{cursor_index} linestart")
            text_before_cursor = self.text.get(line_start, cursor_index)
            match = re.search(r'([a-zA-Z_][a-zA-Z_0-9]*)$', text_before_cursor)
            if match:
                current_word = match.group(1)
                if len(current_word) >= 2:
                    suggestions = [w for w in self.all_known_words if w.startswith(current_word) and w != current_word]
                    if suggestions:
                        self.completion_word_start_index = self.text.index(f"{cursor_index} - {len(current_word)}c")
                        self._show_completion_listbox(suggestions, current_word); return
            self._hide_completion_listbox()
        except tk.TclError: self._hide_completion_listbox()
        except Exception: self._hide_completion_listbox()
    def _show_completion_listbox(self, suggestions, current_word_part):
        if not self.winfo_exists(): return
        try: x, y, _, height = self.text.bbox(tk.INSERT)
        except tk.TclError: self._hide_completion_listbox(); return
        if self.completion_listbox: self.completion_listbox.destroy()
        self.completion_listbox = tk.Listbox(self.text, exportselection=False, font=self.current_font, bg="#FFFFE0", selectbackground="#ADD8E6", highlightthickness=1, relief="solid", takefocus=0, borderwidth=1)
        self.completion_listbox.bind("<ButtonRelease-1>", self._on_completion_select_mouse)
        listbox_height_items = min(len(suggestions), 5)
        item_height = self.current_font.metrics("linespace") + 2
        self.listbox_actual_height = listbox_height_items * item_height
        max_width_chars = max(len(s) for s in suggestions) if suggestions else 20
        self.listbox_actual_width = (max_width_chars + 2) * self.current_font.measure("0")
        self.completion_listbox.place(x=x, y=y + height, width=self.listbox_actual_width, height=self.listbox_actual_height)
        self.potential_completions = suggestions
        for item in suggestions: self.completion_listbox.insert(tk.END, item)
        if not suggestions: self._hide_completion_listbox(); return
        self.completion_listbox.select_set(0); self.completion_listbox.activate(0); self.completion_listbox.see(0)
        self.completion_active = True; self.completion_listbox.lift()
    def _on_key_press(self, event):
        if self.completion_active:
            if event.keysym == 'Tab':
                if self._apply_completion(from_keyboard=True): return "break"
            elif event.keysym == 'Return':
                if self._apply_completion(from_keyboard=True): return "break"
        if event.keysym == 'Tab':
            has_selection = False
            try:
                if self.text.tag_ranges(tk.SEL): has_selection = True
            except tk.TclError: pass
            if has_selection:
                try:
                    sel_start = self.text.index(tk.SEL_FIRST); sel_end = self.text.index(tk.SEL_LAST)
                except tk.TclError: self.text.insert(tk.INSERT, ' ' * 4); return 'break'
                start_line = int(sel_start.split('.')[0]); end_line = int(sel_end.split('.')[0])
                if sel_end.split('.')[1] == '0' and sel_start.split('.')[0] != sel_end.split('.')[0]: end_line -= 1
                end_line = max(start_line, end_line)
                self.text.edit_separator()
                if event.state & 1:
                    for i in range(start_line, end_line + 1):
                        line_start_idx = f"{i}.0"; line_content = self.text.get(line_start_idx, f"{i}.end")
                        if line_content.startswith('    '): self.text.delete(line_start_idx, f"{i}.4")
                        elif line_content.startswith('\t'): self.text.delete(line_start_idx, f"{i}.1")
                else:
                    for i in range(start_line, end_line + 1): self.text.insert(f"{i}.0", ' ' * 4)
                return 'break'
            else: self.text.insert(tk.INSERT, ' ' * 4); return 'break'
        elif event.keysym == 'Return':
            try:
                insert_index = self.text.index(tk.INSERT); current_line_num = int(insert_index.split('.')[0])
                prev_line_text = self.text.get(f"{current_line_num}.0", f"{current_line_num}.end")
                leading_whitespace_match = re.match(r'^(\s*)', prev_line_text)
                leading_whitespace = leading_whitespace_match.group(1) if leading_whitespace_match else ""
                if prev_line_text.strip().endswith(':'): leading_whitespace += ' ' * 4
                cursor_char_index = int(insert_index.split('.')[1])
                text_after_cursor_on_line = prev_line_text[cursor_char_index:]
                if prev_line_text[:cursor_char_index].strip() == "" and\
                   text_after_cursor_on_line.strip().startswith(('}', ')', ']')) and\
                   len(leading_whitespace) >= 4: leading_whitespace = leading_whitespace[:-4]
                self.text.edit_separator()
                self.text.insert(tk.INSERT, '\n' + leading_whitespace)
                self.text.edit_separator()
                self.text.see(tk.INSERT); return 'break'
            except Exception: return None
        return None
    def _trigger_find_dialog_from_editor(self, event=None):
        if self.main_app_ref and hasattr(self.main_app_ref, '_open_find_dialog'):
            self.main_app_ref._open_find_dialog(); return "break"
        return None
    def _create_context_menu(self):
        self.context_menu = tk.Menu(self.text, tearoff=0)
        self.context_menu.add_command(label='Undo', accelerator='Ctrl+Z', command=self.edit_undo)
        self.context_menu.add_command(label='Redo', accelerator='Ctrl+Y', command=self.edit_redo)
        self.context_menu.add_separator()
        self.context_menu.add_command(label='Cut', accelerator='Ctrl+X', command=lambda: self.focus_set() or self.text.event_generate('<<Cut>>'))
        self.context_menu.add_command(label='Copy', accelerator='Ctrl+C', command=lambda: self.focus_set() or self.text.event_generate('<<Copy>>'))
        self.context_menu.add_command(label='Paste', accelerator='Ctrl+V', command=lambda: self.focus_set() or self.text.event_generate('<<Paste>>'))
        self.context_menu.add_separator()
        self.context_menu.add_command(label='Find...', accelerator='Ctrl+F', command=self._trigger_find_dialog_from_editor)
        self.context_menu.add_separator()
        self.context_menu.add_command(label='Select All', accelerator='Ctrl+A', command=self.select_all)
        self.context_menu.add_separator()
        self.context_menu.add_command(label='Comment/Uncomment', command=self.comment_uncomment_block)
        self.context_menu.add_separator()
        self.context_menu.add_command(label='Toggle Breakpoint', command=self._toggle_breakpoint_at_cursor)
        self.context_menu.add_command(label='Remove All Breakpoints', command=self.remove_all_breakpoints)
    def edit_undo(self, event=None):
        try: self.text.edit_undo()
        except tk.TclError: pass
    def edit_redo(self, event=None):
        try: self.text.edit_redo()
        except tk.TclError: pass
    def select_all(self, event=None):
        self.text.tag_add(tk.SEL, "1.0", "end-1c"); self.text.mark_set(tk.INSERT, "1.0"); self.text.see(tk.INSERT); return "break"
    def comment_uncomment_block(self):
        try:
            sel_first_idx = self.text.index(tk.SEL_FIRST); sel_last_idx = self.text.index(tk.SEL_LAST)
            start_line = int(sel_first_idx.split('.')[0]); end_line = int(sel_last_idx.split('.')[0])
            if sel_last_idx.split('.')[1] == '0' and sel_first_idx != sel_last_idx: end_line -= 1
        except tk.TclError: start_line = end_line = int(self.text.index(tk.INSERT).split('.')[0])
        if start_line < 1: return
        self.text.edit_separator()
        first_line_content = self.text.get(f"{start_line}.0", f"{start_line}.end")
        is_commenting = not first_line_content.lstrip().startswith('#')
        for ln_num in range(start_line, end_line + 1):
            line_start_idx = f"{ln_num}.0"; current_line_content = self.text.get(line_start_idx, f"{ln_num}.end")
            if is_commenting: self.text.insert(line_start_idx, '#')
            else:
                stripped_line = current_line_content.lstrip()
                if stripped_line.startswith('#'):
                    hash_pos = current_line_content.find('#')
                    self.text.delete(f"{ln_num}.{hash_pos}", f"{ln_num}.{hash_pos + 1}")
        self.text.edit_separator()
    def _get_line_tag_range(self, line_number):
        if not self.winfo_exists(): return None, None
        start_idx = f"{line_number}.0"
        try:
            last_line_of_text = int(self.text.index(tk.END + "-1c").split('.')[0])
            if line_number == last_line_of_text: end_idx = f"{line_number}.end" 
            else: end_idx = f"{line_number + 1}.0"
            self.text.index(start_idx) 
            if line_number != last_line_of_text or line_number == 1 :
                 if end_idx != f"{line_number}.end": self.text.index(end_idx)
            return start_idx, end_idx
        except (tk.TclError, ValueError, AttributeError): return None, None
    def remove_all_breakpoints(self):
        if not self._breakpoints: return
        for ln in list(self._breakpoints):
            start_idx, end_idx = self._get_line_tag_range(ln)
            if start_idx and end_idx:
                try: self.text.tag_remove('breakpoint_line', start_idx, end_idx)
                except tk.TclError: pass
        self._breakpoints.clear(); self._update_gutter()
    def _toggle_breakpoint_at_cursor(self):
        try: line_num = int(self.text.index(tk.INSERT).split('.')[0]); self.toggle_breakpoint(line_num)
        except ValueError: pass
    def toggle_breakpoint(self, line_number):
        if not isinstance(line_number, int) or line_number <= 0: return
        start_idx, end_idx = self._get_line_tag_range(line_number)
        if not start_idx : return
        action_taken = None
        if line_number in self._breakpoints:
            self._breakpoints.remove(line_number)
            if end_idx: self.text.tag_remove('breakpoint_line', start_idx, end_idx)
            else: self.text.tag_remove('breakpoint_line', start_idx)
            action_taken = "removed"
        else:
            self._breakpoints.add(line_number)
            if end_idx: self.text.tag_add('breakpoint_line', start_idx, end_idx)
            else: self.text.tag_add('breakpoint_line', start_idx)
            action_taken = "added"
        self.text.tag_raise('breakpoint_line'); self._update_gutter()
        if self.main_app_ref and hasattr(self.main_app_ref, 'notify_breakpoint_change'):
            if self.main_app_ref.is_running and self.main_app_ref.paused:
                if self.filepath and action_taken:
                    self.main_app_ref.notify_breakpoint_change(self.filepath, line_number, action_taken)
    @property
    def breakpoints(self): return sorted(list(self._breakpoints))
    def _on_vscroll(self, *args): 
        self.text.yview(*args)
        self.after_idle(self._visual_update_after_scroll)
    def _on_hscroll(self, *args): 
        self.text.xview(*args)
    def _on_yscroll(self, *args): 
        self.vsb.set(*args)
        self.after_idle(self._visual_update_after_scroll)
    def _visual_update_after_scroll(self):
        if not self.winfo_exists(): return
        self._update_gutter()
        self._trigger_highlight_update()
    def _on_mousewheel(self, event, axis):
        delta = event.delta
        if sys.platform == "darwin": delta = delta
        elif sys.platform.startswith("win"): delta = int(delta / 120)
        else: delta = 1 if delta > 0 else -1
        if axis == 'y': self.text.yview_scroll(-delta, 'units')
        else: self.text.xview_scroll(-delta, 'units')
        self.after_idle(self._visual_update_after_scroll)
        return 'break'
    def _on_zoom(self, event):
        if self.main_app_ref:
            if event.delta > 0: self.main_app_ref.increase_font_size()
            else: self.main_app_ref.decrease_font_size()
        else:
            current_size = self.current_font.cget('size')
            if event.delta > 0: new_size = current_size + 1
            else: new_size = current_size -1
            new_size = max(MIN_FONT_SIZE, min(new_size, MAX_FONT_SIZE))
            if new_size != current_size: self.set_font_size(new_size)
        return 'break'
    def _show_context_menu(self, event):
        self.text.focus_set()
        try:
            has_selection = bool(self.text.tag_ranges(tk.SEL))
            self.context_menu.entryconfigure("Cut", state=tk.NORMAL if has_selection else tk.DISABLED)
            self.context_menu.entryconfigure("Copy", state=tk.NORMAL if has_selection else tk.DISABLED)
        except tk.TclError:
            self.context_menu.entryconfigure("Cut", state=tk.DISABLED); self.context_menu.entryconfigure("Copy", state=tk.DISABLED)
        try:
            can_paste = bool(self.text.clipboard_get())
            self.context_menu.entryconfigure("Paste", state=tk.NORMAL if can_paste else tk.DISABLED)
        except tk.TclError: self.context_menu.entryconfigure("Paste", state=tk.DISABLED)
        try: self.text.edit_undo(); self.text.edit_redo(); self.context_menu.entryconfigure("Undo", state=tk.NORMAL)
        except tk.TclError: self.context_menu.entryconfigure("Undo", state=tk.DISABLED)
        try: self.text.edit_redo(); self.text.edit_undo(); self.context_menu.entryconfigure("Redo", state=tk.NORMAL)
        except tk.TclError: self.context_menu.entryconfigure("Redo", state=tk.DISABLED)
        self.context_menu.tk_popup(event.x_root, event.y_root)
    def _on_gutter_click(self, event): pass
    def _on_gutter_double_click(self, event):
        line_num = self.get_line_number_at_y(event)
        if line_num: self.toggle_breakpoint(line_num)
    def get_line_number_at_y(self, event):                                                           
        y_coord = event.y
        try:
            index_at_y = self.text.index(f"@0,{y_coord}")
            dline = self.text.dlineinfo(index_at_y)
            if dline: return int(index_at_y.split('.')[0])
            view_top_index = self.text.index("@0,0"); view_bottom_index = self.text.index(f"@0,{self.text.winfo_height()}")
            if view_top_index and view_bottom_index:
                 first_line_num = int(view_top_index.split('.')[0])
                 first_line_dline = self.text.dlineinfo(view_top_index)
                 if first_line_dline and self.line_height > 0:                                     
                      line_num_guess = first_line_num + int((y_coord - first_line_dline[1]) / self.line_height)
                      if self.text.dlineinfo(f"{line_num_guess}.0"): return line_num_guess
        except (tk.TclError, ValueError): pass
        return None
    def _update_gutter(self):                                     
        if not self.winfo_exists() or not self.gutter.winfo_exists() : return                            
        self.gutter.delete('all')
        try:
            first_visible_index = self.text.index("@0,0")
            bottom_y = self.text.winfo_height()
            last_visible_index = self.text.index(f"@0,{bottom_y-1}") if bottom_y > 0 else self.text.index("@0,0")
            first_line = int(first_visible_index.split('.')[0])
            last_line_num_val = int(last_visible_index.split('.')[0])
            last_line = last_line_num_val + 2 
        except (tk.TclError, ValueError): return
        for line_num in range(first_line, last_line + 1):
            index = f"{line_num}.0"
            dline = self.text.dlineinfo(index)
            if dline:
                x, y, width, height, baseline = dline
                text_x = 5 
                text_y = y + height // 2 
                line_num_text_id = self.gutter.create_text(text_x, text_y, anchor='w', 
                                                           text=str(line_num), font=self.current_font, 
                                                           fill=self.gutter_fg_color)
                if line_num in self._breakpoints:
                    try:
                        text_bbox = self.gutter.bbox(line_num_text_id)
                        if text_bbox:
                             pad_y = 1                  
                             rect_bbox = (2, text_bbox[1] - pad_y, self.gutter_width - 2, text_bbox[3] + pad_y)
                             self.gutter.create_rectangle(rect_bbox, fill="", outline='red', width=1) 
                    except tk.TclError: pass
    def set_read_only(self, read_only):
        if not self.winfo_exists(): return
        try:
            new_state = 'disabled' if read_only else 'normal'
            if self.text['state'] != new_state: self.text.config(state=new_state)
        except tk.TclError: pass
    def _highlight_syntax_visible(self):                                                  
        if not self.winfo_exists(): return
        try:
            first_visible_index = self.text.index("@0,0")
            last_visible_index = self.text.index(f"@0,{self.text.winfo_height()}") + "+1l"
        except (tk.TclError, ValueError): return
        for tag in self._compiled_patterns.keys():                         
            try: self.text.tag_remove(tag, first_visible_index, last_visible_index)
            except tk.TclError: pass
        visible_text = self.text.get(first_visible_index, last_visible_index)
        if not visible_text.strip(): return                            
        for tag in self._highlight_order:
            compiled_pattern = self._compiled_patterns.get(tag)
            if not compiled_pattern: continue
            try:
                for match in compiled_pattern.finditer(visible_text):
                    start, end = match.span()
                    abs_start_index = self.text.index(f"{first_visible_index}+{start}c")
                    abs_end_index = self.text.index(f"{first_visible_index}+{end}c")
                    if tag in ['function', 'class'] and match.lastindex and match.lastindex >= 1:
                         name_start, name_end = match.span(1)
                         abs_start_index = self.text.index(f"{first_visible_index}+{name_start}c")
                         abs_end_index = self.text.index(f"{first_visible_index}+{name_end}c")
                    self.text.tag_add(tag, abs_start_index, abs_end_index)
            except tk.TclError: pass
            except Exception: pass
    def _update_gutter_and_highlight(self, event=None):                        
        self.after_idle(self._update_gutter)
        self.after_idle(self._trigger_highlight_update)                                  
    def highlight_current_line(self, line_number, from_debugger_call=False):                              
        if not self.winfo_exists(): return
        if from_debugger_call:
            self._debugger_active_line = line_number
        elif self._debugger_active_line is not None:                                                      
            return                                          
        self.text.tag_remove('current_line', '1.0', tk.END)                 
        if not isinstance(line_number, int) or line_number <= 0:
            if from_debugger_call: self._debugger_active_line = None
            return
        start_index_str, end_index_str = self._get_line_tag_range(line_number)
        if not start_index_str or not end_index_str:
            if from_debugger_call: self._debugger_active_line = None
            return
        try:
            self.text.tag_add('current_line', start_index_str, end_index_str)
            self.text.update_idletasks()
            dline_info_initial = self.text.dlineinfo(start_index_str)
            self.text.see(start_index_str)
            self.text.update_idletasks()
            dline_info_after_see = self.text.dlineinfo(start_index_str)
            if dline_info_after_see:
                line_y_in_view, line_height, widget_height = dline_info_after_see[1], dline_info_after_see[3], self.text.winfo_height()
                if line_height <=0: line_height = self.current_font.metrics('linespace')
                margin = 2 * line_height
                is_obscured_bottom = (line_y_in_view + line_height > widget_height - margin) and (line_y_in_view < widget_height - line_height - margin)
                is_obscured_top = (line_y_in_view < margin) and (line_y_in_view + line_height > margin)
                is_completely_out_of_view_bottom = line_y_in_view >= widget_height
                is_completely_out_of_view_top = line_y_in_view + line_height <= 0
                if is_obscured_bottom or is_obscured_top or is_completely_out_of_view_bottom or is_completely_out_of_view_top:
                    num_lines_in_view_approx = widget_height / line_height if line_height > 0 else 15.0
                    target_visual_offset_lines = int(num_lines_in_view_approx / 3)
                    scroll_to_line_num = max(1, line_number - target_visual_offset_lines)
                    total_lines_in_doc = int(self.text.index(tk.END + "-1c").split('.')[0])
                    if total_lines_in_doc > 0:
                        fraction = (scroll_to_line_num - 1) / float(total_lines_in_doc); fraction = max(0.0, min(fraction, 1.0)) 
                        self.text.yview_moveto(fraction); self.text.update_idletasks(); self.text.see(start_index_str) 
            else: self.text.see(start_index_str)
            self.text.tag_raise('current_line')
        except (tk.TclError, ValueError, AttributeError, TypeError):
            if from_debugger_call: self._debugger_active_line = None
    def clear_current_line(self):
        if not self.winfo_exists(): return
        try:
            self.text.tag_remove('current_line', '1.0', tk.END)
        except tk.TclError: pass
        self._debugger_active_line = None                                       
    def _update_document_words_safely(self):
        if self.winfo_exists():
            self._update_document_words()
            self.after(2000, self._update_document_words_safely)
    def _update_document_words(self, event=None):
        if not self.winfo_exists(): return
        try:
            if not hasattr(self, '_base_known_words'): return
            current_text_content = self.text.get("1.0", tk.END)
            found_words = set(re.findall(r'\b([a-zA-Z_]\w*)\b', current_text_content))
            self.document_words = { word for word in found_words if word not in self._base_known_words and not word.isdigit() and len(word) > 1 }
            self.all_known_words = sorted(list(set(list(self._base_known_words) + list(self.document_words))))
        except tk.TclError: pass
        except Exception: pass
