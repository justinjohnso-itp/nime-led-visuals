#!/bin/bash
# NIME LED Visuals - Full Raspberry Pi setup (Desktop & Lite)
# Usage: ./scripts/shell/setup-all.sh
# Safe to re-run; idempotent.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=============================================="
echo "  NIME LED Visuals - Raspberry Pi Full Setup"
echo "=============================================="

# 0. Basic checks -------------------------------------------------------------

if [ ! -f /proc/device-tree/model ] || ! grep -qi "raspberry pi" /proc/device-tree/model 2>/dev/null; then
  echo "Error: This script must be run on a Raspberry Pi."
  exit 1
fi

if [ "$(id -u)" -eq 0 ]; then
  echo "Error: Please run this script as a normal user (not root)."
  echo "Example: ./scripts/shell/setup-all.sh"
  exit 1
fi

USER_NAME="$USER"
USER_HOME="$HOME"

if ! command -v sudo >/dev/null 2>&1; then
  echo "Error: sudo is required."
  exit 1
fi

# 1. System packages (ALSA, PulseAudio, PortAudio, tools) ---------------------

echo ""
echo "Step 1/7: Installing system dependencies..."
echo "  (ALSA, PulseAudio, PortAudio, build tools)"
sudo apt-get update -y
sudo apt-get install -y \
  curl git \
  libportaudio2 portaudio19-dev \
  alsa-utils alsa-tools alsa-ucm-conf \
  libasound2 libasound2-plugins \
  pulseaudio pulseaudio-utils

# 2. Enable hardware interfaces & console auto-login --------------------------

echo ""
echo "Step 2/7: Enabling I2C, SPI, and console auto-login..."
if command -v raspi-config >/dev/null 2>&1; then
  sudo raspi-config nonint do_i2c 0 || true
  sudo raspi-config nonint do_spi 0 || true
  sudo raspi-config nonint do_boot_behaviour B2 || true
  echo "  ✓ I2C, SPI enabled; console auto-login enabled"
else
  echo "  ⚠ raspi-config not found; skipping hardware config"
fi

# 3. Add user to required groups ----------------------------------------------

echo ""
echo "Step 3/7: Adding user '${USER_NAME}' to audio/gpio/i2c/spi groups..."
for grp in audio gpio i2c spi; do
  if getent group "$grp" >/dev/null 2>&1; then
    if id -nG "$USER_NAME" | tr ' ' '\n' | grep -qx "$grp"; then
      echo "  ✓ Already in '$grp'"
    else
      sudo usermod -aG "$grp" "$USER_NAME"
      echo "  ✓ Added to '$grp'"
    fi
  fi
done

# 4. Configure WiFi (MrPineapple by default) ----------------------------------

echo ""
echo "Step 4/7: Configuring WiFi..."

SSID="${SSID:-MrPineapple}"
WIFI_PASSWORD="${WIFI_PASSWORD:-spikyfruit}"
WIFI_PRIORITY="${WIFI_PRIORITY:-10}"

if [ -z "$WIFI_PASSWORD" ]; then
  echo "  ⚠ Skipping WiFi (no password set)"
else
  if command -v nmcli >/dev/null 2>&1; then
    echo "  Using NetworkManager..."
    if nmcli connection show "$SSID" >/dev/null 2>&1; then
      sudo nmcli connection modify "$SSID" \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "$WIFI_PASSWORD" \
        connection.autoconnect yes \
        connection.autoconnect-priority "$WIFI_PRIORITY"
      echo "  ✓ Updated existing connection '$SSID'"
    else
      sudo nmcli connection add \
        type wifi \
        con-name "$SSID" \
        ssid "$SSID" \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "$WIFI_PASSWORD" \
        connection.autoconnect yes \
        connection.autoconnect-priority "$WIFI_PRIORITY"
      echo "  ✓ Created connection '$SSID'"
    fi
  else
    echo "  Using wpa_supplicant..."
    WPA_CONF="/etc/wpa_supplicant/wpa_supplicant.conf"
    if sudo grep -q "ssid=\"$SSID\"" "$WPA_CONF" 2>/dev/null; then
      echo "  ✓ Network '$SSID' already configured"
    else
      sudo tee -a "$WPA_CONF" >/dev/null <<EOF

network={
    ssid="$SSID"
    psk="$WIFI_PASSWORD"
    priority=$WIFI_PRIORITY
}
EOF
      echo "  ✓ Added network '$SSID'"
    fi
  fi
fi

# 5. Ensure pixi is installed and install project deps ------------------------

echo ""
echo "Step 5/7: Installing pixi and project dependencies..."

export PATH="$USER_HOME/.pixi/bin:$PATH"

if ! command -v pixi >/dev/null 2>&1; then
  echo "  Installing pixi..."
  curl -fsSL https://pixi.sh/install.sh | bash
  export PATH="$USER_HOME/.pixi/bin:$PATH"
fi

if ! command -v pixi >/dev/null 2>&1; then
  echo "Error: pixi installation failed"
  exit 1
fi

echo "  ✓ pixi available: $(which pixi)"
echo "  Running 'pixi install'..."
pixi install
echo "  ✓ Python dependencies installed"

# 6. Install systemd service --------------------------------------------------

echo ""
echo "Step 6/7: Installing systemd service..."

SERVICE_NAME="nime-led-visuals"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
INSTALL_DIR="$PROJECT_ROOT"
PIXI_PYTHON="${INSTALL_DIR}/.pixi/envs/default/bin/python"

if [ ! -x "$PIXI_PYTHON" ]; then
  echo "Error: Pixi Python not found at $PIXI_PYTHON"
  exit 1
fi

sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=NIME LED Visuals - Audio-reactive LED visualization
After=network.target sound.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=${PIXI_PYTHON} ${INSTALL_DIR}/scripts/main.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

# Give audio hardware time to initialize
ExecStartPre=/bin/sleep 3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}.service"
echo "  ✓ Service installed and enabled"

# 7. Summary ------------------------------------------------------------------

echo ""
echo "Step 7/7: Setup complete!"
echo ""
echo "=============================================="
echo "  Next steps:"
echo "=============================================="
echo ""
echo "  1. Reboot:  sudo reboot"
echo ""
echo "  2. After reboot, the visualization starts automatically."
echo "     View logs:  journalctl -u nime-led-visuals -f"
echo ""
echo "  3. Manual commands:"
echo "     pixi run test-leds   - Test LED strips"
echo "     pixi run run-live    - Run visualization manually"
echo ""
echo "  Hardware:"
echo "     NeoPixel data → GPIO 18"
echo "     Audio input   → Focusrite Scarlett 2i2 USB"
echo ""
echo "=============================================="
