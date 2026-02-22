#!/usr/bin/env python3
"""
Wiz Bulb Control Script
Usage:
    python3 wiz_control.py on          # Turn on
    python3 wiz_control.py off         # Turn off
    python3 wiz_control.py dim 50      # Set brightness (1-255)
    python3 wiz_control.py color red   # Set color (red, green, blue, warm, cool)
    python3 wiz_control.py rgb 255 0 0 # Set custom RGB
    python3 wiz_control.py status      # Get current status
"""

import asyncio
import sys
from pywizlight import wizlight, PilotBuilder

BULB_IP = "172.31.141.147"

COLORS = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "purple": (128, 0, 128),
    "orange": (255, 165, 0),
    "pink": (255, 105, 180),
    "cyan": (0, 255, 255),
    "warm": None,  # Use color temp
    "cool": None,  # Use color temp
}

async def control_bulb(action, *args):
    bulb = wizlight(BULB_IP)
    try:
        if action == "on":
            await bulb.turn_on(PilotBuilder(brightness=255))
            print("✓ Bulb turned ON")

        elif action == "off":
            await bulb.turn_off()
            print("✓ Bulb turned OFF")

        elif action == "dim":
            brightness = int(args[0]) if args else 128
            brightness = max(1, min(255, brightness))
            await bulb.turn_on(PilotBuilder(brightness=brightness))
            print(f"✓ Brightness set to {brightness}")

        elif action == "color":
            color_name = args[0].lower() if args else "warm"
            if color_name == "warm":
                await bulb.turn_on(PilotBuilder(colortemp=2700))
                print("✓ Set to warm white")
            elif color_name == "cool":
                await bulb.turn_on(PilotBuilder(colortemp=6500))
                print("✓ Set to cool white")
            elif color_name in COLORS:
                r, g, b = COLORS[color_name]
                await bulb.turn_on(PilotBuilder(rgb=(r, g, b)))
                print(f"✓ Color set to {color_name}")
            else:
                print(f"Unknown color: {color_name}")
                print(f"Available: {', '.join(COLORS.keys())}")

        elif action == "rgb":
            r, g, b = int(args[0]), int(args[1]), int(args[2])
            await bulb.turn_on(PilotBuilder(rgb=(r, g, b)))
            print(f"✓ RGB set to ({r}, {g}, {b})")

        elif action == "status":
            state = await bulb.updateState()
            print("=== Wiz Bulb Status ===")
            print(f"Power: {'ON' if state.get_state() else 'OFF'}")
            print(f"Brightness: {state.get_brightness()}")
            if state.get_colortemp():
                print(f"Color Temp: {state.get_colortemp()}K")
            if state.get_rgb():
                print(f"RGB: {state.get_rgb()}")

        else:
            print(__doc__)

    finally:
        await bulb.async_close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
    else:
        action = sys.argv[1].lower()
        args = sys.argv[2:]
        asyncio.run(control_bulb(action, *args))
