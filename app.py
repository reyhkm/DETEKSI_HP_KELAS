import streamlit as st
import requests
import json
import time

st.set_page_config(page_title="Dashboard Kelas (Deteksi & Sensor)", layout="wide")

# --- Konfigurasi Ubidots ---
UBIDOTS_TOKEN = "BBUS-LVmlvNvVLuio2pqxZmPRrAvlGSoMyV"
DEVICE_LABEL = "esp32-sic" # <<< Pastikan ini nama device yang benar
UBIDOTS_BASE_URL = "https://industrial.api.ubidots.com/api/v1.6"

# --- Variabel Label di Ubidots (LENGKAPI SEMUA) ---
VAR_TRIGGER = "trigger-kirim"
VAR_AVG_CONFIDENCE = "confidence-rata-rata"
VAR_JUMLAH_HP = "jumlah-hp"
VAR_GAMBAR_URL = "gambar-terdeteksi" # Variabel untuk URL Cloudinary
VAR_SUHU = "temperature"            # <<< Variabel Suhu BARU
VAR_LEMBAB = "humidity"             # <<< Variabel Kelembaban BARU
VAR_SUARA = "sound"                 # <<< Variabel Suara BARU
VAR_GERAKAN = "motion"              # <<< Variabel Gerakan BARU

# --- Konfigurasi Flask API (Tetap Sama) ---
# <<< GANTI 'your-username' DENGAN USERNAME PYTHONANYWHERE KAMU >>>
FLASK_API_URL_GET = "https://oryxn.pythonanywhere.com/get_latest_image_url"

# --- Fungsi ambil data terakhir dari Ubidots ---
@st.cache_data(ttl=5) # Cache 5 detik (sesuaikan jika perlu)
def get_ubidots_last_values(device_label, variable_labels_list):
    results = {}
    if not isinstance(variable_labels_list, list): variable_labels_list = [variable_labels_list]
    for variable_label in variable_labels_list:
        url = f"{UBIDOTS_BASE_URL}/devices/{device_label}/{variable_label}/lv"
        headers = {"X-Auth-Token": UBIDOTS_TOKEN, "Content-Type": "application/json"}
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status(); results[variable_label] = response.json()
        except Exception as e:
            print(f"Gagal ambil Ubidots '{variable_label}': {e}")
            # Beri nilai default yang jelas jika gagal, misal None atau "Error"
            results[variable_label] = "Error" # Atau None
    return results

# --- Fungsi ambil URL dari Flask API ---
@st.cache_data(ttl=5) # Cache 5 detik
def get_url_from_flask():
    try:
        response = requests.get(FLASK_API_URL_GET, timeout=5); response.raise_for_status(); data = response.json(); return data.get("latest_image_url")
    except Exception as e: st.error(f"Error ambil data Flask: {e}"); return None

# ==============================================
# --- Tampilan Utama Aplikasi Streamlit ---
# ==============================================
st.title("📊 Dashboard Kelas: Deteksi HP & Monitoring Sensor")
st.info("Menampilkan status deteksi dan sensor terakhir.")

st.button("🔄 Refresh Dashboard")

# --- Ambil SEMUA Data Terakhir ---
variables_to_fetch_ubidots = [
    VAR_TRIGGER, VAR_JUMLAH_HP, VAR_AVG_CONFIDENCE,
    VAR_SUHU, VAR_LEMBAB, VAR_SUARA, VAR_GERAKAN # <<< Tambahkan var sensor
]
latest_data_ubidots = get_ubidots_last_values(DEVICE_LABEL, variables_to_fetch_ubidots)

latest_image_url = get_url_from_flask()

# --- Ekstrak Nilai ---
trigger_value = latest_data_ubidots.get(VAR_TRIGGER, 0)
jumlah_hp_value = latest_data_ubidots.get(VAR_JUMLAH_HP, 0)
confidence_value = latest_data_ubidots.get(VAR_AVG_CONFIDENCE, 0)
suhu_value = latest_data_ubidots.get(VAR_SUHU, "N/A")        # <<< Ambil nilai suhu
lembab_value = latest_data_ubidots.get(VAR_LEMBAB, "N/A")     # <<< Ambil nilai lembab
suara_value = latest_data_ubidots.get(VAR_SUARA, "N/A")       # <<< Ambil nilai suara
gerakan_value = latest_data_ubidots.get(VAR_GERAKAN, "N/A")   # <<< Ambil nilai gerakan

# --- Tampilkan Data Sensor ---
st.markdown("---")
st.header("🌡️ Sensor Kelas (Data dari Ubidots)")

col_sens1, col_sens2, col_sens3, col_sens4 = st.columns(4)

with col_sens1:
    # Format suhu jika angka, jika tidak tampilkan apa adanya (misal "Error" atau "N/A")
    suhu_display = f"{float(suhu_value):.1f} °C" if isinstance(suhu_value, (int, float)) else suhu_value
    st.metric("Suhu", suhu_display)

with col_sens2:
    lembab_display = f"{float(lembab_value):.1f} %" if isinstance(lembab_value, (int, float)) else lembab_value
    st.metric("Kelembaban", lembab_display)

with col_sens3:
    suara_display = f"{int(suara_value)}" if isinstance(suara_value, (int, float)) else suara_value
    st.metric("Level Suara", suara_display)

with col_sens4:
    # Gerakan biasanya 0 atau 1
    gerakan_display = "Ya" if isinstance(gerakan_value, (int, float)) and gerakan_value >= 1 else ("Tidak" if isinstance(gerakan_value, (int, float)) else gerakan_value)
    st.metric("Gerakan Terdeteksi", gerakan_display)


# --- Tampilkan Status Deteksi HP ---
st.markdown("---")
st.header("📈 Status Deteksi HP Terakhir (Data dari Ubidots)")

col_hp1, col_hp2, col_hp3 = st.columns(3)
with col_hp1: st.metric("Status Deteksi HP", "🚨 ADA HP!" if trigger_value == 1 else "✅ Aman", delta_color="off")
with col_hp2: jumlah_hp_display = int(jumlah_hp_value) if isinstance(jumlah_hp_value, (int, float)) else 0; st.metric("Jumlah HP", f"{jumlah_hp_display} unit")
with col_hp3: confidence_display = float(confidence_value) if isinstance(confidence_value, (int, float)) else 0.0; st.metric("Confidence Rata-rata", f"{confidence_display:.1f}%")

# --- Tampilkan Gambar Snapshot ---
st.markdown("---")
st.header("📸 Snapshot Terakhir Saat Deteksi (Gambar dari Flask API)")

if trigger_value == 1 and isinstance(latest_image_url, str) and latest_image_url.startswith("http"):
    st.image(latest_image_url,
             caption="Gambar terakhir saat HP terdeteksi (dari Cloudinary via Flask).",
             width=600) # <<< Atur lebar gambar
    st.caption(f"URL Gambar: {latest_image_url}")
elif trigger_value == 1:
    st.warning("Status: ADA HP, tapi URL gambar tidak valid/diterima dari server Flask.")
else:
    st.info("Status: Aman (Tidak ada HP terdeteksi pada laporan terakhir).")

# --- Footer ---
st.markdown("---")
st.markdown("Data Sensor via [Ubidots](https://ubidots.com/) | Gambar via [Cloudinary](https://cloudinary.com/) & [Flask](https://flask.palletsprojects.com/)")
st.markdown("Dashboard dibuat dengan Streamlit")

# --- Auto Refresh (Opsional) ---
# time.sleep(5) # Refresh setiap 5 detik?
# st.rerun()
