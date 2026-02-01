#!/usr/bin/env python3
"""
Wiz Light - Minimal Elegant Controller with Music Sync
"""

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk
import colorsys
import math
import time
import threading
import json
import os
import sys
import numpy as np

try:
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

# Handle PyInstaller bundled resources
def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

# Import wiz_discovery from the correct location
sys.path.insert(0, get_base_path())
from wiz_discovery import WizDiscovery

# ============================================================================
# THEME
# ============================================================================

COLORS = {
    "bg": "#0f0f14",
    "surface": "#1a1a24",
    "accent": "#6366f1",
    "text": "#f8fafc",
    "text_dim": "#64748b",
    "on": "#22c55e",
    "off": "#374151",
}

# Store data in user's home directory (works for bundled app)
DATA_DIR = os.path.join(os.path.expanduser("~"), ".wizlight")
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, "wiz_data.json")


# ============================================================================
# COLOR WHEEL
# ============================================================================

class ColorWheel(ctk.CTkFrame):
    def __init__(self, master, size=220, on_change=None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.size = size
        self.on_change = on_change
        self.center = size // 2
        self.radius = size // 2 - 12
        self.hue = 0.0
        self.sat = 1.0
        self.last_send = 0

        self.canvas = ctk.CTkCanvas(self, width=size, height=size,
                                     bg=COLORS["bg"], highlightthickness=0)
        self.canvas.pack()
        self._render_wheel()
        self._draw_selector()

        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)

    def _render_wheel(self):
        img = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        for y in range(self.size):
            for x in range(self.size):
                dx, dy = x - self.center, y - self.center
                dist = math.sqrt(dx*dx + dy*dy)
                if dist <= self.radius:
                    h = (math.atan2(dy, dx) + math.pi) / (2 * math.pi)
                    s = dist / self.radius
                    r, g, b = colorsys.hsv_to_rgb(h, s, 1.0)
                    edge = self.radius - dist
                    a = 255 if edge > 2 else int(255 * edge / 2)
                    img.putpixel((x, y), (int(r*255), int(g*255), int(b*255), a))

        for y in range(self.center - 6, self.center + 6):
            for x in range(self.center - 6, self.center + 6):
                d = math.sqrt((x - self.center)**2 + (y - self.center)**2)
                if d <= 6:
                    a = int(255 * (1 - d/6) * 0.8) if d > 3 else 255
                    img.putpixel((x, y), (255, 255, 255, a))

        self._wheel_img = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor="nw", image=self._wheel_img)

    def _draw_selector(self):
        self.canvas.delete("sel")
        angle = self.hue * 2 * math.pi - math.pi
        dist = self.sat * self.radius
        x = self.center + dist * math.cos(angle)
        y = self.center + dist * math.sin(angle)

        r, g, b = colorsys.hsv_to_rgb(self.hue, self.sat, 1.0)
        fill = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

        self.canvas.create_oval(x-12, y-12, x+12, y+12,
                                outline="white", width=2, tags="sel")
        self.canvas.create_oval(x-8, y-8, x+8, y+8,
                                fill=fill, outline="", tags="sel")

    def _pos_to_hs(self, x, y):
        dx, dy = x - self.center, y - self.center
        dist = min(math.sqrt(dx*dx + dy*dy), self.radius)
        h = (math.atan2(dy, dx) + math.pi) / (2 * math.pi)
        s = dist / self.radius
        return h, s

    def _click(self, e):
        self.hue, self.sat = self._pos_to_hs(e.x, e.y)
        self._draw_selector()
        self._notify(True)

    def _drag(self, e):
        self.hue, self.sat = self._pos_to_hs(e.x, e.y)
        self._draw_selector()
        self._notify(False)

    def _release(self, e):
        self._notify(True)

    def _notify(self, force):
        if self.on_change and (force or time.time() - self.last_send > 0.05):
            self.on_change(self.hue, self.sat)
            self.last_send = time.time()

    def get_rgb(self):
        r, g, b = colorsys.hsv_to_rgb(self.hue, self.sat, 1.0)
        return int(r*255), int(g*255), int(b*255)

    def set_rgb(self, r, g, b):
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        self.hue, self.sat = h, s
        self._draw_selector()

    def set_hue(self, h):
        self.hue = h
        self._draw_selector()


# ============================================================================
# MUSIC VISUALIZER
# ============================================================================

class MusicVisualizer:
    def __init__(self, on_color_change):
        self.on_color_change = on_color_change
        self.running = False
        self.thread = None
        self.p = None
        self.stream = None

        # Audio settings
        self.CHUNK = 1024
        self.RATE = 44100
        self.last_hue = 0
        self.smoothing = 0.3

    def start(self):
        if not AUDIO_AVAILABLE:
            return False, "pyaudio not installed"
        if self.running:
            return True, None

        # Test microphone access first
        try:
            p = pyaudio.PyAudio()
            try:
                device_index = p.get_default_input_device_info()['index']
            except:
                p.terminate()
                return False, "No input device found"

            # Try to open stream briefly to trigger permission dialog
            try:
                test_stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=44100,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=1024
                )
                # Try to read - this triggers the macOS permission dialog
                test_stream.read(1024, exception_on_overflow=False)
                test_stream.stop_stream()
                test_stream.close()
            except OSError as e:
                p.terminate()
                if "Input overflowed" in str(e):
                    pass  # This is ok
                else:
                    return False, "Microphone permission denied. Grant access in System Settings > Privacy > Microphone"
            except Exception as e:
                p.terminate()
                return False, f"Mic error: {e}"

            p.terminate()
        except Exception as e:
            return False, f"Audio init failed: {e}"

        self.running = True
        self.thread = threading.Thread(target=self._audio_loop, daemon=True)
        self.thread.start()
        return True, None

    def stop(self):
        self.running = False
        # Give the audio loop time to exit cleanly
        time.sleep(0.1)

        stream = self.stream
        p = self.p
        self.stream = None
        self.p = None

        if stream:
            try:
                stream.stop_stream()
            except: pass
            try:
                stream.close()
            except: pass
        if p:
            try:
                p.terminate()
            except: pass

    def _audio_loop(self):
        try:
            self.p = pyaudio.PyAudio()

            # Find a working input device (prefer BlackHole or system audio)
            device_index = None
            for i in range(self.p.get_device_count()):
                info = self.p.get_device_info_by_index(i)
                name = info.get('name', '').lower()
                if info.get('maxInputChannels', 0) > 0:
                    if 'blackhole' in name or 'soundflower' in name or 'loopback' in name:
                        device_index = i
                        break

            # Fall back to default input (microphone)
            if device_index is None:
                try:
                    device_index = self.p.get_default_input_device_info()['index']
                except:
                    device_index = None

            if device_index is None:
                print("No audio input device found")
                return

            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.CHUNK
            )

            while self.running and self.stream:
                try:
                    data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                    if not self.running:
                        break

                    audio_data = np.frombuffer(data, dtype=np.int16)

                    # Get frequency spectrum
                    fft = np.abs(np.fft.fft(audio_data))[:self.CHUNK // 2]

                    # Split into frequency bands
                    bass = np.mean(fft[2:20])      # Low frequencies
                    mid = np.mean(fft[20:200])     # Mid frequencies
                    high = np.mean(fft[200:500])   # High frequencies

                    # Normalize
                    total = bass + mid + high + 1
                    bass_n = bass / total
                    mid_n = mid / total
                    high_n = high / total

                    # Map to hue: bass=red, mid=green, high=blue
                    if bass_n > mid_n and bass_n > high_n:
                        hue = 0.0 + (mid_n * 0.15)  # Red-ish
                    elif mid_n > bass_n and mid_n > high_n:
                        hue = 0.33 - (bass_n * 0.1)  # Green-ish
                    elif high_n > bass_n and high_n > mid_n:
                        hue = 0.66 + (mid_n * 0.1)  # Blue-ish
                    else:
                        hue = 0.5  # Cyan when balanced

                    # Volume-based saturation
                    volume = np.mean(np.abs(audio_data)) / 32768
                    sat = min(1.0, volume * 5 + 0.3)

                    # Smooth the hue changes
                    hue = self.last_hue * (1 - self.smoothing) + hue * self.smoothing
                    self.last_hue = hue

                    # Only update if there's significant audio and still running
                    if volume > 0.01 and self.running:
                        self.on_color_change(hue, sat)

                    time.sleep(0.05)

                except OSError:
                    # Stream closed
                    break
                except Exception:
                    if not self.running:
                        break
                    time.sleep(0.1)

        except Exception as e:
            print(f"Audio error: {e}")


# ============================================================================
# MAIN APP
# ============================================================================

class WizApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")

        self.title("Wiz")
        self.geometry("360x480")
        self.minsize(340, 460)
        self.configure(fg_color=COLORS["bg"])
        self.resizable(False, False)

        self.discovery = WizDiscovery()
        self.devices = {}
        self.current_ip = None
        self.device_online = {}
        self.brightness = 100
        self.saved_colors = []
        self.logs = []
        self.is_on = True
        self.music_mode = False
        self.visualizer = MusicVisualizer(self._on_music_color)

        self._load_data()
        self._build_ui()
        self._start_polling()

    def _load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE) as f:
                    d = json.load(f)
                    self.devices = d.get("devices", {})
                    self.saved_colors = d.get("saved_colors", [])
            except: pass

    def _save_data(self):
        try:
            with open(DATA_FILE, "w") as f:
                json.dump({"devices": self.devices, "saved_colors": self.saved_colors}, f)
        except: pass

    def _log(self, msg):
        self.logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        self.logs = self.logs[-50:]

    def _build_ui(self):
        # === HEADER ===
        hdr = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Menu button
        self.menu_btn = ctk.CTkButton(hdr, text="☰", width=36, height=28,
                                       font=ctk.CTkFont(size=16),
                                       fg_color="transparent", hover_color=COLORS["bg"],
                                       command=self._show_menu)
        self.menu_btn.pack(side="left", padx=8, pady=8)

        # Device name (clickable)
        self.device_btn = ctk.CTkButton(hdr, text="No Device", height=28,
                                         font=ctk.CTkFont(size=13, weight="bold"),
                                         fg_color="transparent", hover_color=COLORS["bg"],
                                         text_color=COLORS["text"],
                                         command=self._show_devices)
        self.device_btn.pack(side="left", expand=True)

        # Power button (replaces status dot)
        self.power_btn = ctk.CTkButton(hdr, text="⏻", width=36, height=28,
                                        font=ctk.CTkFont(size=16),
                                        fg_color=COLORS["on"], hover_color="#16a34a",
                                        corner_radius=14,
                                        command=self._toggle_power)
        self.power_btn.pack(side="right", padx=8, pady=8)

        # === MAIN CONTENT ===
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=16, pady=8)

        # Color wheel (centered)
        wheel_frame = ctk.CTkFrame(main, fg_color="transparent")
        wheel_frame.pack(pady=(4, 8))
        self.wheel = ColorWheel(wheel_frame, size=220, on_change=self._on_wheel)
        self.wheel.pack()

        # Hex + Save + Swatches row
        color_row = ctk.CTkFrame(main, fg_color="transparent")
        color_row.pack(fill="x", pady=(0, 10))

        self.hex_lbl = ctk.CTkLabel(color_row, text="#FFFFFF",
                                     font=ctk.CTkFont(size=12, family="Consolas"),
                                     text_color=COLORS["text_dim"])
        self.hex_lbl.pack(side="left")

        ctk.CTkButton(color_row, text="💾", width=32, height=26,
                      font=ctk.CTkFont(size=12),
                      fg_color=COLORS["surface"], hover_color=COLORS["accent"],
                      command=self._save_color).pack(side="left", padx=(8, 4))

        self.swatches = ctk.CTkFrame(color_row, fg_color="transparent")
        self.swatches.pack(side="left", padx=4)
        self._refresh_swatches()

        # Brightness row
        bright_row = ctk.CTkFrame(main, fg_color="transparent")
        bright_row.pack(fill="x", pady=6)

        ctk.CTkLabel(bright_row, text="☀", font=ctk.CTkFont(size=14),
                     text_color=COLORS["text_dim"]).pack(side="left")

        self.bright_sl = ctk.CTkSlider(bright_row, from_=10, to=100,
                                        height=16, button_length=16,
                                        fg_color=COLORS["surface"],
                                        progress_color=COLORS["accent"],
                                        command=self._on_bright)
        self.bright_sl.set(100)
        self.bright_sl.pack(side="left", fill="x", expand=True, padx=8)

        self.bright_lbl = ctk.CTkLabel(bright_row, text="100%", width=40,
                                        font=ctk.CTkFont(size=11),
                                        text_color=COLORS["text_dim"])
        self.bright_lbl.pack(side="right")

        # Temperature slider
        temp_row = ctk.CTkFrame(main, fg_color="transparent")
        temp_row.pack(fill="x", pady=6)

        ctk.CTkLabel(temp_row, text="🌡", font=ctk.CTkFont(size=14),
                     text_color=COLORS["text_dim"]).pack(side="left")

        self.temp_sl = ctk.CTkSlider(temp_row, from_=2200, to=6500,
                                      height=16, button_length=16,
                                      fg_color=COLORS["surface"],
                                      progress_color="#f59e0b",
                                      command=self._on_temp)
        self.temp_sl.set(4000)
        self.temp_sl.pack(side="left", fill="x", expand=True, padx=8)

        self.temp_lbl = ctk.CTkLabel(temp_row, text="4000K", width=45,
                                      font=ctk.CTkFont(size=11),
                                      text_color=COLORS["text_dim"])
        self.temp_lbl.pack(side="right")

        # Music sync button
        music_row = ctk.CTkFrame(main, fg_color="transparent")
        music_row.pack(fill="x", pady=(12, 4))

        self.music_btn = ctk.CTkButton(music_row, text="🎵  Music Sync", height=38,
                                        font=ctk.CTkFont(size=13),
                                        fg_color=COLORS["surface"],
                                        hover_color=COLORS["accent"],
                                        command=self._toggle_music)
        self.music_btn.pack(fill="x")

        if not AUDIO_AVAILABLE:
            self.music_btn.configure(state="disabled", text="🎵  Music Sync (pyaudio required)")

        # Update initial device display
        self._update_device_display()

    def _show_menu(self):
        menu = ctk.CTkToplevel(self)
        menu.title("")
        menu.geometry("160x80")
        menu.transient(self)
        menu.grab_set()

        x = self.winfo_x() + 20
        y = self.winfo_y() + 60
        menu.geometry(f"+{x}+{y}")
        menu.configure(fg_color=COLORS["surface"])
        menu.overrideredirect(True)

        def close(): menu.destroy()

        ctk.CTkButton(menu, text="🔍 Discover", height=32,
                      font=ctk.CTkFont(size=11),
                      fg_color="transparent", hover_color=COLORS["bg"],
                      anchor="w",
                      command=lambda: [close(), self._discover()]).pack(fill="x", padx=4, pady=2)

        ctk.CTkButton(menu, text="📋 Logs", height=32,
                      font=ctk.CTkFont(size=11),
                      fg_color="transparent", hover_color=COLORS["bg"],
                      anchor="w",
                      command=lambda: [close(), self._show_logs()]).pack(fill="x", padx=4, pady=2)

        menu.bind("<FocusOut>", lambda e: close())
        menu.focus_set()

    def _show_devices(self):
        if not self.devices:
            self._discover()
            return

        menu = ctk.CTkToplevel(self)
        menu.title("")
        menu.transient(self)
        menu.grab_set()

        x = self.winfo_x() + 80
        y = self.winfo_y() + 60
        h = min(len(self.devices) * 36 + 8, 200)
        menu.geometry(f"200x{h}+{x}+{y}")
        menu.configure(fg_color=COLORS["surface"])
        menu.overrideredirect(True)

        def select(ip):
            self.current_ip = ip
            self._update_device_display()
            menu.destroy()

        for ip, info in self.devices.items():
            name = info.get("moduleName", ip)
            online = self.device_online.get(ip, False)
            dot = "●" if online else "○"
            color = COLORS["on"] if online else COLORS["off"]

            row = ctk.CTkFrame(menu, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=1)

            ctk.CTkLabel(row, text=dot, font=ctk.CTkFont(size=10),
                         text_color=color).pack(side="left", padx=4)

            ctk.CTkButton(row, text=name, height=28,
                          font=ctk.CTkFont(size=11),
                          fg_color="transparent", hover_color=COLORS["bg"],
                          anchor="w",
                          command=lambda i=ip: select(i)).pack(side="left", fill="x", expand=True)

        menu.bind("<FocusOut>", lambda e: menu.destroy())
        menu.focus_set()

    def _show_logs(self):
        log_win = ctk.CTkToplevel(self)
        log_win.title("Logs")
        log_win.geometry("320x300")
        log_win.configure(fg_color=COLORS["bg"])

        txt = ctk.CTkTextbox(log_win, font=ctk.CTkFont(size=10, family="Consolas"),
                              fg_color=COLORS["surface"])
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", "\n".join(self.logs[-30:]))
        txt.configure(state="disabled")

    def _update_device_display(self):
        if self.current_ip and self.current_ip in self.devices:
            name = self.devices[self.current_ip].get("moduleName", "Device")
            self.device_btn.configure(text=name)
        elif self.devices:
            self.current_ip = list(self.devices.keys())[0]
            self._update_device_display()
        else:
            self.device_btn.configure(text="No Device")

    def _discover(self):
        self._log("Discovering...")
        self.device_btn.configure(text="Scanning...")

        def do():
            try:
                found = self.discovery.discover_wiz_devices(timeout=5)
                for ip, info in found:
                    r = info.get("result", {})
                    self.devices[ip] = {"moduleName": r.get("moduleName", f"Wiz {ip}"), "info": info}
                    self.device_online[ip] = True
                self._save_data()
                self._log(f"Found {len(found)} device(s)")
                self.after(0, self._update_device_display)
            except Exception as e:
                self._log(f"Error: {e}")
                self.after(0, lambda: self.device_btn.configure(text="No Device"))

        threading.Thread(target=do, daemon=True).start()

    def _on_wheel(self, h, s):
        if self.music_mode:
            return  # Don't respond to manual input during music mode
        r, g, b = self.wheel.get_rgb()
        self.hex_lbl.configure(text=f"#{r:02x}{g:02x}{b:02x}".upper())
        if self.current_ip:
            self._send_color(r, g, b)

    def _on_bright(self, v):
        self.brightness = int(v)
        self.bright_lbl.configure(text=f"{self.brightness}%")
        if self.current_ip and not self.music_mode:
            r, g, b = self.wheel.get_rgb()
            self._send_color(r, g, b)

    def _on_temp(self, v):
        temp = int(v)
        self.temp_lbl.configure(text=f"{temp}K")
        if self.current_ip:
            self._send_temp(temp)

    def _send_temp(self, temp):
        def do():
            try:
                self.discovery.set_color_temperature(self.current_ip, temp,
                                                      dimming=self.brightness, turn_on=True)
                self._log(f"Temp: {temp}K")
            except: pass
        threading.Thread(target=do, daemon=True).start()

    def _send_color(self, r, g, b):
        def do():
            try:
                self.discovery.set_color(self.current_ip, r=r, g=g, b=b,
                                          dimming=self.brightness, turn_on=True)
            except: pass
        threading.Thread(target=do, daemon=True).start()

    def _toggle_power(self):
        if not self.current_ip: return
        self.is_on = not self.is_on

        if self.is_on:
            self.power_btn.configure(fg_color=COLORS["on"], hover_color="#16a34a")
        else:
            self.power_btn.configure(fg_color=COLORS["off"], hover_color="#4b5563")

        def do():
            try:
                self.discovery.send_command(self.current_ip, "setPilot",
                                             {"state": self.is_on})
                self._log("ON" if self.is_on else "OFF")
            except: pass
        threading.Thread(target=do, daemon=True).start()

    def _toggle_music(self):
        if self.music_mode:
            # Stop music mode
            self.music_mode = False
            self.visualizer.stop()
            self.music_btn.configure(fg_color=COLORS["surface"], text="🎵  Music Sync")
            self._log("Music sync OFF")
        else:
            # Start music mode
            self.music_btn.configure(text="🎵  Starting...")
            self.update()

            success, error = self.visualizer.start()
            if success:
                self.music_mode = True
                self.music_btn.configure(fg_color=COLORS["accent"], text="🎵  Listening...")
                self._log("Music sync ON - listening via mic")
            else:
                self.music_btn.configure(fg_color=COLORS["surface"], text="🎵  Music Sync")
                self._log(f"Audio failed: {error}")
                # Show error dialog
                self._show_audio_error(error)

    def _show_audio_error(self, error):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Audio Error")
        dialog.geometry("300x150")
        dialog.transient(self)
        dialog.grab_set()

        x = self.winfo_x() + 30
        y = self.winfo_y() + 150
        dialog.geometry(f"+{x}+{y}")
        dialog.configure(fg_color=COLORS["surface"])

        ctk.CTkLabel(dialog, text="🎵 Music Sync Failed",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(16, 8))

        ctk.CTkLabel(dialog, text=error, wraplength=260,
                     font=ctk.CTkFont(size=11),
                     text_color=COLORS["text_dim"]).pack(pady=8)

        ctk.CTkButton(dialog, text="OK", width=80,
                      command=dialog.destroy).pack(pady=12)

    def _on_music_color(self, hue, sat):
        if not self.music_mode or not self.current_ip:
            return

        # Update wheel visually
        self.after(0, lambda: self.wheel.set_hue(hue))

        # Convert to RGB and send
        r, g, b = colorsys.hsv_to_rgb(hue, sat, 1.0)
        r, g, b = int(r * 255), int(g * 255), int(b * 255)

        self.after(0, lambda: self.hex_lbl.configure(text=f"#{r:02x}{g:02x}{b:02x}".upper()))
        self._send_color(r, g, b)

    def _save_color(self):
        r, g, b = self.wheel.get_rgb()
        if [r, g, b] not in self.saved_colors:
            self.saved_colors.append([r, g, b])
            if len(self.saved_colors) > 6:
                self.saved_colors = self.saved_colors[-6:]
            self._save_data()
            self._refresh_swatches()
            self._log(f"Saved #{r:02x}{g:02x}{b:02x}")

    def _refresh_swatches(self):
        for w in self.swatches.winfo_children():
            w.destroy()

        for r, g, b in self.saved_colors:
            hex_c = f"#{r:02x}{g:02x}{b:02x}"
            btn = ctk.CTkButton(self.swatches, text="", width=22, height=22,
                                corner_radius=4,
                                fg_color=hex_c, hover_color=hex_c,
                                command=lambda rgb=(r, g, b): self._load_color(rgb))
            btn.pack(side="left", padx=1)

        if self.saved_colors:
            ctk.CTkButton(self.swatches, text="✕", width=22, height=22,
                          font=ctk.CTkFont(size=10),
                          fg_color=COLORS["surface"], hover_color="#ef4444",
                          command=self._clear_swatches).pack(side="left", padx=(4, 0))

    def _load_color(self, rgb):
        if self.music_mode:
            return
        r, g, b = rgb
        self.wheel.set_rgb(r, g, b)
        self.hex_lbl.configure(text=f"#{r:02x}{g:02x}{b:02x}".upper())
        if self.current_ip:
            self._send_color(r, g, b)

    def _clear_swatches(self):
        self.saved_colors = []
        self._save_data()
        self._refresh_swatches()

    def _start_polling(self):
        def poll():
            while True:
                for ip in list(self.devices.keys()):
                    try:
                        state = self.discovery.get_device_state(ip)
                        self.device_online[ip] = state is not None
                    except:
                        self.device_online[ip] = False
                time.sleep(10)
        threading.Thread(target=poll, daemon=True).start()

    def destroy(self):
        self.visualizer.stop()
        super().destroy()


if __name__ == "__main__":
    WizApp().mainloop()
