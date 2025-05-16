import tkinter as tk
from tkinter import ttk, messagebox
import urllib.parse
import urllib.request
import json
from threading import Thread
import traceback
import os
import uuid
import re
from pygments.formatters import HtmlFormatter               
from pygments import highlight               
from pygments.lexers import get_lexer_by_name, TextLexer               
from bs4 import BeautifulSoup, Comment               
import markdown
try:
    from .themes import THEMES as APP_THEMES
except ImportError:
    APP_THEMES = {
        "light": {"editor_bg": "white", "editor_fg": "black", "name": "light", "app_bg": "#F0F0F0", "console_fg": "#d4d4d4", "gutter_bg":"#f0f0f0", "breakpoint_line_editor_bg":"#FFC0CB", "syntax":{}, "console_bg": "#1e1e1e"},
        "dark": {"editor_bg": "#2b2b2b", "editor_fg": "#A9B7C6", "name": "dark", "app_bg": "#2B2B2B", "console_fg": "#d4d4d4", "gutter_bg":"#313335", "breakpoint_line_editor_bg":"#7A3737", "syntax":{}, "console_bg": "#1e1e1e"}
    }
try:
    from .config_defaults import DEFAULT_CONFIG as FALLBACK_DEFAULT_CONFIG
except ImportError:
    FALLBACK_DEFAULT_CONFIG = {"chat_ai_config": {
        "api_url": "http://localhost:11434", "selected_model": "",
        "include_output": False, "include_code": False
    }}
class MarkdownDisplayChat(tk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        try:
            from tkinterweb import HtmlFrame               
            self.html_label = HtmlFrame(self, messages_enabled=False, javascript_enabled=True)
            self.html_label.pack(fill="both", expand=True)
        except ImportError:
            self.html_label = tk.Text(self, wrap="word", state="disabled", bg="lightgrey")
            self.html_label.pack(fill="both", expand=True)
            if master and master.winfo_exists():
                 messagebox.showwarning("TkinterWeb Not Found",
                                       "The tkinterweb library is not installed. Chat display will be basic text.\n"
                                       "Please install it with: pip install tkinterweb")
    def set_html(self, html_text):
        if not self.winfo_exists(): return
        if hasattr(self, 'html_label') and hasattr(self.html_label, 'load_html'):
            try:
                if self.html_label.winfo_exists(): self.html_label.load_html(html_text)
            except Exception:
                if hasattr(self, 'html_label') and self.html_label.winfo_exists():
                    try:
                        self.html_label.config(state="normal")
                        self.html_label.delete("1.0", tk.END)
                        self.html_label.insert(tk.END, f"Error rendering HTML.\nRaw content:\n{html_text}")
                        self.html_label.config(state="disabled")
                    except tk.TclError: pass                       
        elif hasattr(self, 'html_label') and self.html_label.winfo_exists():
            try:
                self.html_label.config(state="normal")
                self.html_label.delete("1.0", tk.END)
                self.html_label.insert(tk.END, "HTML rendering disabled.\nShowing raw content:\n" + html_text)
                self.html_label.config(state="disabled")
            except tk.TclError: pass
class ChatPanel(tk.Frame):
    def __init__(self, master, main_app_ref=None):
        super().__init__(master)
        self.main_app_ref = main_app_ref
        chat_config_loaded = {}
        if self.main_app_ref and hasattr(self.main_app_ref, 'config'):
            chat_config_loaded = self.main_app_ref.config.get('chat_ai_config', {})
        default_chat_cfg_values = FALLBACK_DEFAULT_CONFIG.get('chat_ai_config', {
            "api_url": "http://localhost:11434", "selected_model": "",
            "include_output": False, "include_code": False
        })
        self.api_url = tk.StringVar(value=chat_config_loaded.get("api_url", default_chat_cfg_values.get("api_url")))
        self.selected_model = tk.StringVar(value=chat_config_loaded.get("selected_model", default_chat_cfg_values.get("selected_model")))
        self.chat_history = []
        self.include_output_var = tk.BooleanVar(value=chat_config_loaded.get("include_output", default_chat_cfg_values.get("include_output")))
        self.code_check_var = tk.BooleanVar(value=chat_config_loaded.get("include_code", default_chat_cfg_values.get("include_code")))
        self.code_check_label_text = tk.StringVar()
        self._build_ui()
        if hasattr(self.md_display, 'html_label') and hasattr(self.md_display.html_label, 'register_JS_object'):
             self.md_display.html_label.register_JS_object("py_copy", self.js_copy_handler)
    def js_copy_handler(self, text_to_copy_encoded):
        if not self.winfo_exists(): return
        try:
            text_to_copy_decoded = urllib.parse.unquote(text_to_copy_encoded)
            self.copy_text_to_clipboard_panel(text_to_copy_decoded)
        except Exception as e:
            if self.winfo_exists(): messagebox.showerror("Copy Error", f"Failed to process text for copying: {e}")
    def copy_text_to_clipboard_panel(self, text):
        if not self.winfo_exists(): return
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Copied", "Text copied to clipboard!")
        except tk.TclError: pass                         
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0); self.grid_rowconfigure(1, weight=1); self.grid_rowconfigure(2, weight=0)
        config_frame = ttk.Frame(self, padding=(5,5)); config_frame.grid(row=0, column=0, sticky="ew")
        config_frame.grid_columnconfigure(1, weight=1); config_frame.grid_columnconfigure(3, weight=1)
        ttk.Label(config_frame, text="Ollama URL:").grid(row=0, column=0, padx=(0,5), pady=2, sticky="w")
        self.url_entry = ttk.Entry(config_frame, textvariable=self.api_url)
        self.url_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(config_frame, text="Model:").grid(row=1, column=0, padx=(0,5), pady=2, sticky="w")
        self.model_combo = ttk.Combobox(config_frame, textvariable=self.selected_model, state="readonly", width=30)
        self.model_combo.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        self.refresh_models_btn = ttk.Button(config_frame, text="Refresh Models", command=self._fetch_models)
        self.refresh_models_btn.grid(row=1, column=2, padx=5, pady=2)
        context_label_frame = ttk.LabelFrame(config_frame, text="Context")
        context_label_frame.grid(row=0, column=3, rowspan=2, padx=10, pady=2, sticky="ns")
        self.output_check = ttk.Checkbutton(context_label_frame, text="Last Output", variable=self.include_output_var)
        self.output_check.pack(anchor="w", padx=5)
        self.code_check = ttk.Checkbutton(context_label_frame, textvariable=self.code_check_label_text, variable=self.code_check_var)
        self.code_check.pack(anchor="w", padx=5)
        self.after_idle(self._update_code_check_label_text_only)
        if self.main_app_ref and hasattr(self.main_app_ref, 'app') and hasattr(self.main_app_ref.app, 'notebook'):
            if self.main_app_ref.app.notebook.winfo_exists():                       
                 self.main_app_ref.app.notebook.bind("<<NotebookTabChanged>>", self._on_main_tab_changed_for_chat_label, add="+")
        self.md_display = MarkdownDisplayChat(self)
        self.md_display.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        input_frame = ttk.Frame(self, padding=(5,5)); input_frame.grid(row=2, column=0, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)
        self.entry = tk.Text(input_frame, height=3, wrap="word", relief="solid", borderwidth=1)
        self.entry.grid(row=0, column=0, sticky="nsew", padx=(0,5))
        self.entry.bind("<Return>", self._on_enter); self.entry.bind("<Shift-Return>", lambda e: "break")
        self.send_btn = ttk.Button(input_frame, text="Send", command=self._send_message_ui)
        self.send_btn.grid(row=0, column=1, padx=(5,0), sticky="ns")
        if self.winfo_exists(): self.after(100, self._fetch_models)                           
    def _on_main_tab_changed_for_chat_label(self, event=None):
        if self.winfo_exists(): self.after_idle(self._update_code_check_label_text_only)
    def _update_code_check_label_text_only(self):
        if not self.winfo_exists(): return
        filename = None
        if self.main_app_ref and hasattr(self.main_app_ref, 'app'):
            try:
                if hasattr(self.main_app_ref.app, 'notebook') and self.main_app_ref.app.notebook.winfo_exists():
                    selected_tab_id = self.main_app_ref.app.notebook.select()
                    if selected_tab_id:
                        active_editor = self.main_app_ref.app.notebook.nametowidget(selected_tab_id)
                        if hasattr(active_editor, 'filepath') and active_editor.filepath:
                            filename = os.path.basename(active_editor.filepath)
                        elif hasattr(active_editor, '_temp_name'):
                            filename = active_editor._temp_name
            except (tk.TclError, AttributeError): pass
        self.code_check_label_text.set(f"Current Code ({filename})" if filename else "Current Code (No file)")
    def _fetch_models(self):
        if not self.winfo_exists(): return
        url = self.api_url.get()
        if not url: messagebox.showerror("Error", "Ollama URL cannot be empty."); return
        self.model_combo.set("Fetching..."); self.model_combo.config(state="disabled")
        self.refresh_models_btn.config(state="disabled")
        Thread(target=self._fetch_models_thread, args=(url,), daemon=True).start()
    def _fetch_models_thread(self, url):
        model_names_r, error_r = None, None
        try:
            req = urllib.request.Request(urllib.parse.urljoin(url, "/api/tags"))
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200: model_names_r = [m['name'] for m in json.loads(resp.read().decode()).get('models', [])]
                else: error_r = ("Error", f"Failed to fetch models: HTTP {resp.status}")
        except Exception as e: error_r = ("Error", f"API Error: {e}\n{traceback.format_exc()}")
        if self.winfo_exists(): self.after(0, self._handle_fetch_models_result, model_names_r, error_r)
    def _handle_fetch_models_result(self, model_names, error_info):
        if not self.winfo_exists(): return
        if error_info: messagebox.showerror(error_info[0], error_info[1]); self.model_combo.set("")
        elif model_names is not None: self._update_models_combobox(model_names)
        self.model_combo.config(state="readonly"); self.refresh_models_btn.config(state="normal")
    def _update_models_combobox(self, model_names):
        if not self.winfo_exists(): return
        self.model_combo['values'] = model_names
        current_sel = self.selected_model.get()
        if model_names:
            if not current_sel or current_sel == "Fetching..." or current_sel not in model_names:
                self.selected_model.set(model_names[0])
        else: self.selected_model.set(""); messagebox.showinfo("No Models", "No models found.")
        self.model_combo.config(state="readonly")
    def freeze_interface(self):
        if not self.winfo_exists(): return
        for widget in [self.send_btn, self.entry, self.url_entry, self.model_combo, self.refresh_models_btn]:
            try: widget.config(state="disabled")
            except tk.TclError: pass                       
        if self.send_btn.winfo_exists(): self.send_btn.config(text="Waiting...")
    def unfreeze_interface(self):
        if not self.winfo_exists(): return
        for widget in [self.entry, self.url_entry, self.refresh_models_btn]:
            try: widget.config(state="normal")
            except tk.TclError: pass
        if self.send_btn.winfo_exists(): self.send_btn.config(state="normal", text="Send")
        if self.model_combo.winfo_exists(): self.model_combo.config(state="readonly")
    def _on_enter(self, event):
        if not (event.state & 0x0001): self._send_message_ui(); return "break"
        return None                                
    def _get_context_data(self):
        context_prefix = ""
        if not self.main_app_ref or not hasattr(self.main_app_ref, 'app'): return context_prefix
        try:
            if self.code_check_var.get():                     
                if hasattr(self.main_app_ref.app, 'notebook') and self.main_app_ref.app.notebook.winfo_exists():
                    sel_id = self.main_app_ref.app.notebook.select()
                    if sel_id:
                        ed = self.main_app_ref.app.notebook.nametowidget(sel_id)
                        if hasattr(ed, 'text') and ed.text.winfo_exists():
                            code = ed.text.get("1.0", tk.END).strip()
                            if code:
                                fp = getattr(ed, 'filepath', getattr(ed, '_temp_name', 'current_code.py'))
                                fn = os.path.basename(fp) if fp else 'current_code.py'
                                context_prefix += f"Code ({fn}):\n```python\n{code}\n```\n\n"
        except (tk.TclError, AttributeError): pass
        try:
            if self.include_output_var.get():
                if hasattr(self.main_app_ref.app, 'output_panel') and self.main_app_ref.app.output_panel.winfo_exists() and\
                   hasattr(self.main_app_ref.app.output_panel, 'text') and self.main_app_ref.app.output_panel.text.winfo_exists():
                    out_txt = self.main_app_ref.app.output_panel.text.get("1.0", tk.END).strip()
                    out_lines = out_txt.splitlines()
                    if len(out_lines) > 20: out_txt = "\n".join(["...(truncated)..."] + out_lines[-20:])
                    if out_txt: context_prefix += f"Output:\n```\n{out_txt}\n```\n\n"
        except (tk.TclError, AttributeError): pass
        return context_prefix
    def _send_message_ui(self):
        if not self.winfo_exists(): return
        msg = self.entry.get("1.0", "end-1c").strip()
        if not msg: return
        if not self.api_url.get(): messagebox.showerror("Error", "Ollama URL missing."); return
        if not self.selected_model.get() or self.selected_model.get() == "Fetching...": messagebox.showerror("Error", "Model not selected/ready."); return
        self.entry.delete("1.0", tk.END)
        ctx = self._get_context_data()
        full_msg = (ctx + "Based on context, answer:\n\n" + msg) if ctx else msg
        self.chat_history.append({"role": "user", "content": full_msg})
        self._add_to_display("user", msg)
        self.freeze_interface()
        Thread(target=self._run_ai_reply_thread, daemon=True).start()
    def _run_ai_reply_thread(self):
        ai_r, err_r = None, None
        try:
            tmp_c = "".join(list(self._chat_stream_api()))
            ai_r = tmp_c
        except Exception as e: err_r = f"Chat API Error: {e}\n{traceback.format_exc()}"
        if self.winfo_exists(): self.after(0, self._handle_ai_reply_result, ai_r, err_r)
    def _handle_ai_reply_result(self, ai_content, error_msg):
        if not self.winfo_exists(): return
        if error_msg:
            self.chat_history.append({"role": "error", "content": error_msg})
            self._add_to_display("error", error_msg)
        elif ai_content is not None:
            self.chat_history.append({"role": "assistant", "content": ai_content})
            self._add_to_display("assistant", ai_content)
        self.unfreeze_interface()
    def _chat_stream_api(self):
        payload = {"model": self.selected_model.get(), "messages": self.chat_history, "stream": False}
        data_ = json.dumps(payload).encode("utf-8")
        api_url_val = self.api_url.get()
        api_full_url = urllib.parse.urljoin(api_url_val, "/api/chat" if api_url_val.endswith('/') else "/api/chat")
        req = urllib.request.Request(api_full_url, data=data_, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp_data = json.loads(resp.read().decode())
                if "message" in resp_data and "content" in resp_data["message"]: yield resp_data["message"]["content"]
                elif "error" in resp_data: yield f"[API Err ({api_full_url}): {resp_data['error']}]"
                else: yield f"[API Err ({api_full_url}): Bad format]"
        except urllib.error.HTTPError as e:
            body = e.read().decode(); jerr = {}
            try: jerr = json.loads(body)
            except json.JSONDecodeError: jerr = {"error": body}
            yield f"[API HTTP Err ({api_full_url}): {e.code} - {jerr.get('error', 'Unknown')}]"
        except urllib.error.URLError as e: yield f"[API URL Err ({api_full_url}): {e.reason}]"
        except TimeoutError: yield f"[API Err ({api_full_url}): Timeout (120s)]"
        except Exception as e: yield f"[Chat Err ({api_full_url}): {e}]"
    def _add_to_display(self, role, content):
        if not self.winfo_exists(): return
        if role is None and content is None:                      
             pass                                                                 
        elif role and content:                                                                            
             pass
        rows_html = []
        display_history = []
        for msg_hist in self.chat_history:
            if msg_hist["role"] == "user":
                original_user_msg = msg_hist["content"]
                ctx_marker = "Based on the context above, answer the following:\n\n"
                if ctx_marker in original_user_msg: original_user_msg = original_user_msg.split(ctx_marker, 1)[-1]
                display_history.append({"role": "user", "content": original_user_msg})
            else: display_history.append(msg_hist)
        current_theme_name = self.main_app_ref.current_theme_name if self.main_app_ref else "light"
        active_palette = APP_THEMES.get(current_theme_name, APP_THEMES["light"])
        user_bg = active_palette.get("console_fg", "#e0e0e0"); user_fg = active_palette.get("console_bg", "#1e1e1e")
        ai_bg = active_palette.get("gutter_bg", "#f5f5f5"); ai_fg = active_palette.get("gutter_fg", "#333333")
        err_bg = active_palette.get("breakpoint_line_editor_bg", "#ffdddd"); err_fg = active_palette.get("syntax",{}).get('string', "#a31515")
        for msg in display_history:
            cr, bg, fg = msg["role"], (user_bg if msg["role"] == "user" else (err_bg if msg["role"] == "error" else ai_bg)),\
                         (user_fg if msg["role"] == "user" else (err_fg if msg["role"] == "error" else ai_fg))
            html_row = self.convert_message_to_html(msg["content"], role=cr)
            td_style = f"background:{bg};color:{fg};border-radius:10px;padding:10px;overflow:auto;border:1px solid #ddd;"
            balloon = f"""<table style="width:100%;table-layout:fixed;margin:10px 0;"><tr>
                           <td style="width:{'80%' if cr != 'user' else '20%'};{'padding-right:5px;' if cr != 'user' else ''} {td_style if cr != 'user' else ''}">{html_row if cr != 'user' else ''}</td>
                           <td style="width:{'20%' if cr != 'user' else '80%'};{'padding-left:5px;' if cr == 'user' else ''} {td_style if cr == 'user' else ''}">{html_row if cr == 'user' else ''}</td>
                         </tr></table>"""
            rows_html.append(balloon)
        py_style = 'monokai' if current_theme_name == "dark" else 'default'
        body_bg_chat = active_palette.get('app_bg', 'white'); body_fg_chat = active_palette.get('editor_fg', 'black')
        py_css = HtmlFormatter(style=py_style, noclasses=True).get_style_defs('.highlight')
        css = f"""<meta name="viewport" content="width=device-width, initial-scale=1"><style>
        body{{margin:0;padding:10px;font-family:Segoe UI,Arial,sans-serif;background-color:{body_bg_chat};color:{body_fg_chat};}}
        table{{border-collapse:separate;border-spacing:0;}} td{{vertical-align:top;}} strong{{color:{body_fg_chat};}}
        .code-container{{border:1px solid #ccc;border-radius:4px;margin:10px 0;background-color:#272822;}}
        .code-header{{display:flex;justify-content:space-between;align-items:center;padding:5px 10px;font-family:monospace;font-size:12px;}}
        .code-lang{{font-weight:bold;}}
        .copy-btn{{border:none;padding:3px 8px;cursor:pointer;border-radius:3px;font-size:11px;}} .copy-btn:hover{{opacity:0.8;}}
        .highlight{{border-radius:0 0 3px 3px;}}
        pre{{padding:10px;font-family:Consolas,monospace;font-size:13px;white-space:pre;word-break:normal;overflow-x:auto;margin:0 !important;background-color:#272822 !important;color:#f8f8f2 !important;border-radius:0 0 4px 4px;}}
        {py_css}
        .think-block{{border:1px dashed #999;padding:5px;margin:5px 0;background-color:{active_palette.get("gutter_bg", "#f9f9f9")};color:{body_fg_chat};font-style:italic;}}
        .think-block div{{margin-left:20px;}}</style>"""
        full_html = f"<html><head>{css}</head><body>{''.join(rows_html)}</body></html>"
        if self.md_display.winfo_exists(): self.md_display.set_html(full_html)
        if self.winfo_exists():
            self.update_idletasks()
            if hasattr(self.md_display, 'html_label') and self.md_display.html_label.winfo_exists():
                try: self.md_display.html_label.yview_moveto(1.0)
                except tk.TclError: pass
    def convert_message_to_html(self, content: str, role: str = "user") -> str:
        current_theme_name = self.main_app_ref.current_theme_name if self.main_app_ref else "light"
        active_palette = APP_THEMES.get(current_theme_name, APP_THEMES["light"])
        txt_color = active_palette.get("editor_fg", "black")
        prefix_html = f"<strong style='color:{txt_color};'>{role.capitalize()}:</strong><br>"
        processed_parts = []
        parts = re.split(r"(```[\s\S]*?```)", content)
        for part in parts:
            if part.startswith("```") and part.endswith("```"):
                code_full = part[3:-3].strip()
                first_line = code_full.split('\n', 1)[0].strip()
                code_highlight = code_full
                lang = first_line.lower() if first_line and not any(c in first_line for c in ['\n', ' ']) else "text"
                if lang != "text" and code_full.lower().startswith(lang + '\n'):
                    code_highlight = code_full.split('\n', 1)[1] if '\n' in code_full else ''
                elif code_full.lower().startswith(lang) and len(code_full.splitlines())==1 and len(code_full.strip())==len(lang):
                    code_highlight = ""
                try: lexer = get_lexer_by_name(lang)
                except Exception: lexer = TextLexer()
                py_style = 'monokai' if current_theme_name == "dark" else 'default'
                formatter = HtmlFormatter(linenos='table', style=py_style, cssclass="highlight", wrapcode=True)
                hl_code = highlight(code_highlight, lexer, formatter)
                raw_code = code_highlight
                uid = str(uuid.uuid4()).replace('-', '')
                test_js_payload = "TEST_FROM_JS_BUTTON"
                onclick_js_str = f"window.py_copy('{urllib.parse.quote(test_js_payload)}'); return false;"
                hdr_fg = active_palette.get("console_fg", "#FFF") if current_theme_name == 'dark' else active_palette.get("console_bg", "#333")
                hdr_bg = active_palette.get("console_bg", "#333") if current_theme_name == 'dark' else active_palette.get("console_fg", "#ECE")
                btn_bg, btn_fg = "#4CAF50", "#FFFFFF"
                code_html = f"""<div class="code-container" id="code-c-{uid}">
                                  <div class="code-header" style="background-color:{hdr_bg};color:{hdr_fg};">
                                    <span class="code-lang">{lang.capitalize()}</span>
                                    <button class="copy-btn" style="background-color:{btn_bg};color:{btn_fg};" onclick="window.py_copy('{urllib.parse.quote(raw_code)}');">Copy</button>
                                  </div>
                                  <div class="code-body" id="code-b-{uid}">{hl_code}</div>
                               </div>"""
                processed_parts.append(code_html)
            else:
                md_html = markdown.markdown(part, extensions=[])
                processed_parts.append(f"<div style='color:{txt_color};'>{md_html}</div>")
        combined_html = "".join(processed_parts)
        def replace_think(match):
            inner = match.group(1).strip()
            if not inner: return ""
            transformed = "<br>".join(inner.splitlines())
            return f"<div class='think-block' style='color:{txt_color};'><i><think><div style='margin-left:20px;'>{transformed}</div></think></i></div>"
        final_html = re.sub(r"<think>([\s\S]*?)</think>", replace_think, combined_html, flags=re.I)
        final_html = re.sub(r"<think>([\s\S]*?)</think>", replace_think, final_html, flags=re.I)
        return prefix_html + final_html
