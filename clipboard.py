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
import traceback
# import syspyinstaller --onefile --noconsole --clean --name

# while True:
#     try:
#         print("Clipboard:", repr(pyperclip.paste()))
#     except Exception as e:
#         print("Error:", e)

# In[3]:



# ---------- Settings ----------
APP_DIR = os.path.join(os.getenv("APPDATA") or ".", "ClipMVP")
HISTORY_PATH = os.path.join(APP_DIR, "history.json")
MAX_HISTORY = 500
POLL_INTERVAL = 0.5  # seconds
HOTKEY_OPEN = "ctrl+shift+v"
# ------------------------------


# In[4]:
def safe_copy(text):
    """Copy text to the OS clipboard while telling the watcher to ignore it briefly."""
    global _ignore_until, last_clipboard
    last_clipboard = text
    _ignore_until = time.time() + 0.6   # mute watcher for 600ms
    pyperclip.copy(text)


def init_last_clipboard():
    """Initialize last_clipboard to the current OS clipboard so startup doesn't re-add it."""
    global last_clipboard
    try:
        val = pyperclip.paste()
        last_clipboard = val if isinstance(val, str) and val.strip() else ""
    except Exception:
        last_clipboard = ""


os.makedirs(APP_DIR, exist_ok=True)

_history_lock = threading.Lock()
clipboard_history = []
last_clipboard = ""
_watcher_started = False
_ignore_until=0.0
history_win = None
app_root = None
# In[5]:

# Optional: try to import pywin32 clipboard functions for a robust fallback
try:
    import win32clipboard
    _have_win32clipboard = True
except Exception:
    _have_win32clipboard = False

# Controls
RETRY_READS = 6            # number of attempts to read clipboard before giving up
RETRY_DELAY = 0.05         # seconds between attempts
LOG_THROTTLE = 5.0         # seconds between "clipboard locked" logs

_last_clip_locked_log = 0.0

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

def _try_paste_with_retries(retries=RETRY_READS, delay=RETRY_DELAY):
    """Try pyperclip.paste() several times; if fails and pywin32 available, try win32 fallback."""
    last_exc = None
    for attempt in range(retries):
        try:
            return pyperclip.paste()
        except Exception as e:
            last_exc = e
            time.sleep(delay)
    # pyperclip failed after retries; try win32clipboard direct open/close fallback if available
    if _have_win32clipboard:
        for attempt in range(retries):
            try:
                # Use win32clipboard safely: try to open, read, then close
                win32clipboard.OpenClipboard()
                try:
                    # Attempt to get unicode text; this can raise if no text format
                    data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                    return data
                finally:
                    try:
                        win32clipboard.CloseClipboard()
                    except Exception:
                        pass
            except Exception as e:
                last_exc = e
                # If can't open clipboard, sleep and retry
                time.sleep(delay)
        # fallback failed too
    raise last_exc

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
        # if newest already equals this text, skip
        if clipboard_history and clipboard_history[0] == text:
            # print("[add_clip] duplicate top skip:", repr(text)); 
            return
        # print("[add_clip] inserting:", repr(text))
        # Move to top if it already exists elsewhere
        if text in clipboard_history:
            clipboard_history.remove(text)
        clipboard_history.insert(0, text)
        if len(clipboard_history) > MAX_HISTORY:
            del clipboard_history[MAX_HISTORY:]
        save_history()


# In[8]:


def watch_clipboard():
    global last_clipboard, _ignore_until, _last_clip_locked_log
    tid = threading.get_ident()
    while True:
        try:
            try:
                text= _try_paste_with_retries()
            except Exception as e:
                now = time.time()
                if now - _last_clip_locked_log > LOG_THROTTLE:
                    _last_clip_locked_log = now
                    print("[watcher] clipboard read failed after retries:", repr(e))
                    traceback.print_exc()
                time.sleep(POLL_INTERVAL)
                continue

            # ignore non-string or empty
            if not isinstance(text, str) or not text.strip():
                time.sleep(POLL_INTERVAL)
                continue

            # If within ignore window, skip (this prevents programmatic-copies being re-added)
            if time.time() < _ignore_until:
                # update last_clipboard so we don't re-add after ignore window
                last_clipboard = text
                print("[watcher] ignoring programmatic copy:", repr(text))
                time.sleep(POLL_INTERVAL)
                continue

            # usual dedupe by last_clipboard
            if text != last_clipboard:
                last_clipboard = text
                # print("[watcher] new clipboard seen:", repr(text))
                try:
                    add_clip(text)
                except Exception as e:
                    print("[watcher] add_clip raised:", e)
                    traceback.print_exc()
                add_clip(text)
        except Exception as e:
            print('watcher exception:',e)
            traceback.print_exc
        time.sleep(POLL_INTERVAL)


# In[ ]:


def show_history_window():
    """
    Create a fresh Toplevel showing clipboard_history.
    If an old window exists, destroy it first — then create a new one.
    IMPORTANT: do NOT call .mainloop() here.
    """
    global history_win, app_root

    # ensure single hidden root exists
    if app_root is None:
        app_root = tk.Tk()
        app_root.withdraw()

    # destroy old Toplevel if present
    if history_win is not None and history_win.winfo_exists():
        try:
            history_win.destroy()
        except Exception:
            pass
        history_win = None

    # create new Toplevel (child of app_root)
    history_win = tk.Toplevel(app_root)
    history_win.title("Clipboard History")
    history_win.geometry("640x420")
    # flash topmost briefly so it appears above other windows, then release topmost
    history_win.attributes("-topmost", True)
    history_win.after(150, lambda: history_win.attributes("-topmost", False))

    # --- UI: frame, scrollbar, tree/listbox (simple example with Listbox) ---
    frame = tk.Frame(history_win)
    frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    lb = tk.Listbox(frame, selectmode=tk.EXTENDED, activestyle="dotbox")
    lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    lb.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=lb.yview)

    # snapshot the history under lock and populate the UI (we store full texts in items list)
    with _history_lock:
        items = clipboard_history[:200]

    for item in items:
        display = item.replace("\n", " ⏎ ").strip()
        if len(display) > 140:
            display = display[:140] + " …"
        lb.insert(tk.END, display)

    # helpers that map UI selection -> full texts
    def selected_texts():
        idxs = lb.curselection()
        if not idxs:
            return []
        return [items[i] for i in idxs if 0 <= i < len(items)]

    def copy_selected():
        texts = selected_texts()
        if not texts:
            messagebox.showwarning("Clipboard", "Select one or more entries.")
            return
        combined = "\n\n".join(t.strip() for t in texts if t.strip())
        safe_copy(combined)

    def combine_and_paste():
        copy_selected()
        try:
            keyboard.send("ctrl+v")
        except Exception:
            messagebox.showinfo("Clipboard", "Combined text copied. Press Ctrl+V to paste.")

    def delete_selected():
        idxs = list(lb.curselection())
        if not idxs:
            return
        # Map indices to full texts (remove one occurrence per selected index)
        to_remove = [items[i] for i in idxs if 0 <= i < len(items)]
        from collections import Counter
        counts = Counter(to_remove)
        with _history_lock:
            new_hist = []
            for h in clipboard_history:
                if counts.get(h, 0) > 0:
                    counts[h] -= 1
                    continue
                new_hist.append(h)
            clipboard_history[:] = new_hist
            save_history()
        # refresh listbox
        lb.delete(0, tk.END)
        with _history_lock:
            refreshed = clipboard_history[:200]
        for it in refreshed:
            disp = it.replace("\n", " ⏎ ").strip()
            if len(disp) > 140:
                disp = disp[:140] + " …"
            lb.insert(tk.END, disp)

    def on_double_click(evt):
        sel = selected_texts()
        if not sel:
            return
        safe_copy(sel[0])
        try:
            keyboard.send("ctrl+v")
        finally:
            # close after paste
            if history_win is not None and history_win.winfo_exists():
                history_win.destroy()

    # buttons
    btns = tk.Frame(history_win)
    btns.pack(fill=tk.X, padx=8, pady=(0,8))
    tk.Button(btns, text="Copy Combined", command=copy_selected).pack(side=tk.LEFT, padx=(0,8))
    tk.Button(btns, text="Combine & Paste", command=combine_and_paste).pack(side=tk.LEFT, padx=(0,8))
    tk.Button(btns, text="Delete Selected", command=delete_selected).pack(side=tk.LEFT, padx=(0,8))
    tk.Button(btns, text="Close (Esc)", command=history_win.destroy).pack(side=tk.RIGHT)

    history_win.bind("<Escape>", lambda e: history_win.destroy())
    lb.bind("<Double-Button-1>", on_double_click)

    # bring to front & focus
    history_win.lift()
    history_win.focus_force()    


# In[10]:


def main():
    """
    Safe startup: initialize history, init last_clipboard, start single watcher thread once,
    create hidden root and register hotkey to schedule show_history_window on the Tk thread.
    """
    global _watcher_started, app_root

    load_history()
    init_last_clipboard()

    if not _watcher_started:
        threading.Thread(target=watch_clipboard, daemon=True).start()
        _watcher_started = True

    # ensure single hidden root exists and run its mainloop
    app_root = tk.Tk()
    app_root.withdraw()

    # register hotkey: schedule UI work on Tk thread using app_root.after
    keyboard.add_hotkey(HOTKEY_OPEN, lambda: app_root.after(0, show_history_window))

    print(f"ClipMVP running. Press {HOTKEY_OPEN} to open history.")
    try:
        app_root.mainloop()
    except KeyboardInterrupt:
        # cleanup hooks if needed
        try:
            keyboard.unhook_all()
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        raise

# --------------------

# In[ ]:





# In[1]:


# show_history_window()


# In[11]:


if __name__ == "__main__":
    main()

