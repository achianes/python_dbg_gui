# gui/custom_notebook.py
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont # Aggiunto per consistenza font

class CustomNotebook(ttk.Notebook):
    __initialized_style_structure = False # Rinominato per chiarezza

    def __init__(self, *args, **kwargs):
        self.main_app_ref = kwargs.pop('main_app_ref', None)
        # Ricevi il tema iniziale, se fornito
        initial_theme_colors = kwargs.pop('theme_colors', None)

        if not CustomNotebook.__initialized_style_structure:
            self._initialize_style_structure() # Chiamata una sola volta
            CustomNotebook.__initialized_style_structure = True

        kwargs["style"] = "CustomNotebook" # Imposta lo stile base del widget
        super().__init__(*args, **kwargs)

        self._active = None
        self.debugging_active = False

        # Applica la configurazione del tema iniziale per i tab
        if initial_theme_colors:
            self.apply_theme_config(initial_theme_colors)

        self.bind("<ButtonPress-1>", self.on_close_press, True)
        self.bind("<ButtonRelease-1>", self.on_close_release)

    def set_debugging_state(self, is_debugging):
        self.debugging_active = is_debugging

    def on_close_press(self, event):
        # ... (codice esistente) ...
        if self.debugging_active:
            return "break"                         
        element = self.identify(event.x, event.y)
        if "close" in element:
            try:                                
                index = self.index(f"@{event.x},{event.y}")
                self.state(['pressed'])
                self._active = index
                return "break"
            except tk.TclError:                           
                self._active = None
                self.state(["!pressed"])                                  
                return "break"                          
        return                                        


    def on_close_release(self, event):
        # ... (codice esistente) ...
        if self.debugging_active and self._active is not None:
            self.state(["!pressed"])
            self._active = None
            return "break"
        if not self.instate(['pressed']) or self._active is None:                         
            return
        element = self.identify(event.x, event.y)
        if "close" not in element:
            self.state(["!pressed"])
            self._active = None
            return
        try:                 
            index_at_release = self.index(f"@{event.x},{event.y}")
            if self._active == index_at_release:
                self.event_generate("<<NotebookTabAboutToClose>>")
        except tk.TclError:
            pass                                                               
        finally:
            self.state(["!pressed"])
            self._active = None


    def _initialize_style_structure(self): # Metodo per definire elementi e layout
        style = ttk.Style()
        current_theme = style.theme_use()
        try:
            if current_theme not in ('clam', 'alt', 'default'):
                style.theme_use('clam')
        except tk.TclError:
            print("Warning: Could not switch to 'clam' theme. Using default.")

        if not hasattr(CustomNotebook, '_tab_close_images'):
            # ... (codice esistente per caricare le immagini) ...
            try:
                img_close = tk.PhotoImage(name="custom_notebook_tab_close", data='''
                    R0lGODlhCAAIAMIBAAAAADs7O4+Pj9nZ2Ts7Ozs7Ozs7Ozs7OyH+EUNyZWF0ZWQg
                    d2l0aCBHSU1QACH5BAEKAAQALAAAAAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU
                    5kEJADs=''' )
                img_closeactive = tk.PhotoImage(name="custom_notebook_tab_close_active", data='''
                    R0lGODlhCAAIAMIEAAAAAP/SAP/bNNnZ2cbGxsbGxsbGxsbGxiH+EUNyZWF0ZWQg
                    d2l0aCBHSU1QACH5BAEKAAQALAAAA
                    AAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU
                    5kEJADs=''' )
                img_closepressed = tk.PhotoImage(name="custom_notebook_tab_close_pressed", data='''
                    R0lGODlhCAAIAMIEAAAAAOUqKv9mZtnZ2Ts7Ozs7Ozs7Ozs7OyH+EUNyZWF0ZWQg
                    d2l0aCBHSU1QACH5BAEKAAQALAAAAAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU
                    5kEJADs=''' )
                CustomNotebook._tab_close_images = (img_close, img_closeactive, img_closepressed)
            except tk.TclError as e:
                print(f"Error creating PhotoImages for tab close button: {e}")
                CustomNotebook._tab_close_images = None
                return                                               
        if not CustomNotebook._tab_close_images:
            print("Tab close images not available, cannot create 'close' element.")
            return
        img_close, img_closeactive, img_closepressed = CustomNotebook._tab_close_images


        try:
            style.element_create("close", "image", img_close,
                                 ("active", "pressed", "!disabled", img_closepressed),
                                 ("active", "!disabled", img_closeactive),
                                 border=8, sticky='')
        except tk.TclError as e:
            # Se l'elemento esiste già (es. cambio tema), non è un errore grave
            if "already exists" not in str(e):
                 print(f"Warning: Could not create style element 'close': {e}. Tab close button may not appear.")
            # return # Non ritornare, continua con il layout

        style.layout("CustomNotebook", [("CustomNotebook.client", {"sticky": "nswe"})])
        style.layout("CustomNotebook.Tab", [
            ("CustomNotebook.tab", {
                "sticky": "nswe",
                "children": [
                    ("CustomNotebook.padding", {
                        "side": "top",
                        "sticky": "nswe",
                        "children": [
                            ("CustomNotebook.focus", {
                                "side": "top",
                                "sticky": "nswe",
                                "children": [
                                    ("CustomNotebook.label", {"side": "left", "sticky": ''}),
                                    ("close", {"side": "left", "sticky": ''}),
                                ]
                            })
                        ]
                    })
                ]
            })
        ])
        # NON configurare font/colori qui, lo farà apply_theme_config

    def apply_theme_config(self, theme_colors):
        """Applica la configurazione del tema ai tab del CustomNotebook."""
        if not theme_colors:
            return

        style = ttk.Style()
        nb_theme_config = theme_colors.get("notebook", {})

        tab_font_family = nb_theme_config.get("tab_font_family", "Arial")
        tab_font_size = nb_theme_config.get("tab_font_size", 10) # Un default ragionevole
        tab_font_style = nb_theme_config.get("tab_font_style", "normal")
        
        try: # Verifica che il font sia valido
            tkfont.Font(family=tab_font_family, size=tab_font_size, weight=tkfont.BOLD if tab_font_style == "bold" else tkfont.NORMAL)
        except tk.TclError:
            tab_font_family = "TkDefaultFont" # Fallback

        tab_font_spec = (tab_font_family, tab_font_size, tab_font_style)
        
        padding = nb_theme_config.get("padding", [8, 2])
        selected_fg = nb_theme_config.get("tab_selected_fg", "white")
        selected_bg = nb_theme_config.get("tab_selected_bg", "#007acc")
        unselected_fg = nb_theme_config.get("tab_unselected_fg", "black")
        unselected_bg = nb_theme_config.get("tab_unselected_bg", "#E0E0E0")
        active_fg = nb_theme_config.get("tab_active_fg", "black") # Per quando il mouse è sopra un tab non selezionato
        active_bg = nb_theme_config.get("tab_active_bg", "#F0F0F0")

        try:
            style.configure("CustomNotebook.Tab",
                            font=tab_font_spec,
                            padding=padding)

            style.map("CustomNotebook.Tab",
                      foreground=[("selected", selected_fg),
                                  ("active", active_fg), # Stato active (mouse over)
                                  ("!selected", unselected_fg)],
                      background=[("selected", selected_bg),
                                  ("active", active_bg), # Stato active
                                  ("!selected", unselected_bg)])
            
            # Potrebbe essere necessario forzare un ridisegno o aggiornamento
            # se il widget è già visibile e il tema cambia dinamicamente.
            # self.update_idletasks() # A volte aiuta
            if self.winfo_exists(): # Se il widget esiste, aggiorna le schede visibili
                for tab_id in self.tabs():
                    self.tab(tab_id, text=self.tab(tab_id, "text")) # Forza rilettura opzioni tab

        except tk.TclError as e:
            print(f"Error applying theme to CustomNotebook.Tab: {e}")