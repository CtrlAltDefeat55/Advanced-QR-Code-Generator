# Contributing

Thanks for helping improve the **Advanced QR Code Generator (Tkinter)**! PRs and issues are welcome.

## Dev setup

```bash
git clone https://github.com/<you>/qr-code-generator-gui.git
cd qr-code-generator-gui
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Project specifics

- **GUI:** Tkinter + `tkinterdnd2` (drag & drop)
- **QR engine:** `qrcode` with `StyledPilImage`, module drawers, and color masks
- **Images:** `Pillow` (logo processing, resizing, rotation)
- **Config:** `qr_generator_config.json` stores preferences only (no payload history persisted)

## Style & quality

- Follow **PEP 8**; docstring functions you add or change.
- Prefer small, focused PRs; update UI text concisely.
- Optional tooling (recommended):
  ```bash
  python -m pip install black ruff
  black .
  ruff check .
  ```

## Testing checklist

Please click through these before submitting:

- Launches on your OS and shows the preview
- Color changes (solid/gradient) render correctly
- All **six** module styles render
- Logo overlay rotation and size work
- Wi‑Fi builder generates a valid `WIFI:` payload (with and without password)
- Optional detection/scan succeeds if tools exist on your OS (otherwise still usable manually)
- Save dialog writes PNG and JPG; SVG export works for basic styles

## Commit messages

Use clear, descriptive messages (e.g., `ui: add gradient toggle`, `wifi: fix nmcli parser`).

## Docs

If behavior changes (module names, formats, builder fields), update **README.md** and **INSTALL.md**.
