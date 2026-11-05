# Challenge 1: talk to a serial bus servo with just a UART
import time
from machine import UART
from hardware.stackchan import StackChan

StackChan(i2c=1, uart=1).set_servo_power(True)   # Stack-chan: servo power
uart = UART(1, baudrate=1_000_000, tx=6, rx=7)


def send(servo, instruction, *params):
    # FF FF  ID  LEN  INSTRUCTION  PARAMS...  CHECKSUM
    body = bytes([servo, len(params) + 2, instruction]) + bytes(params)
    uart.read()                                  # drop stale bytes
    uart.write(b"\xff\xff" + body + bytes([~sum(body) & 0xFF]))
    time.sleep_ms(3)
    return uart.read()                           # its answer


def move(servo, steps, ms):
    # WRITE (0x03) register 42: goal position, time, speed
    send(servo, 0x03, 42, steps >> 8, steps & 0xFF,
         ms >> 8, ms & 0xFF, 0, 0)


for steps in (560, 360, 460):                    # servo 1 turns the head
    move(1, steps, 1200)                         # slowly: sudden starts reset the board
    time.sleep_ms(1400)
    reply = send(1, 0x02, 56, 2)                 # READ 2 bytes of register 56
    position = reply[5] << 8 | reply[6]          # FF FF ID LEN ERR [HI LO] CHK
    print(" ".join("%02X" % b for b in reply), "->", position)
