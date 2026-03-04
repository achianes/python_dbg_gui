# 🐞 Python Debug GUI

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](#requirements)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-informational)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](#license)

A lightweight **desktop GUI debugger** for Python scripts, built with **Tkinter**.  
Breakpoints, step controls, call stack and variable inspection — without needing a full IDE.

---

## ✨ Highlights

- 🔴 **Breakpoints** (add/remove quickly)
- ⏭ **Step Into / Step Over / Continue**
- 🧵 **Call stack** viewer
- 📦 **Variable inspector** (locals / globals)
- 🖥 **Integrated console** (stdout / stderr)
- ⚙️ **Isolated backend** using `multiprocessing` (keeps the GUI responsive)

---

## 🖼 Screenshots

TBD
## 🚀 Quick start

### 1) Clone

```bash
git clone https://github.com/achianes/python_dbg_gui.git
cd python_dbg_gui
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Run

```bash
python main.py
```

---

## 🧪 Debugging Flask apps (important)

If you debug a Flask application, disable Werkzeug reloader and threading to avoid spawning extra processes/threads that may confuse tracing:

```python
app.run(debug=False, use_reloader=False, threaded=False)
```

---

## 🏗 How it works

This project uses:

- `bdb.Bdb` for tracing and breakpoint control
- `multiprocessing.Process` to run the target script in an isolated backend
- `Pipe` to communicate between GUI and backend
- Thread-safe console redirection to show `stdout`/`stderr` in the GUI

Why the backend process matters:
- Keeps the GUI responsive even when the debugged script blocks or is slow
- Avoids contaminating the GUI process state

---

## 📁 Project structure

```text
python_dbg_gui/
├─ gui/                  # GUI + debugger backend components
├─ main.py               # Entry point
├─ requirements.txt
└─ README.md
```

---

## 🧾 Requirements

- Python **3.10+**
- Tkinter (bundled with standard Python on Windows/macOS; on some Linux distros you may need `python3-tk`)

---

## 🗺 Roadmap (ideas)

- [ ] Search + filter in variables view  
- [ ] Conditional breakpoints  
- [ ] Watch expressions  
- [ ] Better support for multi-thread tracing  
- [ ] Export stack/locals snapshot

---

## 🤝 Contributing

PRs are welcome. If you open an issue, include:
- OS + Python version
- Steps to reproduce
- A minimal example script (if possible)

---

## License

MIT — see `LICENSE` (or add one if missing).

---

## Author

Antonio Chianese  
GitHub: https://github.com/achianes

[![Support me on PayPal](https://www.paypalobjects.com/en_US/i/btn/btn_donate_LG.gif)](https://www.paypal.com/donate/?hosted_button_id=T4SKREGYTG5ES)
