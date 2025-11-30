import board
import neopixel

# 144 LEDs on GPIO 18
pixels = neopixel.NeoPixel(board.D18, 144, brightness=0.3, auto_write=False)

# Red
for i in range(144):
    pixels[i] = (255,0,0)
pixels.show()