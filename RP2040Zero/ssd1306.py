# ssd1306 - ssd1315.py
from micropython import const
from machine import I2C, SoftI2C
import framebuf
import time

# Konstanten
SET_CONTRAST        = const(0x81)
SET_ENTIRE_ON       = const(0xA4)
SET_NORM_INV        = const(0xA6)
SET_DISP            = const(0xAE)
SET_MEM_ADDR        = const(0x20)
SET_COL_ADDR        = const(0x21)
SET_PAGE_ADDR       = const(0x22)
SET_DISP_START_LINE = const(0x40)
SET_SEG_REMAP       = const(0xA0)
SET_MUX_RATIO       = const(0xA8)
SET_COM_OUT_DIR     = const(0xC0)
SET_DISP_OFFSET     = const(0xD3)
SET_COM_PIN_CFG     = const(0xDA)
SET_DISP_CLK_DIV    = const(0xD5)
SET_PRECHARGE       = const(0xD9)
SET_VCOM_DESEL      = const(0xDB)
SET_CHARGE_PUMP     = const(0x8D)

class SSD1306:
    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = height // 8
        self.buffer = bytearray(self.pages * width)
        self.fb = framebuf.FrameBuffer(self.buffer, width, height, framebuf.MONO_VLSB)
        
        # Überprüfe I2C-Verbindung
        self._test_i2c()
        
        # Display initialisieren
        self.init_display()

    def _test_i2c(self):
        """Testet die I2C-Verbindung"""
        print(f"Testing I2C connection to address 0x{self.addr:02X}...")
        try:
            devices = self.i2c.scan()
            print(f"Found devices: {[hex(d) for d in devices]}")
            
            if self.addr not in devices:
                raise ValueError(f"Device at address 0x{self.addr:02X} not found!")
                
            # Einfachen I2C-Test durchführen
            self.i2c.writeto(self.addr, b'\x00')
            print("I2C communication test passed")
            
        except Exception as e:
            print(f"I2C test failed: {e}")
            print("\nTroubleshooting tips:")
            print("1. Check wiring: SDA->GP0, SCL->GP1")
            print("2. Add 4.7kΩ pull-up resistors to SDA/SCL")
            print("3. Verify power: 3.3V to VCC, GND to GND")
            print("4. Try different I2C addresses: 0x3C or 0x3D")
            raise

    def write_cmd(self, cmd):
        """Send command to display with error handling"""
        try:
            self.i2c.writeto(self.addr, bytes([0x00, cmd]))
        except OSError as e:
            if e.errno == 5:  # EIO
                print(f"I2C write error: EIO (cmd: 0x{cmd:02X})")
                print("Check I2C connection and pull-up resistors")
            raise

    def init_display(self):
        """Initialize display with SSD1315 compatible settings"""
        print("Initializing SSD1315 display...")
        
        # Display ausschalten während der Initialisierung
        self.write_cmd(SET_DISP)
        time.sleep_ms(10)
        
        # Initialisierungssequenz
        cmds = [
            SET_DISP | 0x00,              # Display off
            SET_MEM_ADDR, 0x00,           # Horizontal addressing mode
            SET_DISP_START_LINE | 0x00,   # Start line 0
            SET_SEG_REMAP | 0x01,         # Segment remap (A0/A1)
            SET_MUX_RATIO, self.height - 1,
            SET_COM_OUT_DIR | 0x08,       # COM output scan direction
            SET_DISP_OFFSET, 0x00,        # Display offset = 0
            SET_COM_PIN_CFG, 0x12 if self.height == 64 else 0x02,
            SET_DISP_CLK_DIV, 0x80,       # Clock divide ratio = 1, oscillator freq
            SET_PRECHARGE, 0xF1,          # Pre-charge period
            SET_VCOM_DESEL, 0x40,         # VCOMH deselect level
            SET_CONTRAST, 0xFF,           # Max contrast
            SET_ENTIRE_ON | 0x00,         # Disable entire display on
            SET_NORM_INV | 0x00,          # Non-inverted display
            SET_CHARGE_PUMP, 0x14,        # Enable charge pump
            SET_DISP | 0x01               # Display on
        ]
        
        try:
            for cmd in cmds:
                if isinstance(cmd, int):
                    self.write_cmd(cmd)
                elif isinstance(cmd, list):
                    self.write_cmd(cmd[0])
                    for b in cmd[1:]:
                        self.write_cmd(b)
            time.sleep_ms(100)
            
            # Buffer löschen und anzeigen
            self.fill(0)
            self.show()
            
            print("Display initialized successfully")
            
        except Exception as e:
            print(f"Display initialization failed: {e}")
            raise

    def fill(self, col):
        self.fb.fill(col)

    def pixel(self, x, y, col):
        self.fb.pixel(x, y, col)

    def text(self, s, x, y, col=1):
        self.fb.text(s, x, y, col)

    def show(self):
        """Update display with buffer content"""
        try:
            self.write_cmd(SET_COL_ADDR)
            self.write_cmd(0)
            self.write_cmd(self.width - 1)
            self.write_cmd(SET_PAGE_ADDR)
            self.write_cmd(0)
            self.write_cmd(self.pages - 1)
            
            # Buffer senden
            data = bytearray([0x40]) + self.buffer
            self.i2c.writeto(self.addr, data)
            
        except Exception as e:
            print(f"Error updating display: {e}")

    def poweroff(self):
        self.write_cmd(SET_DISP)

    def poweron(self):
        self.write_cmd(SET_DISP | 0x01)

    def contrast(self, contrast):
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(contrast)

    def invert(self, inv):
        self.write_cmd(SET_NORM_INV | (inv & 1))
        
    def hline(self, x, y, w, col):
        self.fb.hline(x, y, w, col)
        
    def vline(self, x, y, h, col):
        self.fb.vline(x, y, h, col)
        
    def line(self, x1, y1, x2, y2, col):
        self.fb.line(x1, y1, x2, y2, col)
        
    def rect(self, x, y, w, h, col, fill=False):
        self.fb.rect(x, y, w, h, col)
        if fill:
            self.fb.fill_rect(x, y, w, h, col)
            
    def blit(self, fbuf, x, y, key=-1):
        # FrameBuffer kann FrameBuffer->FrameBuffer blitten
        # (key wird bei MONO meist ignoriert, aber lassen wir drin)
        self.fb.blit(fbuf, x, y, key)

