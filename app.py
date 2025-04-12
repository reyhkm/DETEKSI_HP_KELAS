import streamlit as st
from inference_sdk import InferenceHTTPClient # Roboflow
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import io
import os
import pandas as pd # Masih dipakai untuk detail prediksi
import base64
import requests # Untuk mengirim trigger
import json     # Untuk format data trigger Ubidots
import time     # Untuk timestamp status

st.set_page_config(page_title="Deteksi HP & Trigger Kamera", layout="wide")

# --- Konfigurasi Roboflow ---
ROBOFLOW_API_KEY = "lx9lvRB6j6sOgQ2u9sZr" # (Asumsi masih pakai key ini)
API_URL = "https://serverless.roboflow.com"
MODEL_ID = "mobilephones-ajdcy/1"         # (Asumsi masih pakai model ini)

# --- Konfigurasi Ubidots (HANYA UNTUK TRIGGER) ---
UBIDOTS_TOKEN = "BBUS-LVmlvNvVLuio2pqxZmPRrAvlGSoMyV" # <<< TOKEN UBIDOTS KAMU
DEVICE_LABEL = "esp32-kelas-saya"                     # <<< API Label Device BARU/Pilihanmu
VAR_TRIGGER = "trigger-kirim"                     # <<< Nama variabel trigger
UBIDOTS_BASE_URL = "https://industrial.api.ubidots.com/api/v1.6"

# --- Inisialisasi Klien Roboflow ---
@st.cache_resource
def get_roboflow_client():
    if not ROBOFLOW_API_KEY:
         st.error("API Key Roboflow belum didefinisikan.")
         return None
    try:
        client = InferenceHTTPClient(api_url=API_URL, api_key=ROBOFLOW_API_KEY)
        return client
    except Exception as e:
        st.error(f"Gagal menginisialisasi klien Roboflow: {e}")
        return None

client = get_roboflow_client()

# --- Fungsi untuk MENGIRIM trigger ke Ubidots (Tetap Diperlukan) ---
def set_ubidots_variable(device_label, variable_label, value):
    """Mengirim nilai ke variabel Ubidots."""
    url = f"{UBIDOTS_BASE_URL}/devices/{device_label}"
    headers = {"X-Auth-Token": UBIDOTS_TOKEN, "Content-Type": "application/json"}
    payload = {variable_label: value}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        response.raise_for_status()
        print(f"Berhasil set {variable_label} ke {value}. Response: {response.status_code}")
        return True # Sukses mengirim
    except requests.exceptions.Timeout:
        st.warning(f"Timeout saat mengirim trigger Ubidots untuk {variable_label}")
        return False # Gagal mengirim
    except requests.exceptions.RequestException as e:
        error_detail = ""
        try: error_detail = response.json()
        except: error_detail = response.text # noqa
        st.error(f"Error API Ubidots saat set {variable_label}: {e} - Detail: {error_detail}")
        return False # Gagal mengirim
    except Exception as e:
        st.error(f"Error tidak terduga saat set Ubidots ({variable_label}): {e}")
        return False # Gagal mengirim

# --- Fungsi untuk Menggambar Bounding Box (Tetap Diperlukan) ---
def draw_boxes(image_bytes, predictions):
    # ... (salin kode draw_boxes dari versi sebelumnya) ...
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        draw = ImageDraw.Draw(image)
        try:
            font_size = max(15, int(image.width / 50)); font = ImageFont.load_default(size=font_size)
        except IOError: font = ImageFont.load_default()
        box_color = (0, 100, 255); text_color = (255, 255, 255); text_background = (0, 100, 255)
        if not predictions: return image
        for pred in predictions:
            x_center = pred.get('x'); y_center = pred.get('y'); width = pred.get('width'); height = pred.get('height'); confidence = pred.get('confidence'); class_name = pred.get('class', 'Unknown')
            if None in [x_center, y_center, width, height, confidence]: print(f"Skipping incomplete prediction data: {pred}"); continue
            x1=x_center-width/2; y1=y_center-height/2; x2=x_center+width/2; y2=y_center+height/2
            draw.rectangle([x1, y1, x2, y2], outline=box_color, width=3)
            label = f"{class_name}: {confidence:.1%}"
            try:
                text_bbox = draw.textbbox((0, 0), label, font=font); text_width = text_bbox[2] - text_bbox[0]; text_height = text_bbox[3] - text_bbox[1]
            except AttributeError: text_width = len(label) * int(font_size * 0.6); text_height = font_size + 2
            text_x = x1; text_y = y1 - text_height - 2
            if text_y < 0: text_y = y1 + 2
            bg_x1=text_x; bg_y1=text_y; bg_x2=text_x+text_width; bg_y2=text_y+text_height
            draw.rectangle([bg_x1, bg_y1, bg_x2, bg_y2], fill=text_background)
            draw.text((text_x, text_y), label, fill=text_color, font=font)
        return image
    except Exception as e:
        st.error(f"Error saat menggambar bounding box: {e}")
        try: return Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as img_err: st.error(f"Gagal membuka kembali gambar asli: {img_err}"); return Image.new('RGB', (200, 100), color = 'grey')

# ==============================================
# --- Tampilan Utama Aplikasi Streamlit ---
# ==============================================
st.title("📱 Deteksi HP & Trigger Kamera via Ubidots")

# --- BAGIAN DETEKSI HANDPHONE (ROBOFLOW) ---
st.header("🔍 Deteksi Handphone")
st.write(f"Menggunakan model AI: `{MODEL_ID}`")

# Status trigger terakhir
if 'last_trigger_status' not in st.session_state:
    st.session_state.last_trigger_status = "Belum ada deteksi / trigger."

if client is None:
    st.error("Inisialisasi Klien Roboflow gagal.")
else:
    uploaded_file = st.file_uploader("Pilih file gambar untuk deteksi HP...", type=["jpg", "jpeg", "png"])
    confidence_threshold = st.slider("Minimum Tingkat Keyakinan Deteksi (Confidence)", 0.0, 1.0, 0.5, 0.05, key="conf_slider")

    if uploaded_file is not None:
        image_data_bytes = uploaded_file.getvalue()

        col_img1, col_img2 = st.columns(2)
        with col_img1:
            st.subheader("Gambar Asli")
            try:
                st.image(image_data_bytes, caption='Gambar yang Diunggah.', use_container_width=True)
            except Exception as e:
                st.error(f"Gagal menampilkan gambar asli: {e}")

        if st.button('Deteksi Handphone & Kirim Trigger Jika Perlu'):
            with col_img2:
                with st.spinner('Melakukan deteksi...'):
                    try:
                        # 1. Deteksi
                        base64_image_string = base64.b64encode(image_data_bytes).decode('utf-8')
                        result = client.infer(base64_image_string, model_id=MODEL_ID)
                        all_predictions = result.get('predictions', []) if isinstance(result, dict) else (result if isinstance(result, list) else None)

                        filtered_predictions = []
                        if isinstance(all_predictions, list):
                            for pred in all_predictions:
                                if isinstance(pred, dict) and isinstance(pred.get('confidence'), (int, float)) and pred['confidence'] >= confidence_threshold:
                                    filtered_predictions.append(pred)
                        else:
                            st.error(f"Format hasil Roboflow tidak dikenali: {type(result)}")
                            st.json(result)


                        # Tampilkan Hasil
                        image_with_boxes = draw_boxes(image_data_bytes, filtered_predictions)
                        st.subheader("Hasil Deteksi")

                        # 2. Kirim Trigger HANYA jika ada deteksi
                        if not filtered_predictions:
                            st.warning(f"Tidak ada handphone terdeteksi dengan confidence di atas {confidence_threshold:.0%}.")
                            st.image(image_with_boxes, caption='Tidak ada deteksi.', use_container_width=True)
                            st.session_state.last_trigger_status = f"Tidak ada HP terdeteksi ({time.strftime('%H:%M:%S')}). Trigger TIDAK dikirim."
                        else:
                            num_detections = len(filtered_predictions)
                            st.success(f"Terdeteksi {num_detections} objek (handphone).")
                            st.image(image_with_boxes, caption='Gambar dengan Bounding Box.', use_container_width=True)

                            # KIRIM TRIGGER
                            st.info(f"Mencoba mengirim trigger '{VAR_TRIGGER}=1' ke Ubidots...")
                            success = set_ubidots_variable(DEVICE_LABEL, VAR_TRIGGER, 1)
                            if success:
                                st.success("Trigger '1' berhasil dikirim ke Ubidots!")
                                st.session_state.last_trigger_status = f"Trigger '1' (Ada HP) dikirim pada {time.strftime('%H:%M:%S')}"
                            else:
                                st.error("Gagal mengirim trigger ke Ubidots.")
                                st.session_state.last_trigger_status = "Gagal mengirim trigger terakhir."

                            # Tampilkan detail prediksi (opsional)
                            # ... (kode detail prediksi bisa ditambahkan jika mau) ...


                    except Exception as e:
                        st.error(f"Terjadi kesalahan saat inferensi Roboflow: {e}")
                        if 'result' in locals(): st.json(result) # Tampilkan result jika ada error


# Menampilkan status trigger terakhir
st.markdown("---")
st.info(f"Status Terakhir: {st.session_state.last_trigger_status}")
st.caption("(Status ini menunjukkan apakah Streamlit mencoba mengirim trigger ke Ubidots)")

# --- Footer ---
st.markdown("---")
st.markdown("Model AI via [Roboflow](https://roboflow.com/) | Trigger via [Ubidots](https://ubidots.com/)")
st.markdown("Dibuat dengan Streamlit")
