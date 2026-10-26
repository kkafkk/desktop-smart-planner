import time
time.sleep(3)  # Защита от перепада напряжения при включении
import network
import urequests as requests
from machine import Pin, SPI
import st7789
import framebuf

# --- НАСТРОЙКИ ---
WIFI_SSID = "RT-WIFI-C7B0"
WIFI_PASSWORD = "~Betty_Corgi2711"
SERVER_URL = "http://192.168.3.10:8000"

SCREEN_TIMEOUT_MS = 3 * 60 * 1000
POLL_INTERVAL_MS = 5000

# --- ЖЕЛЕЗО ---
spi = SPI(1, baudrate=20000000, polarity=1, phase=1, sck=Pin(8), mosi=Pin(10))
backlight = Pin(2, Pin.OUT)
backlight.value(1)

tft = st7789.ST7789(spi, 170, 320, reset=Pin(1, Pin.OUT), dc=Pin(3, Pin.OUT), cs=Pin(7, Pin.OUT))
button = Pin(4, Pin.IN, Pin.PULL_UP)

last_activity = time.ticks_ms()
screen_on = True

# Состояние страниц: 0 = TASK (текущая), 1 = NEXT TASK (следующая)
tasks_list = []
view_mode = 0  

def connect_wifi():
    tft.fill(st7789.BLUE) 
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    time.sleep(1)
    
    try:
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        timeout = 20
        while not wlan.isconnected() and timeout > 0:
            time.sleep(0.5)
            timeout -= 1
            
        if wlan.isconnected():
            tft.fill(st7789.GREEN) 
        else:
            tft.fill(st7789.RED) 
    except Exception as e:
        print("ВНУТРЕННЯЯ ОШИБКА WI-FI:", e)
        tft.fill(st7789.YELLOW) 

def draw_rect(x, y, w, h, color):
    tft.set_window(x, y, x + w - 1, y + h - 1)
    
    cs = Pin(7, Pin.OUT)
    dc = Pin(3, Pin.OUT)
    
    cs.value(0)
    dc.value(1)
    
    buf = color.to_bytes(2, 'big') * 64
    total = w * h
    for _ in range(total // 64):
        tft.spi.write(buf)
    rem = total % 64
    if rem:
         tft.spi.write(color.to_bytes(2, 'big') * rem)
         
    cs.value(1)

def draw_text_simple(text, x, y, fg, bg=st7789.BLACK):
    fb = framebuf.FrameBuffer(bytearray(len(text) * 8 * 8), len(text) * 8, 8, framebuf.MONO_HLSB)
    fb.fill(0)
    fb.text(text, 0, 0, 1)
    
    for row in range(8):
        for col in range(len(text) * 8):
            color = fg if fb.pixel(col, row) else bg
            draw_rect(y + (7 - row) * 3, x + col * 3, 3, 3, color)

def render_task(task, is_next=False):
    tft.fill(st7789.WHITE)
    
    header = "NEXT TASK" if is_next else "TASK"
    
    if not task:
        # Если задач нет — рисуем серую шапку по тем же координатам
        draw_rect(130, 0, 35, 1510, 0x7BEF)
        draw_text_simple(header, 20, 132, st7789.WHITE, 0x7BEF)
        draw_text_simple("No tasks", 20, 105, st7789.BLACK, st7789.WHITE)
        return

    # Конвертация цвета
    raw_color = int(task.get("color", "0x001F"), 16)
    if raw_color > 0xFFFF:
        r = (raw_color >> 16) & 0xFF
        g = (raw_color >> 8) & 0xFF
        b = raw_color & 0xFF
        bg_color = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    else:
        bg_color = raw_color
        
    # Твоя шапка во весь экран
    draw_rect(130, 0, 35, 1510, bg_color)
    
    title = task.get("title", "No task")[:12]
    time_str = task.get("time", "12:00")
    
    # Текст строго по твоим координатам
    draw_text_simple(header, 20, 132, st7789.WHITE, bg_color)
    draw_text_simple("Do: " + title, 20, 105, st7789.BLACK, st7789.WHITE)
    draw_text_simple("Time: " + time_str, 20, 75, st7789.BLACK, st7789.WHITE)

def show_current_view():
    """Отображает текущую или следующую задачу в зависимости от view_mode"""
    if not tasks_list:
        render_task(None, is_next=(view_mode == 1))
        return
        
    if view_mode == 0:
        render_task(tasks_list[0], is_next=False)
    else:
        if len(tasks_list) > 1:
            render_task(tasks_list[1], is_next=True)
        else:
            render_task(None, is_next=True)

def fetch_tasks():
    global tasks_list
    # Сначала пробуем получить список всех задач с /api/tasks
    try:
        res = requests.get(SERVER_URL + "/api/tasks")
        if res.status_code == 200:
            data = res.json()
            res.close()
            if isinstance(data, list):
                tasks_list = [t for t in data if not t.get("completed", False)]
                return True
    except:
        pass

    # Если эндпоинта /api/tasks нет, забираем одиночную с /api/task
    try:
        res = requests.get(SERVER_URL + "/api/task")
        if res.status_code == 200:
            data = res.json()
            res.close()
            if data:
                tasks_list = [data]
                return True
    except:
        pass
        
    return False

connect_wifi()
fetch_tasks()
show_current_view()

last_poll = time.ticks_ms()
btn_last = 1

while True:
    now = time.ticks_ms()
    
    # Автоматическое засыпание по таймауту
    if screen_on and time.ticks_diff(now, last_activity) > SCREEN_TIMEOUT_MS:
        backlight.value(0)
        screen_on = False
        
    # Обработка нажатия физической кнопки
    btn_curr = button.value()
    if btn_last == 1 and btn_curr == 0:
        time.sleep_ms(20)  # Антидребезг контактов
        if button.value() == 0:
            last_activity = now
            if not screen_on:
                # 1. Если спал — будим и ВСЕГДА открываем текущий TASK
                backlight.value(1)
                screen_on = True
                view_mode = 0
                show_current_view()
            else:
                # 2. Если уже горел — переключаем между TASK (0) и NEXT TASK (1)
                view_mode = 1 if view_mode == 0 else 0
                show_current_view()
                
            while button.value() == 0:
                time.sleep_ms(10)
    btn_last = btn_curr

    # Периодическая проверка сервера
    if time.ticks_diff(now, last_poll) > POLL_INTERVAL_MS:
        old_ids = [t.get("id") for t in tasks_list]
        if fetch_tasks():
            new_ids = [t.get("id") for t in tasks_list]
            if old_ids != new_ids:
                show_current_view()
        last_poll = now
        
    time.sleep_ms(10)