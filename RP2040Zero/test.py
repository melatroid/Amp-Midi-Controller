from machine import Pin, UART, I2C
import time
from ssd1306 import SSD1306

# ---------- Pins ----------
PIN_RELAY     = 29
PIN_RELAY2    = 28
PIN_BTN_MAIN  = 7
PIN_BTN_MENU  = 8
MIDI_IN_PIN   = 5
MIDI_OUT_PIN  = 4

DEBOUNCE_MS = 30

# ---------- OLED (SSD1306/SSD1315) ----------
OLED_SDA = 0
OLED_SCL = 1
OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_ADDR = 0x3C
OLED_UPDATE_MS = 250

oled = None
last_oled_update = time.ticks_ms()

def oled_init():
    """OLED initialisieren und kurzen Test anzeigen."""
    i2c = I2C(0, sda=Pin(OLED_SDA), scl=Pin(OLED_SCL), freq=400000)
    display = SSD1306(OLED_WIDTH, OLED_HEIGHT, i2c, addr=OLED_ADDR)
    display.fill(0)
    display.text("OLED TEST", 0, 0, 1)
    display.text("SSD1306 OK", 0, 12, 1)
    display.rect(0, 28, 127, 35, 1)
    display.text("AMP TEST", 20, 40, 1)
    display.show()
    return display

def oled_update(display, relay_on, relay2_on, main_pressed, menu_pressed):
    """Kurzer Status-Screen, um OLED im Lauf zu testen."""
    display.fill(0)
    display.text("OLED STATUS", 0, 0, 1)
    display.text("Relay1: %s" % ("ON" if relay_on else "OFF"), 0, 12, 1)
    display.text("Relay2: %s" % ("ON" if relay2_on else "OFF"), 0, 24, 1)
    display.text("Main : %s" % ("DOWN" if main_pressed else "UP"), 0, 36, 1)
    display.text("Menu : %s" % ("DOWN" if menu_pressed else "UP"), 0, 48, 1)
    display.show()

# ---------- Relais & Taster ----------
relay = Pin(PIN_RELAY, Pin.OUT, value=0)
relay2 = Pin(PIN_RELAY2, Pin.OUT, value=0)

# Relais-Zustände in Variablen halten
relay_state = 0
relay.value(relay_state)

relay2_state = 0
relay2.value(relay2_state)

btn_main = Pin(PIN_BTN_MAIN, Pin.IN, Pin.PULL_UP)
btn_menu = Pin(PIN_BTN_MENU, Pin.IN, Pin.PULL_UP)

last_main_change  = time.ticks_ms()
last_menu_change  = time.ticks_ms()
prev_main = btn_main.value()
prev_menu = btn_menu.value()
main_pressed = False
menu_pressed = False

# ---------- MIDI UART ----------
uart = UART(
    1,
    baudrate=31250,
    bits=8,
    parity=None,
    stop=1,
    tx=Pin(MIDI_OUT_PIN),
    rx=Pin(MIDI_IN_PIN),
    invert=UART.INV_TX,   # <<< TX wird invertiert
)

# ---------- MIDI-Parser ----------

class MidiParser:
    def __init__(self):
        self.running_status = None
        self.data_bytes_needed = 0
        self.data_buffer = []

    def _msg_type_and_len(self, status):
        st = status & 0xF0
        if st == 0x80: return "Note OFF", 2
        if st == 0x90: return "Note ON", 2
        if st == 0xA0: return "Poly Aftertouch", 2
        if st == 0xB0: return "Control Change", 2
        if st == 0xC0: return "Program Change", 1
        if st == 0xD0: return "Channel Aftertouch", 1
        if st == 0xE0: return "Pitch Bend", 2
        return None, 0

    def feed(self, byte):
        """Ein einzelnes MIDI-Byte verarbeiten."""
        # Realtime-Messages: immer durchlassen, Running Status bleibt gültig
        if 0xF8 <= byte <= 0xFF:
            return

        # Status-Byte
        if byte & 0x80:
            if byte >= 0xF0:
                # System Common / SysEx – hier nur verwerfen
                self.running_status = None
                self.data_bytes_needed = 0
                self.data_buffer = []
                return

            self.running_status = byte
            self.data_buffer = []
            _, n = self._msg_type_and_len(byte)
            self.data_bytes_needed = n
            return

        # Daten-Byte
        if self.running_status is None or self.data_bytes_needed == 0:
            # Daten-Byte ohne Kontext – ignorieren
            return

        self.data_buffer.append(byte)
        if len(self.data_buffer) >= self.data_bytes_needed:
            self._emit_message()
            self.data_buffer = []

    def _emit_message(self):
        msg_name, _ = self._msg_type_and_len(self.running_status)
        if msg_name is None:
            return
        ch = (self.running_status & 0x0F) + 1
        data_str = " ".join("0x%02X" % d for d in self.data_buffer)
        print("MIDI MSG: %s, Ch %d, Data: %s" % (msg_name, ch, data_str))


parser = MidiParser()

# ---------- OLED Start ----------
try:
    oled = oled_init()
except Exception as e:
    print("OLED init fehlgeschlagen:", e)
    oled = None

# ---------- Hilfsfunktionen Relais ----------

def set_relay(state):
    """Relais1-Zustand setzen (0/1) und global speichern."""
    global relay_state
    relay_state = 1 if state else 0
    relay.value(relay_state)
    print("Relais1", "EIN" if relay_state else "AUS")

def set_relay2(state):
    """Relais2-Zustand setzen (0/1) und global speichern."""
    global relay2_state
    relay2_state = 1 if state else 0
    relay2.value(relay2_state)
    print("Relais2", "EIN" if relay2_state else "AUS")

# ---------- Main Loop ----------
print("System bereit. Warte auf MIDI...")

while True:
    now = time.ticks_ms()

    # ------- MainMomentary (btn_main): Toggle Relais1 -------

    val_main = btn_main.value()
    if val_main != prev_main:
        # Zustand hat gewechselt, Zeit merken
        last_main_change = now
        prev_main = val_main
    else:
        # Zustand stabil -> nach Debounce-Zeit auswerten
        if time.ticks_diff(now, last_main_change) > DEBOUNCE_MS:
            if val_main == 0 and not main_pressed:
                # Taster ist stabil gedrückt -> Toggle
                main_pressed = True
                set_relay(0 if relay_state else 1)

            elif val_main == 1 and main_pressed:
                # Taster losgelassen -> bereit für nächsten Toggle
                main_pressed = False

    # ------- MenuMomentary (btn_menu): Toggle Relais2 -------

    val_menu = btn_menu.value()
    if val_menu != prev_menu:
        last_menu_change = now
        prev_menu = val_menu
    else:
        if time.ticks_diff(now, last_menu_change) > DEBOUNCE_MS:
            if val_menu == 0 and not menu_pressed:
                # Taster stabil gedrückt -> Relais2 toggeln
                menu_pressed = True
                set_relay2(0 if relay2_state else 1)
            elif val_menu == 1 and menu_pressed:
                # Taster losgelassen -> bereit für nächsten Toggle
                menu_pressed = False

    # ------- MIDI einlesen & Thru -------

    n = uart.any()
    if n:
        data = uart.read(n)

        for byte in data:
            parser.feed(byte)
        uart.write(data)

    # ------- OLED Update -------
    if oled is not None and time.ticks_diff(now, last_oled_update) > OLED_UPDATE_MS:
        last_oled_update = now
        oled_update(oled, relay_state, relay2_state, main_pressed, menu_pressed)

    time.sleep_us(100)
