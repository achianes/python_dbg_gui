import tkinter as tk
from tkinter import ttk, messagebox
import urllib.parse
import urllib.request
import json
from threading import Thread
import traceback
from gui.config_defaults import DEFAULT_CONFIG
class OllamaConfigDialog(tk.Toplevel):
    def __init__(self, parent, main_app_ref):
        super().__init__(parent)
        self.main_app_ref = main_app_ref                                                                          
        self.transient(parent)
        self.title("Configure Ollama")
        self.attributes("-topmost", True)
        self.grab_set()                          
        current_chat_config_from_main = {}
        if self.main_app_ref and hasattr(self.main_app_ref, 'config'):
            current_chat_config_from_main = self.main_app_ref.config.get('chat_ai_config', {})
        default_values_for_dialog = DEFAULT_CONFIG.get('chat_ai_config', {
             "api_url": "http://localhost:11434", "selected_model": ""                    
        })
        self.api_url_var = tk.StringVar(value=current_chat_config_from_main.get('api_url', default_values_for_dialog.get('api_url')))
        self.selected_model_var = tk.StringVar(value=current_chat_config_from_main.get('selected_model', default_values_for_dialog.get('selected_model')))
        frame = ttk.Frame(self, padding=10)
        frame.pack(expand=True, fill=tk.BOTH)
        ttk.Label(frame, text="Ollama API URL:").grid(row=0, column=0, sticky=tk.W, pady=(5,2))
        self.url_entry = ttk.Entry(frame, textvariable=self.api_url_var, width=50)
        self.url_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=(5,2), padx=5)
        ttk.Label(frame, text="Default Model:").grid(row=1, column=0, sticky=tk.W, pady=(2,5))
        self.model_combo = ttk.Combobox(frame, textvariable=self.selected_model_var, state="readonly", width=48)
        self.model_combo.grid(row=1, column=1, sticky=tk.EW, pady=(2,5), padx=5)
        self.refresh_btn = ttk.Button(frame, text="Refresh", command=self._fetch_models_for_dialog)
        self.refresh_btn.grid(row=1, column=2, pady=(2,5), padx=(0,5))
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=2, column=0, columnspan=3, pady=(10,0))
        ttk.Button(button_frame, text="Save", command=self._save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)
        frame.grid_columnconfigure(1, weight=1)
        self.url_entry.focus_set()
        self.bind("<Return>", lambda event: self._save_config())
        self.bind("<Escape>", lambda event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.center_window()
        self._fetch_models_for_dialog(initial_load=True)                                
        self.wait_window(self)                                    
    def center_window(self):
        self.update_idletasks()                                             
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()
        if dialog_width <= 1: dialog_width = self.winfo_reqwidth() if self.winfo_reqwidth() > 1 else 450
        if dialog_height <= 1: dialog_height = self.winfo_reqheight() if self.winfo_reqheight() > 1 else 150
        parent_window = self.master
        parent_x = parent_window.winfo_rootx()
        parent_y = parent_window.winfo_rooty()
        parent_width = parent_window.winfo_width()
        parent_height = parent_window.winfo_height()
        position_x = parent_x + (parent_width // 2) - (dialog_width // 2)
        position_y = parent_y + (parent_height // 2) - (dialog_height // 2)
        self.geometry(f"{dialog_width}x{dialog_height}+{position_x}+{position_y}")
    def _fetch_models_for_dialog(self, initial_load=False):
        if not self.winfo_exists(): return
        url = self.api_url_var.get()
        if not url:
            if not initial_load: messagebox.showerror("Error", "Ollama URL is required.", parent=self)
            return
        current_selection = self.selected_model_var.get()
        self.model_combo.set("Fetching...")
        self.model_combo.config(state="disabled")
        if hasattr(self, 'refresh_btn') and self.refresh_btn.winfo_exists():
            self.refresh_btn.config(state="disabled")
        Thread(target=self._fetch_models_thread_for_dialog, args=(url, current_selection, initial_load), daemon=True).start()
    def _fetch_models_thread_for_dialog(self, url, current_selection_before_fetch, initial_load):
        model_names_res, error_res = None, None
        try:
            full_url = urllib.parse.urljoin(url, "/api/tags" if url.endswith('/') else "/api/tags")
            req = urllib.request.Request(full_url)
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    model_names_res = [model['name'] for model in data.get('models', [])]
                else:
                    error_res = ("API Error", f"Failed to fetch models: HTTP {response.status}")
        except Exception as e:
            error_res = ("Connection Error", f"Failed to connect to Ollama or parse models: {e}")
        if self.winfo_exists():                                         
            self.after(0, self._update_models_combo_for_dialog, model_names_res, error_res, current_selection_before_fetch, initial_load)
    def _update_models_combo_for_dialog(self, model_names, error_info, saved_selection, initial_load):
        if not self.winfo_exists(): return
        if error_info:
            if not initial_load: messagebox.showerror(error_info[0], error_info[1], parent=self)
            self.model_combo.set(saved_selection if saved_selection and saved_selection != "Fetching..." else "")
        elif model_names is not None:                             
            self.model_combo['values'] = model_names
            if saved_selection and saved_selection in model_names and saved_selection != "Fetching...":
                self.selected_model_var.set(saved_selection)
            elif model_names:                                                                            
                self.selected_model_var.set(model_names[0])
            else:                         
                self.selected_model_var.set("")
                if not initial_load: messagebox.showinfo("Info", "No models found on the Ollama server.", parent=self)
        if self.model_combo.winfo_exists(): self.model_combo.config(state="readonly")
        if hasattr(self, 'refresh_btn') and self.refresh_btn.winfo_exists():
            self.refresh_btn.config(state="normal")
    def _save_config(self):
        if not self.winfo_exists(): return
        new_url = self.api_url_var.get().strip()
        new_model = self.selected_model_var.get()
        if not new_url:
            messagebox.showerror("Error", "Ollama API URL cannot be empty.", parent=self)
            return
        if self.main_app_ref and hasattr(self.main_app_ref, 'config'):
            chat_config = self.main_app_ref.config.get('chat_ai_config', {})
            chat_config['api_url'] = new_url
            chat_config['selected_model'] = new_model
            self.main_app_ref.config['chat_ai_config'] = chat_config
            messagebox.showinfo("Saved", "Ollama configuration saved.", parent=self)
        else:
            messagebox.showerror("Error", "Cannot save configuration. Main application reference is missing.", parent=self)
        self.destroy()
