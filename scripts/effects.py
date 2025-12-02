"""Visual effects that map audio features to LED patterns"""

import colorsys
import numpy as np
from config import (
    COLORS, NUM_LEDS_PER_STRIP, NUM_STRIPS, LED_BRIGHTNESS,
    HUE_RANGE, EDGE_HUE_SHIFT, CORE_FRACTION_MIN, CORE_FRACTION_MAX,
    MIN_BRIGHTNESS, EDGE_FADE_RATE, TRANSIENT_BOOST, BRIGHTNESS_EXPONENT, FREQ_BANDS
)


class LEDEffects:
    """Container for LED visualization effects"""

    @staticmethod
    def vu_meter(strip, volume, color=(0, 255, 0)):
        """Light up LEDs from start based on volume, with brightness following amplitude
        
        Args:
            strip: neopixel.NeoPixel or PixelSubset object
            volume: 0.0-1.0 volume level
            color: RGB tuple
        """
        num_leds = len(strip)
        num_lit = int(volume * num_leds)

        # Light up from beginning with brightness proportional to volume
        for i in range(num_leds):
            if i < num_lit:
                # Brightness follows the amplitude value
                scaled_color = tuple(int(c * volume) for c in color)
                strip[i] = scaled_color
            else:
                strip[i] = (0, 0, 0)

    # Class-level state for smoothing
    _prev_hue = 0.0
    _prev_brightness = 0.0
    _prev_edge = 0.0
    _prev_bass = 0.0  # Track bass intensity separately for faster decay
    
    @staticmethod
    def get_band_hue(band_index):
        """Map band index 0-31 to smooth hue gradient emphasizing reds and blues.
        
        Red/Orange (bass) → Blue/Cyan (treble), skipping muddy yellow/green midtones.
        
        Args:
            band_index: 0-31 spectrum band index
            
        Returns:
            hue: 0-360 degrees
        """
        # Emphasize warm reds/oranges and cool blues, skip yellow/green
        if band_index < 16:
            # Bands 0-15: Red (0°) to Orange (30°) - bass/mid warmth
            # 16 bands spread over only 30° for rich reds
            return (band_index / 16.0) * 30.0
        else:
            # Bands 16-31: Blue (240°) to Cyan (210°) - high-mid/treble cool
            # 16 bands spread over 30° of blue spectrum
            return 240.0 - ((band_index - 16) / 16.0) * 30.0
    
    @staticmethod
    def get_perceptual_brightness_correction(hue_degrees):
        """Dim non-red hues so red appears as the brightest baseline.
        
        Physical blue/cyan LEDs are inherently brighter than red LEDs at equal RGB intensity.
        This function returns a dimming multiplier for non-red hues to make the entire
        color spectrum appear roughly equal brightness, with red as the reference brightness.
        
        Empirical LED brightness (at 8-bit RGB=255 for saturation):
        - Red (0°): baseline 1.0x
        - Orange (30°): ~0.75x (mix of red and bright green)
        - Yellow (60°): ~0.55x (very bright due to green content)
        - Green (120°): ~0.65x (bright)
        - Cyan (180°): ~0.50x (blue + green, very bright)
        - Blue (240°): ~0.40x (bright blue LED)
        
        Args:
            hue_degrees: 0-360 hue value
            
        Returns:
            brightness_multiplier: 0.4-1.0 to dim non-red hues
        """
        # Normalize hue to 0-1
        h = (hue_degrees % 360.0) / 360.0
        
        # Empirical dimming curve based on LED perceived brightness
        # Red (0°) is baseline at 1.0x, everything else is dimmed
        if h < 0.08:  # 0-30°: Red to Orange
            # Gradual dim from red (1.0) to orange (0.75)
            return 1.0 - ((h / 0.08) * 0.25)
        elif h < 0.17:  # 30-60°: Orange to Yellow
            # Dim from orange (0.75) to yellow (0.55)
            return 0.75 - (((h - 0.08) / 0.09) * 0.20)
        elif h < 0.33:  # 60-120°: Yellow to Green
            # Dim from yellow (0.55) to green (0.65) - green is brighter
            return 0.55 + (((h - 0.17) / 0.16) * 0.10)
        elif h < 0.50:  # 120-180°: Green to Cyan
            # Dim from green (0.65) to cyan (0.50) - cyan is very bright
            return 0.65 - (((h - 0.33) / 0.17) * 0.15)
        elif h < 0.67:  # 180-240°: Cyan to Blue
            # Dim from cyan (0.50) to blue (0.40)
            return 0.50 - (((h - 0.50) / 0.17) * 0.10)
        else:  # 240-360°: Blue to Red
            # Dim from blue (0.40) back to red (1.0)
            # This is the treble/high region (240-360)
            return 0.40 + (((h - 0.67) / 0.33) * 0.60)
    
    @staticmethod
    def frequency_spectrum(strips, features):
        """32-band frequency spectrum with edge effects
        
        Uses 32-band spectrum for smooth color mapping:
        - Bands 0-7 (20-200 Hz): Red (bass)
        - Bands 8-15 (200-1.5k Hz): Amber (low-mid)  
        - Bands 16-31 (1.5k-20k Hz): Blue edges (treble)
        
        Args:
            strips: list of 3 PixelSubset objects [left, center, right]
            features: dict with 'spectrum' (32-band array) and 'envelope'
        """
        spectrum = features.get('spectrum', None)
        envelope = features.get('envelope', 0.0)
        dominant_band = features.get('dominant_band', -1)
        tonalness = features.get('tonalness', 0.0)
        
        if spectrum is None or len(spectrum) < 32:
            spectrum = np.zeros(32)
        
        # Average energy in frequency regions (for edges/brightness)
        bass_energy = float(np.mean(spectrum[0:10]))     # 20-173 Hz (red)
        mid_energy = float(np.mean(spectrum[10:22]))     # 173-2.3k Hz (amber)
        treble_energy = float(np.mean(spectrum[22:32]))  # 2.3k-20k Hz (blue edges)
        
        # Fallback blended hue
        core_total = bass_energy + mid_energy + 0.001
        bass_weight = bass_energy / core_total
        mid_weight = mid_energy / core_total
        blended_hue = (bass_weight * 0.0) + (mid_weight * 30.0)
        
        # Use DOMINANT BAND for color when spectrum is tonal enough
        TONALNESS_THRESHOLD = 0.15
        if dominant_band >= 0 and tonalness > TONALNESS_THRESHOLD:
            # Use smooth 32-band hue gradient for tonal sounds
            target_hue = LEDEffects.get_band_hue(dominant_band)
        else:
            # Fall back to blended hue for noisy/broadband sounds
            target_hue = blended_hue
        
        # Brightness from envelope - go fully dark when envelope is near zero
        if envelope < 0.01:
            target_brightness = 0.0
        else:
            target_brightness = max(MIN_BRIGHTNESS, envelope ** BRIGHTNESS_EXPONENT)
        
        # Edge intensity from treble (now 0-1 range since we use mean)
        target_edge = treble_energy  # Direct mapping, already 0-1
        
        # Smoothing - fast edges for transient response
        attack = 0.9
        decay = 0.5
        
        # Hue smoothing
        hue_diff = target_hue - LEDEffects._prev_hue
        LEDEffects._prev_hue += hue_diff * (attack if hue_diff > 0 else decay)
        
        # Brightness smoothing - faster decay to zero
        if target_brightness > LEDEffects._prev_brightness:
            LEDEffects._prev_brightness += (target_brightness - LEDEffects._prev_brightness) * attack
        elif target_brightness < 0.01:
            LEDEffects._prev_brightness *= 0.7  # Fast fade to black
        else:
            LEDEffects._prev_brightness += (target_brightness - LEDEffects._prev_brightness) * decay
        
        # Edge smoothing - FASTER for treble (more dynamic)
        if target_edge > LEDEffects._prev_edge:
            LEDEffects._prev_edge += (target_edge - LEDEffects._prev_edge) * 0.95  # Very quick rise
        else:
            LEDEffects._prev_edge += (target_edge - LEDEffects._prev_edge) * 0.08  # Fast decay (was 0.5)
        
        # Bass smoothing - responsive but with faster release
        if bass_energy > LEDEffects._prev_bass:
            LEDEffects._prev_bass += (bass_energy - LEDEffects._prev_bass) * 0.95
        else:
            LEDEffects._prev_bass += (bass_energy - LEDEffects._prev_bass) * 0.1  # Very fast decay for punch
        
        # Core color (red/amber) with perceptual brightness correction
        brightness_correction = LEDEffects.get_perceptual_brightness_correction(LEDEffects._prev_hue)
        r, g, b = colorsys.hsv_to_rgb(LEDEffects._prev_hue / 360.0, 1.0, LEDEffects._prev_brightness * brightness_correction * LED_BRIGHTNESS)
        core_color = (int(r * 255), int(g * 255), int(b * 255))
        
        # Edge parameters - treble edges more responsive (BLUES STRONGER)
        edge_intensity = LEDEffects._prev_edge ** 1.0  # Linear for more presence
        edge_size = int(NUM_LEDS_PER_STRIP * 0.85 * LEDEffects._prev_edge)  # Expand more (was 0.7)
        feather_size = max(6, edge_size // 4)  # Tighter feathering (was //3)
        
        # Red core: responsive to bass, doesn't always fill the strip
        # Faster decay but strong presence when active
        bass_core_size = int(NUM_LEDS_PER_STRIP * 0.4 * LEDEffects._prev_bass)  # Smaller, more responsive core
        bass_feather_size = max(6, bass_core_size // 3)  # Feather zone for smooth bleed
        bass_brightness = LEDEffects._prev_brightness
        # Red intensity: full strength when bass present, fades to zero when silent
        bass_intensity = min(1.0, LEDEffects._prev_bass * 3.5)  # More aggressive red bleed
        
        center = NUM_LEDS_PER_STRIP // 2
        
        # Pre-calculate RGB values with perceptual brightness correction applied to all colors
        brightness_correction_core = LEDEffects.get_perceptual_brightness_correction(LEDEffects._prev_hue)
        brightness_correction_red = LEDEffects.get_perceptual_brightness_correction(0.0)  # Red hue
        brightness_correction_blue = LEDEffects.get_perceptual_brightness_correction(240.0)  # Blue hue
        
        cr, cg, cb = colorsys.hsv_to_rgb(LEDEffects._prev_hue / 360.0, 1.0, LEDEffects._prev_brightness * brightness_correction_core * LED_BRIGHTNESS)
        br, bg, bb = colorsys.hsv_to_rgb(0.0, 1.0, bass_brightness * brightness_correction_red * LED_BRIGHTNESS)  # Red with correction
        er, eg, eb = colorsys.hsv_to_rgb(240.0 / 360.0, 1.0, edge_intensity * brightness_correction_blue * LED_BRIGHTNESS)  # Blue with correction
        
        # If brightness is essentially zero, just fill black and return
        if LEDEffects._prev_brightness < 0.005:
            for strip in strips:
                strip.fill((0, 0, 0))
            return
        
        # Fill strips with red core dominating, blue edges on outer boundaries only
        for i in range(NUM_LEDS_PER_STRIP):
            # Strip 0: Red core from LEFT edge (opposite side from blue edges)
            # Red bleeds in from the left, blue edge only on right edge (far left indices)
            dist_from_left = i  # 0 at left edge
            red_blend = min(1.0, (dist_from_left + 1) / max(bass_core_size, 1)) * bass_intensity if bass_core_size > 0 and dist_from_left < bass_core_size else 0.0
            
            # Blue edge only at the far left indices (opposite of strip 2)
            dist_from_outer_left = i  # Distance from index 0
            blue_blend = 0.0
            blue_feather_factor = 1.0  # Hue feathering from blue toward core
            if dist_from_outer_left < edge_size:
                if dist_from_outer_left < edge_size - feather_size:
                    blue_blend = 1.0
                    blue_feather_factor = 0.0
                else:
                    # Feather zone: blend from blue (240°) toward core hue
                    feather_progress = (dist_from_outer_left - (edge_size - feather_size)) / feather_size
                    blue_blend = (1.0 - feather_progress) * edge_intensity
                    blue_feather_factor = feather_progress  # Gradually move toward core hue
            
            # Blend colors with hue feathering in blue zones
            if blue_blend > 0:
                # Feather blue toward core hue
                feathered_blue_hue = 240.0 + (blue_feather_factor * (LEDEffects._prev_hue - 240.0))
                brightness_correction_feathered = LEDEffects.get_perceptual_brightness_correction(feathered_blue_hue)
                br_f, bg_f, bb_f = colorsys.hsv_to_rgb(feathered_blue_hue / 360.0, 1.0, edge_intensity * 1.2 * brightness_correction_feathered * LED_BRIGHTNESS)
                er, eg, eb = int(br_f * 255), int(bg_f * 255), int(bb_f * 255)
            
            final_red_blend = red_blend * (1.0 - blue_blend * 0.7)  # Blue more dominant
            r = int(cr * 255 * (1 - final_red_blend) + br * 255 * final_red_blend + er * blue_blend * 0.7)  # More blue contribution
            g = int(cg * 255 * (1 - final_red_blend) + bg * 255 * final_red_blend + eg * blue_blend * 0.7)
            b = int(cb * 255 * (1 - final_red_blend) + bb * 255 * final_red_blend + eb * blue_blend * 0.7)
            strips[0][i] = (int(max(0, min(255, r))), int(max(0, min(255, g))), int(max(0, min(255, b))))
            
            # Strip 1: bass core from center with feathered gradient AND hue feathering
            dist_from_center = abs(i - center)
            if dist_from_center < bass_core_size:
                if dist_from_center < bass_core_size - bass_feather_size:
                    # Solid core zone: pure red (0°)
                    blend = 1.0
                    red_hue = 0.0
                else:
                    # Feather zone - gradient from red (0°) to core hue
                    feather_progress = (dist_from_center - (bass_core_size - bass_feather_size)) / max(bass_feather_size, 1)
                    blend = (1.0 - feather_progress) * bass_intensity
                    red_hue = feather_progress * LEDEffects._prev_hue  # Fade from red toward core hue
                
                # Use feathered hue for red zone with perceptual correction
                brightness_correction_red_feather = LEDEffects.get_perceptual_brightness_correction(red_hue)
                hr, hg, hb = colorsys.hsv_to_rgb(red_hue / 360.0, 1.0, bass_brightness * brightness_correction_red_feather * LED_BRIGHTNESS)
                r = int(cr * 255 * (1 - blend) + hr * 255 * blend)
                g = int(cg * 255 * (1 - blend) + hg * 255 * blend)
                b = int(cb * 255 * (1 - blend) + hb * 255 * blend)
                strips[1][i] = (r, g, b)
            else:
                strips[1][i] = core_color
            
            # Strip 2: Red core from RIGHT edge (opposite side from blue edges)
            # Red bleeds in from the right, blue edge only on far right indices
            dist_from_right = NUM_LEDS_PER_STRIP - 1 - i  # 0 at right edge
            red_blend_right = min(1.0, (dist_from_right + 1) / max(bass_core_size, 1)) * bass_intensity if bass_core_size > 0 and dist_from_right < bass_core_size else 0.0
            
            # Blue edge only at the far right indices (opposite of strip 0)
            dist_from_outer_right = NUM_LEDS_PER_STRIP - 1 - i  # Distance from right edge
            blue_blend_right = 0.0
            blue_feather_factor_right = 1.0
            er_r, eg_r, eb_r = 0, 0, 0  # Default blue edge color
            if dist_from_outer_right < edge_size:
                if dist_from_outer_right < edge_size - feather_size:
                    blue_blend_right = 1.0
                    blue_feather_factor_right = 0.0
                else:
                    feather_progress_right = (dist_from_outer_right - (edge_size - feather_size)) / feather_size
                    blue_blend_right = (1.0 - feather_progress_right) * edge_intensity
                    blue_feather_factor_right = feather_progress_right
                
                # Blend colors with hue feathering in blue zones (right side)
                feathered_blue_hue_right = 240.0 + (blue_feather_factor_right * (LEDEffects._prev_hue - 240.0))
                brightness_correction_feathered_right = LEDEffects.get_perceptual_brightness_correction(feathered_blue_hue_right)
                br_f_r, bg_f_r, bb_f_r = colorsys.hsv_to_rgb(feathered_blue_hue_right / 360.0, 1.0, edge_intensity * 1.2 * brightness_correction_feathered_right * LED_BRIGHTNESS)
                er_r, eg_r, eb_r = int(br_f_r * 255), int(bg_f_r * 255), int(bb_f_r * 255)
            
            final_red_blend_right = red_blend_right * (1.0 - blue_blend_right * 0.7)  # Blue more dominant
            r = int(cr * 255 * (1 - final_red_blend_right) + br * 255 * final_red_blend_right + er_r * blue_blend_right * 0.7)  # More blue contribution
            g = int(cg * 255 * (1 - final_red_blend_right) + bg * 255 * final_red_blend_right + eg_r * blue_blend_right * 0.7)
            b = int(cb * 255 * (1 - final_red_blend_right) + bb * 255 * final_red_blend_right + eb_r * blue_blend_right * 0.7)
            strips[2][i] = (int(max(0, min(255, r))), int(max(0, min(255, g))), int(max(0, min(255, b))))

    @staticmethod
    def pulse_effect(strip, volume, color=(255, 255, 255)):
        """Pulse entire strip brightness with volume (call pixels.show() after)
        
        Args:
            strip: PixelSubset or neopixel.NeoPixel object
            volume: 0.0-1.0 volume level
            color: RGB tuple
        """
        # Scale brightness by volume
        scaled_color = tuple(int(c * volume) for c in color)

        for i in range(len(strip)):
            strip[i] = scaled_color

    @staticmethod
    def waveform_viz(strip, audio_data):
        """Downsample waveform to LED count and display (call pixels.show() after)
        
        Args:
            strip: PixelSubset or neopixel.NeoPixel object
            audio_data: numpy array of audio samples
        """
        num_leds = len(strip)
        samples_per_led = len(audio_data) // num_leds

        for i in range(num_leds):
            start = i * samples_per_led
            end = start + samples_per_led
            chunk = audio_data[start:end]

            # Get max amplitude in this chunk
            amplitude = max(abs(chunk))

            # Brightness based on amplitude
            brightness = int(amplitude * 255)
            strip[i] = (brightness, brightness, brightness)

    @staticmethod
    def rainbow_chase(strip, position, speed=0.1):
        """Rainbow color chase across strip (call pixels.show() after)
        
        Args:
            strip: PixelSubset or neopixel.NeoPixel object
            position: 0.0-1.0 position along strip
            speed: animation speed (unused, for future)
        """
        num_leds = len(strip)
        led_index = int(position * num_leds) % num_leds

        for i in range(num_leds):
            distance = abs(i - led_index)
            # Fade based on distance
            brightness = max(0, 255 - distance * 30)
            hue = (i / num_leds) * 360
            rgb = LEDEffects._hsv_to_rgb(hue, 1.0, brightness / 255.0)
            strip[i] = rgb

    @staticmethod
    def _hsv_to_rgb(h, s, v):
        """Convert HSV to RGB
        
        Args:
            h: hue 0-360
            s: saturation 0-1
            v: value 0-1
            
        Returns:
            (r, g, b) tuple 0-255
        """
        r, g, b = colorsys.hsv_to_rgb(h / 360.0, s, v)
        return (int(r * 255), int(g * 255), int(b * 255))

    @staticmethod
    def attack_flash(strip, volume, prev_volume, threshold=0.3, flash_color=(255, 255, 255)):
        """Flash on sudden volume increase (call pixels.show() after)
        
        Args:
            strip: PixelSubset or neopixel.NeoPixel object
            volume: current volume 0.0-1.0
            prev_volume: previous volume 0.0-1.0
            threshold: volume increase threshold to trigger flash
            flash_color: RGB tuple for flash
        """
        attack = volume - prev_volume

        if attack > threshold:
            # Flash at full brightness
            for i in range(len(strip)):
                strip[i] = flash_color
        else:
            # Fade to dim
            dim_color = tuple(int(c * volume * 0.5) for c in flash_color)
            for i in range(len(strip)):
                strip[i] = dim_color
