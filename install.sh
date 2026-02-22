#!/bin/bash
# WizLight Installer for macOS

echo "🔮 Installing WizLight..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Install from python.org"
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install customtkinter pillow pyaudio numpy --quiet 2>/dev/null

# Check if portaudio is needed for pyaudio
if ! python3 -c "import pyaudio" 2>/dev/null; then
    echo "📦 Installing portaudio (for music sync)..."
    if command -v brew &> /dev/null; then
        brew install portaudio --quiet
        pip3 install pyaudio --quiet
    else
        echo "⚠️  Music Sync won't work without Homebrew. Install from brew.sh"
    fi
fi

# Copy app to Applications
echo "📱 Installing app..."
cp -r WizLight.app /Applications/ 2>/dev/null || {
    echo "⚠️  Couldn't copy to /Applications. Trying with sudo..."
    sudo cp -r WizLight.app /Applications/
}

# Copy support files
mkdir -p ~/wiz-control
cp wiz_elegant.py wiz_discovery.py ~/wiz-control/

echo ""
echo "✅ WizLight installed!"
echo ""
echo "📍 Find it in: /Applications/WizLight.app"
echo "🎯 Add to Dock: Drag from Applications folder"
echo ""
echo "🚀 Launch now? (y/n)"
read -r answer
if [[ "$answer" == "y" ]]; then
    open /Applications/WizLight.app
fi
