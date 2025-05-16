import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont
import json
import os
import base64
from screeninfo import get_monitors
import cairosvg
import requests
import traceback
import io
from PIL import Image, ImageTk
import sys # Assicurati che sys sia importato

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from gui.debugger_app import DebuggerApp
from gui.editor import CodeEditor
from gui.run_config_dialog import RunConfigDialog
from gui.debug_exec_dialog import DebugExecDialog
from gui.themes import THEMES
from gui.config_defaults import DEFAULT_CONFIG
from gui.ollama_config_dialog import OllamaConfigDialog
from gui.ollama_chat_window import OllamaChatWindow
from gui.custom_notebook import CustomNotebook # Assicurati che sia importato

# --- NUOVA PARTE: GESTIONE PERCORSO CONFIGURAZIONE ---
APP_NAME = "PythonDbgGui" # Nome della tua applicazione per la cartella di configurazione

def get_user_config_path(app_name, filename=".config.json"):
    """
    Restituisce il percorso del file di configurazione specifico dell'utente e della piattaforma.
    Crea la directory se non esiste.
    """
    if sys.platform == "win32":
        # Windows: %APPDATA%\AppName\filename
        base_dir = os.environ.get("APPDATA")
        if not base_dir: # Fallback raro, ma per sicurezza
            base_dir = os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    elif sys.platform == "darwin": # macOS
        # macOS: ~/Library/Application Support/AppName/filename
        base_dir = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else: # Linux e altri Unix-like
        # Linux: $XDG_CONFIG_HOME/AppName/filename o ~/.config/AppName/filename
        base_dir = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))

    if not base_dir:
        # Fallback estremo: usa la directory corrente se non si riesce a determinare nulla
        print(f"ATTENZIONE: Impossibile determinare la directory di configurazione utente standard. "
              f"Il file '{filename}' verrà salvato nella directory corrente.")
        config_dir_path = os.getcwd()
    else:
        config_dir_path = os.path.join(base_dir, app_name)

    try:
        os.makedirs(config_dir_path, exist_ok=True)
    except OSError as e:
        print(f"ATTENZIONE: Impossibile creare la directory di configurazione '{config_dir_path}': {e}. "
              f"Il file '{filename}' verrà salvato nella directory corrente.")
        # Fallback se la creazione della directory fallisce
        config_dir_path = os.getcwd()
        
    return os.path.join(config_dir_path, filename)

CONFIG_PATH = get_user_config_path(APP_NAME) # NUOVA DEFINIZIONE
# --- FINE NUOVA PARTE ---


MIN_WIDTH = 800
MIN_HEIGHT = 600
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 24
FONT_SIZE_STEP = 1
DEFAULT_ICON_DATA = """
iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABHNCSVQICAgIfAhkiAAAAAlwSFlz
AAALEgAACxIB0t1+/AAAABZ0RVh0Q3JlYXRpb24gVGltZQAwNC8xMi8yMyqFOrwAAAAcdEVYdFNv
ZnR3YXJlAEFkb2JlIEZpcmV3b3JrcyBDUzVxteM8AAACVklEQVRYhe2XvWsUQRjHfzM7uxfJSgoV
E7QRwUrBRhARwUJEEEykhYh/gIWihYIiIv4BWyMppLAQEbFSFAVBTCCVtBKxBAsLKd57vNlvN5O9
3b3Zu5eFF3bh4Xn+//N9j2demgF0XQdAZwDYAl4DN8BXYAX4AngC/JSUnU0AK4F54DPwFVgCfgF3
krK9GcAq8CzwH/AWSI43gQngY/AdWAr8AH4CvuN41ga4DDwGvgKjSD5XgY/Azw7gGfAQGPkS6AFO
J+WD1A6oKqm3pOskvSZ9L/WXpMckjb8BTyVlhqROknqu1J+Ujgd8k9SNNuBj4FtSR1R7ewU4BPwC
WgFdkhpY7d0PXIvjZwFeAL0AITkeA74CL/1UaQfeAfckjV3tX/45wCogX/8CPkvKV6s99wKuJk1S
rgR+Ab+B/+XhBeAUUAIsJXWT/QDsA0uSZj8EzgG3gKeBScA2YEFSt/UAB4H5JKP+M+AEcCKZAPQC
owDNwEbgA3AAeAsMAVOAJ+B3YEVSDzI+qWOkfQNsAcuB50h+3j8DbgP/gXPAQ2BtcgA2gX9J+q0k
/QQ0JG1WAaMk9b6E/gW+JY/VugS8AP4GlgGngGNJ2V0CDgDnAWeAI8AZYCNwIpkD/gC9wA5gA3Ax
ORzAZ+A58K747wIjgXvAReAT8BH43yW1KxW9JvURgG+ZfCuB+zz9B46BScCvJH8FvAJuAQOAXaBf
Sg/Al8CNZGvgH/Ank8+A36kC/AIqgXORLwN+Af9pAN+AX0l9I+k/wK9JGncz+r8BvzUAmwDrgVnJ
+5d4C/wIXP8HwA8kyVzX14GvQP+k85KaL7UjYJuk/pN0P/ACeAMcScrgZfBvAAAAAElFTkSuQmCC
"""

class MainApplication:
    def __init__(self, root):
        self.root = root
        self.open_tabs = {}
        self.is_running = False
        self.paused = False
        self.command_pending = False
        self.current_debug_target_path = None
        self.debug_exec_window = None
        # Le seguenti verranno popolate da _load_config
        # self.run_configs = {}
        # self.debug_exec_dialog_config = {}
        self.current_theme_name = "light" # Default, verrà sovrascritto da config
        self.current_editor_font_size = 11 # Default, verrà sovrascritto da config

        self.config = self._load_config() # Carica la configurazione usando il nuovo CONFIG_PATH

        self._pane_states = self.config.get('pane_states', DEFAULT_CONFIG['pane_states'].copy())
        self.run_configs = self.config.get('run_configs', DEFAULT_CONFIG['run_configs'].copy())
        
        # Gestione più robusta di debug_exec_dialog_config
        default_ded_cfg_template = DEFAULT_CONFIG['debug_exec_dialog_config'].copy()
        loaded_ded_cfg = self.config.get('debug_exec_dialog_config', default_ded_cfg_template)
        
        self.debug_exec_dialog_config = default_ded_cfg_template # Inizia con i default
        if isinstance(loaded_ded_cfg, dict):
            for key, value in loaded_ded_cfg.items():
                if key in self.debug_exec_dialog_config: # Copia solo le chiavi conosciute/attese
                    self.debug_exec_dialog_config[key] = value
        # Assicurati che il config principale rifletta la versione pulita/validata
        # Questo è importante se il file di config caricato avesse chiavi inattese
        self.config['debug_exec_dialog_config'] = self.debug_exec_dialog_config.copy()

        self.current_theme_name = self.config.get('theme', DEFAULT_CONFIG['theme'])
        self.current_editor_font_size = self.config.get('editor_font_size', DEFAULT_CONFIG['editor_font_size'])
        
        self._configure_styles() # Configura stili base Tkinter
        
        root.minsize(MIN_WIDTH, MIN_HEIGHT)
        root.config(borderwidth=2, relief='groove') # Stile per la finestra principale
        
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=0) # Toolbar
        self.root.grid_rowconfigure(1, weight=1) # Contenuto principale (DebuggerApp)
        self.root.grid_rowconfigure(2, weight=0) # Status bar
        
        self.toolbar_frame = ttk.Frame(self.root) # Non applicare stile qui, lo farà _apply_theme_globally
        self.toolbar_frame.grid(row=0, column=0, sticky='ew', pady=(0,1), padx=2)
        
        container = ttk.Frame(self.root) # Contenitore per DebuggerApp
        container.grid(row=1, column=0, sticky='nsew')
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        self.ollama_chat_window = None # Finestra chat, inizializzata a None
        
        self.app = DebuggerApp(container, main_app_ref=self)
        self.app.on_breakpoint_hit = self.on_breakpoint_hit
        self.app.on_finished = self.on_finished
        
        if hasattr(self.app, 'notebook') and self.app.notebook:
            self.app.notebook.bind("<<NotebookTabAboutToClose>>", self._on_tab_about_to_close)
            self.app.notebook.bind("<<NotebookTabClosed>>", self._on_tab_closed) # Evento per pulire self.open_tabs
            
        container.after(300, self._restore_all_panes) # Ritarda il ripristino dei pannelli
        
        self.status_var = tk.StringVar(master=self.root, value="Ready")
        status_label = ttk.Label(self.root, textvariable=self.status_var, relief='sunken', anchor='w', padding=(2,2))
        status_label.grid(row=2, column=0, sticky='we')
        
        # Applicazioni iniziali di tema e font
        self.root.after_idle(self._apply_theme_globally)
        self.root.after_idle(self._apply_font_size_to_all_editors)
        
        # Carica i file aperti precedentemente
        for fp in self.config.get('open_files', []):
            if os.path.exists(fp) and os.path.isfile(fp):
                self._create_editor(fp)
                
        root.protocol("WM_DELETE_WINDOW", self.on_exit)
        self._restore_geometry() # Ripristina dimensioni e posizione della finestra
        
        self._create_menus()
        self._create_toolbar_buttons()
        self._set_icon()
    def _configure_styles(self):
        try:
            default_font = tkfont.nametofont("TkMenuFont")
            current_size = default_font.cget('size')
            new_size = max(10, min(16, current_size + 1))
            try: font_family = default_font.cget('family')
            except tk.TclError: font_family = "TkDefaultFont"
            menu_font_spec = f"{{{font_family}}} {new_size}"
            if self.root.winfo_exists():
                self.root.option_add('*Menu.font', menu_font_spec)
                self.root.option_add('*Menubutton.font', menu_font_spec)
        except Exception:
            pass
    def _set_icon(self):
        svg_url = "https://www.svgrepo.com/show/450791/debug-script.svg"
        icon_set = False
        try:
            resp = requests.get(svg_url, timeout=3)
            resp.raise_for_status()
            png_data = cairosvg.svg2png(bytestring=resp.content, dpi=96)               
            icon_img = tk.PhotoImage(data=png_data)
            if self.root.winfo_exists():
                self.root.iconphoto(True, icon_img)
            icon_set = True
        except Exception:
            pass
        if not icon_set:
            try:
                icon_img = tk.PhotoImage(data=base64.b64decode(DEFAULT_ICON_DATA))
                if self.root.winfo_exists():
                    self.root.iconphoto(True, icon_img)
            except Exception:
                pass
    def _restore_geometry(self):
        if not self.root.winfo_exists(): return
        geom_size = self.config.get('geometry', DEFAULT_CONFIG['geometry'])
        geom_pos = self.config.get('main_window_position')
        try:
            w, h = map(int, geom_size.split('x'))
            w = max(MIN_WIDTH, w); h = max(MIN_HEIGHT, h)
            if geom_pos and geom_pos.startswith('+'):
                try:
                    pos_parts = geom_pos.lstrip('+').split('+')
                    if len(pos_parts) == 2:
                        req_x, req_y = int(pos_parts[0]), int(pos_parts[1])
                        monitors = get_monitors()
                        if monitors:
                            monitor = monitors[0]
                            if 0 <= req_x < (monitor.width - 50) and 0 <= req_y < (monitor.height - 50):
                                self.root.geometry(f"{w}x{h}+{req_x}+{req_y}"); return
                except (ValueError, IndexError): pass
            monitors = get_monitors()
            if monitors:
                monitor = monitors[0]
                x = (monitor.width - w) // 2; y = (monitor.height - h) // 2
                self.root.geometry(f"{w}x{h}+{x}+{y}")
            else:                                           
                self.root.geometry(f"{w}x{h}")
        except Exception:
            self.root.geometry(f"{MIN_WIDTH}x{MIN_HEIGHT}")
    def _load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    if isinstance(config_data, dict):
                        merged_config = json.loads(json.dumps(DEFAULT_CONFIG))            
                        def recursive_update(original, updates):
                            for key, value in updates.items():
                                if isinstance(value, dict) and key in original and isinstance(original[key], dict):
                                    recursive_update(original[key], value)
                                else:
                                    original[key] = value
                            for key, value in DEFAULT_CONFIG.items():                                          
                                if key not in original and isinstance(merged_config.get(key),dict) and isinstance(value,dict):                                
                                    original[key] = json.loads(json.dumps(value))            
                                elif key not in original:
                                     original[key] = value
                        recursive_update(merged_config, config_data)
                        return merged_config
            except (json.JSONDecodeError, OSError, Exception):
                 pass
        return json.loads(json.dumps(DEFAULT_CONFIG))                     
    def _save_pane_state(self, name, paned):
        if not isinstance(paned, ttk.PanedWindow) or not paned.winfo_exists(): return
        try:
            paned.update_idletasks()
            panes = paned.panes()
            count = max(len(panes) - 1, 0)
            sash_positions = []
            if count > 0:
                sash_positions = [paned.sashpos(i) for i in range(count) if i < count]                        
            self._pane_states[name] = sash_positions
            for idx, path in enumerate(panes):
                child_widget = paned.nametowidget(path)
                if isinstance(child_widget, ttk.PanedWindow):                                
                    self._save_pane_state(f"{name}_{idx}", child_widget)
        except tk.TclError:
            pass
    def _restore_pane_state(self, name, paned_widget):
        if not isinstance(paned_widget, ttk.PanedWindow) or not paned_widget.winfo_exists(): return
        try:
            paned_widget.update_idletasks()
            self.root.update_idletasks()
            if not (paned_widget.winfo_ismapped() and paned_widget.winfo_width() > 1 and paned_widget.winfo_height() > 1):
                return                                                    
            saved_sash_positions = self._pane_states.get(name)
            if isinstance(saved_sash_positions, list) and saved_sash_positions:
                num_sashes_in_widget = max(0, len(paned_widget.panes()) - 1)
                for i, pos_val in enumerate(saved_sash_positions):
                    if i < num_sashes_in_widget:
                        try:
                            paned_widget.sashpos(i, int(pos_val))
                        except (ValueError, tk.TclError): pass
            child_pane_paths = paned_widget.panes()
            for idx, child_path in enumerate(child_pane_paths):
                try:
                    child_widget_instance = paned_widget.nametowidget(child_path)
                    if isinstance(child_widget_instance, ttk.PanedWindow):
                        self._restore_pane_state(f"{name}_{idx}", child_widget_instance)
                except (tk.TclError, Exception): pass
        except tk.TclError:
            pass
    def _restore_all_panes(self):
        try:
            if hasattr(self.app, 'main_pane') and self.app.main_pane.winfo_exists():
                 self._restore_pane_state('main',  self.app.main_pane)
        except Exception:
            pass
    def _save_config(self):
        if not self.root.winfo_exists(): return
        try:
            main_geo_full = self.root.geometry()
            parts = main_geo_full.split('+', 1)
            self.config['geometry'] = parts[0]
            self.config['main_window_position'] = f"+{parts[1]}" if len(parts) > 1 else None
        except tk.TclError:
            self.config['geometry'] = DEFAULT_CONFIG['geometry']
            self.config.pop('main_window_position', None)
        self.config['open_files'] = [
            ed.filepath for ed in self.open_tabs.values()
            if getattr(ed, 'filepath', None) and os.path.exists(ed.filepath)
        ]
        self._pane_states = {}
        try:
            if hasattr(self.app, 'main_pane') and self.app.main_pane.winfo_exists():
                self._save_pane_state('main',  self.app.main_pane)
            self.config['pane_states'] = self._pane_states.copy()
        except Exception:
            self.config['pane_states'] = DEFAULT_CONFIG['pane_states'].copy()
        bps = []
        if hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists():
            try:
                for tab_id in self.app.notebook.tabs():
                    try:
                        widget = self.app.notebook.nametowidget(tab_id)
                        if isinstance(widget, CodeEditor) and hasattr(widget, 'breakpoints') and\
                           hasattr(widget, 'filepath') and widget.filepath and os.path.exists(widget.filepath):
                            for ln in widget.breakpoints:
                                bps.append([widget.filepath, ln])
                    except (tk.TclError, AttributeError): continue
            except tk.TclError: pass
        self.config['breakpoints'] = bps
        self.config['run_configs'] = self.run_configs.copy()
        self.config['debug_exec_dialog_config'] = self.debug_exec_dialog_config.copy()
        self.config['theme'] = self.current_theme_name
        self.config['editor_font_size'] = self.current_editor_font_size
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except (OSError, TypeError, Exception):
            pass
    def _load_icon_from_url(self, url, size=(16, 16)):
        try:
            resp = requests.get(url, timeout=3)
            resp.raise_for_status()
            png_data = cairosvg.svg2png(bytestring=resp.content, output_width=size[0]*2, output_height=size[1]*2)               
            img_pil = Image.open(io.BytesIO(png_data))
            img_pil = img_pil.resize(size, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img_pil)
        except Exception:
            ph_img = Image.new('RGBA', size, (128,128,128,100))
            return ImageTk.PhotoImage(ph_img)
    def _create_toolbar_buttons(self):
        s = ttk.Style()
        s.configure("Toolbutton", padding=1)
        if not hasattr(self, 'toolbar_frame') or not self.toolbar_frame.winfo_exists():
            self.toolbar_frame = ttk.Frame(self.root)
            self.toolbar_frame.grid(row=0, column=0, sticky='ew', pady=(0,1), padx=2)
        self.btn_dark_mode = ttk.Button(self.toolbar_frame, text="Theme", command=self.toggle_dark_mode, style="Toolbutton", width=5)
        self.btn_dark_mode.pack(side=tk.LEFT, padx=(2,1), pady=1)
        self.btn_font_inc = ttk.Button(self.toolbar_frame, text="A+", command=self.increase_font_size, style="Toolbutton", width=3)
        self.btn_font_inc.pack(side=tk.LEFT, padx=1, pady=1)
        self.btn_font_dec = ttk.Button(self.toolbar_frame, text="A-", command=self.decrease_font_size, style="Toolbutton", width=3)
        self.btn_font_dec.pack(side=tk.LEFT, padx=(1,2), pady=1)
        if self.root.winfo_exists():
            self.root.after(500, self._load_and_apply_toolbar_icons)
    def _load_and_apply_toolbar_icons(self):
        if not self.root.winfo_exists(): return
        try:
            icon_dark = self._load_icon_from_url("https://www.svgrepo.com/show/315691/dark-mode.svg", size=(20,20))
            if icon_dark and hasattr(self, 'btn_dark_mode') and self.btn_dark_mode.winfo_exists():
                self.icon_dark_mode = icon_dark
                self.btn_dark_mode.config(image=self.icon_dark_mode, width=2, text="")
        except Exception: pass
        try:
            icon_inc = self._load_icon_from_url("https://www.svgrepo.com/show/309640/font-increase.svg", size=(20,20))
            if icon_inc and hasattr(self, 'btn_font_inc') and self.btn_font_inc.winfo_exists():
                self.icon_font_increase = icon_inc
                self.btn_font_inc.config(image=self.icon_font_increase, width=2, text="")
        except Exception: pass
        try:
            icon_dec = self._load_icon_from_url("https://www.svgrepo.com/show/310863/font-decrease.svg", size=(20,20))
            if icon_dec and hasattr(self, 'btn_font_dec') and self.btn_font_dec.winfo_exists():
                self.icon_font_decrease = icon_dec
                self.btn_font_dec.config(image=self.icon_font_decrease, width=2, text="")
        except Exception: pass
    def toggle_dark_mode(self):
        self.current_theme_name = "dark" if self.current_theme_name == "light" else "light"
        self._apply_theme_globally()
    def increase_font_size(self):
        self.current_editor_font_size = min(self.current_editor_font_size + FONT_SIZE_STEP, MAX_FONT_SIZE)
        self._apply_font_size_to_all_editors()
    def decrease_font_size(self):
        self.current_editor_font_size = max(self.current_editor_font_size - FONT_SIZE_STEP, MIN_FONT_SIZE)
        self._apply_font_size_to_all_editors()
    def _apply_theme_globally(self):
        if not self.root.winfo_exists(): return
        theme_colors = THEMES.get(self.current_theme_name, THEMES["light"])
        app_bg = theme_colors.get("app_bg", "#F0F0F0")
        toolbar_bg = theme_colors.get("toolbar_bg", "#ECECEC")
        generic_text_fg = theme_colors.get("editor_fg", "black")
        self.root.config(bg=app_bg)
        s = ttk.Style()
        s.configure(".", background=app_bg, foreground=generic_text_fg)
        s.configure("TFrame", background=app_bg)
        s.configure("TLabel", background=app_bg, foreground=generic_text_fg)
        s.configure("TButton", foreground=generic_text_fg, background=toolbar_bg)
        s.configure("Toolbutton", foreground=generic_text_fg, background=toolbar_bg)
        s.configure("TMenubutton", background=toolbar_bg, foreground=generic_text_fg)
        nb_theme = theme_colors.get("notebook", {})
        nb_tab_font_fam = nb_theme.get("tab_font_family", "Segoe UI")
        nb_tab_font_size = nb_theme.get("tab_font_size", 9)
        nb_tab_font_style = nb_theme.get("tab_font_style", "normal")
        try:
            tkfont.Font(family=nb_tab_font_fam, size=nb_tab_font_size, weight=tkfont.BOLD if nb_tab_font_style == "bold" else tkfont.NORMAL)
        except tk.TclError: nb_tab_font_fam = "TkDefaultFont"
        nb_tab_font_spec = (nb_tab_font_fam, nb_tab_font_size, nb_tab_font_style)
        s.configure("TNotebook", background=app_bg, borderwidth=1, bordercolor=nb_theme.get("border_color", toolbar_bg))
        s.configure("TNotebook.Tab", font=nb_tab_font_spec, padding=nb_theme.get("padding", [6, 3]),
                    background=nb_theme.get("tab_unselected_bg", toolbar_bg), foreground=nb_theme.get("tab_unselected_fg", generic_text_fg))
        s.map("TNotebook.Tab",
              background=[("selected", nb_theme.get("tab_selected_bg", app_bg)), ("active", nb_theme.get("tab_active_bg", app_bg))],
              foreground=[("selected", nb_theme.get("tab_selected_fg", generic_text_fg)), ("active", nb_theme.get("tab_active_fg", generic_text_fg))])
        tv_theme = theme_colors.get("treeview_general", {})
        tv_font_fam = tv_theme.get("font_family", "Segoe UI")
        tv_font_size = tv_theme.get("font_size", 9)
        try: tkfont.Font(family=tv_font_fam, size=tv_font_size)
        except tk.TclError: tv_font_fam = "TkDefaultFont"
        tv_font_spec = (tv_font_fam, tv_font_size)
        tv_heading_font_spec = (tv_font_fam, tv_font_size, tv_theme.get("heading_font_style", "bold"))
        s.configure("Treeview", background=tv_theme.get("bg", "white"), foreground=tv_theme.get("fg", "black"),
                    fieldbackground=tv_theme.get("bg", "white"), font=tv_font_spec, rowheight=int(tkfont.Font(font=tv_font_spec).metrics("linespace") * 1.3))
        s.map("Treeview", background=[('selected', tv_theme.get("selected_bg", "#D8D8D8"))], foreground=[('selected', tv_theme.get("fg", "black"))])
        s.configure("Treeview.Heading", background=tv_theme.get("heading_bg", toolbar_bg), foreground=tv_theme.get("heading_fg", generic_text_fg),
                    relief="flat", font=tv_heading_font_spec)
        s.map("Treeview.Heading", relief=[('active','groove'),('pressed','sunken')])
        s.configure("TPanedwindow", background=app_bg)
        s.configure("Sash", background=toolbar_bg, sashthickness=6, griplength=20)
        s.map("Sash", background=[("active", nb_theme.get("tab_selected_bg", toolbar_bg))])
        s.configure("Vertical.TScrollbar", background=toolbar_bg, troughcolor=app_bg)
        s.configure("Horizontal.TScrollbar", background=toolbar_bg, troughcolor=app_bg)
        if hasattr(self, 'toolbar_frame') and self.toolbar_frame.winfo_exists():
            self.toolbar_frame.config(style="TFrame")
        if hasattr(self.app, 'output_panel') and self.app.output_panel.winfo_exists():
            self.app.output_panel.text.config(bg=theme_colors.get("console_bg", "#1e1e1e"), fg=theme_colors.get("console_fg", "#d4d4d4"),
                                               insertbackground=theme_colors.get("editor_insert_bg", "white"), font=(tv_font_fam, tv_font_size))
        if self.ollama_chat_window and self.ollama_chat_window.winfo_exists():
            if hasattr(self.ollama_chat_window, '_apply_theme'):
                self.ollama_chat_window._apply_theme()
        if hasattr(self.app, 'inspector') and self.app.inspector.winfo_exists():
             self.app.inspector.config(bg=app_bg)
             self.app.inspector.tree.config(style="Treeview")
        if hasattr(self.app, 'stack') and self.app.stack.winfo_exists():
             self.app.stack.config(bg=app_bg)
             self.app.stack.tree.config(style="Treeview")
             self.app.stack.tree.tag_configure('current_frame', background=theme_colors.get("current_frame_stack_bg", "#cceeff"))
        self._apply_theme_to_all_editors()
    def _apply_theme_to_all_editors(self):
        theme_colors = THEMES.get(self.current_theme_name, THEMES["light"])
        for editor in self.open_tabs.values():
            if editor.winfo_exists() and isinstance(editor, CodeEditor):
                editor.apply_theme(theme_colors)
    def _apply_font_size_to_all_editors(self):
        for editor in self.open_tabs.values():
            if editor.winfo_exists() and isinstance(editor, CodeEditor):
                editor.set_font_size(self.current_editor_font_size)
    def _create_editor(self, filepath, opened_by_debugger=False, go_to_line=None):
        if not self.root.winfo_exists() or not (hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists()): return None
        try:
            if not isinstance(filepath, str): filepath = str(filepath)
            if not os.path.exists(filepath) or not os.path.isfile(filepath): return None
            norm_filepath = os.path.normcase(os.path.abspath(filepath))
        except Exception as e: messagebox.showerror("Error", f"Invalid file path: {filepath}\n{e}", parent=self.root); return None
        if norm_filepath in self.open_tabs:
            existing_editor = self.open_tabs[norm_filepath]
            if existing_editor.winfo_exists():
                 try:
                      self.app.notebook.select(existing_editor)
                      if opened_by_debugger:
                           existing_editor.set_read_only(True)
                           current_tab_text = self.app.notebook.tab(existing_editor, 'text')
                           is_already_ro = current_tab_text.startswith("[RO]") or current_tab_text.startswith("*[RO]")
                           if not is_already_ro:
                                prefix = "*" if current_tab_text.startswith('*') else ""
                                clean_title = current_tab_text.lstrip('*')
                                self.app.notebook.tab(existing_editor, text=f"{prefix}[RO] {clean_title}")
                      if go_to_line is not None: existing_editor.highlight_current_line(go_to_line)
                      return existing_editor
                 except tk.TclError: pass                                           
            else: del self.open_tabs[norm_filepath]                                         
        editor = CodeEditor(self.app.notebook, main_app_ref=self)
        editor.filepath = norm_filepath
        editor.opened_by_debugger = opened_by_debugger
        try:
            with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
            editor.text.insert('1.0', content)
            editor.text.edit_reset(); editor.text.edit_modified(False); editor.dirty = False
            if opened_by_debugger: editor.set_read_only(True)
        except Exception as e:
            messagebox.showerror("Error Opening File", f"Could not read file:\n{filepath}\n\n{e}", parent=self.root)
            try: editor.destroy()
            except: pass
            return None
        title = os.path.basename(filepath)
        tab_text = f"[RO] {title}" if opened_by_debugger else title
        try:
            self.app.notebook.add(editor, text=tab_text, padding=(2, 2))
            self.app.notebook.select(editor)
        except tk.TclError: editor.destroy(); return None                                 
        self.open_tabs[norm_filepath] = editor
        editor.text.bind('<<Modified>>', lambda e, ed=editor: self._mark_dirty(ed), add='+')
        for bp_path, ln in self.config.get('breakpoints', []):
            try:
                if os.path.normcase(os.path.abspath(str(bp_path))) == norm_filepath and isinstance(ln, int) and ln > 0:
                     editor.toggle_breakpoint(ln)
            except Exception: pass
        if go_to_line is not None: editor.highlight_current_line(go_to_line)
        if self.root.winfo_exists():
            self.root.after_idle(lambda ed=editor: self._apply_theme_to_editor(ed) if ed.winfo_exists() else None)
            self.root.after_idle(lambda ed=editor: self._apply_font_size_to_editor(ed) if ed.winfo_exists() else None)
        return editor
    def _apply_theme_to_editor(self, editor_widget):
        if editor_widget and editor_widget.winfo_exists():
            theme_colors = THEMES.get(self.current_theme_name, THEMES["light"])
            editor_widget.apply_theme(theme_colors)
    def _apply_font_size_to_editor(self, editor_widget):
        if editor_widget and editor_widget.winfo_exists():
            editor_widget.set_font_size(self.current_editor_font_size)
    def _clear_debug_state(self):
        was_running = self.is_running
        self.is_running = False; self.paused = False; self.command_pending = False
        if was_running and hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists():
            tabs_to_close_keys, tabs_to_forget_ids = [], []
            try:
                for tab_id in list(self.app.notebook.tabs()):                            
                    try:
                        widget = self.app.notebook.nametowidget(tab_id)
                        if isinstance(widget, CodeEditor) and getattr(widget, 'opened_by_debugger', False) and not getattr(widget, 'dirty', False):
                            if getattr(widget, 'filepath', None): tabs_to_close_keys.append(widget.filepath)
                            tabs_to_forget_ids.append(tab_id)
                    except (tk.TclError, AttributeError): continue
                for key in tabs_to_close_keys:
                    if key in self.open_tabs: del self.open_tabs[key]
                for tab_id in tabs_to_forget_ids:
                    try: self.app.notebook.forget(tab_id)
                    except tk.TclError: pass
            except tk.TclError: pass
        if hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists():
            try:
                for tab_id in self.app.notebook.tabs():
                    try:
                        widget = self.app.notebook.nametowidget(tab_id)
                        if isinstance(widget, CodeEditor):
                            widget.clear_current_line()
                            widget.set_read_only(False)
                            if getattr(widget, 'opened_by_debugger', False): widget.opened_by_debugger = False
                            current_tab_text = self.app.notebook.tab(tab_id, 'text')
                            new_text = current_tab_text.replace("[RO] ", "").replace("*[RO] ", "*")
                            if new_text != current_tab_text: self.app.notebook.tab(tab_id, text=new_text)
                    except (tk.TclError, AttributeError): continue
            except tk.TclError: pass
        self._update_ui_state()
    def _stop_debugging_session(self):
        if not self.is_running: return
        if self.root.winfo_exists(): self.status_var.set("Stopping...")
        self.app.stop_execution()
        self._clear_debug_state()
        if self.root.winfo_exists(): self.status_var.set("Execution stopped by user.")
        self._update_ui_state()
    def _on_tab_about_to_close(self, event=None):
        if not (hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists()): return "break"
        try:
            current_tab_id = self.app.notebook.select()
            if not current_tab_id: return "break"
            closing_editor_widget = self.app.notebook.nametowidget(current_tab_id)
            closing_filepath = getattr(closing_editor_widget, 'filepath', None)
            key_for_prompt = getattr(closing_editor_widget, '_temp_name', None) or\
                             (os.path.basename(closing_filepath) if closing_filepath else "unsaved file")
        except (tk.TclError, AttributeError): return "break"
        stop_debugging_if_closed = False
        if self.is_running and closing_filepath and\
           os.path.normcase(closing_filepath) == os.path.normcase(self.current_debug_target_path or ""):
            if messagebox.askyesno("Stop Debugging?", f"File being debugged ('{key_for_prompt}') is about to be closed.\nStop debugging session?", parent=self.root):
                stop_debugging_if_closed = True
            else: return "break"
        if getattr(closing_editor_widget, 'dirty', False):
            save_choice = messagebox.askyesnocancel("Save?", f"Save changes to {key_for_prompt}?", parent=self.root)
            if save_choice is None: return "break"
            elif save_choice is True:
                save_method = self.save_file_as if closing_filepath is None else self.save_file
                if save_method() == "break" or getattr(closing_editor_widget, 'dirty', False): return "break"
        try:
            self.app.notebook.forget(current_tab_id)
            if self.app.notebook.winfo_exists():                                    
                 self.app.notebook.event_generate("<<NotebookTabClosed>>")
        except tk.TclError: pass
        if stop_debugging_if_closed:
             self.app.stop_execution()
             self._clear_debug_state()
             if self.root.winfo_exists(): self.status_var.set("Debugging stopped (target file closed).")
             self._update_ui_state()
        return None                       
    def _on_tab_closed(self, event=None):
        current_tab_widgets = set()
        if hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists():
             try: current_tab_widgets = {self.app.notebook.nametowidget(tab_id) for tab_id in self.app.notebook.tabs()}
             except tk.TclError: pass
        closed_keys = [k for k, ed in list(self.open_tabs.items()) if not ed.winfo_exists() or ed not in current_tab_widgets]
        for key in closed_keys:
            if key in self.open_tabs: del self.open_tabs[key]
    def _update_ui_state(self):
        if not self.root.winfo_exists(): return
        is_debugging = self.is_running
        can_perform_debug_action = self.is_running and self.paused and not self.command_pending
        try:
            run_label = "Run F5" if not self.is_running or (self.is_running and not self.paused) else "Continue F5"
            run_state = 'normal' if not self.is_running or can_perform_debug_action else 'disabled'
            self.project_menu.entryconfigure(0, label=run_label, state=run_state)
            conf_args_state = 'disabled'
            if hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists():
                try:
                    current_tab_id = self.app.notebook.select()
                    if current_tab_id:
                        widget = self.app.notebook.nametowidget(current_tab_id)
                        if isinstance(widget, CodeEditor) and getattr(widget, 'filepath', None):
                            conf_args_state = 'normal' if not self.is_running else 'disabled'
                except tk.TclError: pass
            self.project_menu.entryconfigure(1, state=conf_args_state)
            self.project_menu.entryconfigure(2, state='normal' if self.is_running else 'disabled')       
            self.project_menu.entryconfigure(4, state='normal' if can_perform_debug_action else 'disabled')               
            step_state = 'normal' if can_perform_debug_action or not self.is_running else 'disabled'
            for i in [6, 7, 8]: self.project_menu.entryconfigure(i, state=step_state)                       
            file_close_state = 'normal' if not is_debugging else 'disabled'
            if hasattr(self, 'file_menu'):
                for label in ["Close", "Close All"]:
                    try: self.file_menu.entryconfigure(label, state=file_close_state)
                    except tk.TclError: pass                                                                     
            if hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists():
                self.app.notebook.set_debugging_state(is_debugging)
        except (tk.TclError, AttributeError): pass
    def _set_command_pending(self, pending):
        self.command_pending = pending
        self._update_ui_state()
    def _get_or_prompt_for_run_args(self, script_to_run):
        if not self.root.winfo_exists(): return None
        if script_to_run not in self.run_configs:
            dialog = RunConfigDialog(self.root, script_to_run, current_args="")
            script_args_str = dialog.result_args
            if script_args_str is None: return None
            self.run_configs[script_to_run] = script_args_str
            return script_args_str.split()
        else:
            return self.run_configs[script_to_run].split()
    def _do_step(self, step_command_func):
        if self.command_pending or not self.root.winfo_exists(): return
        if not (hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists()): return
        if not self.is_running:
            try:
                cur_tab_id = self.app.notebook.select()
                if not cur_tab_id: messagebox.showwarning("Step", "No file selected.", parent=self.root); return
                editor_widget = self.app.notebook.nametowidget(cur_tab_id)
            except tk.TclError: messagebox.showerror("Step Error", "No editor selected.", parent=self.root); return
            script_to_run = getattr(editor_widget, 'filepath', None)
            if not script_to_run: messagebox.showwarning("Step", "Selected file has no path. Please save it first.", parent=self.root); return
            script_args_list = self._get_or_prompt_for_run_args(script_to_run)
            if script_args_list is None: return
            breakpoints = editor_widget.breakpoints if hasattr(editor_widget, 'breakpoints') else []
            self.is_running = True; self.paused = False; self.current_debug_target_path = script_to_run
            self._set_command_pending(True)
            self.status_var.set(f"Starting step debug ({step_command_func.__name__})...")
            if not step_command_func(script_args=script_args_list):
                 self._clear_debug_state(); self.status_var.set("Failed to start debugger.")
            self._update_ui_state()
        elif self.paused:
            self._set_command_pending(True)
            self.status_var.set(f"Executing {step_command_func.__name__}...")
            if not step_command_func():
                self._set_command_pending(False); self.status_var.set("Failed to send step command.")
            self._update_ui_state()
        else: messagebox.showwarning("Step", "Debugger must be paused or not running to step.", parent=self.root)
    def _open_debug_exec_dialog(self):
        if not self.root.winfo_exists(): return
        if not self.is_running or not self.paused: messagebox.showwarning("Execute Code", "Debugger must be paused.", parent=self.root); return
        if self.command_pending: messagebox.showwarning("Execute Code", "Debugger busy.", parent=self.root); return
        if self.debug_exec_window is None or not self.debug_exec_window.winfo_exists():
            dialog_settings_to_pass = self.debug_exec_dialog_config.copy()
            self.debug_exec_window = DebugExecDialog(self.root, main_app_ref=self, config=dialog_settings_to_pass)
        else:
            self.debug_exec_window.lift(); self.debug_exec_window.focus_set()
    def _configure_run_arguments(self):
        if not self.root.winfo_exists() or not (hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists()): return
        try:
            cur_tab_id = self.app.notebook.select()
            if not cur_tab_id: messagebox.showwarning("Configure Run", "No file selected.", parent=self.root); return
            editor_widget = self.app.notebook.nametowidget(cur_tab_id)
        except tk.TclError: messagebox.showerror("Configure Run", "No editor selected.", parent=self.root); return
        script_to_run = getattr(editor_widget, 'filepath', None)
        if not script_to_run: messagebox.showwarning("Configure Run", "Selected file has no path. Please save it first.", parent=self.root); return
        current_args = self.run_configs.get(script_to_run, "")
        dialog = RunConfigDialog(self.root, script_to_run, current_args=current_args)
        if dialog.result_args is not None: self.run_configs[script_to_run] = dialog.result_args
    def _create_menus(self):
        if not self.root.winfo_exists(): return
        m = tk.Menu(self.root)
        fm = tk.Menu(m, tearoff=0)
        fm.add_command(label="New", accelerator="Ctrl+N", command=self.new_file)
        fm.add_command(label="Open...", accelerator="Ctrl+O", command=self.open_file)
        fm.add_command(label="Save", accelerator="Ctrl+S", command=self.save_file)
        fm.add_command(label="Save As...", command=self.save_file_as)
        fm.add_separator(); fm.add_command(label="Close", accelerator="Ctrl+W", command=self.close_file)
        fm.add_command(label="Close All", command=self.close_all_files); 
        fm.add_separator()
        fm.add_command(label="Configure Ollama...", command=self._open_ollama_config_dialog)        
        fm.add_separator()
        fm.add_command(label="Exit", command=self.on_exit); m.add_cascade(label="File", menu=fm); self.file_menu = fm
        em = tk.Menu(m, tearoff=0)
        em.add_command(label="Undo", accelerator="Ctrl+Z", command=self._dispatch_edit_command("edit_undo"))
        em.add_command(label="Redo", accelerator="Ctrl+Y", command=self._dispatch_edit_command("edit_redo"))
        em.add_separator(); em.add_command(label="Cut", accelerator="Ctrl+X", command=self._dispatch_standard_edit("<<Cut>>"))
        em.add_command(label="Copy", accelerator="Ctrl+C", command=self._dispatch_standard_edit("<<Copy>>"))
        em.add_command(label="Paste", accelerator="Ctrl+V", command=self._dispatch_standard_edit("<<Paste>>"))
        em.add_separator(); em.add_command(label="Select All", accelerator="Ctrl+A", command=self._dispatch_edit_command("select_all"))
        em.add_separator(); em.add_command(label="Find...", accelerator="Ctrl+F", command=self._open_find_dialog)
        m.add_cascade(label="Edit", menu=em)
        pm = tk.Menu(m, tearoff=0)
        pm.add_command(label="Run F5", accelerator="F5", command=self.toggle_run)
        pm.add_command(label="Configure Run Arguments...", command=self._configure_run_arguments)
        pm.add_command(label="Stop", command=self._stop_debugging_session, state='disabled'); pm.add_separator()
        pm.add_command(label="Execute Code in Debugger...", accelerator="Ctrl+E", command=self._open_debug_exec_dialog, state='disabled')
        pm.add_separator(); pm.add_command(label="Step Over", accelerator="F10", command=lambda: self._do_step(self.app.step_next))
        pm.add_command(label="Step Into", accelerator="F11", command=lambda: self._do_step(self.app.step_into))
        pm.add_command(label="Step Out", accelerator="Shift+F11", command=lambda: self._do_step(self.app.step_out))
        m.add_cascade(label="Project", menu=pm); self.project_menu = pm
        tm = tk.Menu(m, tearoff=0)
        tm.add_command(label="Ollama AI Chat", command=self._open_ollama_chat_window)
        m.add_cascade(label="Tools", menu=tm)                
        bindings = {
            "<F5>": lambda: self.toggle_run() if not self.command_pending else None,
            "<F10>": lambda: self._do_step(self.app.step_next) if not self.command_pending else None,
            "<F11>": lambda: self._do_step(self.app.step_into) if not self.command_pending else None,
            "<Shift-F11>": lambda: self._do_step(self.app.step_out) if not self.command_pending else None,
            "<Control-e>": self._open_debug_exec_dialog, "<Control-n>": self.new_file,
            "<Control-o>": self.open_file, "<Control-s>": self.save_file,
            "<Control-w>": self.close_file, "<Control-f>": self._open_find_dialog,
            "<Control-z>": self._dispatch_edit_command("edit_undo"),
            "<Control-y>": self._dispatch_edit_command("edit_redo")
        }
        for seq, cmd in bindings.items():
            self.root.bind_all(seq, lambda e, c=cmd: (c(), "break")[1])               
        self.root.config(menu=m); self._update_ui_state()
    def _dispatch_edit_command(self, method_name):
        def handler():
            if not self.root.winfo_exists(): return
            focused_widget = self.root.focus_get()
            editor_widget = None
            if isinstance(focused_widget, tk.Text):
                 for editor in self.open_tabs.values():
                      if editor.winfo_exists() and editor.text == focused_widget:
                           editor_widget = editor; break
            if editor_widget and hasattr(editor_widget, method_name):
                try: getattr(editor_widget, method_name)()
                except tk.TclError: pass                                   
        return handler
    def _dispatch_standard_edit(self, event_name):
         def handler():
              if not self.root.winfo_exists(): return
              focused_widget = self.root.focus_get()
              if focused_widget and focused_widget.winfo_exists():
                   try: focused_widget.event_generate(event_name)
                   except tk.TclError: pass
         return handler
    def _open_find_dialog(self, event=None):
        if not self.root.winfo_exists() or not (hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists()): return
        active_editor = None
        try:
            current_tab_id = self.app.notebook.select()
            if current_tab_id:
                widget = self.app.notebook.nametowidget(current_tab_id)
                if isinstance(widget, CodeEditor): active_editor = widget
        except tk.TclError: pass
        if not active_editor: messagebox.showinfo("Find", "No active editor tab to search in.", parent=self.root); return
        from gui.search_dialog import SearchReplaceDialog
        SearchReplaceDialog(self.root, self)
    def toggle_run(self):
        if self.command_pending or not self.root.winfo_exists(): return
        if not (hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists()): return
        if not self.is_running:
            try:
                cur_tab_id = self.app.notebook.select()
                if not cur_tab_id: messagebox.showwarning("Run", "No file selected to run.", parent=self.root); return
                editor_widget = self.app.notebook.nametowidget(cur_tab_id)
            except tk.TclError: messagebox.showerror("Run Error", "Could not get editor widget.", parent=self.root); return
            script_to_run = getattr(editor_widget, 'filepath', None)
            if not script_to_run: messagebox.showwarning("Run", "Selected file has no path. Please save it first.", parent=self.root); return
            script_args_list = self._get_or_prompt_for_run_args(script_to_run)
            if script_args_list is None: return
            self.is_running = True; self.paused = False
            self.current_debug_target_path = script_to_run
            self._set_command_pending(True)
            self.status_var.set(f"Running {os.path.basename(script_to_run)}...")
            if not self.app.run_project(script_args=script_args_list):
                self._clear_debug_state(); self.status_var.set("Failed to start debugger.")
            else: self._set_command_pending(True)                                                                    
            self._update_ui_state()
        elif self.is_running and self.paused:
            self.paused = False; self._set_command_pending(True)
            self.status_var.set("Continuing...")
            if not self.app.continue_execution():
                self.paused = True; self._set_command_pending(False); self.status_var.set("Failed to continue.")
            else: self._set_command_pending(False)                                                                           
            self._update_ui_state()
    def on_breakpoint_hit(self, filepath, line_number):
        if not self.root.winfo_exists(): return
        try:
            if not isinstance(filepath, str): filepath = str(filepath)
            norm_filepath = os.path.normcase(os.path.abspath(filepath))
        except Exception:
             self.status_var.set(f"Paused at invalid path: {line_number} (Path error)"); self.is_running=True;self.paused=True;self._set_command_pending(False);self._update_ui_state();return
        self.is_running = True; self.paused = True; self._set_command_pending(False)
        self.current_debug_target_path = norm_filepath; self._update_ui_state()
        for editor_key, ed_widget in list(self.open_tabs.items()):                              
            if ed_widget.winfo_exists(): ed_widget.clear_current_line()
            else: del self.open_tabs[editor_key]                                 
        editor = self.open_tabs.get(norm_filepath)
        if editor and not editor.winfo_exists():                                             
            del self.open_tabs[norm_filepath]; editor = None
        if editor:
            try:
                 self.app.notebook.select(editor); editor.highlight_current_line(line_number); editor.set_read_only(True)
                 current_tab_text = self.app.notebook.tab(editor, 'text')
                 if not (current_tab_text.startswith("[RO]") or current_tab_text.startswith("*[RO]")):
                      self.app.notebook.tab(editor, text=f"{'*' if current_tab_text.startswith('*') else ''}[RO] {current_tab_text.lstrip('*')}")
            except tk.TclError: editor = None                                  
        if not editor:
             editor = self._create_editor(norm_filepath, opened_by_debugger=True, go_to_line=line_number)
             if not editor: self.status_var.set(f"Paused at {os.path.basename(norm_filepath or '???')}:{line_number} (Editor fail)"); return
        if editor.winfo_exists():
            status_msg = f"Paused at {os.path.basename(norm_filepath or '???')}:{line_number}"
            if editor.text['state'] == 'disabled': status_msg += " [Read-Only]"
            self.status_var.set(status_msg)
        else: self.status_var.set(f"Paused at ???:{line_number} (Editor error)")
    def on_finished(self):
        self._clear_debug_state()
        if self.root.winfo_exists(): self.status_var.set("Execution finished")
    def on_exit(self):
         if not self.root.winfo_exists(): return
         can_exit = True
         for key, ed in list(self.open_tabs.items()):
             if ed.winfo_exists() and getattr(ed, 'dirty', False):
                 try:
                     self.app.notebook.select(ed)                     
                     key_for_prompt = getattr(ed, 'filepath', getattr(ed, '_temp_name', 'unsaved file'))
                     basename = os.path.basename(key_for_prompt) if key_for_prompt != 'unsaved file' else key_for_prompt
                     save_choice = messagebox.askyesnocancel("Save Changes?", f"Save changes to {basename} before exiting?", parent=self.root)
                     if save_choice is None: can_exit = False; break
                     elif save_choice is True:
                          save_method = self.save_file_as if ed.filepath is None else self.save_file
                          if save_method() == "break" or getattr(ed, 'dirty', False):                 
                              messagebox.showwarning("Save Failed", f"Could not save {basename}. Exit aborted.", parent=self.root)
                              can_exit = False; break
                 except tk.TclError: continue                                                
         if not can_exit: return
         if self.is_running: self.app.stop_execution()
         self._save_config()
         self.root.destroy()
    def _mark_dirty(self, ed):
        if not ed.winfo_exists() or not ed.text.edit_modified(): return
        if not getattr(ed, 'dirty', False):
            ed.dirty = True
            try:
                 if self.app.notebook.winfo_exists():
                     tab_id_text = self.app.notebook.tab(ed, 'text')                                       
                     if not tab_id_text.startswith('*'): self.app.notebook.tab(ed, text='*'+tab_id_text)
            except tk.TclError: pass
    def new_file(self, event=None):
        if not self.root.winfo_exists() or not (hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists()): return "break"
        i = 0
        while True:
            temp_name = f"new_{i}.py" if i > 0 else "new.py"
            if temp_name not in self.open_tabs: break
            i += 1
        editor = CodeEditor(self.app.notebook, main_app_ref=self)
        editor.filepath = None; editor._temp_name = temp_name; editor.dirty = False
        editor.text.edit_reset(); editor.text.edit_modified(False)
        try:
            self.app.notebook.add(editor, text=temp_name, padding=(2, 2))
            self.app.notebook.select(editor)
        except tk.TclError: editor.destroy(); return "break"
        self.open_tabs[temp_name] = editor
        editor.text.bind('<<Modified>>', lambda e, ed=editor: self._mark_dirty(ed), add='+')
        if self.root.winfo_exists():
            self.root.after_idle(lambda ed=editor: self._apply_theme_to_editor(ed) if ed.winfo_exists() else None)
            self.root.after_idle(lambda ed=editor: self._apply_font_size_to_editor(ed) if ed.winfo_exists() else None)
        return "break"
    def open_file(self, event=None):
        if not self.root.winfo_exists(): return "break"
        fps = filedialog.askopenfilenames(parent=self.root, title="Open Python Files", filetypes=[("Python","*.py")])
        if fps:                                 
            for fp_raw in fps:
                try:
                    fp = os.path.abspath(fp_raw)
                    if os.path.exists(fp) and os.path.isfile(fp): self._create_editor(fp)
                except Exception: continue                                 
        return "break"
    def save_file_as(self, event=None):
        if not self.root.winfo_exists() or not (hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists()): return "break"
        try:
            sel_tab_id = self.app.notebook.select(); ed = self.app.notebook.nametowidget(sel_tab_id)
        except tk.TclError: return "break"
        if not isinstance(ed, CodeEditor): return "break"
        initial_name = os.path.basename(ed.filepath or getattr(ed, '_temp_name', 'new.py'))
        fp_dialog = filedialog.asksaveasfilename(parent=self.root, defaultextension=".py",
            filetypes=[("Python","*.py")], initialfile=initial_name)
        if not fp_dialog: return "break"
        path_to_save_to_orig_case = fp_dialog
        norm_fp_saved = os.path.normcase(os.path.abspath(path_to_save_to_orig_case))
        if norm_fp_saved in self.open_tabs and self.open_tabs[norm_fp_saved] != ed:
             if not messagebox.askyesno("Overwrite?", f"{os.path.basename(norm_fp_saved)} is already open. Overwrite its content in the editor and on disk?", parent=self.root): return "break"
        old_key = getattr(ed, '_temp_name', ed.filepath)                                              
        ed.filepath = norm_fp_saved                      
        if hasattr(ed, '_temp_name'): delattr(ed, '_temp_name')
        if old_key and old_key in self.open_tabs and old_key != norm_fp_saved:
            del self.open_tabs[old_key]
        self.open_tabs[norm_fp_saved] = ed                                     
        try:
            if self.app.notebook.winfo_exists():
                self.app.notebook.tab(ed, text=os.path.basename(path_to_save_to_orig_case))
        except tk.TclError: pass
        try:
            content_to_save = ed.text.get('1.0', 'end-1c')
            with open(path_to_save_to_orig_case, 'w', encoding='utf-8') as f: f.write(content_to_save)
            ed.dirty = False; ed.text.edit_modified(False)                    
            if self.root.winfo_exists(): self.status_var.set(f"Saved as {os.path.basename(path_to_save_to_orig_case)}")
        except Exception as e: messagebox.showerror("Error Saving As", str(e), parent=self.root)
        return "break"
    def save_file(self, event=None):
        if not self.root.winfo_exists() or not (hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists()): return "break"
        try:
            sel_tab_id = self.app.notebook.select(); ed = self.app.notebook.nametowidget(sel_tab_id)
        except tk.TclError: return "break"
        if not isinstance(ed, CodeEditor): return "break"
        if ed.filepath is None: return self.save_file_as()
        path_for_write_operation = ed.filepath
        try:
            content_to_save = ed.text.get('1.0', 'end-1c')
            with open(path_for_write_operation, 'w', encoding='utf-8') as f: f.write(content_to_save)
            if self.app.notebook.winfo_exists():
                try:
                    current_tab_text = self.app.notebook.tab(ed, 'text')
                    if current_tab_text.startswith('*') and not current_tab_text.startswith("*[RO]"):
                       self.app.notebook.tab(ed, text=current_tab_text.lstrip('*'))
                except tk.TclError: pass
            ed.dirty = False; ed.text.edit_modified(False)
            if self.root.winfo_exists(): self.status_var.set(f"Saved {os.path.basename(path_for_write_operation)}")
        except Exception as e: messagebox.showerror("Error saving", str(e), parent=self.root)
        return "break"
    def close_file(self, event=None):
        if hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists():
            try:
                current_tab_id = self.app.notebook.select()
                if current_tab_id:
                    self.app.notebook.event_generate("<<NotebookTabAboutToClose>>")
            except tk.TclError: pass
        return "break"
    def close_all_files(self, event=None):
        if hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists():
            tab_ids_to_process = list(self.app.notebook.tabs())                    
            for tab_id in tab_ids_to_process:
                try:
                    if not self.app.notebook.winfo_exists(): break                
                    current_tabs_after_potential_close = self.app.notebook.tabs()
                    if tab_id not in current_tabs_after_potential_close : continue
                    self.app.notebook.select(tab_id)
                except tk.TclError: continue                                                     
                if self._on_tab_about_to_close() == "break":                                                   
                    return "break"
        return "break"
    def notify_breakpoint_change(self, filepath, line_number, action):
        if not (self.is_running and self.paused and not self.command_pending): return
        if self.command_pending:
            if self.root.winfo_exists(): messagebox.showinfo("Debugger Busy", "Cannot change breakpoint while debugger is processing.", parent=self.root)
            return
        if not self.app.dbg_conn: return
        norm_filepath = os.path.normcase(os.path.abspath(filepath))
        command_type = "add_breakpoint_runtime" if action == "added" else\
                       "remove_breakpoint_runtime" if action == "removed" else None
        if command_type:
            try: self.app.dbg_conn.send((command_type, (norm_filepath, line_number)))
            except Exception as e:
                if self.root.winfo_exists(): messagebox.showerror("Breakpoint Error", f"Failed to update breakpoint: {e}", parent=self.root)
    def _open_ollama_config_dialog(self):
        if not self.root.winfo_exists(): return
        OllamaConfigDialog(self.root, main_app_ref=self)
    def _open_ollama_chat_window(self):
        if not self.root.winfo_exists(): return
        if self.ollama_chat_window is None or not self.ollama_chat_window.winfo_exists():
            chat_cfg = self.config.get('chat_ai_config', {})
            api_url = chat_cfg.get('api_url')
            model_name = chat_cfg.get('selected_model')
            if not api_url or not model_name:
                messagebox.showwarning("Ollama Not Configured", 
                                       "Ollama API URL or default model is not set.\n"
                                       "Please configure it via File > Configure Ollama.", 
                                       parent=self.root)
                self._open_ollama_config_dialog()                             
                chat_cfg = self.config.get('chat_ai_config', {}) 
                api_url = chat_cfg.get('api_url')
                model_name = chat_cfg.get('selected_model')
                if not api_url or not model_name:                         
                    return 
            self.ollama_chat_window = OllamaChatWindow(self.root, main_app_ref=self)
        else:
            self.ollama_chat_window.lift()
            self.ollama_chat_window.focus_set()
    def get_active_editor_text_widget(self):
        if hasattr(self.app, 'notebook') and self.app.notebook.winfo_exists():
            try:
                current_tab_id = self.app.notebook.select()
                if current_tab_id:
                    editor_widget = self.app.notebook.nametowidget(current_tab_id)
                    if isinstance(editor_widget, CodeEditor) and hasattr(editor_widget, 'text'):
                        return editor_widget.text
            except tk.TclError:
                pass
        return None
if __name__ == "__main__":
    try:
        from multiprocessing import freeze_support
        freeze_support()
    except ImportError: pass
    root = tk.Tk()
    root.title("Python Debugger")
    main_app_instance = MainApplication(root)
    root.mainloop()
