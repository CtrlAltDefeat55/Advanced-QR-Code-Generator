# Advanced QR Code Generator (Tkinter)

A cross‑platform desktop app to **create beautiful, scannable QR codes** with a live preview, gradients or solid colors,
six module styles, optional **logo overlay** with rotation/size controls, **drag‑and‑drop** save location, and a smart
**Wi‑Fi payload builder** that can auto‑detect your current network or scan nearby networks (where supported).

- **Core script:** `QR code Generator.py` (Tkinter GUI)
- **Config file (auto‑created):** `qr_generator_config.json` (stores preferences like colors and last save path)

---

## Table of Contents

- [Features](#features)
- [Screenshot](#screenshot)
- [Installation](#installation)
- [Usage](#usage)
- [Tips & Notes](#tips--notes)
- [Dependencies](#dependencies)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Live preview** while you type or tweak options
- **Colors:** solid foreground/background *or* radial gradient
- **Six styles:** Square, GappedSquare, Circle, Rounded, VerticalBars, HorizontalBars
- **Logo overlay:** pick any image, rotate ±180°, scale to 10–50%
- **Drag & drop:** drop a folder onto the **Save Path** field
- **Session history:** quickly re‑use recent payloads (not persisted to disk)
- **Wi‑Fi builder:** create `WIFI:` payloads; optionally auto‑detect the current SSID and security, or scan nearby networks
  using **netsh** (Windows), **airport/networksetup** (macOS), or **nmcli** (Linux), when available
- **Safe saves:** warns on invalid names and reports success/failure

## Screenshot

> Add a screenshot at `assets/screenshot.png` and reference it here:

```
![App screenshot](assets/screenshot.png)
```

## Installation

Quick start is below. For a step‑by‑step guide and OS‑specific notes (Linux/macOS Tk setup, Wi‑Fi tooling), see **[INSTALL.md](INSTALL.md)**.

```bash
# (Recommended) create & activate a virtual environment
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# Install runtime deps
python -m pip install -r requirements.txt

# Run the app
python "QR code Generator.py"
```

## Usage

1. **Enter data** in the large text box (URL, text, or a prepared string).  
   - For Wi‑Fi: use **Wi‑Fi** → **Wi‑Fi Builder…** to auto‑fill SSID/security and generate a standards‑compliant `WIFI:` payload.
2. **Customize** colors (solid or gradient), error correction, module style, and border/box size.
3. **(Optional) Logo:** pick a logo, rotate, and size it 10–50% of the QR width.
4. **Choose save path** (type, browse, or drag a folder onto the field), file name, and format (**.png**, **.jpg**, **.svg**).
5. Click **Save QR Code**.

> The app stores preferences in `qr_generator_config.json` in the working directory.

### Supported content examples

- **URL:** `https://example.com`
- **Plain text:** `Hello, world!`
- **Wi‑Fi:** built via the dialog; output looks like `WIFI:T:WPA;S:MySSID;P:password;H:false;;`

## Tips & Notes

- **Cross‑platform GUI:** Tkinter works on Windows/macOS/Linux. On some Linux distros you may need `python3-tk` (details in INSTALL.md).
- **Wi‑Fi detection/scanning:** Requires the OS tools listed above. If not present, the builder still works—you’ll just fill fields manually.
- **SVG export:** Uses the `qrcode` package’s SVG support. Some advanced styles are raster‑only.
- **Drag‑and‑drop:** Provided by `tkinterdnd2`; no extra setup beyond `pip install` is usually needed.

## Dependencies

From `requirements.txt`:

- `qrcode>=7.4`
- `Pillow>=10.0.0`
- `tkinterdnd2>=0.3.0`

> Tkinter ships with CPython on Windows/macOS. On Linux, install your distro’s Tk packages (see INSTALL.md).

## Contributing

Contributions are welcome! Read **[CONTRIBUTING.md](CONTRIBUTING.md)** for style, testing, and PR tips.

## License

Add a license if you plan to distribute. Otherwise, this code is provided as‑is, without warranty.
=======
# Advanced-QR-Code-Generator
A cross-platform desktop app to create QR codes with a live preview and customization
>>>>>>> e555cdff646a229d6ae6116c6e8fc5552605ba76

