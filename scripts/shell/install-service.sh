#!/bin/bash
# Install systemd service for LED visualization auto-start at boot

set -e
cd "$(dirname "$0")/../.."

SERVICE_NAME="nime-led-visuals"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
INSTALL_DIR="$(pwd)"
PIXI_PYTHON="${INSTALL_DIR}/.pixi/envs/default/bin/python"

echo "=== Installing ${SERVICE_NAME} systemd service ==="
echo "Install directory: ${INSTALL_DIR}"
echo "Python: ${PIXI_PYTHON}"

# Check if pixi environment exists
if [ ! -f "${PIXI_PYTHON}" ]; then
    echo "Error: Pixi Python not found at ${PIXI_PYTHON}"
    echo "Run 'pixi install' first"
    exit 1
fi

# Create systemd service file
sudo tee "${SERVICE_FILE}" > /dev/null << EOF
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

echo "✓ Service file created: ${SERVICE_FILE}"

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}.service"

echo "✓ Service enabled for boot"
echo ""
echo "Commands:"
echo "  Start now:     sudo systemctl start ${SERVICE_NAME}"
echo "  Stop:          sudo systemctl stop ${SERVICE_NAME}"
echo "  View logs:     journalctl -u ${SERVICE_NAME} -f"
echo "  Disable:       sudo systemctl disable ${SERVICE_NAME}"
echo ""
echo "The service will start automatically on next boot."
