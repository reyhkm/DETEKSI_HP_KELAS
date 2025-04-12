import streamlit as st
from inference_sdk import InferenceHTTPClient # Roboflow
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import io
import os
import pandas as pd
import base64
import requests # Untuk mengirim data
import json     # Untuk format data Ubidots
import time     # Untuk timestamp status

st.set_page_config(page_title="Deteksi HP & Data ke Ubidots", layout="wide")

# --- Konfigurasi Roboflow ---
ROBOFLOW_API_KEY = "lx9lvRB6j6sOgQ2u9sZr"
API_URL = "https://serverless.roboflow.com"
MODEL_ID = "mobilephones-ajdcy/1"

# --- Konfigurasi Ubidots ---
UBIDOTS_TOKEN = "BBUS-LVmlvNvVLuio2pqxZmPRrAvlGSoMyV" # <<< TOKEN UBIDOTS KAMU
DEVICE_LABEL = "esp32-kelas-saya"                     # <<< API Label Device Pilihanmu
UBIDOTS_BASE_URL = "https://industrial.api.ubidots.com/api/v1.6"

# --- Variabel Label di Ubidots ---
VAR_TRIGGER = "trigger-kirim"         # Variabel trigger (nilai 0 atau 1)
VAR_AVG_CONFIDENCE = "confidence-rata-rata" # Variabel confidence rata-rata
VAR_JUMLAH_HP = "jumlah-hp"           # <<< VARIABEL BARU untuk jumlah HP

# --- Inisialisasi Klien Roboflow ---
@st.cache_resource
def get_roboflow_client():
    # ... (fungsi get_roboflow_client tetap sama) ...
    if not ROBOFLOW_API_KEY: st.error("API Key Roboflow belum didefinisikan."); return None
    try: client = InferenceHTTPClient(api_url=API_URL, api_key=ROBOFLOW_API_KEY); return client
    except Exception as e: st.error(f"Gagal menginisialisasi klien Roboflow: {e}"); return None

client = get_roboflow_client()

# --- Fungsi untuk MENGIRIM nilai ke Ubidots (Tetap Sama) ---
def set_ubidots_variable(device_label, variable_label, value):
    url = f"{UBIDOTS_BASE_URL}/devices/{device_label}"
    headers = {"X-Auth-Token": UBIDOTS_TOKEN, "Content-Type": "application/json"}
    # Ubah sedikit: payload sekarang hanya untuk 1 variabel per panggilan
    payload = {variable_label: value}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        response.raise_for_status(); print(f"Set {variable_label}={value}. Status: {response.status_code}"); return True
    except requests.exceptions.Timeout: st.warning(f"Timeout Ubidots ({variable_label})"); return False
    except requests.exceptions.RequestException as e:
        try: detail = response.json()
        except: detail = response.text # noqa
        st.error(f"Error API Ubidots ({variable_label}): {e} - Detail: {detail}"); return False
    except Exception as e: st.error(f"Error Ubidots ({variable_label}): {e}"); return False

# --- Fungsi untuk Menggambar Bounding Box (Tetap Sama) ---
def draw_boxes(image_bytes, predictions):
    # ... (kode draw_boxes tidak berubah, salin dari sebelumnya) ...
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        draw = ImageDraw.Draw(image); font_size = max(15, int(image.width / 50))
        try: font = ImageFont.load_default(size=font_size)
        except IOError: font = ImageFont.load_default()
        box_color=(0, 100, 255); text_color=(255, 255, 255); text_background=(0, 100, 255)
        if not predictions: return image
        for pred in predictions:
            x_center=pred.get('x'); y_center=pred.get('y'); width=pred.get('width'); height=pred.get('height'); confidence=pred.get('confidence'); class_name=pred.get('class', 'Unknown')
            if None in [x_center, y_center, width, height, confidence]: continue
            x1=x_center-width/2; y1=y_center-height/2; x2=x_center+width/2; y2=y_center+height/2
            draw.rectangle([x1, y1, x2, y2], outline=box_color, width=3); label = f"{class_name}: {confidence:.1%}"
            try: text_bbox=draw.textbbox((0,0), label, font=font); text_width=text_bbox[2]-text_bbox[0]; text_height=text_bbox[3]-text_bbox[1]
            except AttributeError: text_width=len(label)*int(font_size*0.6); text_height=font_size+2
            text_x=x1; text_y=y1-text_height-2;
            if text_y<0: text_y=y1+2
            bg_x1=text_x; bg_y1=text_y; bg_x2=text_x+text_width; bg_y2=text_y+text_height
            draw.rectangle([bg_x1, bg_y1, bg_x2, bg_y2], fill=text_background); draw.text((text_x, text_y), label, fill=text_color, font=font)
        return image
    except Exception as e: st.error(f"Error gambar box: {e}"); return Image.new('RGB',(200,100),color='grey')


# ==============================================
# --- Tampilan Utama Aplikasi Streamlit ---
# ==============================================
st.title("📱 Deteksi HP & Kirim Data ke Ubidots")

# --- BAGIAN DETEKSI HANDPHONE ---
st.header("🔍 Deteksi Handphone")
st.write(f"Menggunakan model AI: `{MODEL_ID}`")

if 'last_status' not in st.session_state:
    st.session_state.last_status = "Belum ada deteksi."

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
            try: st.image(image_data_bytes, caption='Gambar yang Diunggah.', use_container_width=True)
            except Exception as e: st.error(f"Gagal menampilkan gambar asli: {e}")

        if st.button('Deteksi Handphone & Kirim Data'):
            with col_img2:
                with st.spinner('Melakukan deteksi dan mengirim data ke Ubidots...'):
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
                            st.json(result); filtered_predictions=None

                        # Tampilkan Hasil Deteksi di Streamlit
                        st.subheader("Hasil Deteksi")
                        if filtered_predictions is None:
                             st.error("Tidak bisa memproses hasil deteksi.")
                             st.session_state.last_status = "Gagal proses hasil Roboflow."
                        elif not filtered_predictions:
                            image_with_boxes = draw_boxes(image_data_bytes, filtered_predictions)
                            st.warning(f"Tidak ada HP terdeteksi (conf > {confidence_threshold:.0%}).")
                            st.image(image_with_boxes, caption='Tidak ada deteksi.', use_container_width=True)
                            # Kirim 0 ke Jumlah HP jika tidak terdeteksi
                            jumlah_hp_success = set_ubidots_variable(DEVICE_LABEL, VAR_JUMLAH_HP, 0)
                            st.session_state.last_status = f"Tidak ada HP terdeteksi ({time.strftime('%H:%M:%S')}). Jumlah HP (0) {'berhasil' if jumlah_hp_success else 'gagal'} dikirim."
                        else: # ADA HP TERDETEKSI
                            image_with_boxes = draw_boxes(image_data_bytes, filtered_predictions)
                            num_detections = len(filtered_predictions) # <<< JUMLAH HP
                            st.success(f"Terdeteksi {num_detections} HP.")
                            st.image(image_with_boxes, caption='Gambar dengan Bounding Box.', use_container_width=True)

                            # --- HITUNG & TAMPILKAN CONFIDENCE RATA-RATA ---
                            total_confidence = sum(pred.get('confidence', 0) for pred in filtered_predictions)
                            average_confidence = total_confidence / num_detections if num_detections > 0 else 0
                            st.metric("Confidence Rata-rata", f"{average_confidence:.1%}")
                            # ---------------------------------------------

                            # --- KIRIM DATA KE UBIDOTS ---
                            st.info(f"Mencoba mengirim data ke Ubidots...")
                            # Kirim Trigger = 1
                            trigger_success = set_ubidots_variable(DEVICE_LABEL, VAR_TRIGGER, 1)
                            # Kirim Confidence Rata-rata
                            confidence_to_send = round(average_confidence * 100, 1)
                            conf_success = set_ubidots_variable(DEVICE_LABEL, VAR_AVG_CONFIDENCE, confidence_to_send)
                            # Kirim Jumlah HP
                            jumlah_hp_success = set_ubidots_variable(DEVICE_LABEL, VAR_JUMLAH_HP, num_detections) # <<< KIRIM JUMLAH
                            # ---------------------------

                            # --- UPDATE STATUS ---
                            msg = f"({time.strftime('%H:%M:%S')}) "
                            results_list = []
                            if trigger_success: results_list.append("Trig(1):OK")
                            else: results_list.append("Trig(1):FAIL")
                            if conf_success: results_list.append(f"Conf({confidence_to_send}%):OK")
                            else: results_list.append("Conf:FAIL")
                            if jumlah_hp_success: results_list.append(f"Jml({num_detections}):OK")
                            else: results_list.append("Jml:FAIL")

                            msg += ", ".join(results_list) + " dikirim."

                            if trigger_success and conf_success and jumlah_hp_success:
                                st.success("Semua data berhasil dikirim ke Ubidots!")
                            else:
                                st.error("Sebagian atau semua data gagal dikirim ke Ubidots.")
                            st.session_state.last_status = msg
                            # ---------------------

                            # Tampilkan detail prediksi (opsional)
                            # ... (kode detail prediksi bisa ditambahkan jika mau) ...

                    except Exception as e:
                        st.error(f"Terjadi kesalahan saat inferensi Roboflow: {e}")
                        if 'result' in locals(): st.json(result)
                        st.session_state.last_status = f"Error saat deteksi: {e}"

# Menampilkan status terakhir
st.markdown("---")
st.info(f"Status Pengiriman Terakhir: {st.session_state.last_status}")

# --- Footer ---
st.markdown("---")
st.markdown("Model AI via [Roboflow](https://roboflow.com/) | Data via [Ubidots](https://ubidots.com/)")
st.markdown("Dibuat dengan Streamlit")
