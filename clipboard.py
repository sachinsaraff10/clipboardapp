#!/usr/bin/env python
# coding: utf-8

# In[2]:


import os, shutil
import json
import time
import threading
import tkinter as tk
from tkinter import messagebox
import pyperclip
import keyboard
# import syspyinstaller --onefile --noconsole --clean --name


# In[3]:


# ---------- Settings ----------
APP_DIR = os.path.join(os.getenv("APPDATA") or ".", "ClipMVP")
HISTORY_PATH = os.path.join(APP_DIR, "history.json")
MAX_HISTORY = 500
POLL_INTERVAL = 0.5  # seconds
HOTKEY_OPEN = "ctrl+shift+v"
# ------------------------------


# In[4]:


os.makedirs(APP_DIR, exist_ok=True)

_history_lock = threading.Lock()
clipboard_history = []
last_clipboard = ""


# In[5]:


# HISTORY_FILE = "clipboard_history.json"
def load_history():
    global clipboard_history
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                clipboard_history = data[:MAX_HISTORY]
        except Exception:
            clipboard_history = []



# In[6]:

def add_to_startup(app_name="ClipMVP", exe_path=None):
    """
    Creates a shortcut to the app in the Windows Startup folder
    so it launches automatically on login.
    """
    try:
        startup_dir = os.path.join(os.getenv("APPDATA"), 
                                   "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
        os.makedirs(startup_dir, exist_ok=True)

        if exe_path is None:
            exe_path = os.path.abspath(sys.argv[0])  # current script or exe

        shortcut_path = os.path.join(startup_dir, f"{app_name}.url")

        # .url file is a simple shortcut format, no external deps needed
        with open(shortcut_path, "w") as shortcut:
            shortcut.write(f"[InternetShortcut]\nURL=file:///{exe_path.replace(os.sep, '/')}\n")

        return True
    except Exception as e:
        print("Failed to add to startup:", e)
        return False
def save_history():
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(clipboard_history[:MAX_HISTORY], f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# In[ ]:





# In[7]:


def add_clip(text: str):
    text = text.strip()
    if not text:
        return
    with _history_lock:
        # Move to top if it already exists elsewhere
        if text in clipboard_history:
            clipboard_history.remove(text)
        clipboard_history.insert(0, text)
        # Trim
        if len(clipboard_history) > MAX_HISTORY:
            del clipboard_history[MAX_HISTORY:]
        save_history()


# In[8]:


def watch_clipboard():
    global last_clipboard
    while True:
        try:
            text = pyperclip.paste()
            if isinstance(text, str) and text and text != last_clipboard:
                last_clipboard = text
                add_clip(text)
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)


# In[ ]:


def show_history_window():
    # Build GUI
    win = tk.Tk()
    win.title("Clipboard History")
    win.geometry("520x380")
    win.attributes("-topmost", True)  # pop above quickly
    def _minimize_if_unfocused():
        # If no widget of this window currently has focus, minimize
        if win.focus_displayof() is None:
            win.iconify()

    def _on_focus_out(evt):
        # Small delay avoids false positives when focus moves between child widgets
        win.after(120, _minimize_if_unfocused)

    win.bind("<FocusOut>", _on_focus_out)

    # Optional: also minimize with Esc instead of closing
    # win.bind("<Escape>", lambda e: win.iconify())
    # Listbox with scrollbar, multi-select
    frame = tk.Frame(win)
    frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    lb = tk.Listbox(frame, selectmode=tk.EXTENDED, activestyle="dotbox")
    lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    lb.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=lb.yview)

    # Populate list
    with _history_lock:
        items = clipboard_history[:200]
    for item in items:
        # Keep lines short in the UI, but store full strings in listbox anyway
        display = item.replace("\n", " ⏎ ").strip()
        if len(display) > 140:
            display = display[:140] + " …"
        lb.insert(tk.END, display)
        # Listbox still holds actual text via an index lookup later

    # Actions bar
    btns = tk.Frame(win)
    btns.pack(fill=tk.X, padx=8, pady=(0,8))

    with _history_lock:
        items = clipboard_history[:200]

# dictionary mapping UI index -> full text
    index_to_text = {}

    for idx, item in enumerate(items):
        display = item.replace("\n", " ⏎ ").strip()
        if len(display) > 140:
            display = display[:140] + " …"
        lb.insert(tk.END, display)
        index_to_text[idx] = item   # store full version

    def selected_texts():
        idxs = lb.curselection()
        if not idxs:
            return []
        return [index_to_text[i] for i in idxs]


    def copy_selected():
        texts = selected_texts()
        if not texts:
            messagebox.showwarning("Clipboard", "Select one or more entries.")
            return
        # Join as separate paragraphs
        combined = "\n\n".join(t.strip() for t in texts if t.strip())
        pyperclip.copy(combined)

    
    def combine_and_paste():
        copy_selected()
        # Send Ctrl+V to paste wherever the focus is
        try:
            keyboard.send("ctrl+v")
        except Exception:
            messagebox.showinfo("Clipboard", "Combined text copied. Press Ctrl+V to paste.")

    def delete_selected():
        selected = list(lb.curselection())
        if not selected:
            return

        # Collect values to remove
        values_to_remove = [items[i] for i in selected]

        with _history_lock:
            # Remove from clipboard_history (the true persistent list)
            clipboard_history[:] = [h for h in clipboard_history if h not in values_to_remove]

            # Save to disk
            save_history()

        # Refresh UI
        lb.delete(0, tk.END)
        with _history_lock:
            refreshed = clipboard_history[:200]
        for it in refreshed:
            disp = it.replace("\n", " ⏎ ").strip()
            if len(disp) > 140:
                disp = disp[:140] + " …"
            lb.insert(tk.END, disp)


    def on_double_click(_evt):
        # Double-click on one item: copy and paste that single item
        sel = selected_texts()
        if not sel:
            return
        pyperclip.copy(sel[0])
        try:
            keyboard.send("ctrl+v")
        finally:
            win.destroy()

    # Buttons
    tk.Button(btns, text="Copy Combined", command=copy_selected).pack(side=tk.LEFT, padx=(0,8))
    tk.Button(btns, text="Combine & Paste", command=combine_and_paste).pack(side=tk.LEFT, padx=(0,8))
    tk.Button(btns, text="Delete Selected", command=delete_selected).pack(side=tk.LEFT, padx=(0,8))
    tk.Button(btns, text="Close (Esc)", command=win.destroy).pack(side=tk.RIGHT)

    # Shortcuts
    win.bind("<Escape>", lambda e: win.destroy())
    lb.bind("<Double-Button-1>", on_double_click)
    win.mainloop()  


# In[10]:


def main():
    load_history()
    threading.Thread(target=watch_clipboard, daemon=True).start()
    keyboard.add_hotkey(HOTKEY_OPEN, show_history_window)
    print(f"ClipMVP running. Press {HOTKEY_OPEN} to open history.")
    # NOTE: keyboard may require Administrator privileges on some systems
    keyboard.wait()


# In[ ]:





# In[1]:


show_history_window()


# In[11]:


if __name__ == "__main__":
    main()

