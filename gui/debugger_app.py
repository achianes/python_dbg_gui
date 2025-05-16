import os
import sys
import traceback
import bdb
from bdb import BdbQuit
import time
from multiprocessing import Process, Pipe
import tkinter as tk
from tkinter import messagebox
import tkinter.ttk as ttk
import io
import builtins
from functools import partial                  
from gui.editor import CodeEditor
from gui.console import ConsolePanel
from gui.inspector import VariablesPanel
from gui.stack import StackPanel
from gui.custom_notebook import CustomNotebook
from gui.input_dialog import InputDialog
class StdOutRedirect:
    def __init__(self, conn):
        self.conn = conn
    def write(self, text):
        if text:
            try: self.conn.send(('stdout', text))
            except (OSError, EOFError, BrokenPipeError): pass
    def flush(self):
        pass
class StdErrRedirect:
    def __init__(self, conn):
        self.conn = conn
    def write(self, text):
        if text:
            try: self.conn.send(('stderr', text))
            except (OSError, EOFError, BrokenPipeError): pass
    def flush(self):
        pass
class StdInRedirect:
    def __init__(self, conn_obj):                                            
        self.conn = conn_obj                       
    def readline_with_prompt(self, prompt_text_from_caller=""):
        unique_input_id = f"input_{time.time()}_{id(self)}"
        try:
            self.conn.send(('gui_input_request_with_prompt', unique_input_id, str(prompt_text_from_caller)))
        except (OSError, BrokenPipeError, EOFError):
            raise EOFError("Debugger connection lost while requesting GUI input.")
        while True:
            try:
                kind, *rest = self.conn.recv()
                if kind == 'gui_input_response':
                    response_id, user_input_line = rest
                    if response_id == unique_input_id:
                        return user_input_line
                elif kind == 'finished':
                    raise EOFError("Debugger finished while waiting for GUI input response.")
            except (EOFError, OSError, BrokenPipeError):
                raise EOFError("Debugger connection lost while waiting for GUI input response.")
            except ValueError: 
                raise EOFError("Invalid message received while waiting for GUI input.")
    def readline(self):
        return self.readline_with_prompt("")
    def read(self, size=-1):
        try:
            line = self.readline()
        except EOFError:
            return "" 
        if size < 0 or size >= len(line):
            return line
        else:
            return line[:size]                                         
    def write(self, data):
        raise OSError("Cannot write to an input stream.")
    def flush(self):
        pass
class DebuggerBackend(bdb.Bdb):
    def __init__(self, script_path_from_gui, conn, breakpoints=None, script_args=None):
        super().__init__()
        self.main_script_bdb_key = self.canonic(script_path_from_gui)
        self.conn_to_gui = conn                                               
        self.script_args = script_args if script_args is not None else []
        self._instance_saved_bplist = {}
        self._instance_saved_bpbynumber = [None]
        self._user_line_state_sent_this_pause = False
        from bdb import Breakpoint as BDB_Breakpoint_Class
        if not hasattr(BDB_Breakpoint_Class, 'bplist'): BDB_Breakpoint_Class.bplist = {}
        if not hasattr(BDB_Breakpoint_Class, 'bpbynumber'): BDB_Breakpoint_Class.bpbynumber = [None]
        self.clear_all_breaks()
        if breakpoints:
            for lineno in breakpoints:
                try:
                    self.set_break(script_path_from_gui, lineno)
                except Exception: pass
        if hasattr(BDB_Breakpoint_Class, 'bplist'): self._instance_saved_bplist = dict(BDB_Breakpoint_Class.bplist)
        if hasattr(BDB_Breakpoint_Class, 'bpbynumber'): self._instance_saved_bpbynumber = list(BDB_Breakpoint_Class.bpbynumber)
        self.original_builtin_input = None
        self.redirected_stdin_instance = None                                                   
    def _safe_repr(self, value, max_len=100, visited=None):
        if visited is None: visited = set()
        try:
             obj_id = id(value)
             if obj_id in visited: return "<Recursion detected>"
             visited.add(obj_id)
        except TypeError: obj_id = None
        try: s = repr(value)
        except Exception:
            try: s = str(value)
            except Exception as e: s = f"<Error getting repr: {e}>"
        finally:
             if obj_id is not None and obj_id in visited: visited.remove(obj_id)
        if isinstance(s, str) and len(s) > max_len: s = s[:max_len] + '...'
        return s
    def _get_safe_vars(self, var_dict, depth=0, max_depth=2, visited=None):
        if visited is None: visited = set()
        if depth > max_depth:
             info = ""
             if isinstance(var_dict, dict): info = f"dict{{{len(var_dict)}}}"
             elif isinstance(var_dict, (list, tuple, set)): info = f"{type(var_dict).__name__}[{len(var_dict)}]"
             else: info = type(var_dict).__name__
             return f"<{info} Max depth {max_depth} reached>"
        safe_vars_processed = {}
        if not isinstance(var_dict, dict): return safe_vars_processed 
        try: sorted_keys = sorted(var_dict.keys(), key=str)
        except TypeError: sorted_keys = list(var_dict.keys())
        for k in sorted_keys:
            safe_key = self._safe_repr(k)
            try: v = var_dict[k]
            except Exception as e: safe_vars_processed[safe_key] = f"<Error accessing value: {e}>"; continue
            try:
                 obj_id = id(v)
                 if obj_id in visited: safe_vars_processed[safe_key] = "<Recursion detected>"; continue
                 visited.add(obj_id)
            except TypeError: obj_id = None
            if isinstance(v, (int, float, str, bool, bytes, type(None))):
                safe_vars_processed[safe_key] = v
            elif isinstance(v, (list, tuple, set)):
                 if depth < max_depth:
                      safe_collection = []
                      for item in v:
                           safe_item = self._get_safe_vars({'_': item}, depth + 1, max_depth, visited.copy()).get('_', self._safe_repr(item, visited=visited.copy()))
                           safe_collection.append(safe_item)
                      safe_vars_processed[safe_key] = type(v)(safe_collection)
                 else:
                      safe_vars_processed[safe_key] = f"{type(v).__name__}[{len(v) if hasattr(v, '__len__') else '?'}] <Max depth>"
            elif isinstance(v, dict):
                 if depth < max_depth: safe_vars_processed[safe_key] = self._get_safe_vars(v, depth + 1, max_depth, visited.copy())
                 else: safe_vars_processed[safe_key] = f"dict{{{len(v) if hasattr(v, '__len__') else '?'}}} <Max depth>"
            else:
                safe_vars_processed[safe_key] = self._safe_repr(v, visited=visited.copy())
            if obj_id is not None and obj_id in visited: visited.remove(obj_id)
        return safe_vars_processed
    def break_here(self, frame):
        from bdb import Breakpoint as BDB_Breakpoint_Class_bh
        original_bplist = None; original_bpbynumber = None
        if hasattr(BDB_Breakpoint_Class_bh, 'bplist'): original_bplist = dict(BDB_Breakpoint_Class_bh.bplist)
        if hasattr(BDB_Breakpoint_Class_bh, 'bpbynumber'): original_bpbynumber = list(BDB_Breakpoint_Class_bh.bpbynumber)
        BDB_Breakpoint_Class_bh.bplist = dict(self._instance_saved_bplist)
        BDB_Breakpoint_Class_bh.bpbynumber = list(self._instance_saved_bpbynumber)
        is_bp = False
        try:
            is_bp = super().break_here(frame)
        except Exception: is_bp = False
        finally:
            if original_bplist is not None: BDB_Breakpoint_Class_bh.bplist = original_bplist
            if original_bpbynumber is not None: BDB_Breakpoint_Class_bh.bpbynumber = original_bpbynumber
        return is_bp
    def user_line(self, frame):
        if not hasattr(self, '_user_line_state_sent_this_pause'):
            self._user_line_state_sent_this_pause = False
        if not self._user_line_state_sent_this_pause:
            try:
                current_file_abspath = self.canonic(frame.f_code.co_filename)
                path_for_gui = os.path.normcase(current_file_abspath)
                current_line_no = frame.f_lineno
                self.conn_to_gui.send(('line', path_for_gui, current_line_no))
                stack_list = []; temp_frame = frame; count = 0
                while temp_frame and count < 50:
                    stack_list.append((temp_frame, temp_frame.f_lineno))
                    temp_frame = temp_frame.f_back; count += 1
                stack_list.reverse()
                simple_stack = [(f.f_code.co_filename, l, f.f_code.co_name) for f, l in stack_list]
                self.conn_to_gui.send(('stack', simple_stack))
                safe_locals = self._get_safe_vars(frame.f_locals)
                safe_globals = self._get_safe_vars(frame.f_globals)
                self.conn_to_gui.send(('variables', {'locals': safe_locals, 'globals': safe_globals}))
            except Exception:
                try:
                    self.conn_to_gui.send(('line', '?', frame.f_lineno if frame else '?'))
                    self.conn_to_gui.send(('stack', []))
                    self.conn_to_gui.send(('variables', {'locals': {}, 'globals': {}}))
                except (OSError, EOFError, BrokenPipeError): pass
            self._user_line_state_sent_this_pause = True
        while True:
            filename_orig = frame.f_code.co_filename
            if filename_orig.startswith(("<frozen importlib", "<string>", "<frozen abc")):
                self._user_line_state_sent_this_pause = False; self.set_next(frame); return
            try:
                cmd, arg = self.conn_to_gui.recv()
            except (EOFError, OSError, BrokenPipeError): self.set_quit(); return
            if cmd == 'step': self._user_line_state_sent_this_pause = False; self.set_step(); return
            elif cmd == 'next': self._user_line_state_sent_this_pause = False; self.set_next(frame); return
            elif cmd == 'continue': self._user_line_state_sent_this_pause = False; self.set_continue(); return
            elif cmd == 'return': self._user_line_state_sent_this_pause = False; self.set_return(frame); return
            elif cmd == 'quit': self._user_line_state_sent_this_pause = False; self.set_quit(); return
            elif cmd == 'eval':
                eval_result = None; success = True
                try: eval_result = eval(arg, frame.f_globals, frame.f_locals)
                except Exception as e: eval_result = repr(e); success = False
                self.conn_to_gui.send(('eval_result', arg, self._safe_repr(eval_result), success))
            elif cmd == 'execute_code_interactive':
                code_to_exec = arg; captured_stdout = io.StringIO(); captured_stderr = io.StringIO()
                success = True; exception_str = ""
                _old_stdout, _old_stderr = sys.stdout, sys.stderr
                try:
                    sys.stdout = captured_stdout; sys.stderr = captured_stderr
                    exec(code_to_exec, frame.f_globals, frame.f_locals)
                except Exception as e_exec:
                    success = False; traceback.print_exc(file=captured_stderr); exception_str = str(e_exec)
                finally:
                    sys.stdout = _old_stdout; sys.stderr = _old_stderr
                    self.conn_to_gui.send(('interactive_result', code_to_exec, captured_stdout.getvalue(), captured_stderr.getvalue(), success, exception_str))
                    captured_stdout.close(); captured_stderr.close()
            elif cmd == 'add_breakpoint_runtime':
                bp_file, bp_line = arg; bp_file_canonic = self.canonic(bp_file)
                err_msg = self.set_break(bp_file_canonic, bp_line)
                if not err_msg:
                    from bdb import Breakpoint as BDB_BP_Class
                    if hasattr(BDB_BP_Class, 'bplist'): self._instance_saved_bplist = dict(BDB_BP_Class.bplist)
                    if hasattr(BDB_BP_Class, 'bpbynumber'): self._instance_saved_bpbynumber = list(BDB_BP_Class.bpbynumber)
                    self.conn_to_gui.send(('breakpoint_runtime_status', ('added', bp_file, bp_line, None)))
                else: self.conn_to_gui.send(('breakpoint_runtime_status', ('failed', bp_file, bp_line, err_msg)))
            elif cmd == 'remove_breakpoint_runtime':
                bp_file, bp_line = arg; bp_file_canonic = self.canonic(bp_file)
                try:
                    self.clear_break(bp_file_canonic, bp_line)
                    from bdb import Breakpoint as BDB_BP_Class
                    if hasattr(BDB_BP_Class, 'bplist'): self._instance_saved_bplist = dict(BDB_BP_Class.bplist)
                    if hasattr(BDB_BP_Class, 'bpbynumber'): self._instance_saved_bpbynumber = list(BDB_BP_Class.bpbynumber)
                    self.conn_to_gui.send(('breakpoint_runtime_status', ('removed', bp_file, bp_line, None)))
                except Exception as e_clear: self.conn_to_gui.send(('breakpoint_runtime_status', ('failed_remove', bp_file, bp_line, str(e_clear))))
            else:
                try: self.conn_to_gui.send(('unknown_command_status', cmd))
                except (OSError, EOFError, BrokenPipeError): self.set_quit(); return
    def _patched_input_with_stdin_instance(self, stdin_instance, prompt=""):
        if prompt:
            sys.stdout.write(str(prompt))
            sys.stdout.flush()
        return stdin_instance.readline_with_prompt(str(prompt)).rstrip('\n')
    def start(self):
        _old_stdout, _old_stderr, _old_stdin = sys.stdout, sys.stderr, sys.stdin
        _old_sys_path = list(sys.path)
        if self.original_builtin_input is None:
            self.original_builtin_input = builtins.input
        user_code_execution_completed = False
        try: _old_cwd = os.getcwd()
        except OSError: _old_cwd = None
        try:
            script_path = self.main_script_bdb_key
            script_directory = os.path.dirname(script_path)
            if script_directory and (not _old_cwd or os.path.normcase(script_directory) != os.path.normcase(_old_cwd)):
                try: os.chdir(script_directory)
                except OSError: pass
            if script_directory and script_directory not in sys.path:
                sys.path.insert(0, script_directory)
            original_argv = list(sys.argv)
            sys.argv = [script_path] + self.script_args
            current_stdout = StdOutRedirect(self.conn_to_gui)
            current_stderr = StdErrRedirect(self.conn_to_gui)
            self.redirected_stdin_instance = StdInRedirect(self.conn_to_gui)
            sys.stdout = current_stdout
            sys.stderr = current_stderr
            sys.stdin = self.redirected_stdin_instance
            bound_patched_input = partial(self._patched_input_with_stdin_instance, self.redirected_stdin_instance)
            builtins.input = bound_patched_input
            globals_dict = {'__name__': '__main__', '__file__': self.main_script_bdb_key}
            with open(self.main_script_bdb_key, 'rb') as f_src: 
                src = f_src.read()
            code = compile(src, self.main_script_bdb_key, 'exec')
            self.runctx(code, globals_dict, globals_dict)
            user_code_execution_completed = True                                                
        except SystemExit:
            user_code_execution_completed = True                                                             
            try: 
                if self.conn_to_gui and not self.conn_to_gui.closed:
                    if hasattr(sys.stdout, 'flush') and sys.stdout is current_stdout: sys.stdout.flush()
                    if hasattr(sys.stderr, 'flush') and sys.stderr is current_stderr: sys.stderr.flush()
                    self.conn_to_gui.send(('stdout', f"Script terminated with SystemExit\n"))
            except (OSError, EOFError, BrokenPipeError): pass
        except BdbQuit:
            user_code_execution_completed = True                                                     
            pass
        except EOFError as eof: 
            user_code_execution_completed = True                                               
            try: 
                if self.conn_to_gui and not self.conn_to_gui.closed:
                    if hasattr(sys.stderr, 'flush') and sys.stderr is current_stderr: sys.stderr.flush()
                    self.conn_to_gui.send(('stderr', f"Input interrupted or connection lost: {eof}\n"))
            except (OSError, EOFError, BrokenPipeError): pass
        except Exception: 
            user_code_execution_completed = True                                       
            tb_str = traceback.format_exc()
            try: 
                if self.conn_to_gui and not self.conn_to_gui.closed:
                    if hasattr(sys.stderr, 'flush') and sys.stderr is current_stderr: sys.stderr.flush()
                    self.conn_to_gui.send(('stderr', f"Unhandled ERROR in backend start():\n{tb_str}"))
            except (OSError, EOFError, BrokenPipeError): pass
        finally:
            if hasattr(sys.stdout, 'flush') and sys.stdout is current_stdout:
                sys.stdout.flush()
            if hasattr(sys.stderr, 'flush') and sys.stderr is current_stderr:
                sys.stderr.flush()
            if user_code_execution_completed:                                                              
                time.sleep(0.25)                                                 
            if self.original_builtin_input is not None:
                builtins.input = self.original_builtin_input
                self.original_builtin_input = None 
            sys.stdout, sys.stderr, sys.stdin = _old_stdout, _old_stderr, _old_stdin
            sys.path = _old_sys_path
            sys.argv = original_argv
            if _old_cwd:
                try: os.chdir(_old_cwd)
                except OSError: pass
            try:
                if self.conn_to_gui and not self.conn_to_gui.closed: 
                    self.conn_to_gui.send(('finished',))
                    self.conn_to_gui.close()
            except (OSError, EOFError, BrokenPipeError):
                 pass
            self.redirected_stdin_instance = None
class DebuggerApp:
    def __init__(self, parent, main_app_ref=None):
        self.parent = parent
        self.main_app_ref = main_app_ref
        self.main_frame = parent
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_pane = ttk.PanedWindow(self.main_frame, orient='horizontal')
        self.main_pane.grid(row=0, column=0, sticky='nsew')
        self.left_pane = ttk.PanedWindow(self.main_pane, orient='vertical')
        self.main_pane.add(self.left_pane, weight=2)
        self.notebook = CustomNotebook(self.left_pane, main_app_ref=self.main_app_ref)
        self.left_pane.add(self.notebook, weight=3)
        self.console_nb = ttk.Notebook(self.left_pane)
        self.left_pane.add(self.console_nb, weight=1)
        self.output_panel = ConsolePanel(self.console_nb, app_ref=self)
        self.console_nb.add(self.output_panel, text='Output/Input')
        self.right_pane = ttk.PanedWindow(self.main_pane, orient='vertical')
        self.main_pane.add(self.right_pane, weight=1)
        self.inspector = VariablesPanel(self.right_pane)
        self.right_pane.add(self.inspector, weight=1)
        self.stack = StackPanel(self.right_pane)
        self.right_pane.add(self.stack, weight=1)
        self.dbg_proc = None
        self.dbg_conn = None
        self.on_breakpoint_hit = None
        self.on_finished = None
        self.interactive_exec_callback = None
        self.parent.after(100, self._poll_debugger)
    def _create_pipe_and_start_backend(self, script_path, breakpoints, script_args=None):
        if self.dbg_conn is not None: return False
        parent_conn, child_conn = Pipe()
        backend = DebuggerBackend(script_path, child_conn, breakpoints=breakpoints, script_args=script_args)
        self.dbg_proc = Process(target=backend.start, args=(), name=f"DebuggerBackend-{os.path.basename(script_path)}")
        self.dbg_proc.daemon = True
        try:
             self.dbg_proc.start(); self.dbg_conn = parent_conn; time.sleep(0.25); return True
        except Exception: traceback.print_exc(); return False
    def _get_script_and_breakpoints_from_active_tab(self):
        if not hasattr(self.notebook, 'select') or not self.notebook.winfo_exists(): return None, None
        try:
            cur_tab_id = self.notebook.select()
            if not cur_tab_id: messagebox.showwarning('Debugger', 'No file selected.'); return None, None
            editor_widget = self.notebook.nametowidget(cur_tab_id)
            if not isinstance(editor_widget, CodeEditor): raise tk.TclError("Selected widget is not a CodeEditor")
        except tk.TclError: messagebox.showerror('Debugger Error', 'Could not find selected editor widget.'); return None, None
        script_to_run = getattr(editor_widget, 'filepath', None)
        if not script_to_run: messagebox.showwarning('Debugger', 'Selected file has no path. Please save it first.'); return None, None
        breakpoints = editor_widget.breakpoints
        return script_to_run, breakpoints
    def run_project(self, script_args=None):
        if self.main_app_ref and hasattr(self.main_app_ref, 'output_panel_manager')\
           and hasattr(self.main_app_ref.output_panel_manager, 'clear_output_by_type'):                           
            self.main_app_ref.output_panel_manager.clear_output_by_type('debugger_console')
        elif hasattr(self.output_panel, 'clear'):                                          
             self.output_panel.clear()
        script_to_run, breakpoints = self._get_script_and_breakpoints_from_active_tab()
        if not script_to_run: return False
        if self._create_pipe_and_start_backend(script_to_run, breakpoints, script_args=script_args):
            self.dbg_conn.send(('continue', None)); return True
        else: messagebox.showerror("Run Error", "Failed to start the debugger process."); return False
    def step_next(self, script_args=None):
        if not self.dbg_conn:
            if self.main_app_ref and hasattr(self.main_app_ref, 'output_panel_manager')\
               and hasattr(self.main_app_ref.output_panel_manager, 'clear_output_by_type'):
                self.main_app_ref.output_panel_manager.clear_output_by_type('debugger_console')
            elif hasattr(self.output_panel, 'clear'): self.output_panel.clear()
            script_to_run, breakpoints = self._get_script_and_breakpoints_from_active_tab()
            if not script_to_run: return False
            if self._create_pipe_and_start_backend(script_to_run, breakpoints, script_args=script_args): return True
            else: messagebox.showerror("Step Error", "Failed to start the debugger process."); return False
        else: self.dbg_conn.send(('next', None)); return True
    def step_into(self, script_args=None):
        if not self.dbg_conn:
            if self.main_app_ref and hasattr(self.main_app_ref, 'output_panel_manager')\
               and hasattr(self.main_app_ref.output_panel_manager, 'clear_output_by_type'):
                self.main_app_ref.output_panel_manager.clear_output_by_type('debugger_console')
            elif hasattr(self.output_panel, 'clear'): self.output_panel.clear()
            script_to_run, breakpoints = self._get_script_and_breakpoints_from_active_tab()
            if not script_to_run: return False
            if self._create_pipe_and_start_backend(script_to_run, breakpoints, script_args=script_args): return True
            else: messagebox.showerror("Step Error", "Failed to start the debugger process."); return False
        else: self.dbg_conn.send(('step', None)); return True
    def step_out(self, script_args=None):
        if not self.dbg_conn:
            if self.main_app_ref and hasattr(self.main_app_ref, 'output_panel_manager')\
               and hasattr(self.main_app_ref.output_panel_manager, 'clear_output_by_type'):
                self.main_app_ref.output_panel_manager.clear_output_by_type('debugger_console')
            elif hasattr(self.output_panel, 'clear'): self.output_panel.clear()
            script_to_run, breakpoints = self._get_script_and_breakpoints_from_active_tab()
            if not script_to_run: return False
            if self._create_pipe_and_start_backend(script_to_run, breakpoints, script_args=script_args): return True
            else: messagebox.showerror("Step Error", "Failed to start the debugger process."); return False
        else: self.dbg_conn.send(('return', None)); return True
    def continue_execution(self):
        if self.dbg_conn: self.dbg_conn.send(('continue', None)); return True
        else: return False
    def stop_execution(self):
        if self.dbg_proc and self.dbg_proc.is_alive():
            try: self.dbg_proc.terminate(); self.dbg_proc.join(timeout=0.5)
            except Exception: pass
        if self.dbg_conn:
            try: self.dbg_conn.close()
            except Exception: pass
        self.dbg_conn = None; self.dbg_proc = None
    def evaluate_expression(self, expr: str):
        if self.dbg_conn: self.dbg_conn.send(('eval', expr)); return True
        else: return False
    def evaluate_expression_from_window(self, code_to_exec, callback):
        if self.dbg_conn:
            self.interactive_exec_callback = callback
            self.dbg_conn.send(('execute_code_interactive', code_to_exec))
            return True
        self.interactive_exec_callback = None; return False
    def _poll_debugger(self):
        process_died = False; connection_closed = False; msg = None
        if self.dbg_proc and not self.dbg_proc.is_alive() and self.dbg_conn:
            process_died = True; connection_closed = True
        if self.dbg_conn or process_died:
            can_poll = self.dbg_conn and not process_died; has_message = False
            if can_poll:
                 try: has_message = self.dbg_conn.poll(timeout=0)
                 except (OSError, EOFError, BrokenPipeError): connection_closed = True; has_message = False
            if has_message or process_died or connection_closed:
                if process_died or connection_closed:
                    if not has_message: msg = ('finished',) 
                if has_message and self.dbg_conn:
                     try: msg = self.dbg_conn.recv()
                     except (EOFError, OSError, BrokenPipeError): msg = ('finished',); connection_closed = True
                if msg:
                    kind, *rest = msg
                    if kind == 'line':
                        fname, ln = rest
                        if self.on_breakpoint_hit: self.on_breakpoint_hit(fname, ln)
                    elif kind == 'stack':
                         stack_data = rest[0] if rest else []
                         if self.stack.winfo_exists(): self.stack.update_stack(stack_data)
                    elif kind == 'variables':
                         var_data = rest[0] if rest else {'locals':{}, 'globals':{}}
                         if self.inspector.winfo_exists(): self.inspector.update_variables(var_data.get('locals'), var_data.get('globals'))
                    elif kind == 'stdout':
                        text, = rest
                        if self.output_panel.winfo_exists(): self.output_panel.write(text)
                    elif kind == 'stderr':
                        text, = rest
                        if self.output_panel.winfo_exists(): self.output_panel.write(text)
                    elif kind == 'gui_input_request_with_prompt':
                        input_id, prompt_from_backend = rest
                        self.parent.after_idle(self.show_gui_input_dialog, input_id, "Script Input", prompt_from_backend)
                    elif kind == 'gui_input_request': 
                        input_id = rest[0]
                        prompt_for_dialog = "Script requires input (check console for exact prompt):"
                        self.parent.after_idle(self.show_gui_input_dialog, input_id, "Script Input", prompt_for_dialog)
                    elif kind == 'eval_result':
                        expr, val, success_flag = rest
                        if self.parent.winfo_exists():
                            messagebox.showinfo('Evaluation Result', f"{expr} = {val}", parent=self.parent)
                    elif kind == 'interactive_result':
                        original_code, stdout_val, stderr_val, success, exc_str = rest
                        if self.interactive_exec_callback:
                            try: self.interactive_exec_callback(original_code, stdout_val, stderr_val, success, exc_str)
                            except Exception: pass
                            finally: self.interactive_exec_callback = None
                    elif kind == 'breakpoint_runtime_status': pass 
                    elif kind == 'finished': connection_closed = True
            if connection_closed:
                 if self.dbg_conn:
                     try: self.dbg_conn.close()
                     except Exception: pass
                 self.dbg_conn = None
                 if self.dbg_proc and not process_died:
                      if self.dbg_proc.is_alive():
                           try: self.dbg_proc.terminate(); self.dbg_proc.join(timeout=0.2)
                           except Exception: pass
                 self.dbg_proc = None
                 if self.on_finished: self.on_finished()
        try:
            if self.parent.winfo_exists():
                self.parent.after(100, self._poll_debugger)
        except tk.TclError: pass
    def show_gui_input_dialog(self, input_id, title, prompt_text_for_dialog):
        if not self.parent.winfo_exists():
            if self.dbg_conn: self.dbg_conn.send(('gui_input_response', input_id, '\n'))
            return
        dialog_parent = self.main_app_ref.root if self.main_app_ref and hasattr(self.main_app_ref, 'root') and self.main_app_ref.root.winfo_exists() else self.parent
        actual_prompt = prompt_text_for_dialog if prompt_text_for_dialog else "Enter value:"
        dialog = InputDialog(dialog_parent, title=title, prompt_text=actual_prompt)
        user_input = dialog.result
        if self.dbg_conn:
            if user_input is not None:
                self.dbg_conn.send(('gui_input_response', input_id, user_input + '\n'))
            else:
                self.dbg_conn.send(('gui_input_response', input_id, '\n'))
        if self.main_app_ref and hasattr(self.main_app_ref, 'get_active_editor_text_widget'):
            active_text_widget = self.main_app_ref.get_active_editor_text_widget()
            if active_text_widget and active_text_widget.winfo_exists():
                active_text_widget.focus_set()
