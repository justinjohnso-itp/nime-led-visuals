#!/bin/bash
# Pi setup script for nime-led-visuals
# Run this once on a fresh Pi to configure hardware interfaces and install system deps

set -e
cd "$(dirname "$0")/../.."

echo "=== NIME LED Visuals - Raspberry Pi Setup ==="

# Check if running on Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "Error: This script should be run on a Raspberry Pi"
    exit 1
fi

echo ""
echo "Step 1: Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y libportaudio2 portaudio19-dev

echo ""
echo "Step 2: Enabling I2C interface..."
sudo raspi-config nonint do_i2c 0

echo ""
echo "Step 3: Enabling SPI interface..."
sudo raspi-config nonint do_spi 0

echo ""
echo "Step 4: Installing pixi dependencies..."
pixi install

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Reboot the Pi: sudo reboot"
echo "  2. After reboot, test LEDs: pixi run test-leds"
echo "  3. Run live visualization: pixi run run-live"
echo ""
echo "Hardware connections:"
echo "  - NeoPixel data wire → GPIO 18"
echo "  - Audio input via Focusrite 2i2 USB"
