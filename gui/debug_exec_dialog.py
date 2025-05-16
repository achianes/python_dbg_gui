import tkinter as tk
from tkinter import ttk
import os 
import traceback
class DebugExecDialog(tk.Toplevel):
    def __init__(self, parent, main_app_ref, config=None):
        super().__init__(parent)
        self.main_app_ref = main_app_ref
        self.config = config if isinstance(config, dict) else {} 
        title_suffix = ""
        if self.main_app_ref and self.main_app_ref.current_debug_target_path:
            try: 
                title_suffix = f" (Context: {os.path.basename(self.main_app_ref.current_debug_target_path)})"
            except Exception:
                title_suffix = " (Context: Unknown)" 
        self.title(f"Debug Execution{title_suffix}")
        self.transient(parent)
        self.attributes("-topmost", True)
        self._executing = False
        main_dialog_frame = ttk.Frame(self, padding=5, borderwidth=1, relief="sunken")
        main_dialog_frame.pack(fill=tk.BOTH, expand=True)
        self.paned_window = ttk.PanedWindow(main_dialog_frame, orient=tk.VERTICAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=2, pady=2) 
        editor_outer_frame = ttk.Frame(self.paned_window, padding=0) 
        editor_frame = ttk.Frame(editor_outer_frame, borderwidth=1, relief="groove", padding=(2,2))
        self.mini_editor = tk.Text(editor_frame, undo=True, height=10, font=("Consolas", 10),
                                   borderwidth=0, highlightthickness=0) 
        self.mini_editor.pack(fill=tk.BOTH, expand=True)
        editor_frame.pack(fill=tk.BOTH, expand=True)
        self.mini_editor.bind("<Control-a>", lambda e: self.mini_editor.tag_add("sel", "1.0", "end") or "break")
        self.create_editor_context_menu()
        self.paned_window.add(editor_outer_frame, weight=2)
        console_outer_frame = ttk.Frame(self.paned_window, padding=0)
        console_frame = ttk.Frame(console_outer_frame, borderwidth=1, relief="groove", padding=(2,2))
        self.mini_console = tk.Text(console_frame, state="disabled", height=5,
                                    bg="black", fg="lightgrey", font=("Consolas", 10),
                                    borderwidth=0, highlightthickness=0) 
        self.mini_console.pack(fill=tk.BOTH, expand=True)
        console_frame.pack(fill=tk.BOTH, expand=True)
        self.paned_window.add(console_outer_frame, weight=1)
        self.exec_button = ttk.Button(main_dialog_frame, text="Execute (Ctrl+Enter)", command=self.execute_code)
        self.exec_button.pack(pady=5, side=tk.BOTTOM)
        self.mini_editor.bind("<Control-Return>", lambda e: self.execute_code())
        self._apply_config_geometry_and_position() 
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        if self.main_app_ref:
            self.main_app_ref.debug_exec_window = self 
        self._sash_applied_after_configure = False 
        self.bind("<Configure>", self._on_dialog_configure_apply_sash, add="+")
        self.mini_editor.focus_set()
    def _apply_config_geometry_and_position(self):
        geom_str = self.config.get('geometry', "600x450")
        pos_str = self.config.get('position')
        final_geometry_string = geom_str
        should_center_after_resize = True 
        if pos_str and pos_str.startswith('+'):
            try:
                pos_parts = pos_str.lstrip('+').split('+')
                if len(pos_parts) == 2:
                    x_pos = int(pos_parts[0]); y_pos = int(pos_parts[1])
                    screen_w = self.winfo_screenwidth(); screen_h = self.winfo_screenheight()
                    current_w, current_h = 600, 450 
                    try: current_w, current_h = map(int, geom_str.split('x'))
                    except ValueError: pass
                    if 0 <= x_pos < (screen_w - 20) and 0 <= y_pos < (screen_h - 20):
                        final_geometry_string = f"{geom_str}{pos_str}"
                        should_center_after_resize = False
                        print(f"DebugExecDialog: Applying saved geometry and position: {final_geometry_string}")
                    else:
                        print(f"DebugExecDialog: Saved position '{pos_str}' seems off-screen. Will apply size and then center.")
                else:
                    print(f"DebugExecDialog: Invalid position format '{pos_str}'. Will apply size and then center.")
            except ValueError:
                print(f"DebugExecDialog: Invalid numbers in position string '{pos_str}'. Will apply size and then center.")
        else:
            if pos_str is not None: 
                 print(f"DebugExecDialog: Position string '{pos_str}' is invalid. Will apply size and then center.")
        try:
            self.geometry(final_geometry_string)
            print(f"DebugExecDialog: Geometry set to '{final_geometry_string}'")
        except tk.TclError as e:
            print(f"DebugExecDialog: Error applying geometry '{final_geometry_string}': {e}. Using default 600x450.")
            self.geometry("600x450")
            should_center_after_resize = True 
        if should_center_after_resize:
            self.center_window()
    def _on_dialog_configure_apply_sash(self, event=None):
        if not self._sash_applied_after_configure:
            if hasattr(self, 'paned_window') and self.paned_window.winfo_exists():
                pw_height = self.paned_window.winfo_height()
                if pw_height > 40: 
                    print(f"DebugExecDialog: <Configure> event, pw_height: {pw_height}. Applying sash.")
                    self._apply_sash_position_final()
                    self._sash_applied_after_configure = True
                else:
                    print(f"DebugExecDialog: <Configure> event, pw_height: {pw_height} too small. Deferring sash apply.")
            else:
                print(f"DebugExecDialog: <Configure> event, paned_window not ready for sash.")
    def _apply_sash_position_final(self):
        sash_pos_config_val = self.config.get('sash_pos')
        default_sash_pos = 250 
        if hasattr(self, 'paned_window') and self.paned_window.winfo_exists():
            self.paned_window.update_idletasks() 
            if self.paned_window.panes(): 
                try:
                    target_sash_pos = default_sash_pos
                    if sash_pos_config_val is not None:
                        try:
                            target_sash_pos = int(sash_pos_config_val)
                            print(f"DebugExecDialog (_apply_sash_position_final): Using configured sash_pos: {target_sash_pos}")
                        except ValueError:
                            print(f"DebugExecDialog (_apply_sash_position_final): Invalid configured sash_pos '{sash_pos_config_val}', using default {default_sash_pos}.")
                    else:
                        print(f"DebugExecDialog (_apply_sash_position_final): No sash_pos in config, using default: {default_sash_pos}")
                    self.paned_window.update_idletasks() 
                    pw_height = self.paned_window.winfo_height()
                    print(f"DebugExecDialog (_apply_sash_position_final): PanedWindow height for sash adjustment: {pw_height}")
                    if pw_height < 50: 
                        print(f"DebugExecDialog (_apply_sash_position_final): PanedWindow height {pw_height} too small, skipping sashpos adjustment.")
                        return 
                    min_sash_limit = 20 
                    max_sash_limit = pw_height - 20 
                    final_sash_val = target_sash_pos
                    if min_sash_limit < max_sash_limit : 
                        adjusted_sash_pos = max(min_sash_limit, min(target_sash_pos, max_sash_limit))
                        if adjusted_sash_pos != target_sash_pos:
                            print(f"DebugExecDialog (_apply_sash_position_final): Adjusted sash_pos from {target_sash_pos} to {adjusted_sash_pos} for window height {pw_height}.")
                        final_sash_val = adjusted_sash_pos
                    else: 
                        if target_sash_pos < 20 :
                             final_sash_val = default_sash_pos 
                             print(f"DebugExecDialog (_apply_sash_position_final): Target sash {target_sash_pos} too small for height {pw_height}, using {final_sash_val}")
                    self.paned_window.sashpos(0, final_sash_val) 
                    print(f"DebugExecDialog (_apply_sash_position_final): Applied final sash position: {final_sash_val}")
                except (tk.TclError, ValueError, IndexError) as e:
                    print(f"DebugExecDialog (_apply_sash_position_final): Error applying sash_pos '{sash_pos_config_val}': {e}. Using default {default_sash_pos}.")
                    try:
                        if self.paned_window.winfo_exists() and self.paned_window.panes():
                           self.paned_window.sashpos(0, default_sash_pos)
                    except Exception as e_fallback_sash:
                        print(f"DebugExecDialog (_apply_sash_position_final): Error applying fallback sash: {e_fallback_sash}")
            else: print(f"DebugExecDialog (_apply_sash_position_final): PanedWindow has no panes. Sash not set.")
        else: print("DebugExecDialog (_apply_sash_position_final): PanedWindow not available for sash setting.")
    def center_window(self):
        self.update_idletasks() 
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1: width = 600
        if height <= 1: height = 450
        parent_window = self.master
        if not parent_window:
            parent_window = self.winfo_toplevel()
            if parent_window == self:
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                x_coord = (screen_width // 2) - (width // 2)
                y_coord = (screen_height // 2) - (height // 2)
                self.geometry(f'{width}x{height}+{x_coord}+{y_coord}')
                print(f"DebugExecDialog: Centered on screen to {width}x{height}+{x_coord}+{y_coord}")
                return
        parent_x = parent_window.winfo_x()
        parent_y = parent_window.winfo_y()
        parent_width = parent_window.winfo_width()
        parent_height = parent_window.winfo_height()
        x_coord = parent_x + (parent_width // 2) - (width // 2)
        y_coord = parent_y + (parent_height // 2) - (height // 2)
        self.geometry(f'+{x_coord}+{y_coord}')
        print(f"DebugExecDialog: Centered relative to parent at +{x_coord}+{y_coord} (current size {width}x{height})")
    def create_editor_context_menu(self):
        menu = tk.Menu(self.mini_editor, tearoff=0)
        menu.add_command(label="Undo", command=lambda: self.mini_editor.edit_undo() if self.mini_editor['state'] == 'normal' else None)
        menu.add_command(label="Redo", command=lambda: self.mini_editor.edit_redo() if self.mini_editor['state'] == 'normal' else None)
        menu.add_separator()
        menu.add_command(label="Cut", command=lambda: self.mini_editor.event_generate("<<Cut>>") if self.mini_editor['state'] == 'normal' else None)
        menu.add_command(label="Copy", command=lambda: self.mini_editor.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: self.mini_editor.event_generate("<<Paste>>") if self.mini_editor['state'] == 'normal' else None)
        menu.add_separator()
        menu.add_command(label="Select All", command=lambda: self.mini_editor.tag_add("sel", "1.0", "end"))
        self.mini_editor.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))
    def execute_code(self):
        if self._executing:
            self.add_to_console("Execution already in progress...\n", "error")
            return
        code_to_exec = self.mini_editor.get("1.0", tk.END).strip()
        if not code_to_exec:
            return
        if not self.main_app_ref.is_running or not self.main_app_ref.paused:
            self.add_to_console("Debugger not paused. Cannot execute code.\n", "error")
            return
        if self.main_app_ref.command_pending:
            self.add_to_console("Debugger busy. Try again shortly.\n", "error")
            return
        self._executing = True
        print("DEBUG: Set _executing flag in DebugExecDialog")
        self.add_to_console(f">>> {code_to_exec}\n", "command")
        self.main_app_ref.app.evaluate_expression_from_window(code_to_exec, self.receive_eval_result_wrapper)
    def receive_eval_result_wrapper(self, original_code, captured_stdout, captured_stderr, success, exception_str):
        try:
            self.receive_exec_result(original_code, captured_stdout, captured_stderr, success, exception_str)
        finally:
            self._executing = False
            print("DEBUG: Reset _executing flag in DebugExecDialog via wrapper")
    def receive_exec_result(self, original_code, captured_stdout, captured_stderr, success, exception_str):
        if captured_stdout:
            self.add_to_console(captured_stdout, "stdout_exec")
        if captured_stderr:
            self.add_to_console(captured_stderr, "stderr_exec")
        if not captured_stdout and not captured_stderr and success:
             self.add_to_console("[No output or non-expression statement]\n", "info")
        elif not success and not captured_stderr:
            self.add_to_console(f"Error: {exception_str}\n", "error")
    def add_to_console(self, text, tag=None):
        self.mini_console.config(state="normal")
        if tag == "error":
            self.mini_console.tag_configure("error", foreground="red")
            self.mini_console.insert(tk.END, text, "error")
        elif tag == "command":
            self.mini_console.tag_configure("command", foreground="yellow")
            self.mini_console.insert(tk.END, text, "command")
        elif tag == "stdout_exec":
            self.mini_console.tag_configure("stdout_exec", foreground="lightgreen")
            self.mini_console.insert(tk.END, text, "stdout_exec")
        elif tag == "stderr_exec":
            self.mini_console.tag_configure("stderr_exec", foreground="#FF8C00") 
            self.mini_console.insert(tk.END, text, "stderr_exec")
        elif tag == "info":
            self.mini_console.tag_configure("info", foreground="lightblue")
            self.mini_console.insert(tk.END, text, "info")
        else:
            self.mini_console.insert(tk.END, text)
        self.mini_console.see(tk.END)
        self.mini_console.config(state="disabled")
    def on_close(self):
        if self.main_app_ref:
            if self.winfo_exists():
                try:
                    dialog_geo_full = self.geometry()
                    parts = dialog_geo_full.split('+', 1)
                    geom = parts[0]
                    pos = f"+{parts[1]}" if len(parts) > 1 else None
                    sash = None
                    if hasattr(self, 'paned_window') and self.paned_window.winfo_exists() and self.paned_window.panes():
                        try: sash = self.paned_window.sashpos(0)
                        except tk.TclError as e_sash:
                            print(f"DebugExecDialog.on_close: Could not get sash position during save: {e_sash}")
                            sash = self.config.get('sash_pos')
                    updated_settings = {'geometry': geom}
                    if pos: updated_settings['position'] = pos
                    if sash is not None: updated_settings['sash_pos'] = int(sash)
                    if hasattr(self.main_app_ref, 'config') and\
                       'debug_exec_dialog_config' in self.main_app_ref.config and\
                       isinstance(self.main_app_ref.config['debug_exec_dialog_config'], dict):
                        main_app_dialog_config_ref = self.main_app_ref.config['debug_exec_dialog_config']
                        main_app_dialog_config_ref.clear() 
                        main_app_dialog_config_ref.update(updated_settings) 
                    else:
                        print(f"DebugExecDialog.on_close: Warning - main_app_ref.config['debug_exec_dialog_config'] was not a dict or missing. Recreating.")
                        self.main_app_ref.config['debug_exec_dialog_config'] = updated_settings.copy()
                    self.main_app_ref.debug_exec_dialog_config = self.main_app_ref.config['debug_exec_dialog_config'].copy()
                    print(f"DebugExecDialog.on_close: Updated main_app_ref.debug_exec_dialog_config to: {self.main_app_ref.debug_exec_dialog_config}")
                except (tk.TclError, AttributeError) as e:
                    print(f"DebugExecDialog.on_close: Error getting/setting geometry/state for save: {e}")
                    traceback.print_exc()
            self.main_app_ref.debug_exec_window = None
        self.destroy()
