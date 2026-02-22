# WizLight

Music-reactive smart light controller for WiZ bulbs. Sync your lights to music in real time, control them from a minimal GUI, or script them from the command line.

Forked from [Kajsing/wiz-control](https://github.com/Kajsing/wiz-control), which provides the core device discovery, room management, and Tkinter GUI.

## What's New in This Fork

### Music Sync

Real-time audio analysis that maps sound to light color and intensity. The system runs FFT on audio input at ~43fps and uses two detection methods:

- **Bass energy analysis** (60-150Hz) for kick drum detection
- **Spectral flux** for onset/transient detection

Detected beats trigger color changes based on the dominant frequency band:

| Frequency Range | Color |
|---|---|
| Sub-bass (20-60Hz) | Red |
| Bass (60-250Hz) | Orange |
| Low-mid (250-500Hz) | Yellow |
| Mid (500Hz-2kHz) | Green |
| Upper-mid (2-4kHz) | Cyan |
| Presence (4-8kHz) | Blue |
| Brilliance (8-16kHz) | Magenta |

Between beats, color saturation and brightness decay smoothly. Requires a loopback audio device (BlackHole or Soundflower) to capture system audio.

### Elegant GUI

A second, minimal interface (`wiz_elegant.py`) built with CustomTkinter. Dark mode, interactive HSV color wheel, single-device focus. Stores config in `~/.wizlight/` instead of the repo directory.

### CLI Control

Command-line interface (`wiz_control.py`) for scripting and automation:

```bash
python3 wiz_control.py on          # Turn on
python3 wiz_control.py off         # Turn off
python3 wiz_control.py dim 150     # Set brightness (1-255)
python3 wiz_control.py color warm  # Named color (red, green, blue, yellow, purple, orange, pink, cyan, warm, cool)
python3 wiz_control.py rgb 255 0 0 # Custom RGB
python3 wiz_control.py status      # Show device status
```

### macOS App Bundle

Packaged as `WizLight.app` via PyInstaller with a one-step installer:

```bash
bash install.sh
```

Handles Homebrew portaudio installation, pip dependencies, and copies the app to `/Applications/`.

### Enhanced Discovery

Auto-detection of broadcast address, validated pilot payloads with parameter clamping (dimming 10-100, temperature 1000-10000K), and high-level helper methods (`set_scene()`, `set_color_temperature()`, `set_color()`).

## Three Ways to Use

| Interface | Command | Best For |
|---|---|---|
| Elegant GUI | `python3 wiz_elegant.py` | Music sync, minimal single-device control |
| Full GUI | `python3 wiz_gui.py` | Multi-room management, scenes, presets |
| CLI | `python3 wiz_control.py <cmd>` | Scripts, automation, quick toggles |

## Installation

### Prerequisites

- Python 3.10+ with Tkinter
- WiZ bulbs on the same local network (UDP port 38899)

### Quick Start

```bash
git clone https://github.com/Stealthinator16/wiz-control.git
cd wiz-control
pip install customtkinter pillow pyaudio numpy pywizlight
python3 wiz_elegant.py
```

### Music Sync Setup

For system audio capture, install a loopback audio device:

```bash
brew install blackhole-2ch
```

Then set BlackHole as your system output (or use a multi-output device to keep speakers active). The music sync mode will pick up the loopback input automatically.

### macOS App Install

```bash
bash install.sh
```

This installs portaudio via Homebrew, pip dependencies, and copies WizLight.app to `/Applications/`.

## Architecture

| Module | Role |
|---|---|
| `wiz_elegant.py` | Minimal GUI + music sync (CustomTkinter, pyaudio, numpy) |
| `wiz_gui.py` | Full-featured room manager (Tkinter) |
| `wiz_control.py` | CLI control (pywizlight) |
| `wiz_discovery.py` | UDP discovery, device commands, payload validation |

See [AGENTS.md](AGENTS.md) for contributor guidelines.

## Credits

Original project by [Kajsing](https://github.com/Kajsing/wiz-control) -- device discovery protocol, room management GUI, scene control, and persistent data storage.

## License

MIT License. See [LICENSE](LICENSE) for details.
