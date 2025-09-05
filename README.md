# 📋 ClipMVP – Clipboard Manager for Windows

A lightweight **clipboard history manager** for Windows.  
Automatically saves everything you copy and lets you paste any past entry with a global hotkey (**Ctrl+Shift+V**).  

🚀 Built with Python, Tkinter, and Pyperclip.

---

## ✨ Features

- 📝 **Clipboard history** – every copy is saved, nothing overwritten.  
- 🔎 **Quick recall** – press `Ctrl+Shift+V` to open a searchable history window.  
- 🖱️ **Multi-select** – select multiple entries, combine them, and paste in one go.  
- ❌ **Delete entries** – remove unwanted items (persists across sessions).  
- 🔄 **Session persistence** – history is saved between reboots.  
- ⚡ **Background utility** – runs silently, hotkey always ready.  

---

## 🔧 Installation

> ⚠️ No `.exe` provided (unsigned executables get blocked by Windows Defender).  
> Run the app **directly from source**.

### 1. Clone this repository

```bash
git clone https://github.com/sachinsaraff10/clipboardapp.git
cd clipboardapp
```
###2. Optional: Create a new Venv
```bash
python -m venv .venv
.venv\Scripts\activate   # Windows PowerShell
```
###3.Install requirements and run
```bash
pip install -r requirements.txt
python clipboard.py
```

