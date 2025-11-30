# 🔌 Hardware Setup - Physical Wiring Guide

## 🛠️ Parts List

### What You Have
- ✅ Raspberry Pi 3B
- ✅ 3x WS2812B LED strips (144 LEDs each, 3.2ft, 5V DC)
- ✅ Daisy Seed instrument (audio source)

### What You Need to Buy

| Item | Qty | Est. Cost | Notes |
|------|-----|-----------|-------|
| **5V Power Supply** | 1 | $20-35 | 10A minimum, 20-30A ideal |
| **3.5mm Y-splitter** | 1 | $5 | Stereo audio splitter |
| **USB Audio Interface** | 1 | $8 | For Pi audio input |
| **Logic Level Shifter** | 1 | $2-5 | 74AHCT125 or 74HCT245 (optional but recommended) |
| **Jumper wires** | 1 set | $8 | M-F and M-M |
| **Terminal blocks** | 3-5 | $5 | For power distribution |

**Total: $48-66** (less if you skip level shifter or use lower power supply)

---

## ⚡ Power Supply Guide

### What to Buy

**Your strips require:**
- **Voltage:** 5V DC (exactly!)
- **Current needed:** 
  - Full brightness white: ~26A (144 LEDs × 3 strips × 60mA)
  - Typical usage (colors, 50% brightness): ~10-15A
  - Conservative (30% brightness): ~8A

**Recommended options:**

| Supply | Cost | Use Case |
|--------|------|----------|
| 5V 10A (50W) | $20 | Budget - run at 30% brightness |
| 5V 20A (100W) | $25 | Good - most colors at high brightness |
| 5V 30A (150W) | $35 | Best - full white at 100% |

**Search term:** "5V 30A LED power supply" or "5V 20A switching power supply"

**❌ DON'T buy 12V** - Will instantly destroy your WS2812B strips!

---

## 🔌 Wiring Diagram

### Option A: Daisy-Chained Data (Simpler)

```
AUDIO CHAIN:
┌──────────────┐
│ Daisy Seed   │
│ Audio Output │
└──────┬───────┘
       │
   [Y-Splitter]
       ├────────→ Sound System (mixer/speakers)
       │
       └────────→ [USB Audio Interface] ──→ Pi USB port


LED POWER (Star topology - inject at each strip):
┌─────────────────┐
│ 5V Power Supply │
└─┬───────────────┘
  │
  ├─ +5V (red) ──┬──→ Strip 1 +5V (red wire)
  │              ├──→ Strip 2 +5V (red wire)
  │              └──→ Strip 3 +5V (red wire)
  │
  └─ GND (black)─┬──→ Strip 1 GND (white wire)
                 ├──→ Strip 2 GND (white wire)
                 ├──→ Strip 3 GND (white wire)
                 └──→ Pi GND (physical pin 6, 9, 14, etc.)


LED DATA (Daisy-chained):
┌──────────────┐
│ Raspberry Pi │
└──────┬───────┘
       │
   GPIO 18 ──→ [Level Shifter] ──→ Strip 1 Data In (green)
                                     │
                                Strip 1 Data Out (green)
                                     │
                                     └──→ Strip 2 Data In (green)
                                           │
                                      Strip 2 Data Out (green)
                                           │
                                           └──→ Strip 3 Data In (green)

Result: Control all 432 LEDs as one continuous strip
```

### Option B: Parallel Data (More Flexible)

```
LED DATA (Parallel):
┌──────────────┐
│ Raspberry Pi │
└─┬──┬──┬──────┘
  │  │  │
  │  │  └─ GPIO 19 ──→ [Level Shifter] ──→ Strip 3 Data In
  │  │
  │  └──── GPIO 13 ──→ [Level Shifter] ──→ Strip 2 Data In
  │
  └─────── GPIO 18 ──→ [Level Shifter] ──→ Strip 1 Data In

POWER: Same as Option A (star topology)

Result: Control each strip independently (different effects per strip)
```

**Recommendation:** Option B for your use case (bass/mid/high on different strips)

---

## 🔧 Detailed Wiring Steps

### Step 1: Power Distribution (MOST IMPORTANT!)

**Materials needed:**
- Terminal blocks OR solder + heat shrink
- Red wire (22 AWG or thicker for power)
- Black wire (22 AWG or thicker for ground)

**Wiring:**
1. Cut 3x red wires (~6 inches each)
2. Cut 3x black wires (~6 inches each)
3. Connect in terminal block or solder:
   ```
   Power supply +5V ──→ Terminal block ──→ 3x red wires to strip +5V
   Power supply GND ──→ Terminal block ──→ 3x black wires to strip GND
                                      └──→ 1x black wire to Pi GND
   ```

**Critical safety check:**
- ✅ Measure power supply voltage BEFORE connecting strips
- ✅ Should read 5.0V ± 0.2V
- ✅ If higher than 5.5V, DO NOT CONNECT (wrong supply!)

### Step 2: LED Strip Connections

Each WS2812B strip has 3 wires at the start:
- **Red** = +5V power
- **White** = GND
- **Green** = Data In

**At the END of each strip:**
- **Red** = +5V (can chain power, but not recommended)
- **White** = GND
- **Green** = Data Out (for daisy-chaining data)

**Connect:**
1. Strip 1/2/3 red → 5V from power supply
2. Strip 1/2/3 white → GND from power supply
3. Strip 1/2/3 green → (see data wiring below)

### Step 3: Data Lines (with Level Shifter)

**Using 74AHCT125 quad buffer:**

```
74AHCT125 Pinout:
Pin 1: 1A (input)  → Connect to Pi GPIO 18
Pin 2: 1Y (output) → Connect to Strip 1 data in
Pin 7: GND         → Connect to common GND
Pin 14: VCC        → Connect to 5V from power supply

Repeat for channels 2, 3, 4 if using parallel data
```

**Without level shifter (try first!):**
- Some WS2812B strips accept 3.3V data signals
- Connect Pi GPIO directly to strip data in
- If LEDs are glitchy/wrong colors, you need the shifter

**Add 470Ω resistor:**
- Between Pi GPIO and data line (or level shifter input)
- Protects Pi and reduces signal reflections

### Step 4: Raspberry Pi GPIO Pinout

**For LED data (use these PWM-capable pins):**
- GPIO 18 (Physical pin 12) - PWM0
- GPIO 13 (Physical pin 33) - PWM1
- GPIO 19 (Physical pin 35) - PWM1

**For GND (any of these):**
- Physical pin 6, 9, 14, 20, 25, 30, 34, 39

**For 3.3V (if using level shifter low side):**
- Physical pin 1 or 17

**Pi Pinout Reference:**
```
    3.3V [ 1] [ 2] 5V
         [ 3] [ 4] 5V
         [ 5] [ 6] GND  ← Use for LED GND
         [ 7] [ 8]
     GND [ 9] [10]
         [11] [12] GPIO 18 ← Strip 1 data
GPIO 13 [33] [34] GND
GPIO 19 [35] [36]
```

### Step 5: Audio Input

**Y-Splitter:**
- Plug into Daisy Seed audio output
- One output → mixer/speakers
- Other output → USB audio interface

**USB Audio Interface:**
- Plug into Pi USB port
- Connect 3.5mm cable from Y-splitter to interface LINE IN
- No power needed (USB powered)

**Verify:**
```bash
# On Pi, list audio devices
arecord -l
# Should show "USB Audio Device" or similar
```

---

## ✅ Testing Checklist

### Before Powering On
- [ ] All GNDs connected together (Pi + Power supply + Strips)
- [ ] Power supply is 5V (measure with multimeter!)
- [ ] No shorts between +5V and GND (check with continuity tester)
- [ ] Data lines connected correctly (GPIO → shifter → strips)
- [ ] Pi powered separately (not from LED supply!)

### Power On Sequence
1. Connect Pi power (USB micro)
2. Boot Pi, SSH in
3. Connect 5V LED power supply
4. Run LED test script
5. If working, connect audio and run full script

### Safety
- ⚠️ Never hot-plug LED strips (power off first)
- ⚠️ Watch for heat on power supply (should be warm, not hot)
- ⚠️ If anything smells burnt, power off immediately
- ✅ Use fuses if available (inline 10A fuse on +5V line)

---

## 📸 Visual Verification

**Correct wiring looks like:**
- Clean power distribution (no loose wires)
- Common ground point visible
- Short data runs (minimize wire length)
- Power supply has ventilation (not enclosed)
- No exposed metal touching

**Wrong wiring:**
- LEDs powered from Pi GPIO (will crash)
- No common ground
- 12V supply connected (will destroy LEDs)
- Long, messy data wires (causes signal issues)

---

## 🐛 Common Hardware Issues

| Problem | Cause | Fix |
|---------|-------|-----|
| Pi reboots when LEDs turn on | LEDs drawing power from Pi | Use external 5V supply |
| First few LEDs work, rest don't | Voltage drop | Inject power at each strip start |
| Random colors/glitches | 3.3V data signal too weak | Add level shifter |
| LEDs flicker | Insufficient current | Larger power supply |
| No LEDs light up | Reversed polarity or bad data | Check wiring, test with simple code |
| Some LEDs stuck on one color | Damaged LED in chain | Find and bypass/replace |

---

## 📐 Physical Layout Suggestions

**For performance visibility:**

```
Option 1: Backdrop
┌─────────────────────────────┐
│  Strip 1 (horizontal)       │
│  Strip 2 (horizontal)       │ ← Behind performer
│  Strip 3 (horizontal)       │
└─────────────────────────────┘

Option 2: Vertical Bars
│ │ │
│ │ │  ← Three vertical strips
│ │ │     beside/behind performer
S1 S2 S3

Option 3: Surround
    Strip 2 (top)
       ┌─────┐
Strip 1│ YOU │Strip 3
       └─────┘
```

**Mounting:**
- WS2812B strips have adhesive backing
- Can stick to walls, stands, frames
- Keep away from liquids (non-waterproof!)

---

## ⚡ Quick Reference

**Power:**
- 5V ONLY (never 12V)
- 10A+ recommended
- Inject at each strip start
- Common GND with Pi

**Data:**
- Pi GPIO 18/13/19
- Level shifter for reliability
- 470Ω resistor recommended
- Keep wires short (<1 meter)

**Audio:**
- Y-splitter from Daisy
- USB audio interface to Pi
- Or use sounddevice library

Ready for the code guide!
