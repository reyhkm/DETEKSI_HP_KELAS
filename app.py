import streamlit as st
import requests
import json
import time

st.set_page_config(page_title="Dashboard Deteksi HP (via Cloudinary)", layout="wide")

# --- Konfigurasi Ubidots ---
UBIDOTS_TOKEN = "BBUS-LVmlvNvVLuio2pqxZmPRrAvlGSoMyV"
DEVICE_LABEL = "kamera-kelas"
UBIDOTS_BASE_URL = "https://industrial.api.ubidots.com/api/v1.6"

# --- Variabel Label di Ubidots (Nama Disesuaikan) ---
VAR_TRIGGER = "trigger-kirim"
VAR_AVG_CONFIDENCE = "confidence-rata-rata"
VAR_JUMLAH_HP = "jumlah-hp"
VAR_GAMBAR_URL = "gambar-terdeteksi" # <<< GANTI NAMA VARIABEL DI SINI

# --- Fungsi ambil data terakhir dari Ubidots ---
@st.cache_data(ttl=5)
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

# ==============================================
# --- Tampilan Utama Aplikasi Streamlit ---
# ==============================================
st.title("📊 Dashboard Deteksi Handphone (Status & Gambar dari Cloudinary)")
st.info("Dashboard ini menampilkan status terakhir yang dikirim oleh script detektor.")

st.button("🔄 Refresh Dashboard")

# Ambil semua data terakhir dari Ubidots (Menggunakan nama variabel baru)
variables_to_fetch = [VAR_TRIGGER, VAR_JUMLAH_HP, VAR_AVG_CONFIDENCE, VAR_GAMBAR_URL] # <<< Ambil URL
latest_data = get_ubidots_last_values(DEVICE_LABEL, variables_to_fetch)

# Ekstrak nilai (Menggunakan nama variabel baru)
trigger_value = latest_data.get(VAR_TRIGGER, 0)
jumlah_hp_value = latest_data.get(VAR_JUMLAH_HP, 0)
confidence_value = latest_data.get(VAR_AVG_CONFIDENCE, 0)
gambar_url_value = latest_data.get(VAR_GAMBAR_URL, None) # <<< Ambil URL dari var "gambar-terdeteksi"

st.markdown("---")
st.header("📈 Status Deteksi Terakhir")

col1, col2, col3 = st.columns(3)
with col1: st.metric("Status Deteksi", "🚨 ADA HP!" if trigger_value == 1 else "✅ Aman", delta_color="off")
with col2: jumlah_hp_display = int(jumlah_hp_value) if isinstance(jumlah_hp_value, (int, float)) else 0; st.metric("Jumlah HP", f"{jumlah_hp_display} unit")
with col3: confidence_display = float(confidence_value) if isinstance(confidence_value, (int, float)) else 0.0; st.metric("Confidence Rata-rata", f"{confidence_display:.1f}%")

st.markdown("---")
st.header("📸 Snapshot Terakhir Saat Deteksi (via Cloudinary)")

# Tampilkan gambar langsung dari URL jika trigger aktif dan URL (dari var "gambar-terdeteksi") ada
if trigger_value == 1 and isinstance(gambar_url_value, str) and gambar_url_value.startswith("http"):
    st.image(gambar_url_value, caption="Gambar terakhir saat HP terdeteksi (dari Cloudinary).", use_container_width=True)
elif trigger_value == 1:
    st.warning("HP terdeteksi, tapi URL gambar tidak valid atau tidak diterima dari Ubidots (variabel 'gambar-terdeteksi').")
else:
    st.info("Tidak ada HP terdeteksi pada status terakhir.")

# --- Footer ---
st.markdown("---")
st.markdown("Data via [Ubidots](https://ubidots.com/) | Gambar via [Cloudinary](https://cloudinary.com/)")
st.markdown("Dashboard dibuat dengan Streamlit")
