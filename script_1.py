import os
import json
import time
import threading
import tkinter as tk
from tkinter import messagebox
import pyperclip
import keyboard

# ---------- Settings ----------
APP_DIR = os.path.join(os.getenv("APPDATA") or ".", "ClipMVP")
HISTORY_PATH = os.path.join(APP_DIR, "history.json")
MAX_HISTORY = 500
POLL_INTERVAL = 0.5  # seconds
HOTKEY_OPEN = "ctrl+shift+v"
# ------------------------------

os.makedirs(APP_DIR, exist_ok=True)

_history_lock = threading.Lock()
clipboard_history = []
last_clipboard = ""

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

def save_history():
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(clipboard_history[:MAX_HISTORY], f, ensure_ascii=False, indent=2)
    except Exception:
        pass

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

def show_history_window():
    # Build GUI
    win = tk.Tk()
    win.title("Clipboard History")
    win.geometry("520x380")
    win.attributes("-topmost", True)  # pop above quickly

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

    def selected_texts():
        idxs = lb.curselection()
        if not idxs:
            return []
        # Map UI indices back to the actual strings
        with _history_lock:
            return [items[i] for i in idxs if 0 <= i < len(items)]

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
        idxs = list(lb.curselection())
        if not idxs:
            return
        idxs_set = set(idxs)
        # Remove from in-memory history by matching the subset
        with _history_lock:
            keep = []
            for i, val in enumerate(items):
                if i not in idxs_set:
                    keep.append(val)
            # Rebuild: keep selected range removed + everything beyond shown slice
            # Map back into the full clipboard_history by excluding these items once
            delete_set = set(items[i] for i in idxs)
            new_hist = []
            for h in clipboard_history:
                if h in delete_set and h not in delete_set.__dict__.setdefault("_used", set()):
                    delete_set._used.add(h)
                    continue
                new_hist.append(h)
            # Fallback if the trick above confuses: simpler rebuild
            clipboard_history[:] = [h for h in clipboard_history if h not in set(items[i] for i in idxs)]
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

def main():
    load_history()
    threading.Thread(target=watch_clipboard, daemon=True).start()
    keyboard.add_hotkey(HOTKEY_OPEN, show_history_window)
    print(f"ClipMVP running. Press {HOTKEY_OPEN} to open history.")
    # NOTE: keyboard may require Administrator privileges on some systems
    keyboard.wait()

if __name__ == "__main__":
    main()
