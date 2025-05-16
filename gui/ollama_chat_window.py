import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import urllib.parse
import urllib.request
import json
import re
import uuid
import os
from threading import Thread
import traceback
from pygments.formatters import HtmlFormatter               
from pygments import highlight               
from pygments.lexers import get_lexer_by_name, TextLexer               
import markdown               
try:
    from gui.themes import THEMES as APP_THEMES
    from gui.config_defaults import DEFAULT_CONFIG
    from gui.editor import CodeEditor
except ImportError:
    print("Warning: Could not import APP_THEMES, DEFAULT_CONFIG, CodeEditor from gui. Using fallback values.")
    APP_THEMES = {
        "light": {"editor_bg": "white", "editor_fg": "black", "name": "light", "app_bg": "#F0F0F0", "console_fg": "#d4d4d4", "gutter_bg":"#f0f0f0", "breakpoint_line_editor_bg":"#FFC0CB", "syntax":{}, "console_bg": "#1e1e1e"},
        "dark": {"editor_bg": "#2b2b2b", "editor_fg": "#A9B7C6", "name": "dark", "app_bg": "#2B2B2B", "console_fg": "#d4d4d4", "gutter_bg":"#313335", "breakpoint_line_editor_bg":"#7A3737", "syntax":{}, "console_bg": "#1e1e1e"}
    }
    DEFAULT_CONFIG = {"chat_ai_config": {
        "api_url": "http://localhost:11434", "selected_model": "",
        "include_output": False, "include_code": False
    }}
    class CodeEditor: pass              
class MarkdownDisplayChatWindow(tk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.is_tkinterweb = False
        try:
            from tkinterweb import HtmlFrame               
            self.html_label = HtmlFrame(self, messages_enabled=False, javascript_enabled=True,
                                        on_link_click=self.on_link_clicked)
            self.html_label.pack(fill="both", expand=True)
            self.is_tkinterweb = True
        except ImportError:
            self.html_label = tk.Text(self, wrap="word", state="disabled", bg="lightgrey", relief="sunken", borderwidth=1)
            self.html_label.pack(fill="both", expand=True)
            if master and master.winfo_exists():
                 messagebox.showwarning("TkinterWeb Not Found",
                                       "tkinterweb library not installed. Chat display will be basic text.",
                                       parent=master.winfo_toplevel())
        self._create_context_menu()
    def _create_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self._copy_selection)
        self.context_menu.add_command(label="Select All", command=self._select_all_html_content)
        self.html_label.bind("<Button-3>", self._show_context_menu)
        if not self.is_tkinterweb:                             
            self.html_label.bind("<Control-c>", lambda e: self._copy_selection())
            self.html_label.bind("<Control-C>", lambda e: self._copy_selection())
            self.html_label.bind("<Control-a>", lambda e: self._select_all_html_content())
            self.html_label.bind("<Control-A>", lambda e: self._select_all_html_content())
    def _show_context_menu(self, event):
        can_copy = False
        if self.is_tkinterweb:
            can_copy = True                                                  
        else:          
            try:
                if self.html_label.tag_ranges(tk.SEL):
                    can_copy = True
            except tk.TclError:
                pass                    
        self.context_menu.entryconfigure("Copy", state=tk.NORMAL if can_copy else tk.DISABLED)
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
    def _copy_selection(self):
        if not self.winfo_exists(): return
        if self.is_tkinterweb:
            try:
                selected_text_js = self.html_label.evaluate_javascript("window.getSelection().toString();")
                if selected_text_js:
                    self.clipboard_clear()
                    self.clipboard_append(selected_text_js)
                    messagebox.showinfo("Copied", "Selected text copied to clipboard!", parent=self.winfo_toplevel())
                else:
                    messagebox.showinfo("Copy", "No text selected in the AI output.", parent=self.winfo_toplevel())
            except Exception as e:
                 messagebox.showwarning("Copy", f"Could not copy selection from AI output. Please use Ctrl+C.\nError: {e}", parent=self.winfo_toplevel())
        else:          
            try:
                if self.html_label.tag_ranges(tk.SEL):
                    selected_text = self.html_label.get(tk.SEL_FIRST, tk.SEL_LAST)
                    self.clipboard_clear()
                    self.clipboard_append(selected_text)
            except tk.TclError:
                 messagebox.showinfo("Copy", "No text selected in the AI output.", parent=self.winfo_toplevel())
        return "break"
    def _select_all_html_content(self):
        if not self.winfo_exists(): return
        if self.is_tkinterweb:
            try:
                self.html_label.evaluate_javascript(
                    "var body = document.body, range, sel;"
                    "if (document.createRange && window.getSelection) {"
                    "    range = document.createRange();"
                    "    sel = window.getSelection();"
                    "    sel.removeAllRanges();"
                    "    try {"
                    "        range.selectNodeContents(body);"
                    "        sel.addRange(range);"
                    "    } catch (e) {"
                    "        range.selectNode(body);"
                    "        sel.addRange(range);"
                    "    }"
                    "} else if (document.body.createTextRange) {"
                    "    range = document.body.createTextRange();"
                    "    range.moveToElementText(body);"
                    "    range.select();"
                    "}"
                )
            except Exception as e:
                messagebox.showwarning("Select All", f"Could not select all content in AI output.\nError: {e}", parent=self.winfo_toplevel())
        else:          
            try:
                self.html_label.config(state="normal")                                  
                self.html_label.tag_add(tk.SEL, "1.0", tk.END)
                self.html_label.mark_set(tk.INSERT, "1.0")
                self.html_label.see(tk.INSERT)
            except tk.TclError:
                pass
            finally:
                if not self.is_tkinterweb: self.html_label.config(state="disabled")                          
        return "break"
    def set_html(self, html_text):
        if not self.winfo_exists(): return
        if hasattr(self.html_label, 'load_html'):
            try:
                if self.html_label.winfo_exists(): self.html_label.load_html(html_text)
            except Exception:
                if hasattr(self.html_label, 'winfo_exists') and self.html_label.winfo_exists():
                    try:
                        self.html_label.config(state="normal")
                        self.html_label.delete("1.0", tk.END)
                        self.html_label.insert(tk.END, f"Error rendering HTML.\nRaw content:\n{html_text[:500]}...")
                        if not self.is_tkinterweb: self.html_label.config(state="disabled")
                    except tk.TclError: pass
        elif hasattr(self.html_label, 'config') and self.html_label.winfo_exists():
            try:
                self.html_label.config(state="normal")
                self.html_label.delete("1.0", tk.END)
                self.html_label.insert(tk.END, "HTML rendering disabled.\nShowing raw content:\n" + html_text[:500]+"...")
                if not self.is_tkinterweb: self.html_label.config(state="disabled")
            except tk.TclError: pass
    def on_link_clicked(self, url: str):
        if not self.winfo_exists(): return None
        if url.startswith("copy://"):
            encoded_text_to_copy = url[len("copy://"):]
            try:
                decoded_text_to_copy = urllib.parse.unquote(encoded_text_to_copy)
                self.clipboard_clear()
                self.clipboard_append(decoded_text_to_copy)
                messagebox.showinfo("Copied", "Code copied to clipboard!", parent=self.winfo_toplevel())
            except Exception as e:
                messagebox.showerror("Copy Error", f"Failed to copy: {e}", parent=self.winfo_toplevel())
            return None
        elif url.startswith("http://") or url.startswith("https://"):
            print(f"Link clicked (not handled by copy): {url}")
            return url
        return url
class OllamaChatWindow(tk.Toplevel):
    def __init__(self, parent, main_app_ref):
        super().__init__(parent)
        self.main_app_ref = main_app_ref
        self.transient(parent)
        self.title("Ollama AI Chat")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.attributes("-topmost", True)
        chat_cfg_from_main_config = {}
        if self.main_app_ref and hasattr(self.main_app_ref, 'config'):
             chat_cfg_from_main_config = self.main_app_ref.config.get('chat_ai_config', {})
        default_chat_values = DEFAULT_CONFIG.get('chat_ai_config', {
            "api_url": "http://localhost:11434", "selected_model": "",
            "include_output": False, "include_code": False
        })
        self.api_url = chat_cfg_from_main_config.get('api_url', default_chat_values.get('api_url'))
        self.model = chat_cfg_from_main_config.get('selected_model', default_chat_values.get('selected_model'))
        if not self.model:
            messagebox.showerror("Ollama Not Configured",
                                 "Default Ollama model not set. Please configure it via File > Configure Ollama.",
                                 parent=self)
            self.after_idle(self.destroy)
            return
        self.chat_history = []
        self.include_output_var = tk.BooleanVar(value=chat_cfg_from_main_config.get('include_output', default_chat_values.get('include_output')))
        self.code_check_var = tk.BooleanVar(value=chat_cfg_from_main_config.get('include_code', default_chat_values.get('include_code')))
        self.code_check_label_text = tk.StringVar()
        self._build_ui()
        self._apply_theme()
        self.center_window()
    def center_window(self):
        self.update_idletasks()
        parent_w = self.master
        parent_x = parent_w.winfo_rootx() if parent_w.winfo_exists() else 0
        parent_y = parent_w.winfo_rooty() if parent_w.winfo_exists() else 0
        parent_width = parent_w.winfo_width() if parent_w.winfo_exists() else self.winfo_screenwidth()
        parent_height = parent_w.winfo_height() if parent_w.winfo_exists() else self.winfo_screenheight()
        dlg_w = self.winfo_width(); dlg_h = self.winfo_height()
        if dlg_w <= 1: dlg_w = 800
        if dlg_h <= 1: dlg_h = 650
        pos_x = parent_x + (parent_width//2) - (dlg_w//2)
        pos_y = parent_y + (parent_height//2) - (dlg_h//2)
        scr_w = self.winfo_screenwidth(); scr_h = self.winfo_screenheight()
        pos_x = max(0, min(pos_x, scr_w - dlg_w))
        pos_y = max(0, min(pos_y, scr_h - dlg_h))
        self.geometry(f"{dlg_w}x{dlg_h}+{pos_x}+{pos_y}")
    def _build_ui(self):
        self.geometry("800x650")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        top_bar_frame = ttk.Frame(self, padding=(10,10,10,5))
        top_bar_frame.grid(row=0, column=0, sticky="ew")
        context_frame = ttk.Frame(top_bar_frame)
        context_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.output_check = ttk.Checkbutton(context_frame, text="Include IDE Last Output", variable=self.include_output_var)
        self.output_check.pack(side=tk.LEFT, padx=(0,10))
        self.code_check = ttk.Checkbutton(context_frame, textvariable=self.code_check_label_text, variable=self.code_check_var)
        self.code_check.pack(side=tk.LEFT, padx=5)
        self._update_code_check_label()
        if self.main_app_ref and hasattr(self.main_app_ref,'app') and hasattr(self.main_app_ref.app,'notebook') and self.main_app_ref.app.notebook.winfo_exists():
            self.main_app_ref.app.notebook.bind("<<NotebookTabChanged>>", self._on_main_tab_changed_for_label, add="+")
        reset_button = ttk.Button(top_bar_frame, text="Reset Chat", command=self._reset_chat)
        reset_button.pack(side=tk.RIGHT, padx=(10,0))
        md_display_outer_frame = ttk.Frame(self, padding=(10,0,10,5), relief="sunken", borderwidth=1)
        md_display_outer_frame.grid(row=1, column=0, sticky="nsew")
        md_display_outer_frame.grid_columnconfigure(0, weight=1)
        md_display_outer_frame.grid_rowconfigure(0, weight=1)
        self.md_display = MarkdownDisplayChatWindow(md_display_outer_frame)
        self.md_display.grid(row=0, column=0, sticky="nsew")
        input_frame = ttk.Frame(self, padding=(10,5,10,10)); input_frame.grid(row=2,column=0,sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)
        self.entry = tk.Text(input_frame,height=3,relief="solid",borderwidth=1,wrap="word", undo=True)                     
        self.entry.grid(row=0,column=0,sticky="nsew",padx=(0,10))
        self.entry.bind("<Return>",self._on_enter_key); self.entry.bind("<Shift-Return>",lambda e:"break")
        self.send_btn = ttk.Button(input_frame,text="Send",command=self._send_message_from_dialog); self.send_btn.grid(row=0,column=1,sticky="ns")
        self.entry.focus_set()
        self._create_entry_context_menu()
    def _create_entry_context_menu(self):
        self.entry_context_menu = tk.Menu(self.entry, tearoff=0)
        self.entry_context_menu.add_command(label="Cut", command=lambda: self.entry.event_generate("<<Cut>>"))
        self.entry_context_menu.add_command(label="Copy", command=lambda: self.entry.event_generate("<<Copy>>"))
        self.entry_context_menu.add_command(label="Paste", command=lambda: self.entry.event_generate("<<Paste>>"))
        self.entry_context_menu.add_separator()
        self.entry_context_menu.add_command(label="Select All", command=self._entry_select_all)
        self.entry.bind("<Button-3>", self._show_entry_context_menu)
    def _show_entry_context_menu(self, event):
        try:
            has_selection = bool(self.entry.tag_ranges(tk.SEL))
            self.entry_context_menu.entryconfigure("Cut", state=tk.NORMAL if has_selection else tk.DISABLED)
            self.entry_context_menu.entryconfigure("Copy", state=tk.NORMAL if has_selection else tk.DISABLED)
        except tk.TclError:                                                  
            self.entry_context_menu.entryconfigure("Cut", state=tk.DISABLED)
            self.entry_context_menu.entryconfigure("Copy", state=tk.DISABLED)
        try:
            can_paste = bool(self.entry.clipboard_get())
            self.entry_context_menu.entryconfigure("Paste", state=tk.NORMAL if can_paste else tk.DISABLED)
        except tk.TclError:                                       
            self.entry_context_menu.entryconfigure("Paste", state=tk.DISABLED)
        self.entry_context_menu.tk_popup(event.x_root, event.y_root)
    def _entry_select_all(self):
        self.entry.tag_add(tk.SEL, "1.0", tk.END)
        self.entry.mark_set(tk.INSERT, "1.0")
        self.entry.see(tk.INSERT)
        return "break"                              
    def _reset_chat(self):
        if not self.winfo_exists(): return
        if messagebox.askyesno("Reset Chat", "Are you sure you want to clear the chat history?", parent=self):
            self.chat_history = []
            self._add_message_to_display(None, None)
            if self.entry.winfo_exists(): self.entry.delete("1.0", tk.END)
    def _on_main_tab_changed_for_label(self, event=None):
        if self.winfo_exists(): self.after_idle(self._update_code_check_label)
    def _update_code_check_label(self):
        if not self.winfo_exists(): return
        filename = None
        if self.main_app_ref and hasattr(self.main_app_ref, 'app'):
            try:
                if hasattr(self.main_app_ref.app, 'notebook') and self.main_app_ref.app.notebook.winfo_exists():
                    selected_tab_id = self.main_app_ref.app.notebook.select()
                    if selected_tab_id:
                        active_editor_widget = self.main_app_ref.app.notebook.nametowidget(selected_tab_id)
                        if isinstance(active_editor_widget, CodeEditor):
                            if hasattr(active_editor_widget, 'filepath') and active_editor_widget.filepath:
                                filename = os.path.basename(active_editor_widget.filepath)
                            elif hasattr(active_editor_widget, '_temp_name'):
                                filename = active_editor_widget._temp_name
            except (tk.TclError, AttributeError): pass
        self.code_check_label_text.set(f"Include IDE Code ({filename})" if filename else "Include IDE Code (No file)")
    def _on_enter_key(self, event):
        if not (event.state & 1): self._send_message_from_dialog(); return "break"
        return None
    def freeze_interface(self):
        if not self.winfo_exists(): return
        for w in [self.send_btn, self.entry, self.output_check, self.code_check]:
            if w.winfo_exists(): w.config(state="disabled")
        if self.send_btn.winfo_exists(): self.send_btn.config(text="Waiting...")
    def unfreeze_interface(self):
        if not self.winfo_exists(): return
        for w in [self.entry, self.output_check, self.code_check]:
            if w.winfo_exists(): w.config(state="normal")
        if self.send_btn.winfo_exists(): self.send_btn.config(state="normal", text="Send")
    def _get_context_from_ide(self):
        context_parts = []
        ide_context_present = False
        if not self.main_app_ref or not hasattr(self.main_app_ref, 'app'): return ""
        try:
            if self.code_check_var.get():
                nb = self.main_app_ref.app.notebook
                if nb.winfo_exists():
                    sel_id = nb.select()
                    if sel_id:
                        ed = nb.nametowidget(sel_id)
                        if isinstance(ed, CodeEditor) and hasattr(ed, 'text') and ed.text.winfo_exists():
                            code = ed.text.get("1.0", tk.END).strip()
                            if code:
                                fp = getattr(ed, 'filepath', getattr(ed, '_temp_name', 'current_script.py'))
                                fn = os.path.basename(fp) if fp else 'current_script.py'
                                context_parts.append(f"The current IDE code in '{fn}' is:\n```python\n{code}\n```")
                                ide_context_present = True
        except Exception: pass
        try:
            if self.include_output_var.get():
                op = self.main_app_ref.app.output_panel
                if op.winfo_exists() and hasattr(op, 'text') and op.text.winfo_exists():
                    out_txt = op.text.get("1.0", tk.END).strip()
                    lines = out_txt.splitlines()
                    if len(lines) > 20: out_txt = "... (IDE output truncated) ...\n" + "\n".join(lines[-20:])
                    if out_txt:
                        context_parts.append(f"The last execution output from the IDE is:\n```\n{out_txt}\n```")
                        ide_context_present = True
        except Exception: pass
        if not ide_context_present: return ""
        return "Please consider the following context from the Integrated Development Environment (IDE):\n\n" +\
               "\n\n".join(context_parts) + "\n\n"
    def _send_message_from_dialog(self):
        if not self.winfo_exists(): return
        user_query_original = self.entry.get("1.0", "end-1c").strip()
        if not user_query_original: return
        if not self.api_url or not self.model:
            messagebox.showerror("Configuration Error", "Ollama API URL or Model not set.", parent=self)
            return
        self.entry.delete("1.0", tk.END)
        ide_context_string = self._get_context_from_ide()
        prompt_for_api = f"{ide_context_string}Based on the IDE context provided above, please answer the following user query:\n\nUser Query: {user_query_original}" if ide_context_string else user_query_original
        self.chat_history.append({"role": "user", "content": prompt_for_api})
        self._add_message_to_display("user", user_query_original)
        self.freeze_interface()
        Thread(target=self._run_ai_reply_thread_for_dialog, daemon=True).start()
    def _run_ai_reply_thread_for_dialog(self):
        ai_r, err_r = None, None
        try: ai_r = "".join(list(self._ollama_api_call()))
        except Exception as e: err_r = f"[Comm Error: {e}]\n{traceback.format_exc()}"
        if self.winfo_exists(): self.after(0, self._handle_ai_reply_result_for_dialog, ai_r, err_r)
    def _handle_ai_reply_result_for_dialog(self, ai_content, error_msg):
        if not self.winfo_exists(): return
        if error_msg:
            self.chat_history.append({"role": "error", "content": error_msg})
            self._add_message_to_display("error", error_msg)
        elif ai_content is not None:
            self.chat_history.append({"role": "assistant", "content": ai_content})
            self._add_message_to_display("assistant", ai_content)
        self.unfreeze_interface()
    def _ollama_api_call(self):
        payload = {"model": self.model, "messages": self.chat_history, "stream": False}
        data_ = json.dumps(payload).encode("utf-8")
        api_url_full = urllib.parse.urljoin(self.api_url, "/api/chat" if self.api_url.endswith('/') else "/api/chat")
        req = urllib.request.Request(api_url_full, data=data_, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read().decode())
                if "message" in d and "content" in d["message"]: yield d["message"]["content"]
                elif "error" in d: yield f"[API Err ({os.path.basename(api_url_full)}): {d['error']}]"
                else: yield f"[API Err ({os.path.basename(api_url_full)}): Bad format]"
        except urllib.error.HTTPError as e:
            b = e.read().decode(); j = {};
            try: j = json.loads(b)
            except: j = {"error": b}
            yield f"[API HTTP Err ({os.path.basename(api_url_full)}): {e.code} - {j.get('error', 'Unknown')}]"
        except urllib.error.URLError as e: yield f"[API URL Err ({os.path.basename(api_url_full)}): {e.reason}]"
        except TimeoutError: yield f"[API Err ({os.path.basename(api_url_full)}): Timeout(120s)]"
        except Exception as e: yield f"[Chat Call Err ({os.path.basename(api_url_full)}): {e}]"
    def _add_message_to_display(self, role, content_to_display):
        if not self.winfo_exists(): return
        if role is None and content_to_display is None: pass
        rows_html = []
        display_hist_render = []
        for msg_h in self.chat_history:
            actual_content_for_display = msg_h["content"]
            if msg_h["role"] == "user":
                ide_context_header_start = "Please consider the following context from the Integrated Development Environment (IDE):"
                user_query_actual_start_marker = "User Query: "
                if actual_content_for_display.strip().startswith(ide_context_header_start):
                    parts = actual_content_for_display.split(user_query_actual_start_marker, 1)
                    if len(parts) > 1: actual_content_for_display = parts[1].strip()
                    else:
                        context_end_marker_generic = "Based on the IDE context provided above, please answer the following user query:\n\n"
                        idx_generic_marker = actual_content_for_display.find(context_end_marker_generic)
                        if idx_generic_marker != -1:
                             actual_content_for_display = actual_content_for_display[idx_generic_marker + len(context_end_marker_generic):].strip()
            display_hist_render.append({"role": msg_h["role"], "content": actual_content_for_display})
        curr_theme_name = self.main_app_ref.current_theme_name if self.main_app_ref and hasattr(self.main_app_ref, 'current_theme_name') else "light"
        palette = APP_THEMES.get(curr_theme_name, APP_THEMES.get("light", {}))
        if curr_theme_name == "dark":
            usr_bg, usr_fg = palette.get("console_bg", "#2a2a2a"), palette.get("console_fg", "#d4d4d4")
            ai_bg, ai_fg = palette.get("editor_bg", "#3c3c3c"), palette.get("editor_fg", "#a9b7c6")
            err_bg, err_fg = palette.get("breakpoint_line_editor_bg", "#7A3737"), palette.get("editor_fg", "#ffdddd")
        else:
            usr_bg, usr_fg = palette.get("app_bg", "#F0F0F0"), palette.get("editor_fg", "black")
            ai_bg, ai_fg = palette.get("gutter_bg", "#f5f5f5"), palette.get("editor_fg", "#333333")
            err_bg, err_fg = palette.get("breakpoint_line_editor_bg", "#ffdddd"), palette.get("syntax", {}).get('string', "#a31515")
        for msg_item in display_hist_render:
            r, c_for_html = msg_item["role"], msg_item["content"]
            current_bg, current_fg = (usr_bg if r == "user" else (err_bg if r == "error" else ai_bg)),\
                                     (usr_fg if r == "user" else (err_fg if r == "error" else ai_fg))
            html_row_content = self._convert_single_message_to_html(c_for_html, r)
            td_style = f"background:{current_bg};color:{current_fg};border-radius:10px;padding:10px;overflow-wrap:break-word;word-break:break-word;border:1px solid #ccc;"
            if r == "user":
                balloon = f"""<table style="width:100%;table-layout:fixed;margin:10px 0;"><tr>
                               <td style="width:20%;"></td><td style="width:80%;{td_style}">{html_row_content}</td>
                             </tr></table>"""
            else:
                balloon = f"""<table style="width:100%;table-layout:fixed;margin:10px 0;"><tr>
                               <td style="width:80%;{td_style}">{html_row_content}</td><td style="width:20%;"></td>
                             </tr></table>"""
            rows_html.append(balloon)
        py_style = 'monokai' if curr_theme_name == "dark" else 'default'
        body_bg_chat = palette.get('app_bg', 'white'); body_fg_chat = palette.get('editor_fg', 'black')
        py_css = HtmlFormatter(style=py_style, noclasses=True).get_style_defs('.highlight')
        css = f"""<meta name="viewport" content="width=device-width,initial-scale=1"><style>
        body{{margin:0;padding:10px;font-family:Segoe UI,Arial,sans-serif;background-color:{body_bg_chat};color:{body_fg_chat};}}
        table{{border-collapse:separate;border-spacing:0;width:100%;table-layout:fixed;}} td{{vertical-align:top;word-wrap:break-word;}} strong{{color:{body_fg_chat};}}
        .code-container{{border:1px solid #ccc;border-radius:4px;margin:10px 0;background-color:#272822;}}
        .code-header{{display:flex;justify-content:space-between;align-items:center;padding:5px 10px;font-family:monospace;font-size:12px;}}
        .code-lang{{font-weight:bold;}}
        a.copy-btn {{
            text-decoration: none; border:none;padding:3px 8px;cursor:pointer;border-radius:3px;font-size:11px;
            display: inline-block;
        }}
        a.copy-btn:hover{{opacity:0.8;}}
        .highlight{{border-radius:0 0 3px 3px; overflow: hidden;}}
        pre{{padding:10px;font-family:Consolas,monospace;font-size:13px;white-space:pre;word-break:normal;overflow-x:auto;margin:0 !important;background-color:#272822 !important;color:#f8f8f2 !important;border-radius:0 0 4px 4px;}}
        .highlight table {{ width: auto; table-layout: auto; margin:0; border-collapse: collapse; }}
        .highlight td {{ padding: 0px 5px 0px 5px !important; border: none !important; }}
        .highlight .linenos {{ color: #999; background-color: #333; border-right: 1px solid #555 !important; text-align:right; -webkit-user-select: none; -moz-user-select: none; -ms-user-select: none; user-select: none;}}
        .highlight .code {{ width: 100%; }}
        {py_css}
        .think-block{{border:1px dashed #999;padding:5px;margin:5px 0;background-color:{palette.get("gutter_bg", "#f9f9f9")};color:{body_fg_chat};font-style:italic;}}
        .think-block div{{margin-left:20px;}}</style>"""
        full_html = f"<html><head>{css}</head><body>{''.join(rows_html)}</body></html>"
        if self.md_display.winfo_exists(): self.md_display.set_html(full_html)
        if self.winfo_exists():
            self.update_idletasks()
            if hasattr(self.md_display, 'html_label') and self.md_display.html_label.winfo_exists():
                try: self.md_display.html_label.yview_moveto(1.0)
                except tk.TclError: pass
    def _convert_single_message_to_html(self, content: str, role: str) -> str:
        curr_theme_name = self.main_app_ref.current_theme_name if self.main_app_ref and hasattr(self.main_app_ref, 'current_theme_name') else "light"
        palette = APP_THEMES.get(curr_theme_name, APP_THEMES.get("light", {}))
        txt_color = palette.get("editor_fg", "black")
        prefix_html = f"<strong style='color:{txt_color};'>{role.capitalize()}:</strong><br>"
        processed_parts = []
        parts = re.split(r"(```[\s\S]*?```)", content)
        for part in parts:
            if part.startswith("```") and part.endswith("```"):
                code_full = part[3:-3].strip()
                first_line = code_full.split('\n', 1)[0].strip()
                code_hl = code_full
                lang = first_line.lower() if first_line and not any(c in first_line for c in ['\n', ' ']) else "text"
                if lang != "text" and code_full.lower().startswith(lang + '\n'):
                    code_hl = code_full.split('\n', 1)[1] if '\n' in code_full else ''
                elif code_full.lower().startswith(lang) and len(code_full.splitlines())==1 and len(code_full.strip())==len(lang):
                    code_hl = ""
                try: lexer = get_lexer_by_name(lang)
                except Exception: lexer = TextLexer()
                py_style = 'monokai' if curr_theme_name == "dark" else 'default'
                formatter = HtmlFormatter(linenos='table', style=py_style, cssclass="highlight", wrapcode=True)
                hl_code_html = highlight(code_hl, lexer, formatter)
                raw_code_for_copy = code_hl
                uid = str(uuid.uuid4()).replace('-', '')
                if curr_theme_name == 'dark':
                    hdr_fg = palette.get("console_fg", "#FFFFFF")
                    hdr_bg = palette.get("console_bg", "#333333")
                else:
                    hdr_fg = palette.get("console_bg", "#333333")
                    hdr_bg = palette.get("console_fg", "#ECECEC")
                btn_bg_color = "#4CAF50"
                btn_fg_color = "#FFFFFF"
                copy_link_html = f"""<a class="copy-btn"
                                         href="copy://{urllib.parse.quote(raw_code_for_copy)}"
                                         style="background-color:{btn_bg_color};color:{btn_fg_color};"
                                         target="_blank">Copy</a>"""
                code_html = f"""<div class="code-container" id="cc-{uid}">
                                  <div class="code-header" style="background-color:{hdr_bg};color:{hdr_fg};">
                                    <span class="code-lang">{lang.capitalize()}</span>
                                    {copy_link_html}
                                  </div>
                                  <div class="code-body" id="cb-{uid}">{hl_code_html}</div></div>"""
                processed_parts.append(code_html)
            else:
                md_html = markdown.markdown(part, extensions=[])
                processed_parts.append(f"<div style='color:{txt_color};'>{md_html}</div>")
        combined = "".join(processed_parts)
        def replace_think_tags(m):
            inner = m.group(1).strip()
            if not inner: return ""
            transformed_inner = inner.replace(chr(10), '<br>')
            return f"<div class='think-block' style='color:{txt_color};'><i><think><div style='margin-left:20px;'>{transformed_inner}</div></think></i></div>"
        final = re.sub(r"<think>([\s\S]*?)</think>", replace_think_tags, combined, flags=re.I)
        final = re.sub(r"<think>([\s\S]*?)</think>", replace_think_tags, final, flags=re.I)
        return prefix_html + final
    def _apply_theme(self):
        if not self.winfo_exists(): return
        curr_theme_name = self.main_app_ref.current_theme_name if self.main_app_ref and hasattr(self.main_app_ref, 'current_theme_name') else "light"
        palette = APP_THEMES.get(curr_theme_name, APP_THEMES.get("light", {}))
        self.config(bg=palette.get('app_bg', '#F0F0F0'))
        self._add_message_to_display(None, None)                                            
    def _on_close(self):
        if self.main_app_ref and hasattr(self.main_app_ref, 'config') and hasattr(self.main_app_ref, 'ollama_chat_window'):
            chat_cfg = self.main_app_ref.config.get('chat_ai_config', {})
            if hasattr(self, 'include_output_var'): chat_cfg['include_output'] = self.include_output_var.get()
            if hasattr(self, 'code_check_var'): chat_cfg['include_code'] = self.code_check_var.get()
            self.main_app_ref.config['chat_ai_config'] = chat_cfg
            self.main_app_ref.ollama_chat_window = None
        self.destroy()
if __name__ == '__main__':
    class MockMainApp:
        def __init__(self):
            self.config = {'chat_ai_config': DEFAULT_CONFIG['chat_ai_config'].copy(),
                           'theme': 'light',
                           'editor_font_size': 11
                          }
            self.current_theme_name = self.config['theme']
            class AppMock:
                pass
            self.app = AppMock()
            class NotebookMock:
                def winfo_exists(self, *args):
                    return False
                def select(self, *args):
                    return None
                def nametowidget(self, name, *args):
                    return None
                def bind(self, event, callback, add=None):
                    pass
            self.app.notebook = NotebookMock()
            class OutputPanelMock:
                def winfo_exists(self, *args):
                    return False
                text = None
            self.app.output_panel = OutputPanelMock()
            self.ollama_chat_window = None
    root = tk.Tk()
    root.withdraw()
    mock_main_app_ref = MockMainApp()
    mock_main_app_ref.config['chat_ai_config']['api_url'] = "http://localhost:11434"
    mock_main_app_ref.config['chat_ai_config']['selected_model'] = 'llama3.2:latest'
    def open_chat():
        if mock_main_app_ref.ollama_chat_window is None or not mock_main_app_ref.ollama_chat_window.winfo_exists():
            mock_main_app_ref.ollama_chat_window = OllamaChatWindow(root, mock_main_app_ref)
        else:
            mock_main_app_ref.ollama_chat_window.lift()
            mock_main_app_ref.ollama_chat_window.focus_set()
    open_chat_button = ttk.Button(root, text="Open Ollama Chat Test", command=open_chat)
    open_chat_button.pack(pady=20)
    def toggle_theme_test():
        current = mock_main_app_ref.current_theme_name
        new_theme = "dark" if current == "light" else "light"
        mock_main_app_ref.current_theme_name = new_theme
        mock_main_app_ref.config['theme'] = new_theme
        if mock_main_app_ref.ollama_chat_window and mock_main_app_ref.ollama_chat_window.winfo_exists():
            mock_main_app_ref.ollama_chat_window._apply_theme()
        print(f"Theme changed to: {new_theme}")
    theme_button = ttk.Button(root, text="Toggle Theme", command=toggle_theme_test)
    theme_button.pack(pady=10)
    root.deiconify()
    root.mainloop()
