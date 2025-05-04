import streamlit as st
import requests
import json
import time

st.set_page_config(page_title="Dashboard Deteksi HP (Ubidots + Flask)", layout="wide")

# --- Konfigurasi Ubidots ---
UBIDOTS_TOKEN = "BBUS-LVmlvNvVLuio2pqxZmPRrAvlGSoMyV"
DEVICE_LABEL = "esp32-sic"
UBIDOTS_BASE_URL = "https://industrial.api.ubidots.com/api/v1.6"
VAR_TRIGGER = "trigger-kirim"
VAR_AVG_CONFIDENCE = "confidence-rata-rata"
VAR_JUMLAH_HP = "jumlah-hp"

# --- Konfigurasi Flask API ---
# <<< GANTI 'your-username' DENGAN USERNAME PYTHONANYWHERE KAMU >>>
FLASK_API_URL_GET = "https://oryxn.pythonanywhere.com/get_latest_image_url"

# --- Fungsi ambil data terakhir dari Ubidots ---
@st.cache_data(ttl=3)
def get_ubidots_last_values(device_label, variable_labels_list):
    results = {}
    # ... (Kode fungsi get_ubidots_last_values sama seperti sebelumnya) ...
    if not isinstance(variable_labels_list, list): variable_labels_list = [variable_labels_list]
    for variable_label in variable_labels_list:
        url = f"{UBIDOTS_BASE_URL}/devices/{device_label}/{variable_label}/lv"
        headers = {"X-Auth-Token": UBIDOTS_TOKEN, "Content-Type": "application/json"}
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status(); results[variable_label] = response.json()
        except Exception as e: print(f"Gagal ambil Ubidots '{variable_label}': {e}"); results[variable_label] = None
    return results

# --- Fungsi ambil URL dari Flask API ---
@st.cache_data(ttl=3)
def get_url_from_flask():
    # ... (Kode fungsi get_url_from_flask sama seperti sebelumnya) ...
    try:
        response = requests.get(FLASK_API_URL_GET, timeout=5)
        response.raise_for_status(); data = response.json(); return data.get("latest_image_url")
    except Exception as e: st.error(f"Error ambil data Flask: {e}"); return None

# ==============================================
# --- Tampilan Utama Aplikasi Streamlit ---
# ==============================================
st.title("📊 Dashboard Deteksi HP (Status Ubidots & Gambar Flask)")
st.info("Dashboard ini menampilkan status dari Ubidots dan gambar terakhir dari Flask API.")

st.button("🔄 Refresh Dashboard")

# --- Ambil Data dari Ubidots ---
variables_ubidots = [VAR_TRIGGER, VAR_JUMLAH_HP, VAR_AVG_CONFIDENCE]
latest_data_ubidots = get_ubidots_last_values(DEVICE_LABEL, variables_ubidots)
trigger_value = latest_data_ubidots.get(VAR_TRIGGER, 0)
jumlah_hp_value = latest_data_ubidots.get(VAR_JUMLAH_HP, 0)
confidence_value = latest_data_ubidots.get(VAR_AVG_CONFIDENCE, 0)

# --- Ambil URL Gambar dari Flask ---
latest_image_url = get_url_from_flask()

st.markdown("---")
st.header("📈 Status Deteksi Terakhir (Data dari Ubidots)")

col1, col2, col3 = st.columns(3)
with col1: st.metric("Status Deteksi", "🚨 ADA HP!" if trigger_value == 1 else "✅ Aman", delta_color="off")
with col2: jumlah_hp_display = int(jumlah_hp_value) if isinstance(jumlah_hp_value, (int, float)) else 0; st.metric("Jumlah HP", f"{jumlah_hp_display} unit")
with col3: confidence_display = float(confidence_value) if isinstance(confidence_value, (int, float)) else 0.0; st.metric("Confidence Rata-rata", f"{confidence_display:.1f}%")

st.markdown("---")
st.header("📸 Snapshot Terakhir Saat Deteksi (Gambar dari Flask API)")

# Tampilkan gambar jika URL valid (tidak perlu cek trigger lagi, biarkan Flask yg menentukan)
if isinstance(latest_image_url, str) and latest_image_url.startswith("http"):
    st.image(latest_image_url, caption="Gambar terakhir saat HP terdeteksi (dari Cloudinary via Flask).", use_container_width=True)
    st.caption(f"URL Gambar: {latest_image_url}")
else:
    st.info("Belum ada snapshot deteksi terbaru yang dilaporkan ke server Flask.")

# --- Footer ---
st.markdown("---")
st.markdown("Data via [Ubidots](https://ubidots.com/) | Gambar via [Cloudinary](https://cloudinary.com/) & [Flask](https://flask.palletsprojects.com/)")
st.markdown("Dashboard dibuat dengan Streamlit")

# --- Auto Refresh (Opsional) ---
# time.sleep(3)
# st.rerun()
