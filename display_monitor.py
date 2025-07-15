#!/usr/bin/env python3
import sys
import math
import time
import colorsys
import threading

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from st7789 import ST7789

import socket, uuid, psutil
from datetime import datetime


SPI_PORT = 0
SPI_CS = 1
SPI_DC = 19   # PA0
SPI_RES = 17   # PA1
BACKLIGHT = 20 # PA3

# Create ST7789 LCD display class.
disp = ST7789(
    height=170,
    width=320,
    rotation=0,
    port=SPI_PORT,
    cs=SPI_CS,
    dc=SPI_DC,
    rst=SPI_RES,
    backlight=BACKLIGHT,
    spi_speed_hz=80 * 1000 * 1000,
    offset_left=0,
    offset_top=35
)
thermal_zones = {
    "CPU": "/sys/class/thermal/thermal_zone0/temp",
    "Hotspot": "/sys/class/thermal/thermal_zone1/temp",
    "NPU": "/sys/class/thermal/thermal_zone2/temp",
    "DDR": "/sys/class/thermal/thermal_zone3/temp"
}

metrics_data = []

def get_ip_address():
    try:
        # Создаём временное подключение и получаем IP адрес интерфейса, через который выходит в интернет
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Псевдоподключение к DNS Google
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"  # Фолбэк, если сеть недоступна
    
def GetThermalZone(zone="/sys/class/thermal/thermal_zone0/temp"):
    value = 0
    try:
        with open(zone, "r") as f:
            value = int(f.read().strip()) / 1000.0
    except FileNotFoundError:
        return None
    return value

def GetMetrics():
    ip = get_ip_address()
    raw_mac=('%012X' % uuid.getnode() )
    mac = ':'.join([raw_mac[i:i+2] for i in range(0, len(raw_mac), 2)])
    date_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    cpu_temp = GetThermalZone(thermal_zones["CPU"])
    hSpt_temp = GetThermalZone(thermal_zones["Hotspot"])
    cpu_load_percent=psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    ram_used_mb = ram.used / (1024 ** 2)
    ram_total_mb = ram.total / (1024 ** 2)
    message = [
        {
            "text": f"ipv4: {ip}",
            "size_x" : 0,
            "font_height": 0,
            "pos_x" : 0
        }, 
        {
            "text": f"mac: {mac}",
            "size_x" : 0,
            "font_height": 0,
            "pos_x" : 0
        }, 
        {
            "text": f"{date_time}",
            "size_x" : 0,
            "font_height": 0,
            "pos_x" : 0
        }, 
        {
            "text": f"CPU/hSpt: {cpu_temp:.1f} / {hSpt_temp:.1f} °C",
            "size_x" : 0,
            "font_height": 0,
            "pos_x" : 0
        }, 
        {
            "text": f"CPU load: {cpu_load_percent:.1f}%",
            "size_x" : 0,
            "font_height": 0,
            "pos_x" : 0
        }, 
        {
            "text": f"Mem usage: {ram_used_mb:.1f} MB / {ram_total_mb:.1f} MB",
            "size_x" : 0,
            "font_height": 0,
            "pos_x" : 0
        }  
    ]
    return message

def update_metrics_loop():
    global metrics_data
    while True:
        metrics_data = GetMetrics()
        time.sleep(1)  # Интервал обновления 



if __name__ == "__main__":  
    # Запуск фонового потока
    threading.Thread(target=update_metrics_loop, daemon=True).start()
    # Initialize display.
    disp.begin()

    img = Image.new('RGB', (disp.width, disp.height), color=(0, 0, 0)) 
    draw = ImageDraw.Draw(img)
    font_height = 22
    line_padding = 2
    line_height = font_height + line_padding
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_height)
 
    text_x = 0
    text_y = 0

    t_start = time.time()

    while True: 
        x = (time.time() - t_start) * 10 
        message = metrics_data
        for metric in message:
            metric["size_x"] = draw.textlength(metric["text"], font)
        draw.rectangle((0, 0, disp.width, disp.height), (0, 0, 0))
        text_y = 0
        for metric in message:
            size_x = metric["size_x"]
            x_1 =x % (size_x + disp.width)
            text = metric["text"]
            if size_x > disp.width:
                draw.text((int(text_x - x_1), text_y), text, font=font, fill=(255, 255, 255))
            else:
                draw.text((int(text_x), text_y), text, font=font, fill=(255, 255, 255))
            text_y += line_height
        
        

        disp.display(img)
