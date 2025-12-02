#!/bin/bash
# Configure WiFi network with priority (for auto-connect)
# Usage: ./setup-wifi.sh "NetworkName" "password" [priority]

set -e

SSID="${1:-MrPineapple}"
PASSWORD="${2:-spikyfruit}"
PRIORITY="${3:-10}"

if [ -z "$PASSWORD" ]; then
    echo "Usage: $0 <SSID> <password> [priority]"
    echo "Example: $0 MrPineapple mypassword 10"
    echo ""
    echo "Higher priority = connect first when multiple networks available"
    exit 1
fi

echo "=== Configuring WiFi: ${SSID} ==="

# Check if using NetworkManager (Bookworm) or wpa_supplicant (older)
if command -v nmcli &> /dev/null; then
    echo "Using NetworkManager..."
    
    # Add or update connection
    if nmcli connection show "${SSID}" &> /dev/null; then
        echo "Updating existing connection..."
        nmcli connection modify "${SSID}" \
            wifi-sec.key-mgmt wpa-psk \
            wifi-sec.psk "${PASSWORD}" \
            connection.autoconnect yes \
            connection.autoconnect-priority "${PRIORITY}"
    else
        echo "Creating new connection..."
        nmcli connection add \
            type wifi \
            con-name "${SSID}" \
            ssid "${SSID}" \
            wifi-sec.key-mgmt wpa-psk \
            wifi-sec.psk "${PASSWORD}" \
            connection.autoconnect yes \
            connection.autoconnect-priority "${PRIORITY}"
    fi
    
    echo "✓ WiFi configured with priority ${PRIORITY}"
    echo ""
    echo "Current WiFi connections (sorted by priority):"
    nmcli -f NAME,AUTOCONNECT,AUTOCONNECT-PRIORITY connection show | grep -E "NAME|wifi"
    
else
    echo "Using wpa_supplicant (legacy)..."
    
    # Add to wpa_supplicant.conf
    WPA_CONF="/etc/wpa_supplicant/wpa_supplicant.conf"
    
    # Check if network already exists
    if grep -q "ssid=\"${SSID}\"" "${WPA_CONF}" 2>/dev/null; then
        echo "Network ${SSID} already in ${WPA_CONF}"
        echo "Edit manually if you need to change priority"
    else
        echo "Adding network to ${WPA_CONF}..."
        sudo tee -a "${WPA_CONF}" > /dev/null << EOF

network={
    ssid="${SSID}"
    psk="${PASSWORD}"
    priority=${PRIORITY}
}
EOF
        echo "✓ Network added"
        echo "Reboot or run 'wpa_cli -i wlan0 reconfigure' to apply"
    fi
fi
