import board
import neopixel

# Test with 144 LEDs on GPIO 18
pixels = neopixel.NeoPixel(board.D18, 144, brightness=0.3, auto_write=False)

# Red test
for i in range(144):
    pixels[i] = (255, 0, 0)  # Red
pixels.show()

print("If LEDs are red, it's working!")
