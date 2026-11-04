# Challenge 4a: draw the face with M5GFX primitives
import random
import time
import M5

M5.begin()
lcd = M5.Display
lcd.setRotation(1)
lcd.fillScreen(0x000000)
WHITE, BLACK = 0xFFFFFF, 0x000000


def face(dx=0, closed=False):
    lcd.fillRect(40, 70, 240, 110, BLACK)
    for x in (100, 220):
        if closed:
            lcd.fillRect(x - 14 + dx, 104, 28, 5, WHITE)
        else:
            lcd.fillCircle(x + dx, 106, 13, WHITE)
    lcd.fillRect(130 + dx // 2, 160, 60, 5, WHITE)    # mouth


while True:
    look = random.choice((-14, 0, 0, 14))
    face(look)
    time.sleep_ms(random.randint(1200, 3000))
    face(look, closed=True)                           # blink
    time.sleep_ms(120)
