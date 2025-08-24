# Install & Run — Advanced QR Code Generator (Tkinter)

This app is a **Python Tkinter GUI** that runs on **Windows, macOS, and Linux**. Optional Wi‑Fi auto‑detect/scan uses
system tools when present (Windows: `netsh`; macOS: `airport`/`networksetup`; Linux: `nmcli`).

## 1) Get the code

```bash
git clone https://github.com/<you>/qr-code-generator-gui.git
cd qr-code-generator-gui
```

## 2) Create a virtual environment (recommended)

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

## 3) Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Linux Tkinter prerequisites

On Debian/Ubuntu:
```bash
sudo apt-get update
sudo apt-get install -y python3-tk
```

On Fedora:
```bash
sudo dnf install -y python3-tkinter
```

You may also need NetworkManager to use `nmcli` for Wi‑Fi scans.

### macOS notes

- Tkinter is included with the official Python.org installer. With Homebrew Python, you may need `brew install tcl-tk`
  and ensure your Python links against it.
- Wi‑Fi scan uses Apple’s private `airport` tool if available, else falls back to `networksetup` to read the current SSID.

### Windows notes

No extra setup. Wi‑Fi info uses `netsh` if available.

## 4) Run the app

```bash
python "QR code Generator.py"
```

## 5) Troubleshooting

- **`ModuleNotFoundError` for `tkinter`** → install your OS’s Tk packages (see Linux/macOS notes above).
- **`tkinterdnd2` import error** → `pip install tkinterdnd2` (already in requirements.txt).
- **No Wi‑Fi info** → your OS tool isn’t available; use the dialog manually.
- **Fonts/emoji rendering issues** → depends on system fonts; try another font or export as PNG instead of JPG.
