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
import threading
import queue
from functools import partial
from gui.editor import CodeEditor
from gui.console import ConsolePanel
from gui.inspector import VariablesPanel
from gui.stack import StackPanel
from gui.custom_notebook import CustomNotebook
from gui.input_dialog import InputDialog

def _backend_process_main(script_path, child_cmd_conn, child_io_conn, breakpoints, script_args):
    # Funzione wrapper essenziale per il multiprocessing
    backend = DebuggerBackend(
        script_path_from_gui=script_path,
        cmd_conn=child_cmd_conn,
        io_conn=child_io_conn,
        breakpoints=breakpoints,
        script_args=script_args
    )
    backend.start()

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
    def __init__(self, io_conn_obj):
        self.conn = io_conn_obj
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
    def __init__(self, script_path_from_gui, cmd_conn, io_conn, breakpoints=None, script_args=None):
        super().__init__()
        self.main_script_path = self.canonic(script_path_from_gui)
        self.conn_to_gui = cmd_conn
        self.io_conn_to_gui = io_conn
        self.script_args = script_args if script_args is not None else []

        self._gui_cmd_queue = queue.Queue()
        self._user_line_state_sent_this_pause = False
        self._startup_continue_consumed = False

        self._runtime_stop_event = threading.Event()
        self._runtime_thread = None
        self._runtime_bp_lock = threading.RLock()

        self.dynamic_breakpoints = set()

        self.clear_all_breaks()
        if breakpoints:
            for lineno in breakpoints:
                self.dynamic_breakpoints.add((self.main_script_path, int(lineno)))
                self.set_break(self.main_script_path, int(lineno))

        self.original_builtin_input = None
        self.redirected_stdin_instance = None

    def canonic(self, filename):
        if not filename: return filename
        if filename.startswith("<") and filename.endswith(">"): return filename
        return os.path.normcase(os.path.abspath(filename))

    def _safe_repr(self, v):
        try:
            s = repr(v)
            return s[:200] + "..." if len(s) > 200 else s
        except Exception as e:
            return f"<repr error: {e}>"

    def _get_locals(self, frame):
        return {str(k): self._safe_repr(v) for k, v in frame.f_locals.items() if not str(k).startswith('__')}

    def trace_dispatch(self, frame, event, arg):
        if self.quitting:
            return None

        if event == 'line':
            filename = self.canonic(frame.f_code.co_filename)
            lineno = frame.f_lineno
            
            with self._runtime_bp_lock:
                is_bp = (filename, lineno) in self.dynamic_breakpoints
            
            if is_bp:
                self.set_step()

        res = super().trace_dispatch(frame, event, arg)

        # Mantiene attivo il trace per le funzioni utente
        if res is None and event == 'call':
            filename = self.canonic(frame.f_code.co_filename)
            main_dir = os.path.dirname(self.main_script_path)
            if filename.startswith(main_dir) or filename == self.main_script_path:
                return self.trace_dispatch

        return res

    def set_continue(self):
        self._set_stopinfo(self.botframe, None, -1)

    def set_quit(self):
        self.stopframe = self.botframe
        self.returnframe = None
        self.quitting = True
        sys.settrace(None)

    def user_line(self, frame):
        filename = self.canonic(frame.f_code.co_filename)
        
        # Filtro: Ignora file non del progetto
        if not filename.startswith(os.path.dirname(self.main_script_path)) and filename != self.main_script_path:
            self.set_continue()
            return

        # Consuma il "continue" iniziale automatico
        if not self._startup_continue_consumed:
            self._startup_continue_consumed = True
            is_f5_run = False
            try:
                if not self._gui_cmd_queue.empty():
                    c, a = self._gui_cmd_queue.queue[0]
                    if c == 'continue':
                        self._gui_cmd_queue.get_nowait()
                        is_f5_run = True
            except Exception: pass
            
            with self._runtime_bp_lock:
                is_bp = (filename, frame.f_lineno) in self.dynamic_breakpoints
            
            if is_f5_run and not is_bp and not self.break_here(frame):
                self.set_continue()
                return

        if not self._user_line_state_sent_this_pause:
            try:
                self.conn_to_gui.send(('line', filename, frame.f_lineno))
                
                stack = []
                curr = frame
                while curr:
                    stack.append((curr.f_code.co_filename, curr.f_lineno, curr.f_code.co_name))
                    curr = curr.f_back
                self.conn_to_gui.send(('stack', stack))

                self.conn_to_gui.send(('variables', {'locals': self._get_locals(frame), 'globals': {}}))
            except: pass
            self._user_line_state_sent_this_pause = True

        while True:
            try:
                cmd, arg = self._gui_cmd_queue.get(timeout=0.1)
                
                if cmd == 'step': self._user_line_state_sent_this_pause = False; self.set_step(); return
                elif cmd == 'next': self._user_line_state_sent_this_pause = False; self.set_next(frame); return
                elif cmd == 'continue': self._user_line_state_sent_this_pause = False; self.set_continue(); return
                elif cmd == 'return': self._user_line_state_sent_this_pause = False; self.set_return(frame); return
                elif cmd == 'quit': self.set_quit(); return
                elif cmd == 'eval':
                    try:
                        res = eval(arg, frame.f_globals, frame.f_locals)
                        self.conn_to_gui.send(('eval_result', arg, self._safe_repr(res), True))
                    except Exception as e:
                        self.conn_to_gui.send(('eval_result', arg, str(e), False))
                elif cmd == 'execute_code_interactive':
                    try:
                        exec(arg, frame.f_globals, frame.f_locals)
                        self.conn_to_gui.send(('interactive_result', arg, "Executed successfully", "", True, ""))
                    except Exception as e:
                        self.conn_to_gui.send(('interactive_result', arg, "", str(e), False, str(e)))
            except queue.Empty:
                continue

    def _runtime_command_loop(self):
        while not self._runtime_stop_event.is_set():
            try:
                if not self.conn_to_gui.poll(0.05): continue
                msg = self.conn_to_gui.recv()
                if not msg: continue
                
                cmd = msg[0]
                arg = msg[1] if len(msg) > 1 else None

                if cmd == 'add_breakpoint_runtime':
                    fname, fline = arg
                    canon_path = self.canonic(fname)
                    with self._runtime_bp_lock:
                        self.dynamic_breakpoints.add((canon_path, int(fline)))
                        self.set_break(canon_path, int(fline))
                
                elif cmd == 'remove_breakpoint_runtime':
                    fname, fline = arg
                    canon_path = self.canonic(fname)
                    with self._runtime_bp_lock:
                        self.dynamic_breakpoints.discard((canon_path, int(fline)))
                        self.clear_break(canon_path, int(fline))
                
                else:
                    self._gui_cmd_queue.put((cmd, arg))
            except: break

    def start(self):
        _old_stdout, _old_stderr, _old_stdin = sys.stdout, sys.stderr, sys.stdin
        _old_cwd = os.getcwd()
        if self.original_builtin_input is None: self.original_builtin_input = builtins.input
        
        try:
            # === FIX ENVIRONMENT (SOLUZIONE DEFINITIVA) ===
            # Cambia la directory corrente in quella dello script da debuggare
            # Così SQLAlchemy trova .env e database locali.
            script_dir = os.path.dirname(self.main_script_path)
            if os.path.exists(script_dir):
                try:
                    os.chdir(script_dir)
                    if script_dir not in sys.path:
                        sys.path.insert(0, script_dir)
                except OSError: pass
            # ===============================================

            sys.argv = [self.main_script_path] + self.script_args
            sys.stdout = StdOutRedirect(self.io_conn_to_gui)
            sys.stderr = StdErrRedirect(self.io_conn_to_gui)
            self.redirected_stdin_instance = StdInRedirect(self.io_conn_to_gui)
            sys.stdin = self.redirected_stdin_instance
            builtins.input = lambda p="": self.redirected_stdin_instance.readline_with_prompt(p).rstrip('\n')

            self._runtime_stop_event.clear()
            self._runtime_thread = threading.Thread(target=self._runtime_command_loop, daemon=True)
            self._runtime_thread.start()

            with open(self.main_script_path, 'rb') as f:
                code_obj = compile(f.read(), self.main_script_path, 'exec')
            
            globals_dict = {'__name__': '__main__', '__file__': self.main_script_path}

            threading.settrace(self.trace_dispatch)
            self.runctx(code_obj, globals_dict, globals_dict)

        except (BdbQuit, SystemExit): pass
        except Exception:
            try: self.conn_to_gui.send(('stderr', traceback.format_exc()))
            except: pass
        finally:
            self._runtime_stop_event.set()
            sys.stdout, sys.stderr, sys.stdin = _old_stdout, _old_stderr, _old_stdin
            builtins.input = self.original_builtin_input
            
            # Ripristina CWD
            try: os.chdir(_old_cwd)
            except: pass

            time.sleep(0.2)
            try:
                self.conn_to_gui.send(('finished',))
                self.conn_to_gui.close()
            except: pass

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
        self.io_conn = None
        self.on_breakpoint_hit = None
        self.on_finished = None
        self.interactive_exec_callback = None
        self._eval_callbacks = {}
        self.parent.after(100, self._poll_debugger)
        
    def add_breakpoint_runtime(self, bp_file: str, bp_line: int):
        if not self.dbg_conn: return False
        try:
            self.dbg_conn.send(('add_breakpoint_runtime', (bp_file, int(bp_line))))
            return True
        except Exception: return False

    def remove_breakpoint_runtime(self, bp_file: str, bp_line: int):
        if not self.dbg_conn: return False
        try:
            self.dbg_conn.send(('remove_breakpoint_runtime', (bp_file, int(bp_line))))
            return True
        except Exception: return False        
            
    def _create_pipe_and_start_backend(self, script_path, breakpoints, script_args=None):
        if self.dbg_conn is not None:
            return False

        parent_cmd_conn, child_cmd_conn = Pipe()
        parent_io_conn, child_io_conn = Pipe()

        # IMPORTANTISSIMO: NON daemon.
        # Flask/Werkzeug (debug=True) può creare processi (reloader) e un processo daemon non può avere figli.
        self.dbg_proc = Process(
            target=_backend_process_main,
            args=(script_path, child_cmd_conn, child_io_conn, breakpoints, script_args),
            name=f"DebuggerBackend-{os.path.basename(script_path)}",
            daemon=False
        )

        try:
            self.dbg_proc.start()

            # Nel processo padre chiudiamo i riferimenti "child"
            child_cmd_conn.close()
            child_io_conn.close()

            self.dbg_conn = parent_cmd_conn
            self.io_conn = parent_io_conn

            time.sleep(0.25)
            return True

        except Exception:
            traceback.print_exc()
            try:
                parent_cmd_conn.close()
                parent_io_conn.close()
            except Exception:
                pass
            try:
                child_cmd_conn.close()
                child_io_conn.close()
            except Exception:
                pass
            self.dbg_proc = None
            return False
        
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
        if self.main_app_ref and hasattr(self.main_app_ref, 'output_panel_manager') and hasattr(self.main_app_ref.output_panel_manager, 'clear_output_by_type'):                           
            self.main_app_ref.output_panel_manager.clear_output_by_type('debugger_console')
        elif hasattr(self.output_panel, 'clear'): self.output_panel.clear()
        script_to_run, breakpoints = self._get_script_and_breakpoints_from_active_tab()
        if not script_to_run: return False
        if self._create_pipe_and_start_backend(script_to_run, breakpoints, script_args=script_args):
            self.dbg_conn.send(('continue', None)); return True
        else: messagebox.showerror("Run Error", "Failed to start the debugger process."); return False

    def step_next(self, script_args=None):
        if not self.dbg_conn:
            if self.main_app_ref and hasattr(self.main_app_ref, 'output_panel_manager') and hasattr(self.main_app_ref.output_panel_manager, 'clear_output_by_type'):
                self.main_app_ref.output_panel_manager.clear_output_by_type('debugger_console')
            elif hasattr(self.output_panel, 'clear'): self.output_panel.clear()
            script_to_run, breakpoints = self._get_script_and_breakpoints_from_active_tab()
            if not script_to_run: return False
            if self._create_pipe_and_start_backend(script_to_run, breakpoints, script_args=script_args): return True
            else: messagebox.showerror("Step Error", "Failed to start the debugger process."); return False
        else: self.dbg_conn.send(('next', None)); return True

    def step_into(self, script_args=None):
        if not self.dbg_conn:
            if self.main_app_ref and hasattr(self.main_app_ref, 'output_panel_manager') and hasattr(self.main_app_ref.output_panel_manager, 'clear_output_by_type'):
                self.main_app_ref.output_panel_manager.clear_output_by_type('debugger_console')
            elif hasattr(self.output_panel, 'clear'): self.output_panel.clear()
            script_to_run, breakpoints = self._get_script_and_breakpoints_from_active_tab()
            if not script_to_run: return False
            if self._create_pipe_and_start_backend(script_to_run, breakpoints, script_args=script_args): return True
            else: messagebox.showerror("Step Error", "Failed to start the debugger process."); return False
        else: self.dbg_conn.send(('step', None)); return True

    def step_out(self, script_args=None):
        if not self.dbg_conn:
            if self.main_app_ref and hasattr(self.main_app_ref, 'output_panel_manager') and hasattr(self.main_app_ref.output_panel_manager, 'clear_output_by_type'):
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
        if self.io_conn:
            try: self.io_conn.close()
            except Exception: pass
        self.dbg_conn = None; self.dbg_proc = None; self.io_conn = None

    def evaluate_expression(self, expr: str):
        if self.dbg_conn: self.dbg_conn.send(('eval', expr)); return True
        else: return False
        
    def evaluate_expression_async(self, expr: str, callback):
        if not self.dbg_conn: return False
        expr = (expr or "").strip()
        if not expr: return False
        try:
            if expr not in self._eval_callbacks: self._eval_callbacks[expr] = []
            self._eval_callbacks[expr].append(callback)
            self.dbg_conn.send(('eval', expr))
            return True
        except Exception: return False

    def add_watch(self, expr: str):
        expr = (expr or "").strip()
        if not expr: return False
        try:
            if self.inspector and hasattr(self.inspector, "add_watch"):
                ok = self.inspector.add_watch(expr)
                if ok and self.main_app_ref and getattr(self.main_app_ref, "paused", False):
                    self.parent.after_idle(self._refresh_watch_values)
                return ok
        except Exception: return False
        return False

    def _refresh_watch_values(self):
        if not self.dbg_conn or not (self.main_app_ref and getattr(self.main_app_ref, "paused", False)): return
        if not (self.inspector and hasattr(self.inspector, "get_watch_expressions")): return
        try: exprs = list(self.inspector.get_watch_expressions() or [])
        except Exception: exprs = []
        for expr in exprs:
            def _mk_cb(e):
                return lambda _expr, val, success: (
                    self.inspector.update_watch_value(e, val, success)
                    if self.inspector and hasattr(self.inspector, "update_watch_value") else None
                )
            self.evaluate_expression_async(expr, _mk_cb(expr))

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
                         try: self._refresh_watch_values()
                         except Exception: pass
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
                    elif kind == "eval_expression_result":
                        req_id, text = rest
                        if self.main_app_ref and hasattr(self.main_app_ref, "_on_eval_expression_result"):
                            self.main_app_ref._on_eval_expression_result(req_id, text)
                    elif kind == 'eval_result':
                        expr, val, success_flag = rest
                        cb = None
                        try:
                            if expr in self._eval_callbacks and self._eval_callbacks[expr]:
                                cb = self._eval_callbacks[expr].pop(0)
                                if not self._eval_callbacks[expr]: del self._eval_callbacks[expr]
                        except Exception: cb = None
                        if cb:
                            try: cb(expr, val, bool(success_flag))
                            except Exception: pass
                        else:
                            if self.parent.winfo_exists():
                                messagebox.showinfo('Evaluation Result', f"{expr} = {val}", parent=self.parent)
                    elif kind == 'interactive_result':
                        original_code, stdout_val, stderr_val, success, exc_str = rest
                        if self.interactive_exec_callback:
                            try: self.interactive_exec_callback(original_code, stdout_val, stderr_val, success, exc_str)
                            except Exception: pass
                            finally: self.interactive_exec_callback = None
                    elif kind == 'breakpoint_runtime_status':
                        try:
                            status, bp_file, bp_line, msg = rest[0]
                            if self.output_panel and self.output_panel.winfo_exists():
                                self.output_panel.write(f"[runtime bp] {status} {bp_file}:{bp_line} {msg or ''}\n")
                        except Exception: pass 
                    elif kind == 'finished': connection_closed = True

            if self.io_conn and self.dbg_proc and self.dbg_proc.is_alive():
                try:
                    while self.io_conn.poll(timeout=0):
                        msg2 = self.io_conn.recv()
                        if not msg2: continue
                        kind2, *rest2 = msg2
                        if kind2 == 'stdout':
                            (text,) = rest2
                            if self.output_panel.winfo_exists(): self.output_panel.write(text)
                        elif kind2 == 'stderr':
                            (text,) = rest2
                            if self.output_panel.winfo_exists(): self.output_panel.write(text)
                        elif kind2 == 'breakpoint_runtime_status':
                            try:
                                status, bp_file, bp_line, msg = rest2[0]
                                if self.output_panel and self.output_panel.winfo_exists():
                                    self.output_panel.write(f"[runtime bp] {status} {bp_file}:{bp_line} {msg or ''}\n")
                            except Exception: pass
                        elif kind2 == 'gui_input_request_with_prompt':
                            input_id, prompt_from_backend = rest2
                            self.parent.after_idle(self.show_gui_input_dialog, input_id, "Script Input", prompt_from_backend)
                        elif kind2 == 'gui_input_request':
                            input_id = rest2[0] if rest2 else None
                            prompt_for_dialog = "Script requires input (check console for exact prompt):"
                            if input_id is not None:
                                self.parent.after_idle(self.show_gui_input_dialog, input_id, "Script Input", prompt_for_dialog)
                except (EOFError, OSError, BrokenPipeError): pass

            if connection_closed:
                 if self.dbg_conn:
                     try: self.dbg_conn.close()
                     except Exception: pass
                 self.dbg_conn = None
                 if self.io_conn:
                     try: self.io_conn.close()
                     except Exception: pass
                 self.io_conn = None
                 if self.dbg_proc and not process_died:
                      if self.dbg_proc.is_alive():
                           try: self.dbg_proc.terminate(); self.dbg_proc.join(timeout=0.2)
                           except Exception: pass
                 self.dbg_proc = None
                 if self.on_finished: self.on_finished()
        try:
            if self.parent.winfo_exists(): self.parent.after(100, self._poll_debugger)
        except tk.TclError: pass

    def show_gui_input_dialog(self, input_id, title, prompt_text_for_dialog):
        if not self.parent.winfo_exists():
            if self.io_conn: self.io_conn.send(('gui_input_response', input_id, '\n'))
            return
        dialog_parent = self.main_app_ref.root if self.main_app_ref and hasattr(self.main_app_ref, 'root') and self.main_app_ref.root.winfo_exists() else self.parent
        actual_prompt = prompt_text_for_dialog if prompt_text_for_dialog else "Enter value:"
        dialog = InputDialog(dialog_parent, title=title, prompt_text=actual_prompt)
        user_input = dialog.result
        if self.io_conn:
            if user_input is not None:
                self.io_conn.send(('gui_input_response', input_id, user_input + '\n'))
            else:
                self.io_conn.send(('gui_input_response', input_id, '\n'))
        if self.main_app_ref and hasattr(self.main_app_ref, 'get_active_editor_text_widget'):
            active_text_widget = self.main_app_ref.get_active_editor_text_widget()
            if active_text_widget and active_text_widget.winfo_exists():
                active_text_widget.focus_set()