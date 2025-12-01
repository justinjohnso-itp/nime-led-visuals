import board
import neopixel

print("Initializing NeoPixel on GPIO 18...")
# 144 LEDs on GPIO 18
pixels = neopixel.NeoPixel(board.D18, 144, brightness=0.3, auto_write=False)
print("✓ NeoPixel initialized successfully")

print("Setting all LEDs to red...")
# Red
for i in range(144):
    pixels[i] = (255,0,0)
print("✓ Color data set")

print("Writing to LED strip...")
pixels.show()
print("✓ LEDs should now be red")