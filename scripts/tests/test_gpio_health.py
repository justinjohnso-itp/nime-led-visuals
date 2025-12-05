#!/usr/bin/env python3
"""
Diagnostic script to check GPIO pin health.
Run WITHOUT sudo first to check basic GPIO access.
"""

import subprocess
import sys

GPIOS_TO_TEST = [18, 21, 12, 13, 10]

print("=== GPIO Health Check ===\n")

# Check raspi-gpio tool
try:
    result = subprocess.run(['which', 'raspi-gpio'], capture_output=True, text=True)
    if result.returncode != 0:
        print("⚠ raspi-gpio not found. Install with: sudo apt install raspi-gpio")
        print("  Falling back to /sys/class/gpio method...\n")
        use_raspi_gpio = False
    else:
        use_raspi_gpio = True
except Exception:
    use_raspi_gpio = False

print("Checking GPIO states:\n")
print(f"{'GPIO':<8} {'Pin':<6} {'State':<40} {'Use Case'}")
print("-" * 70)

pin_map = {
    18: (12, "PWM0 - original LED data pin"),
    21: (40, "PCM_DOUT - recommended alternative"),
    12: (32, "PWM0 - shares channel with GPIO18"),
    13: (33, "PWM1 - independent PWM"),
    10: (19, "SPI MOSI - requires SPI enabled"),
}

for gpio in GPIOS_TO_TEST:
    pin, use_case = pin_map[gpio]
    
    if use_raspi_gpio:
        try:
            result = subprocess.run(
                ['raspi-gpio', 'get', str(gpio)],
                capture_output=True, text=True
            )
            state = result.stdout.strip().split(': ', 1)[-1] if result.returncode == 0 else "ERROR"
        except Exception as e:
            state = f"ERROR: {e}"
    else:
        # Fallback: try to read from sysfs
        try:
            # Export GPIO
            subprocess.run(['sudo', 'sh', '-c', f'echo {gpio} > /sys/class/gpio/export'], 
                         capture_output=True, stderr=subprocess.DEVNULL)
            # Read value
            with open(f'/sys/class/gpio/gpio{gpio}/value', 'r') as f:
                val = f.read().strip()
            state = f"level={val}"
            # Unexport
            subprocess.run(['sudo', 'sh', '-c', f'echo {gpio} > /sys/class/gpio/unexport'],
                         capture_output=True, stderr=subprocess.DEVNULL)
        except Exception:
            state = "(unable to read - may be in use or need sudo)"
    
    print(f"GPIO{gpio:<4} {pin:<6} {state:<40} {use_case}")

print("\n" + "=" * 70)
print("If GPIO18 shows unexpected state (stuck HIGH, etc.), it may be damaged.")
print("Try GPIO21 (pin 40) as alternative - run: sudo python test_gpio21.py")
