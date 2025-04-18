from machine import Pin, I2C, ADC
import dht
import time
importx	ssd1306
import network
import urequests
import gc

# ====== Konfigurasi WiFi dan Ubidots ====== 
WIFI_SSID = "stephen"
WIFI_PASSWORD = "siapanamamu"
UBIDOTS_TOKEN = "BBUS-V0J3uZcao48EpkLTKdLN7AdI9ILglD"
DEVICE_LABEL = "esp32-sic"
UBIDOTS_URL = "http://industrial.api.ubidots.com/api/v1.6/devices/{}".format(DEVICE_LABEL)

# ====== Fungsi koneksi WiFi dengan delay setelah reconnect ======
def connect_wifi(timeout=10):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print('Menghubungkan ke WiFi...')
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        start = time.time()
        while not wlan.isconnected():
            if time.time() - start > timeout:
                print("❌ Gagal konek WiFi.")
                return False
            time.sleep(1)

        print('✅ Terhubung ke WiFi:', wlan.ifconfig())
        print("⏳ Menunggu WiFi stabil...")
        time.sleep(3) 
    return True

# ====== Inisialisasi perangkat ======
sensor = dht.DHT11(Pin(15))
pir_pin = Pin(13, Pin.IN)
mic = ADC(Pin(32))
mic.atten(ADC.ATTN_11DB)

i2c = I2C(0, scl=Pin(22), sda=Pin(21))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)
led = Pin(2, Pin.OUT)

SUARA_THRESHOLD = 2000
wifi_connected = False

def motion_detected():
    count = 0
    for _ in range(5):
        count += pir_pin.value()
        time.sleep(0.1)
    return count >= 3

def send_to_ubidots(suhu, kelembaban, gerakan, suara):
    try:
        data = {
            "temperature": suhu,
            "humidity": kelembaban,
            "motion": gerakan,
            "sound": suara
        }
        headers = {
            "X-Auth-Token": UBIDOTS_TOKEN,
            "Content-Type": "application/json"
        }
        response = urequests.post(UBIDOTS_URL, json=data, headers=headers)
        print("✅ Kirim ke Ubidots:", response.status_code)
        response.close()
        gc.collect()
    except Exception as e:
        print("❌ Gagal kirim ke Ubidots:", e)

# ====== Coba koneksi awal ======
wifi_connected = connect_wifi()

# ====== Loop Utama ======
while True:
    try:
        sensor.measure()
        suhu = sensor.temperature()
        kelembaban = sensor.humidity()
        gerakan = 1 if motion_detected() else 0
        nilai_suara = mic.read()

        print("Suhu: {:.2f}°C".format(suhu))
        print("Kelembaban: {:.2f}%".format(kelembaban))
        print("Gerakan:", "Ya" if gerakan else "Tidak")
        print("Suara:", nilai_suara)

        oled.fill(0)
        oled.text("Suhu: {:.2f}C".format(suhu), 0, 0)
        oled.text("Kelembaban: {:.2f}%".format(kelembaban), 0, 10)
        oled.text("Gerakan: {}".format(gerakan), 0, 20)
        oled.text("Suara: {}".format(nilai_suara), 0, 30)
        oled.show()

        led.value(1 if gerakan or nilai_suara > SUARA_THRESHOLD else 0)

        wlan = network.WLAN(network.STA_IF)
        if not wlan.isconnected():
            print("⚠ WiFi terputus. Mencoba reconnect...")
            wifi_connected = connect_wifi()
        else:
            wifi_connected = True

        if wifi_connected:
            send_to_ubidots(suhu, kelembaban, gerakan, nilai_suara)
        else:
            print("🚫 Lewati pengiriman data karena WiFi belum siap.")

    except Exception as e:
        print("❌ ERROR (Sensor atau WiFi):", e)

    time.sleep(5)