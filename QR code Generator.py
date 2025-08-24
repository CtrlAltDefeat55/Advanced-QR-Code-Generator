import os
import re
import json
import shutil
import platform
import subprocess
from io import BytesIO
import tkinter as tk
from tkinter import (
    ttk, filedialog, messagebox, colorchooser,
    StringVar, IntVar, BooleanVar, DoubleVar, Toplevel, Text
)
from PIL import Image, ImageTk, ImageDraw
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import (
    SquareModuleDrawer, GappedSquareModuleDrawer, CircleModuleDrawer,
    RoundedModuleDrawer, VerticalBarsDrawer, HorizontalBarsDrawer
)
from qrcode.image.styles.colormasks import SolidFillColorMask, RadialGradiantColorMask
from tkinterdnd2 import DND_FILES, TkinterDnD

# --- Configuration ---
CONFIG_FILE = "qr_generator_config.json"
DEFAULT_COLORS = {
    "fg": "#000000", "bg": "#FFFFFF",
    "grad_cen": "#000000", "grad_edge": "#4A044E"
}
DEFAULT_CONFIG = {
    "save_path": os.path.join(os.path.expanduser("~"), "Downloads"),
    "file_type": ".png", "box_size": 10, "border_size": 4,
    "error_correction": "H", "module_drawer": "Square",
    "color_presets": {}
}

# --- Utility Functions ---
def hex_to_rgb(hex_color):
    """Converts a hex color string #RRGGBB to an (R, G, B) tuple."""
    hex_color = hex_color.strip().lstrip('#')
    try:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return (0, 0, 0)  # Fallback to black


def _escape_wifi(s: str) -> str:
    """Escape special chars per Wi-Fi QR spec (\, ; , : , \")."""
    if s is None:
        return ""
    return (
        s.replace("\\", "\\\\")
         .replace(";", r"\;")
         .replace(",", r"\,")
         .replace(":", r"\:")
         .replace('"', r'\"')
    )


def build_wifi_payload(ssid: str, password: str, auth: str = "WPA", hidden: bool = False) -> str:
    """
    Build WIFI: payload that iOS/Android cameras understand.
    Auth: 'WPA', 'WEP', or 'nopass'. Hidden -> 'true'/'false'.
    """
    auth = (auth or "").upper()
    # If no password, prefer nopass unless user explicitly picked WEP.
    if not password and auth != "WEP":
        auth = "nopass"
    if auth not in ("WPA", "WEP", "nopass"):
        auth = "WPA" if password else "nopass"

    S = _escape_wifi(ssid or "")
    P = _escape_wifi(password or "")
    H = "true" if hidden else "false"

    if auth == "nopass":
        return f"WIFI:T:nopass;S:{S};H:{H};;"
    else:
        return f"WIFI:T:{auth};S:{S};P:{P};H:{H};;"


def _run(cmd):
    """Run a command and return stdout text, or '' on failure."""
    try:
        cp = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore"
        )
        if cp.returncode == 0:
            return cp.stdout
    except Exception:
        pass
    return ""


def _map_security(sec_text: str) -> str:
    """Map platform security strings to 'WPA'/'WEP'/'nopass'."""
    s = (sec_text or "").lower()
    if "wep" in s:
        return "WEP"
    if "wpa" in s:  # covers wpa, wpa2, wpa3, personal/enterprise
        return "WPA"
    if "open" in s or "none" in s or s.strip() == "":
        return "nopass"
    # Windows may show 'Open' as Authentication
    if "authentication" in s and "open" in s:
        return "nopass"
    return "WPA"


def detect_current_wifi():
    """
    Try to detect the current Wi-Fi connection: returns dict {ssid, security} or None.
    Windows: netsh
    macOS: airport -I or networksetup
    Linux: nmcli
    """
    system = platform.system()

    if system == "Windows" and shutil.which("netsh"):
        out = _run(["netsh", "wlan", "show", "interfaces"])
        if out:
            ssid = None
            auth = None
            for line in out.splitlines():
                if "SSID" in line and "BSSID" not in line:
                    ssid = line.split(":", 1)[-1].strip()
                elif "Authentication" in line:
                    auth = line.split(":", 1)[-1].strip()
            if ssid:
                return {"ssid": ssid, "security": _map_security(auth)}
        return None

    if system == "Darwin":
        # Prefer airport
        airport = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
        if os.path.exists(airport):
            out = _run([airport, "-I"])
            if out:
                ssid = None
                auth = None
                for line in out.splitlines():
                    if " SSID:" in line:
                        ssid = line.split(":", 1)[-1].strip()
                    elif "link auth" in line or "auth" in line:
                        auth = line.split(":", 1)[-1].strip()
                if ssid:
                    return {"ssid": ssid, "security": _map_security(auth)}
        # Fallback: networksetup (need Wi-Fi device)
        if shutil.which("networksetup"):
            hw = _run(["networksetup", "-listallhardwareports"])
            wifi_dev = None
            block = []
            for ln in hw.splitlines():
                if ln.strip() == "":
                    block = []
                    continue
                block.append(ln)
                if ln.startswith("Device:"):
                    # Check if this block was Wi-Fi
                    for b in block:
                        if "Wi-Fi" in b or "AirPort" in b:
                            wifi_dev = ln.split(":", 1)[-1].strip()
                            break
                if wifi_dev:
                    break
            if wifi_dev:
                out = _run(["networksetup", "-getairportnetwork", wifi_dev])
                # Example: "Current Wi-Fi Network: MySSID"
                m = re.search(r"Current Wi-Fi Network:\s*(.*)$", out.strip())
                if m:
                    ssid = m.group(1).strip()
                    return {"ssid": ssid, "security": "WPA"}  # best guess
        return None

    if shutil.which("nmcli"):
        # Active line: yes:<ssid>:<security>
        out = _run(["nmcli", "-t", "-f", "active,ssid,security", "dev", "wifi"])
        if out:
            for line in out.splitlines():
                parts = line.split(":")
                if parts and parts[0] == "yes":
                    ssid = parts[1] if len(parts) > 1 else ""
                    sec = parts[2] if len(parts) > 2 else ""
                    return {"ssid": ssid, "security": _map_security(sec)}
        return None

    return None


def scan_wifi_networks():
    """
    Scan surrounding Wi-Fi networks.
    Returns a list of dicts: [{'ssid': 'Name', 'security': 'WPA'|'WEP'|'nopass'}]
    """
    system = platform.system()
    results = []

    if system == "Windows" and shutil.which("netsh"):
        out = _run(["netsh", "wlan", "show", "networks", "mode=bssid"])
        if out:
            ssid = None
            auth = None
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("SSID "):
                    # e.g., "SSID 1 : MyNetwork"
                    ssid = line.split(":", 1)[-1].strip()
                    auth = None
                elif line.lower().startswith("authentication"):
                    auth = line.split(":", 1)[-1].strip()
                    if ssid:
                        results.append({"ssid": ssid, "security": _map_security(auth)})
                        ssid = None
                        auth = None
            # Deduplicate by SSID preserving first seen security
            uniq = {}
            for r in results:
                if r["ssid"] and r["ssid"] not in uniq:
                    uniq[r["ssid"]] = r
            return list(uniq.values())

    if system == "Darwin":
        airport = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
        if os.path.exists(airport):
            out = _run([airport, "-s"])
            # Output is a table; we'll try to split by columns
            lines = [ln for ln in out.splitlines() if ln.strip()]
            if len(lines) >= 2:
                hdr = lines[0]
                # crude column positions
                cols = [hdr.find("SSID"), hdr.find("BSSID"), hdr.find("RSSI"),
                        hdr.find("CHANNEL"), hdr.find("HT"), hdr.find("CC"),
                        hdr.find("SECURITY")]
                # Fallback if SECURITY not found
                sec_idx = cols[-1] if cols[-1] != -1 else None
                for ln in lines[1:]:
                    ssid = ln[:cols[1]].strip() if cols[1] != -1 else ln.split()[0]
                    sec = ln[sec_idx:].strip() if sec_idx is not None else ""
                    if ssid:
                        results.append({"ssid": ssid, "security": _map_security(sec)})
            # Dedup
            uniq = {}
            for r in results:
                if r["ssid"] and r["ssid"] not in uniq:
                    uniq[r["ssid"]] = r
            return list(uniq.values())

    if shutil.which("nmcli"):
        out = _run(["nmcli", "-t", "-f", "ssid,security", "dev", "wifi"])
        if out:
            for line in out.splitlines():
                parts = line.split(":")
                ssid = parts[0].strip()
                sec = parts[1].strip() if len(parts) > 1 else ""
                if ssid:
                    results.append({"ssid": ssid, "security": _map_security(sec)})
            # Dedup
            uniq = {}
            for r in results:
                if r["ssid"] and r["ssid"] not in uniq:
                    uniq[r["ssid"]] = r
            return list(uniq.values())

    # No scanner available
    return []


# The main application class now inherits from TkinterDnD.Tk
class QRCodeGeneratorApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("Advanced QR Code Generator")
        # Increased by +100 in height (was 980 in the last version)
        self.geometry("1100x1080")

        self.config = self.load_config()
        self.setup_variables()
        self.create_widgets()
        self.layout_widgets()

        self.generated_image = None
        self.qr_image_display = None
        self.history = []
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after(100, self.generate_qr_code)

    def setup_variables(self):
        """Initialize all Tkinter variables."""
        self.save_path_var = StringVar(value=self.config.get("save_path"))
        self.file_name_var = StringVar(value="my_qr_code")
        self.file_type_var = StringVar(value=self.config.get("file_type", ".png"))
        self.logo_path_var = StringVar()
        self.logo_rotation_var = DoubleVar(value=0)
        self.logo_size_var = DoubleVar(value=0.25)

        self.box_size_var = IntVar(value=self.config.get("box_size", 10))
        self.border_size_var = IntVar(value=self.config.get("border_size", 4))
        self.error_correction_var = StringVar(value=self.config.get("error_correction", "H"))
        self.module_drawer_var = StringVar(value=self.config.get("module_drawer", "Square"))

        self.use_gradient_var = BooleanVar(value=False)
        self.fg_color_var = StringVar(value=DEFAULT_COLORS["fg"])
        self.bg_color_var = StringVar(value=DEFAULT_COLORS["bg"])
        self.gradient_center_var = StringVar(value=DEFAULT_COLORS["grad_cen"])
        self.gradient_edge_var = StringVar(value=DEFAULT_COLORS["grad_edge"])

        self.preset_var = StringVar()

    def create_widgets(self):
        """Create all the widgets for the application."""
        # --- Main Paned Window for Resizing ---
        self.main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)

        # --- Control Frame (Left Pane) ---
        self.control_frame = ttk.Frame(self.main_pane, padding=15)
        self.main_pane.add(self.control_frame, weight=1)

        # Data Input
        ttk.Label(self.control_frame, text="Data (URL, Text, WIFI payload, etc.):").pack(fill="x", padx=5)
        self.data_frame = ttk.Frame(self.control_frame)
        self.data_text = Text(self.data_frame, height=5, wrap="word", undo=True)
        self.data_scrollbar = ttk.Scrollbar(self.data_frame, orient="vertical", command=self.data_text.yview)
        self.data_text.config(yscrollcommand=self.data_scrollbar.set)
        self.data_text.bind("<KeyRelease>", lambda e: self.generate_qr_code())

        # Templates / Helpers
        self.template_frame = ttk.Frame(self.control_frame)
        ttk.Button(self.template_frame, text="URL", command=lambda: self.set_data_text("https://")).pack(side="left")

        # Wi-Fi: open the smart builder (autofill + scan)
        ttk.Button(self.template_frame, text="Wi-Fi", command=self.open_wifi_builder_dialog).pack(side="left")
        # Keep explicit label if you like; both open the same dialog
        ttk.Button(self.template_frame, text="Wi-Fi Builder...", command=self.open_wifi_builder_dialog).pack(side="left")

        ttk.Button(self.template_frame, text="Text", command=lambda: self.set_data_text("")).pack(side="left")
        ttk.Button(self.template_frame, text="Composite...", command=self.open_composite_data_dialog).pack(side="left")

        # Customization Options
        self.options_frame = ttk.LabelFrame(self.control_frame, text="Customization", padding=10)

        # Color Options
        self.color_frame = ttk.LabelFrame(self.options_frame, text="Colors", padding=10)
        self.fg_button = ttk.Button(self.color_frame, text="QR Color", command=lambda: self.choose_color('fg'))
        self.bg_button = ttk.Button(self.color_frame, text="BG Color", command=lambda: self.choose_color('bg'))
        self.gradient_check = ttk.Checkbutton(self.color_frame, text="Use Gradient", variable=self.use_gradient_var, command=self.toggle_gradient)
        self.gradient_center_button = ttk.Button(self.color_frame, text="Center Color", command=lambda: self.choose_color('gradient_center'), state="disabled")
        self.gradient_edge_button = ttk.Button(self.color_frame, text="Edge Color", command=lambda: self.choose_color('gradient_edge'), state="disabled")
        self.reset_colors_button = ttk.Button(self.color_frame, text="Reset to Default", command=self.reset_colors)

        # Color Presets
        self.preset_frame = ttk.LabelFrame(self.options_frame, text="Color Presets", padding=10)
        self.preset_combo = ttk.Combobox(self.preset_frame, textvariable=self.preset_var, state="readonly")
        self.preset_combo.bind("<<ComboboxSelected>>", self.apply_preset)
        self.save_preset_button = ttk.Button(self.preset_frame, text="Save Preset", command=self.save_preset)
        self.update_preset_list()

        # Sizing and Style
        ttk.Label(self.options_frame, text="Module Size:").grid(row=2, column=0, sticky="w", pady=5)
        self.size_scale = ttk.Scale(self.options_frame, from_=1, to=20, orient="horizontal", variable=self.box_size_var, command=lambda e: self.generate_qr_code())
        ttk.Label(self.options_frame, text="Border Size:").grid(row=3, column=0, sticky="w", pady=5)
        self.border_scale = ttk.Scale(self.options_frame, from_=1, to=20, orient="horizontal", variable=self.border_size_var, command=lambda e: self.generate_qr_code())
        ttk.Label(self.options_frame, text="Error Correction:").grid(row=4, column=0, sticky="w", pady=5)
        self.error_combo = ttk.Combobox(self.options_frame, textvariable=self.error_correction_var, values=["L", "M", "Q", "H"], state="readonly")
        self.error_combo.bind("<<ComboboxSelected>>", lambda e: self.generate_qr_code())
        ttk.Label(self.options_frame, text="Module Style:").grid(row=5, column=0, sticky="w", pady=5)
        self.module_combo = ttk.Combobox(self.options_frame, textvariable=self.module_drawer_var, values=["Square", "GappedSquare", "Circle", "Rounded", "VerticalBars", "HorizontalBars"], state="readonly")
        self.module_combo.bind("<<ComboboxSelected>>", lambda e: self.generate_qr_code())

        # Logo
        self.logo_frame = ttk.LabelFrame(self.options_frame, text="Logo", padding=10)
        self.logo_button = ttk.Button(self.logo_frame, text="Select Logo", command=self.select_logo)
        self.clear_logo_button = ttk.Button(self.logo_frame, text="Clear Logo", command=self.clear_logo)
        self.logo_label = ttk.Label(self.logo_frame, text="No logo selected.", wraplength=150)

        self.logo_rotation_label = ttk.Label(self.logo_frame, text="Rotation: 0°")
        self.logo_rotation_slider = ttk.Scale(self.logo_frame, from_=-180, to=180, orient="horizontal",
                                              variable=self.logo_rotation_var, command=self.update_rotation_label_and_regen)

        self.logo_size_label = ttk.Label(self.logo_frame, text="Size: 25%")
        self.logo_size_slider = ttk.Scale(self.logo_frame, from_=0.10, to=0.50, orient="horizontal",
                                          variable=self.logo_size_var, command=self.update_size_label_and_regen)

        self.logo_actions_frame = ttk.Frame(self.logo_frame)
        # Intuitive: left = CCW (+90), right = CW (-90)
        self.rotate_left_button = ttk.Button(self.logo_actions_frame, text="<-", command=lambda: self.rotate_logo_fixed(+90), width=4)
        self.reset_logo_button = ttk.Button(self.logo_actions_frame, text="Reset Logo", command=self.reset_logo)
        self.rotate_right_button = ttk.Button(self.logo_actions_frame, text="->", command=lambda: self.rotate_logo_fixed(-90), width=4)

        # Save Options
        self.save_frame = ttk.LabelFrame(self.control_frame, text="Save Options", padding=10)
        self.save_path_entry = ttk.Entry(self.save_frame, textvariable=self.save_path_var)
        self.browse_button = ttk.Button(self.save_frame, text="Browse", command=self.browse_save_path)
        ttk.Label(self.save_frame, text="File Name:").grid(row=1, column=0, sticky="w", pady=5)
        self.file_name_entry = ttk.Entry(self.save_frame, textvariable=self.file_name_var)
        self.file_type_combo = ttk.Combobox(self.save_frame, textvariable=self.file_type_var, values=[".png", ".jpg", ".svg"], width=5, state="readonly")

        # Drag and Drop binding
        self.save_path_entry.drop_target_register(DND_FILES)
        self.save_path_entry.dnd_bind('<<Drop>>', self.handle_drop)

        self.save_button = ttk.Button(self.control_frame, text="Save QR Code", command=self.save_qr_code)

        # --- Display Area (Right Pane) ---
        self.display_pane = ttk.PanedWindow(self.main_pane, orient=tk.VERTICAL)
        self.main_pane.add(self.display_pane, weight=2)

        self.qr_frame = ttk.LabelFrame(self.display_pane, text="QR Code Preview", padding=10)
        self.qr_canvas = tk.Canvas(self.qr_frame, bg="white", highlightthickness=0)
        self.qr_canvas.bind("<Configure>", lambda e: self.display_qr_code())
        self.display_pane.add(self.qr_frame, weight=3)

        self.history_frame = ttk.LabelFrame(self.display_pane, text="History (Session Only)", padding=10)
        self.history_listbox = tk.Listbox(self.history_frame)
        self.history_listbox.bind("<<ListboxSelect>>", self.load_from_history)
        self.clear_history_button = ttk.Button(self.history_frame, text="Clear Session History", command=self.clear_history)
        self.display_pane.add(self.history_frame, weight=1)

    def layout_widgets(self):
        """Layout all the widgets in the main window."""
        # --- Left Pane: Controls ---
        self.data_frame.pack(expand=True, fill="both", padx=5, pady=5)
        self.data_scrollbar.pack(side="right", fill="y")
        self.data_text.pack(side="left", expand=True, fill="both")
        self.template_frame.pack(fill="x", padx=5)

        self.options_frame.pack(expand=True, fill="both", padx=5, pady=10)
        self.options_frame.columnconfigure(1, weight=1)

        self.color_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)
        self.color_frame.columnconfigure(1, weight=1)
        self.fg_button.grid(row=0, column=0, padx=2)
        self.bg_button.grid(row=0, column=1, padx=2)
        self.gradient_check.grid(row=1, column=0)
        self.gradient_center_button.grid(row=1, column=1, padx=2)
        self.gradient_edge_button.grid(row=1, column=2, padx=2)
        self.reset_colors_button.grid(row=0, column=2, padx=2)

        self.preset_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
        self.preset_frame.columnconfigure(0, weight=1)
        self.preset_combo.grid(row=0, column=0, sticky="ew", padx=2)
        self.save_preset_button.grid(row=0, column=1, padx=2)

        self.size_scale.grid(row=2, column=1, sticky="ew")
        self.border_scale.grid(row=3, column=1, sticky="ew")
        self.error_combo.grid(row=4, column=1, sticky="ew")
        self.module_combo.grid(row=5, column=1, sticky="ew")

        self.logo_frame.grid(row=6, column=0, columnspan=2, sticky="ew", pady=5)
        self.logo_frame.columnconfigure(1, weight=1)
        self.logo_button.grid(row=0, column=0, sticky="ew")
        self.clear_logo_button.grid(row=0, column=1, sticky="ew")
        self.logo_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=5)
        self.logo_rotation_label.grid(row=2, column=0, sticky="w", padx=5, pady=(5, 0))
        self.logo_rotation_slider.grid(row=2, column=1, sticky="ew", padx=5, pady=(5, 0))
        self.logo_size_label.grid(row=3, column=0, sticky="w", padx=5, pady=(5, 0))
        self.logo_size_slider.grid(row=3, column=1, sticky="ew", padx=5, pady=(5, 0))
        self.logo_actions_frame.grid(row=4, column=0, columnspan=2, pady=(5, 0))
        self.rotate_left_button.pack(side="left", expand=True, fill="x")
        self.reset_logo_button.pack(side="left", expand=True, fill="x", padx=10)
        self.rotate_right_button.pack(side="left", expand=True, fill="x")

        self.save_frame.pack(expand=True, fill="x", padx=5, pady=10)
        self.save_frame.columnconfigure(1, weight=1)
        self.save_path_entry.grid(row=0, column=1, sticky="ew")
        self.browse_button.grid(row=0, column=0, padx=5)
        self.file_name_entry.grid(row=1, column=1, sticky="ew", padx=5)
        self.file_type_combo.grid(row=1, column=2, padx=5)

        self.save_button.pack(fill="x", padx=5, pady=10)

        # --- Right Pane: Display ---
        self.qr_canvas.pack(expand=True, fill="both")
        self.history_listbox.pack(expand=True, fill="both")
        self.clear_history_button.pack(fill="x", pady=(6, 0))

        # --- Pack the main container LAST ---
        self.main_pane.pack(expand=True, fill="both")

    def update_rotation_label_and_regen(self, event=None):
        angle = int(self.logo_rotation_var.get())
        self.logo_rotation_label.config(text=f"Rotation: {angle}°")
        self.generate_qr_code()

    def update_size_label_and_regen(self, event=None):
        size_percent = int(self.logo_size_var.get() * 100)
        self.logo_size_label.config(text=f"Size: {size_percent}%")
        self.generate_qr_code()

    def rotate_logo_fixed(self, angle_change):
        current_angle = self.logo_rotation_var.get()
        new_angle = (current_angle + angle_change)
        while new_angle > 180:
            new_angle -= 360
        while new_angle <= -180:
            new_angle += 360
        self.logo_rotation_var.set(new_angle)
        self.update_rotation_label_and_regen()

    def reset_logo(self):
        self.logo_rotation_var.set(0)
        self.logo_size_var.set(0.25)
        self.update_rotation_label_and_regen()
        self.update_size_label_and_regen()

    def handle_drop(self, event):
        path = event.data.strip('{}')
        if os.path.isdir(path):
            self.save_path_var.set(path)
        else:
            messagebox.showwarning("Invalid Drop", "Please drop a folder, not a file.")

    def set_data_text(self, text):
        self.data_text.delete("1.0", tk.END)
        self.data_text.insert("1.0", text)
        self.generate_qr_code()

    def choose_color(self, target):
        if target in ['fg', 'bg']:
            var_name = f"{target}_color_var"
        else:
            var_name = f"{target}_var"

        current_color = getattr(self, var_name).get()
        color_code = colorchooser.askcolor(title=f"Choose color", initialcolor=current_color)[1]

        if color_code:
            getattr(self, var_name).set(color_code)
            self.generate_qr_code()

    def reset_colors(self):
        self.use_gradient_var.set(False)
        self.fg_color_var.set(DEFAULT_COLORS["fg"])
        self.bg_color_var.set(DEFAULT_COLORS["bg"])
        self.gradient_center_var.set(DEFAULT_COLORS["grad_cen"])
        self.gradient_edge_var.set(DEFAULT_COLORS["grad_edge"])
        self.toggle_gradient()

    def save_preset(self):
        dialog = Toplevel(self)
        dialog.title("Save Preset")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("300x120")
        ttk.Label(dialog, text="Enter preset name:").pack(padx=10, pady=5)
        name_entry = ttk.Entry(dialog, width=30)
        name_entry.pack(padx=10, pady=5)
        name_entry.focus()

        def on_ok():
            name = name_entry.get().strip()
            if not name:
                return
            self.config["color_presets"][name] = {
                "use_gradient": self.use_gradient_var.get(),
                "fg": self.fg_color_var.get(),
                "bg": self.bg_color_var.get(),
                "grad_cen": self.gradient_center_var.get(),
                "grad_edge": self.gradient_edge_var.get(),
            }
            self.update_preset_list()
            self.preset_var.set(name)
            dialog.destroy()

        ttk.Button(dialog, text="Save", command=on_ok).pack(pady=10)

    def apply_preset(self, event=None):
        preset_name = self.preset_var.get()
        preset = self.config["color_presets"].get(preset_name)
        if preset:
            self.use_gradient_var.set(preset["use_gradient"])
            self.fg_color_var.set(preset["fg"])
            self.bg_color_var.set(preset["bg"])
            self.gradient_center_var.set(preset["grad_cen"])
            self.gradient_edge_var.set(preset["grad_edge"])
            self.toggle_gradient()

    def update_preset_list(self):
        presets = list(self.config["color_presets"].keys())
        self.preset_combo['values'] = presets
        if presets:
            if self.preset_var.get() not in presets:
                self.preset_var.set(presets[0])
        else:
            self.preset_var.set("")

    def generate_qr_code(self, data=None, is_batch=False):
        data_to_encode = data if data is not None else self.data_text.get("1.0", tk.END).strip()
        if not data_to_encode:
            self.qr_canvas.delete("all")
            self.generated_image = None
            return

        try:
            error_map = {"L": qrcode.constants.ERROR_CORRECT_L, "M": qrcode.constants.ERROR_CORRECT_M,
                         "Q": qrcode.constants.ERROR_CORRECT_Q, "H": qrcode.constants.ERROR_CORRECT_H}
            qr = qrcode.QRCode(version=None, error_correction=error_map[self.error_correction_var.get()],
                               box_size=self.box_size_var.get(), border=self.border_size_var.get())
            qr.add_data(data_to_encode)
            qr.make(fit=True)

            bg_color_rgb = hex_to_rgb(self.bg_color_var.get())
            color_mask = (RadialGradiantColorMask(back_color=bg_color_rgb,
                                                  center_color=hex_to_rgb(self.gradient_center_var.get()),
                                                  edge_color=hex_to_rgb(self.gradient_edge_var.get()))
                          if self.use_gradient_var.get() else
                          SolidFillColorMask(front_color=hex_to_rgb(self.fg_color_var.get()), back_color=bg_color_rgb))

            # Logo transformations (resize, rotate) in memory
            logo_path = self.logo_path_var.get()
            embedded_logo_data = None

            if logo_path and os.path.exists(logo_path):
                try:
                    logo = Image.open(logo_path).convert("RGBA")
                    # Estimate QR pixel size to scale logo
                    qr_pixel_width = (qr.modules_count + 2 * self.border_size_var.get()) * self.box_size_var.get()
                    logo_size_ratio = self.logo_size_var.get()
                    max_logo_size = int(qr_pixel_width * logo_size_ratio)
                    logo.thumbnail((max_logo_size, max_logo_size), Image.Resampling.LANCZOS)

                    angle = self.logo_rotation_var.get()
                    if angle != 0:
                        logo = logo.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)

                    # Save transformed logo to in-memory buffer
                    logo_io = BytesIO()
                    logo.save(logo_io, format='PNG')
                    logo_io.seek(0)
                    embedded_logo_data = logo_io

                except Exception as e:
                    print(f"Error preparing logo: {e}")

            # Generate final QR image
            img = qr.make_image(image_factory=StyledPilImage,
                                module_drawer=self.get_module_drawer(),
                                color_mask=color_mask,
                                embeded_image_path=embedded_logo_data)

            if not is_batch:
                self.generated_image = img
                self.display_qr_code()
                self.update_history(data_to_encode, self.generated_image)
            return img
        except Exception as e:
            if not is_batch:
                messagebox.showerror("Generation Error", f"Failed to generate QR code:\n{e}")
            return None

    def display_qr_code(self, pil_image=None):
        image_to_show = pil_image or self.generated_image
        if not image_to_show:
            self.qr_canvas.delete("all")
            return

        canvas_w, canvas_h = self.qr_canvas.winfo_width(), self.qr_canvas.winfo_height()
        if canvas_w < 20 or canvas_h < 20:
            return

        img_w, img_h = image_to_show.size
        ratio = min((canvas_w - 20) / img_w, (canvas_h - 20) / img_h)
        new_w, new_h = int(img_w * ratio), int(img_h * ratio)
        if new_w <= 0 or new_h <= 0:
            return

        resized_img = image_to_show.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.qr_image_display = ImageTk.PhotoImage(resized_img)

        self.qr_canvas.delete("all")
        self.qr_canvas.create_image(canvas_w / 2, canvas_h / 2, image=self.qr_image_display)

    def open_wifi_builder_dialog(self):
        """Wi-Fi builder with auto-fill from current network and scan list."""
        dialog = Toplevel(self)
        dialog.title("Wi-Fi Builder")
        dialog.geometry("520x480")
        dialog.transient(self)
        dialog.grab_set()

        main = ttk.Frame(dialog, padding=15)
        main.pack(expand=True, fill="both")

        # --- Auto section: current + scan ---
        auto_frame = ttk.LabelFrame(main, text="Detect / Scan", padding=10)
        auto_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(auto_frame, text="Choose a detected network or use Custom:").grid(row=0, column=0, columnspan=2, sticky="w")

        networks_combo = ttk.Combobox(auto_frame, state="readonly")
        networks_combo.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=6)

        refresh_btn = ttk.Button(auto_frame, text="Refresh", width=10)
        refresh_btn.grid(row=1, column=1, sticky="e")

        auto_frame.columnconfigure(0, weight=1)

        # --- Manual fields ---
        ttk.Label(main, text="Network Name (SSID):").pack(anchor="w")
        ssid_var = StringVar()
        ttk.Entry(main, textvariable=ssid_var).pack(fill="x", padx=(0, 0), pady=(2, 8), ipady=2)

        ttk.Label(main, text="Password (leave blank for open networks):").pack(anchor="w")
        pass_var = StringVar()
        ttk.Entry(main, textvariable=pass_var, show="•").pack(fill="x", padx=(0, 0), pady=(2, 8), ipady=2)

        row2 = ttk.Frame(main)
        row2.pack(fill="x")
        ttk.Label(row2, text="Security:").pack(side="left")
        auth_var = StringVar(value="WPA")
        ttk.Combobox(row2, textvariable=auth_var, values=["WPA", "WEP", "nopass"], width=10, state="readonly").pack(side="left", padx=8)
        hidden_var = BooleanVar(value=False)
        ttk.Checkbutton(row2, text="Hidden network", variable=hidden_var).pack(side="left")

        help_txt = (
            "How to use:\n"
            "• Pick your network from the list above (or Custom).\n"
            "• SSID and Security auto-fill from detected info; you can edit.\n"
            "• Enter Password only if required; leave blank for open networks.\n"
            "• Hidden network: check if your SSID is not broadcast.\n\n"
            "On scan, phones will prompt to join this network."
        )
        ttk.Label(main, text=help_txt, foreground="#555", justify="left", wraplength=460).pack(fill="x", pady=(8, 0))

        # --- Populate combo ---
        def load_networks():
            items = [("Custom…", None)]
            current = detect_current_wifi()
            scanned = scan_wifi_networks()
            # Put current first if found
            if current and current.get("ssid"):
                items.append((f"Current: {current['ssid']} — {current['security']}", current))
            # Append scanned (unique by ssid, skip if same as current)
            seen = set([current["ssid"]] if current else [])
            for n in scanned:
                if n["ssid"] and n["ssid"] not in seen:
                    items.append((f"{n['ssid']} — {n['security']}", n))
                    seen.add(n["ssid"])
            networks_combo["values"] = [name for name, _ in items]
            networks_combo._items = items  # stash mapping
            # Default selection: Current if exists, else Custom
            sel_idx = 1 if len(items) > 1 else 0
            networks_combo.current(sel_idx)
            apply_selection(sel_idx)

        def apply_selection(idx):
            label, data = networks_combo._items[idx]
            if data is None:
                # Custom
                # do not change fields
                return
            ssid_var.set(data.get("ssid", ""))
            auth_var.set(_map_security(data.get("security", "")))

        def on_combo_change(event=None):
            idx = networks_combo.current()
            if hasattr(networks_combo, "_items") and 0 <= idx < len(networks_combo._items):
                apply_selection(idx)

        networks_combo.bind("<<ComboboxSelected>>", on_combo_change)
        refresh_btn.configure(command=load_networks)

        # Initial load
        load_networks()

        def on_insert():
            ssid = ssid_var.get().strip()
            if not ssid:
                messagebox.showwarning("Missing SSID", "Please enter or select the Wi-Fi network name (SSID).")
                return
            payload = build_wifi_payload(ssid, pass_var.get(), auth=auth_var.get(), hidden=hidden_var.get())
            self.set_data_text(payload)
            dialog.destroy()

        ttk.Button(main, text="Insert", command=on_insert).pack(pady=12)

    def open_composite_data_dialog(self):
        dialog = Toplevel(self)
        dialog.title("Composite Data Entry")
        dialog.geometry("500x560")
        dialog.transient(self)
        dialog.grab_set()

        main = ttk.Frame(dialog, padding=15)
        main.pack(expand=True, fill="both")

        # URL section
        url_var = StringVar()
        use_url_var = BooleanVar(value=False)
        url_row = ttk.LabelFrame(main, text="URL (optional)", padding=10)
        url_row.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(url_row, text="Include URL", variable=use_url_var).pack(anchor="w")
        url_entry = ttk.Entry(url_row, textvariable=url_var)
        url_entry.pack(fill="x", pady=4, ipady=2)

        # Wi-Fi section
        use_wifi_var = BooleanVar(value=False)
        wifi_row = ttk.LabelFrame(main, text="Wi-Fi (optional)", padding=10)
        wifi_row.pack(fill="x", pady=(0, 8))

        ttk.Checkbutton(wifi_row, text="Include Wi-Fi", variable=use_wifi_var).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        # Quick load from detection
        quick_btn = ttk.Button(wifi_row, text="Load from system…")
        quick_btn.grid(row=1, column=0, sticky="w", pady=(0, 6))
        quick_status = ttk.Label(wifi_row, text="", foreground="#555")
        quick_status.grid(row=1, column=1, columnspan=2, sticky="w", padx=6)

        ttk.Label(wifi_row, text="SSID:").grid(row=2, column=0, sticky="e")
        ssid_var = StringVar()
        ssid_entry = ttk.Entry(wifi_row, textvariable=ssid_var)
        ssid_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=6, pady=2)

        ttk.Label(wifi_row, text="Password:").grid(row=3, column=0, sticky="e")
        pass_var = StringVar()
        pass_entry = ttk.Entry(wifi_row, textvariable=pass_var, show="•")
        pass_entry.grid(row=3, column=1, columnspan=2, sticky="ew", padx=6, pady=2)

        ttk.Label(wifi_row, text="Security:").grid(row=4, column=0, sticky="e")
        auth_var = StringVar(value="WPA")
        auth_combo = ttk.Combobox(wifi_row, textvariable=auth_var, values=["WPA", "WEP", "nopass"], state="readonly", width=10)
        auth_combo.grid(row=4, column=1, sticky="w", padx=6, pady=2)

        hidden_var = BooleanVar(value=False)
        ttk.Checkbutton(wifi_row, text="Hidden network", variable=hidden_var).grid(row=4, column=2, sticky="w", padx=6, pady=2)

        wifi_help = (
            "Wi-Fi help:\n"
            "• SSID = your Wi-Fi name exactly.\n"
            "• Password = leave empty for open networks.\n"
            "• Security = WPA (most common), WEP (legacy), or 'nopass' (open).\n"
            "• Hidden network = check if the SSID is not broadcast.\n"
            "No brackets—use these fields. On scan, devices prompt to join."
        )
        ttk.Label(wifi_row, text=wifi_help, foreground="#555", justify="left", wraplength=420).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(6, 0)
        )

        wifi_row.columnconfigure(1, weight=1)
        wifi_row.columnconfigure(2, weight=0)

        def quick_load():
            quick_status.config(text="Detecting / scanning…")
            self.update_idletasks()
            current = detect_current_wifi()
            scanned = scan_wifi_networks()
            if current and current.get("ssid"):
                ssid_var.set(current["ssid"])
                auth_var.set(_map_security(current.get("security", "")))
                quick_status.config(text=f"Loaded current: {current['ssid']}")
            elif scanned:
                ssid_var.set(scanned[0]["ssid"])
                auth_var.set(scanned[0]["security"])
                quick_status.config(text=f"Loaded scanned: {scanned[0]['ssid']}")
            else:
                quick_status.config(text="No system Wi-Fi info found. Enter manually.")

        quick_btn.configure(command=quick_load)

        # Notes section
        use_notes_var = BooleanVar(value=False)
        notes_row = ttk.LabelFrame(main, text="Notes (optional)", padding=10)
        notes_row.pack(fill="both", expand=True, pady=(0, 8))
        ttk.Checkbutton(notes_row, text="Include Notes", variable=use_notes_var).pack(anchor="w")
        notes_text = Text(notes_row, height=6, wrap="word")
        notes_text.pack(fill="both", expand=True, pady=4)

        # Guidance
        hint = ttk.Label(
            main,
            foreground="#555",
            text=(
                "Tip: Scanners usually act on the FIRST recognized item.\n"
                "We'll put Wi-Fi first (if included), then URL, then notes."
            )
        )
        hint.pack(fill="x", pady=(4, 0))

        def normalize_url(u: str) -> str:
            u = u.strip()
            if not u:
                return ""
            if "://" not in u:
                return "https://" + u
            return u

        def on_confirm():
            parts = []

            # Wi-Fi first
            if use_wifi_var.get():
                ssid = ssid_var.get().strip()
                pwd = pass_var.get()
                auth = auth_var.get()
                if ssid:
                    parts.append(build_wifi_payload(ssid, pwd, auth=auth, hidden=hidden_var.get()))

            # URL second
            if use_url_var.get():
                url = normalize_url(url_var.get())
                if url:
                    parts.append(url)

            # Notes last
            if use_notes_var.get():
                txt = notes_text.get("1.0", tk.END).strip()
                if txt:
                    parts.append(txt)

            if not parts:
                messagebox.showwarning("Nothing to include", "Choose at least one item (URL, Wi-Fi, or Notes).")
                return

            self.set_data_text("\n".join(parts))
            dialog.destroy()

        ttk.Button(main, text="Confirm", command=on_confirm).pack(pady=12)
        url_entry.focus_set()

    def toggle_gradient(self):
        state = "normal" if self.use_gradient_var.get() else "disabled"
        self.gradient_center_button.config(state=state)
        self.gradient_edge_button.config(state=state)
        self.fg_button.config(state="disabled" if self.use_gradient_var.get() else "normal")
        self.generate_qr_code()

    def select_logo(self):
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp")])
        if path:
            self.logo_path_var.set(path)
            self.logo_label.config(text=os.path.basename(path))
            self.generate_qr_code()

    def clear_logo(self):
        self.logo_path_var.set("")
        self.logo_label.config(text="No logo selected.")
        self.reset_logo()
        self.generate_qr_code()

    def browse_save_path(self):
        path = filedialog.askdirectory(initialdir=self.save_path_var.get())
        if path:
            self.save_path_var.set(path)

    def get_module_drawer(self):
        drawers = {"Square": SquareModuleDrawer(), "GappedSquare": GappedSquareModuleDrawer(), "Circle": CircleModuleDrawer(),
                   "Rounded": RoundedModuleDrawer(), "VerticalBars": VerticalBarsDrawer(), "HorizontalBars": HorizontalBarsDrawer()}
        return drawers.get(self.module_drawer_var.get(), SquareModuleDrawer())

    def update_history(self, data, image):
        # Session-only history; not persisted to disk
        if data in [item['data'] for item in self.history]:
            return
        history_entry = {"data": data, "image": image.copy()}
        self.history.insert(0, history_entry)
        self.history_listbox.insert(0, data[:80] + "..." if len(data) > 80 else data)
        if len(self.history) > 20:
            self.history.pop()
            self.history_listbox.delete(tk.END)

    def clear_history(self):
        self.history.clear()
        self.history_listbox.delete(0, tk.END)

    def load_from_history(self, event):
        if not self.history_listbox.curselection():
            return
        history_entry = self.history[self.history_listbox.curselection()[0]]
        self.set_data_text(history_entry["data"])
        self.generated_image = history_entry["image"]
        self.display_qr_code(self.generated_image)

    def save_qr_code(self):
        if not self.generated_image:
            messagebox.showerror("Save Error", "Please generate a QR code first.")
            return

        file_name = self.file_name_var.get()
        file_type = self.file_type_var.get()
        save_path = self.save_path_var.get()

        if not file_name:
            messagebox.showerror("Save Error", "File name cannot be empty.")
            return

        full_path = os.path.join(save_path, f"{file_name}{file_type}")

        try:
            if file_type.lower() == '.jpg':
                rgb_image = self.generated_image.convert('RGB')
                rgb_image.save(full_path, 'JPEG')
            else:
                self.generated_image.save(full_path)

            messagebox.showinfo("Success", f"QR Code saved successfully to:\n{full_path}")
        except (IOError, PermissionError, ValueError) as e:
            messagebox.showerror("Save Error", f"Failed to save file: {e}\nCheck permissions or file name.")
        except Exception as e:
            messagebox.showerror("Save Error", f"An unexpected error occurred: {e}")

    def on_closing(self):
        self.save_config()
        self.destroy()

    def save_config(self):
        # Persist ONLY preferences (no history)
        self.config.update({
            "save_path": self.save_path_var.get(), "file_type": self.file_type_var.get(),
            "box_size": self.box_size_var.get(), "border_size": self.border_size_var.get(),
            "error_correction": self.error_correction_var.get(), "module_drawer": self.module_drawer_var.get()
        })
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=4)
        except IOError:
            print("Warning: Could not save config file.")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    full_config = DEFAULT_CONFIG.copy()
                    full_config.update(config)
                    return full_config
            except (IOError, json.JSONDecodeError):
                return DEFAULT_CONFIG.copy()
        return DEFAULT_CONFIG.copy()


if __name__ == "__main__":
    app = QRCodeGeneratorApp()
    app.mainloop()
