#!/usr/bin/env python3
"""
System Monitor for RK3588 on ST7789 display.
Displays IP, MAC, date/time, CPU/Hotspot temperature,
CPU load and memory usage with auto‐scrolling text.
"""

import threading
import time
import socket
import uuid
from datetime import datetime

import psutil
from PIL import Image, ImageDraw, ImageFont

from st7789 import ST7789

# ─── SPI / Display Configuration ─────────────────────────────────────────────

SPI_PORT   = 0
SPI_CS     = 1
SPI_DC     = 19   # Data/Command GPIO
SPI_RES    = 17   # Reset GPIO
BACKLIGHT  = 20   # Backlight GPIO

disp = ST7789(
    height        = 170,
    width         = 320,
    rotation      = 0,
    port          = SPI_PORT,
    cs            = SPI_CS,
    dc            = SPI_DC,
    rst           = SPI_RES,
    backlight     = BACKLIGHT,
    spi_speed_hz  = 80 * 1000 * 1000,
    offset_left   = 0,
    offset_top    = 35
)

# ─── Thermal Zone Paths ──────────────────────────────────────────────────────

THERMAL_ZONES = {
    "CPU":     "/sys/class/thermal/thermal_zone0/temp",
    "Hotspot": "/sys/class/thermal/thermal_zone1/temp",
    "NPU":     "/sys/class/thermal/thermal_zone2/temp",
    "DDR":     "/sys/class/thermal/thermal_zone3/temp"
}

# This global is updated by the background thread
metrics_data = []


# ─── Utility Functions ──────────────────────────────────────────────────────

def get_ip_address():
    """
    Return the primary IPv4 address by opening a UDP socket to a public DNS.
    No actual packets are sent.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        sock.close()
    return ip


def get_thermal_zone(path: str) -> float | None:
    """
    Read the temperature in millidegrees and return Celsius.
    Returns None if the file isn't found or content is invalid.
    """
    try:
        with open(path, "r") as f:
            return int(f.read().strip()) / 1000.0
    except (FileNotFoundError, ValueError):
        return None


def get_metrics() -> list[dict]:
    """
    Gather all system metrics into a list of dicts.
    Each dict has keys: text, size_x, font_height, pos_x.
    """
    # Network identifiers
    ip = get_ip_address()
    raw_mac = f"{uuid.getnode():012X}"
    mac = ":".join(raw_mac[i : i + 2] for i in range(0, 12, 2))

    # Time
    dt = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    # Temperatures
    cpu_t  = get_thermal_zone(THERMAL_ZONES["CPU"])
    hs_t   = get_thermal_zone(THERMAL_ZONES["Hotspot"])

    # Load & memory
    cpu_load    = psutil.cpu_percent(interval=1)
    mem         = psutil.virtual_memory()
    mem_used_mb = mem.used  / (1024**2)
    mem_tot_mb  = mem.total / (1024**2)

    # Build a list of metric entries
    return [
        {"text": f"IPv4: {ip}",                                 "size_x": 0, "font_height": 0, "pos_x": 0},
        {"text": f"MAC: {mac}",                                 "size_x": 0, "font_height": 0, "pos_x": 0},
        {"text":     dt,                                        "size_x": 0, "font_height": 0, "pos_x": 0},
        {"text": f"CPU/Hotspot: {cpu_t:.1f}/{hs_t:.1f}°C",      "size_x": 0, "font_height": 0, "pos_x": 0},
        {"text": f"CPU Load: {cpu_load:.1f}%",                  "size_x": 0, "font_height": 0, "pos_x": 0},
        {"text": f"RAM: {mem_used_mb:.1f}/{mem_tot_mb:.1f} MB", "size_x": 0, "font_height": 0, "pos_x": 0}
    ]


def update_metrics_loop():
    """
    Background thread that refreshes metrics_data every second.
    """
    global metrics_data
    while True:
        metrics_data = get_metrics()
        time.sleep(1)


# ─── Main / Drawing Loop ────────────────────────────────────────────────────

def main():
    # Start the background metrics-updater
    threading.Thread(target=update_metrics_loop, daemon=True).start()

    # Initialize the display hardware
    disp.begin()

    # Prepare a PIL image canvas and drawing context
    img = Image.new("RGB", (disp.width, disp.height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Font and layout settings
    font_height   = 22
    line_padding  = 2
    line_height   = font_height + line_padding
    font_path     = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font          = ImageFont.truetype(font_path, font_height)

    start_time = time.time()

    while True:
        # Calculate a scroll offset based on elapsed time
        scroll_offset = (time.time() - start_time) * 10

        # Precompute width of each text entry
        for entry in metrics_data:
            entry["size_x"] = draw.textlength(entry["text"], font)

        # Clear the screen
        draw.rectangle((0, 0, disp.width, disp.height), fill=(0, 0, 0))

        # Draw each metric line, with auto‐scroll if needed
        y = 0
        for entry in metrics_data:
            text   = entry["text"]
            width  = entry["size_x"]

            if width > disp.width:
                # Auto‐scrolling: text slides left when too wide
                offset = int(scroll_offset % (width + disp.width))
                x = -offset
            else:
                # Center small text
                x = (disp.width - width) // 2

            draw.text((x, y), text, font=font, fill=(255, 255, 255))
            y += line_height

        # Push the buffer to the display
        disp.display(img)


if __name__ == "__main__":
    main()
