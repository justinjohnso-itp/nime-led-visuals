import sys
import time
import board
import neopixel

# Import config for LED count
sys.path.insert(0, '.')
from scripts.config import NUM_LEDS_PER_STRIP, NUM_STRIPS, LED_BRIGHTNESS

TOTAL_LEDS = NUM_LEDS_PER_STRIP * NUM_STRIPS  # 432

print("=== LED Debug Test ===")
print(f"Python: {sys.executable}")
print(f"neopixel module: {neopixel.__file__}")
print(f"Total LEDs: {TOTAL_LEDS} ({NUM_STRIPS} strips x {NUM_LEDS_PER_STRIP})")

print(f"\nInitializing NeoPixel on GPIO 18 with {TOTAL_LEDS} LEDs...")
pixels = neopixel.NeoPixel(board.D18, TOTAL_LEDS, brightness=LED_BRIGHTNESS, auto_write=False)
print(f"✓ NeoPixel initialized, len(pixels) = {len(pixels)}")

print("\nTest 1: Fill all LEDs red...")
pixels.fill((255, 0, 0))
pixels.show()
time.sleep(2)

print("Test 2: Chase through all LEDs...")
for i in range(TOTAL_LEDS):
    pixels.fill((0, 0, 0))
    pixels[i] = (0, 255, 0)
    pixels.show()
    time.sleep(0.005)

print("\nTest 3: Light each strip a different color...")
# Strip 1 (0-143): Red
for i in range(NUM_LEDS_PER_STRIP):
    pixels[i] = (255, 0, 0)
# Strip 2 (144-287): Green
for i in range(NUM_LEDS_PER_STRIP, 2 * NUM_LEDS_PER_STRIP):
    pixels[i] = (0, 255, 0)
# Strip 3 (288-431): Blue
for i in range(2 * NUM_LEDS_PER_STRIP, 3 * NUM_LEDS_PER_STRIP):
    pixels[i] = (0, 0, 255)
pixels.show()
time.sleep(3)

print("\nTurning off...")
pixels.fill((0, 0, 0))
pixels.show()
print("✓ Test complete!")