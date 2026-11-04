# Hello Stack-chan: screen, LEDs and a beep
import M5
from M5 import Widgets
from hardware.stackchan import StackChan

M5.begin()
Widgets.setRotation(1)
Widgets.fillScreen(0x000000)
Widgets.Label("Hola PyConES!", 70, 105, 1.0, 0xFFFFFF, 0x000000,
              Widgets.FONTS.DejaVu24)

robot = StackChan(i2c=1, uart=1)
robot.set_rgb_color(0xFF4F9A)   # all 12 LEDs
M5.Speaker.tone(880, 150)
print("Hello from", M5.getBoard())
