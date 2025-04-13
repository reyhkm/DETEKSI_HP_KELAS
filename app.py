import streamlit as st
import requests
import json
import base64
from PIL import Image
import io
import time

st.set_page_config(page_title="Dashboard Deteksi HP", layout="wide")

# --- Konfigurasi Ubidots ---
UBIDOTS_TOKEN = "BBUS-LVmlvNvVLuio2pqxZmPRrAvlGSoMyV"
DEVICE_LABEL = "esp32-kelas-saya"
UBIDOTS_BASE_URL = "https://industrial.api.ubidots.com/api/v1.6"

# --- Variabel Label di Ubidots (SESUAIKAN DENGAN NAMA BARU) ---
VAR_TRIGGER = "trigger-kirim"           # <<< Diubah
VAR_AVG_CONFIDENCE = "confidence-rata-rata" # <<< Diubah
VAR_JUMLAH_HP = "jumlah-hp"             # <<< Diubah
VAR_GAMBAR_B64 = "gambar-terdeteksi"   # <<< Diubah

# --- Fungsi ambil data terakhir dari Ubidots (Kode fungsi sama) ---
@st.cache_data(ttl=3)
def get_ubidots_last_values(device_label, variable_labels_list):
    results = {}
    if not isinstance(variable_labels_list, list): variable_labels_list = [variable_labels_list]
    for variable_label in variable_labels_list:
        url = f"{UBIDOTS_BASE_URL}/devices/{device_label}/{variable_label}/lv"
        headers = {"X-Auth-Token": UBIDOTS_TOKEN, "Content-Type": "application/json"}
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status(); results[variable_label] = response.json()
        except Exception as e: print(f"Gagal ambil '{variable_label}': {e}"); results[variable_label] = None
    return results

# --- Fungsi decode Base64 (Kode fungsi sama) ---
def decode_base64_image(base64_string):
    if not base64_string or not isinstance(base64_string, str): return None
    try: image_bytes = base64.b64decode(base64_string); image = Image.open(io.BytesIO(image_bytes)); return image
    except Exception as e: st.error(f"Gagal decode base64: {e}"); return None

# ==============================================
# --- Tampilan Utama Aplikasi Streamlit ---
# ==============================================
st.title("📊 Dashboard Deteksi Handphone (Status dari Backend)")
st.info("Dashboard ini menampilkan status terakhir yang dikirim oleh script detektor.")

st.button("🔄 Refresh Dashboard")

# Ambil semua data terakhir dari Ubidots (Menggunakan nama variabel baru)
variables_to_fetch = [VAR_TRIGGER, VAR_JUMLAH_HP, VAR_AVG_CONFIDENCE, VAR_GAMBAR_B64]
latest_data = get_ubidots_last_values(DEVICE_LABEL, variables_to_fetch)

# Ekstrak nilai (Menggunakan nama variabel baru)
trigger_value = latest_data.get(VAR_TRIGGER, 0)
jumlah_hp_value = latest_data.get(VAR_JUMLAH_HP, 0)
confidence_value = latest_data.get(VAR_AVG_CONFIDENCE, 0)
gambar_b64_value = latest_data.get(VAR_GAMBAR_B64, None)

st.markdown("---")
st.header("📈 Status Deteksi Terakhir")

col1, col2, col3 = st.columns(3)
with col1: st.metric("Status Deteksi", "🚨 ADA HP!" if trigger_value == 1 else "✅ Aman", delta_color="off")
with col2: jumlah_hp_display = int(jumlah_hp_value) if isinstance(jumlah_hp_value, (int, float)) else 0; st.metric("Jumlah HP", f"{jumlah_hp_display} unit")
with col3: confidence_display = float(confidence_value) if isinstance(confidence_value, (int, float)) else 0.0; st.metric("Confidence Rata-rata", f"{confidence_display:.1f}%")

st.markdown("---")
st.header("📸 Snapshot Terakhir Saat Deteksi")

if trigger_value == 1 and gambar_b64_value:
    decoded_image = decode_base64_image(gambar_b64_value)
    if decoded_image: st.image(decoded_image, caption="Gambar terakhir saat HP terdeteksi.", use_container_width=True)
    else: st.warning("Menerima data gambar, tapi gagal menampilkannya.")
elif trigger_value == 1 and not gambar_b64_value: st.warning("HP terdeteksi, tapi tidak ada data gambar diterima.")
else: st.info("Tidak ada HP terdeteksi pada status terakhir.")

# --- Footer ---
st.markdown("---")
st.markdown("Data via [Ubidots](https://ubidots.com/)")
st.markdown("Dashboard dibuat dengan Streamlit")

# --- Auto Refresh (Opsional) ---
# time.sleep(3)
# st.rerun()
