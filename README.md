# Python DBG GUI

## Description

Python DBG GUI is a graphical user interface (GUI) for the Python debugger, designed to simplify the process of debugging Python code. It offers an integrated environment with a code editor, output panel, variable inspector, call stack, and step-by-step debugging capabilities.

The application also includes an integration with Ollama for AI assistance during coding and debugging.

![image](https://github.com/user-attachments/assets/a7a65274-e2ce-426c-a1cc-d67d7b5c02b3)


## Key Features

*   **Integrated Code Editor:**
    *   Syntax highlighting for Python.
    *   Line numbering and breakpoint management via double-click on the gutter.
    *   Basic autocompletion for keywords and words in the document.
    *   Customizable themes (light/dark) and adjustable font size.
    *   Standard editing functions (cut, copy, paste, undo, redo).
    *   Text search functionality.
*   **Visual Debugger:**
    *   Execution control: Run (F5), Continue (F5), Stop.
    *   Step-by-step debugging: Step Over (F10), Step Into (F11), Step Out (Shift+F11).
    *   Breakpoint management directly from the editor.
    *   Configuration of execution arguments for scripts.
*   **Information Panels:**
    *   **Console/Output:** Displays script output and handles input (stdin).
    *   **Variables Inspector:** Shows local and global variables in the current debug context.
    *   **Call Stack:** Displays the call stack during debugging.
*   **AI Integration (Ollama):**
    *   Dedicated chat window to interact with an Ollama model.
    *   Option to include the current editor code and/or the last console output as context for AI queries.
    *   Configuration of the Ollama server URL and selection of the default model.
*   **Persistent Configurations:**
    *   Automatic saving of application state (open files, breakpoints, panel sizes, theme, run configurations) to a platform-specific user directory (Windows, macOS, Linux).
*   **Debug Code Execution Window:**
    *   Allows execution of Python expressions or code blocks within the context of the current debug frame when execution is paused.

## Installation

### Prerequisites

*   Python 3.7+
*   `pip` (Python package installer)
*   `tkinter` (usually included with standard Python installations)
*   Optional (for enhanced AI chat display): `tkinterweb`
*   Optional (for dynamic icons from SVG URLs): `requests`, `cairosvg`, `Pillow`

### Steps

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/YOUR_USERNAME/python_dbg_gui.git
    cd python_dbg_gui
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the application:**
    ```bash
    python main.py
    ```

## Ollama Configuration (Optional)

If you wish to use the AI integration:

1.  Ensure you have [Ollama](https://ollama.com/) installed and running.
2.  Pull the models you want to use (e.g., `ollama pull llama3.2`).
3.  In the Python DBG GUI application, go to `File > Configure Ollama...`.
4.  Enter your Ollama server URL (usually `http://localhost:11434`) and select a default model from the list.

## Usage

*   **Open/Create Files:** Use the `File` menu.
*   **Save Files:** `Ctrl+S` or `File` menu.
*   **Set Breakpoints:** Double-click on the line number in the editor's gutter.
*   **Start Debugging:**
    *   Open the Python file you want to debug.
    *   Optional: Configure arguments via `Project > Configure Run Arguments...`.
    *   Press `F5` (Run/Continue) or `F10` (Step Over) / `F11` (Step Into) to start.
*   **Navigate Debugging:** Use `F10`, `F11`, `Shift+F11` or the corresponding buttons in the `Project` menu.
*   **AI Chat:** `Tools > Ollama AI Chat`.

*   ## Contributing

Contributions are welcome! If you have suggestions, bug reports, or want to contribute code:

1.  Fork the Project.
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the Branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

## License

This project is distributed under the MIT License. See the `LICENSE` file for more details (if you add one).

[![Support me on PayPal](https://www.paypalobjects.com/en_US/i/btn/btn_donate_LG.gif)](https://www.paypal.com/donate/?hosted_button_id=T4SKREGYTG5ES)
---

*This README was generated as a draft. Feel free to modify and improve it!*
