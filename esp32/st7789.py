import time
from micropython import const
import ustruct as struct

ST7789_SWRESET = const(0x01)
ST7789_SLPOUT  = const(0x11)
ST7789_NORON   = const(0x13)
ST7789_INVON   = const(0x21)
ST7789_DISPON  = const(0x29)
ST7789_CASET   = const(0x2A)
ST7789_RASET   = const(0x2B)
ST7789_RAMWR   = const(0x2C)
ST7789_COLMOD  = const(0x3A)

# Цвета RGB565
BLACK   = const(0x0000)
BLUE    = const(0x001F)
RED     = const(0xF800)
GREEN   = const(0x07E0)
CYAN    = const(0x07FF)
MAGENTA = const(0xF81F)
YELLOW  = const(0xFFE0)
WHITE   = const(0xFFFF)

class ST7789:
    def __init__(self, spi, width=170, height=320, reset=None, dc=None, cs=None, backlight=None):
        self.spi = spi
        self.width = width
        self.height = height
        self.reset = reset
        self.dc = dc
        self.cs = cs
        self.backlight = backlight

        if self.cs:
            self.cs.init(self.cs.OUT, value=1)
        if self.dc:
            self.dc.init(self.dc.OUT, value=0)
        if self.reset:
            self.reset.init(self.reset.OUT, value=1)
        if self.backlight:
            self.backlight.init(self.backlight.OUT, value=1)

        self._hard_reset()
        self._init_display()

    def _write_cmd(self, cmd):
        if self.cs: self.cs(0)
        if self.dc: self.dc(0)
        self.spi.write(bytearray([cmd]))
        if self.cs: self.cs(1)

    def _write_data(self, data):
        if self.cs: self.cs(0)
        if self.dc: self.dc(1)
        self.spi.write(data)
        if self.cs: self.cs(1)

    def _hard_reset(self):
        if self.reset:
            self.reset(1)
            time.sleep_ms(50)
            self.reset(0)
            time.sleep_ms(50)
            self.reset(1)
            time.sleep_ms(150)

    def _init_display(self):
        self._write_cmd(ST7789_SWRESET)
        time.sleep_ms(150)
        self._write_cmd(ST7789_SLPOUT)
        time.sleep_ms(120)
        self._write_cmd(ST7789_COLMOD)
        self._write_data(bytearray([0x55])) # 16 бит RGB565
        self._write_cmd(ST7789_INVON)       # Инверсия для IPS
        self._write_cmd(ST7789_NORON)
        time.sleep_ms(10)
        self._write_cmd(ST7789_DISPON)
        time.sleep_ms(100)

    def set_window(self, x0, y0, x1, y1):
        col_offset = 35
        row_offset = 0
        self._write_cmd(ST7789_CASET)
        self._write_data(struct.pack(">HH", x0 + col_offset, x1 + col_offset))
        self._write_cmd(ST7789_RASET)
        self._write_data(struct.pack(">HH", y0 + row_offset, y1 + row_offset))
        self._write_cmd(ST7789_RAMWR)

    def fill(self, color):
        self.set_window(0, 0, self.width - 1, self.height - 1)
        chunk_pixels = 64
        buf = struct.pack(">H", color) * chunk_pixels
        total_pixels = self.width * self.height
        
        if self.cs: self.cs(0)
        if self.dc: self.dc(1)
        for _ in range(total_pixels // chunk_pixels):
            self.spi.write(buf)
        rem = total_pixels % chunk_pixels
        if rem:
            self.spi.write(struct.pack(">H", color) * rem)
        if self.cs: self.cs(1)