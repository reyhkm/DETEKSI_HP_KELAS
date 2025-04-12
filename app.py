import streamlit as st
from inference_sdk import InferenceHTTPClient # Roboflow
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import io
import os
import pandas as pd
import base64
import requests # Untuk mengirim trigger
import json     # Untuk format data Ubidots
import time     # Untuk timestamp status dan delay kecil
import cv2      # <<< Untuk akses webcam

st.set_page_config(page_title="Deteksi HP Real-time (Forced Demo)", layout="wide")

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
    if not ROBOFLOW_API_KEY: st.error("API Key Roboflow belum didefinisikan."); return None
    try: client = InferenceHTTPClient(api_url=API_URL, api_key=ROBOFLOW_API_KEY); return client
    except Exception as e: st.error(f"Gagal menginisialisasi klien Roboflow: {e}"); return None

client = get_roboflow_client()

# --- Fungsi untuk MENGIRIM nilai ke Ubidots (Tetap Sama) ---
def set_ubidots_variable(device_label, variable_label, value):
    url = f"{UBIDOTS_BASE_URL}/devices/{device_label}"; headers = {"X-Auth-Token": UBIDOTS_TOKEN, "Content-Type": "application/json"}
    payload = {variable_label: value}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=5) # Timeout lebih pendek
        response.raise_for_status(); print(f"Set {variable_label}={value}. Status: {response.status_code}"); return True
    except requests.exceptions.Timeout: print(f"Timeout Ubidots ({variable_label})"); return False # Ubah ke print agar tidak penuhi layar
    except requests.exceptions.RequestException as e: print(f"Error API Ubidots ({variable_label}): {e}"); return False
    except Exception as e: print(f"Error Ubidots ({variable_label}): {e}"); return False

# --- Fungsi untuk Menggambar Bounding Box (MODIFIKASI: Input & Output NumPy Array) ---
def draw_boxes_on_frame(frame_bgr, predictions):
    """Menggambar box di frame OpenCV (BGR) dan mengembalikan frame BGR baru."""
    image = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)) # Konversi ke PIL RGB
    draw = ImageDraw.Draw(image); font_size = max(15, int(image.width / 50))
    try: font = ImageFont.load_default(size=font_size)
    except IOError: font = ImageFont.load_default()
    box_color=(0, 0, 255); text_color=(255, 255, 255); text_background=(0, 0, 255) # Warna BGR untuk OpenCV

    if not predictions: return frame_bgr # Kembalikan frame asli jika tidak ada deteksi

    for pred in predictions:
        x_center=pred.get('x'); y_center=pred.get('y'); width=pred.get('width'); height=pred.get('height'); confidence=pred.get('confidence'); class_name=pred.get('class', 'Unknown')
        if None in [x_center, y_center, width, height, confidence]: continue
        x1=int(x_center-width/2); y1=int(y_center-height/2); x2=int(x_center+width/2); y2=int(y_center+height/2)

        # Gambar langsung di objek Image PIL
        draw.rectangle([x1, y1, x2, y2], outline=box_color, width=3); label = f"{class_name}: {confidence:.1%}"
        try: text_bbox=draw.textbbox((0,0), label, font=font); text_width=text_bbox[2]-text_bbox[0]; text_height=text_bbox[3]-text_bbox[1]
        except AttributeError: text_width=len(label)*int(font_size*0.6); text_height=font_size+2
        text_x=x1; text_y=y1-text_height-2;
        if text_y<0: text_y=y1+2
        bg_x1=text_x; bg_y1=text_y; bg_x2=text_x+text_width; bg_y2=text_y+text_height
        draw.rectangle([bg_x1, bg_y1, bg_x2, bg_y2], fill=text_background); draw.text((text_x, text_y), label, fill=text_color, font=font)

    # Konversi kembali ke format OpenCV BGR
    frame_processed_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    return frame_processed_bgr


# ==============================================
# --- Tampilan Utama Aplikasi Streamlit ---
# ==============================================
st.title("📱 Deteksi HP Real-time (Forced Demo - AKAN LAMBAT!)")
st.warning("""
    **PERINGATAN:** Mode ini HANYA untuk demonstrasi struktur kode.
    Karena menggunakan API Roboflow hosted via internet untuk setiap frame,
    aplikasi ini **AKAN SANGAT LAMBAT dan PATAH-PATAH (LAGGY)**.
    Ini bukan solusi real-time yang sesungguhnya. Pertimbangkan menggunakan
    Roboflow Inference Server Lokal untuk performa real-time.
""")

# Tombol untuk memulai/menghentikan (menggunakan session state)
if 'running' not in st.session_state:
    st.session_state.running = False

start_button = st.button("Mulai Deteksi Real-time dari Webcam")
stop_button = st.button("Hentikan Deteksi")

if start_button:
    st.session_state.running = True
if stop_button:
    st.session_state.running = False

# Placeholder untuk video feed
FRAME_WINDOW = st.image([])
# Placeholder untuk status
status_text = st.empty()

if st.session_state.running:
    if client is None:
        st.error("Klien Roboflow gagal diinisialisasi.")
        st.session_state.running = False # Hentikan jika klien gagal
    else:
        cap = cv2.VideoCapture(0) # Buka webcam default (index 0)
        if not cap.isOpened():
            st.error("Gagal membuka webcam.")
            st.session_state.running = False
        else:
            status_text.info("Webcam terbuka, memulai loop deteksi...")
            while st.session_state.running: # Loop selama 'running' True
                ret, frame = cap.read() # Baca frame dari webcam
                if not ret:
                    status_text.error("Gagal membaca frame dari webcam. Menghentikan.")
                    st.session_state.running = False
                    break

                # ---- Proses Inferensi Per Frame (INI BAGIAN LAMBAT) ----
                try:
                    # 1. Encode frame ke JPEG bytes lalu ke Base64
                    _, buffer = cv2.imencode('.jpg', frame)
                    base64_image_string = base64.b64encode(buffer).decode('utf-8')

                    # 2. Kirim ke Roboflow API (PANGGILAN INTERNET)
                    start_time = time.time()
                    result = client.infer(base64_image_string, model_id=MODEL_ID)
                    end_time = time.time()
                    api_latency = end_time - start_time

                    # 3. Proses Hasil Roboflow
                    all_predictions = result.get('predictions', []) if isinstance(result, dict) else (result if isinstance(result, list) else [])
                    confidence_threshold = 0.5 # Ambil dari slider jika diperlukan, tapi untuk loop mending fix
                    filtered_predictions = []
                    if all_predictions:
                        for pred in all_predictions:
                            if isinstance(pred, dict) and isinstance(pred.get('confidence'), (int, float)) and pred['confidence'] >= confidence_threshold:
                                filtered_predictions.append(pred)

                    # 4. Gambar Bounding Box
                    frame_with_boxes = draw_boxes_on_frame(frame, filtered_predictions)

                    # 5. Kirim Data ke Ubidots JIKA ada deteksi
                    num_detections = len(filtered_predictions)
                    trigger_sent = False
                    conf_sent = False
                    count_sent = False
                    if num_detections > 0:
                        total_confidence = sum(p.get('confidence', 0) for p in filtered_predictions)
                        average_confidence = total_confidence / num_detections
                        confidence_to_send = round(average_confidence * 100, 1)

                        trigger_sent = set_ubidots_variable(DEVICE_LABEL, VAR_TRIGGER, 1)
                        conf_sent = set_ubidots_variable(DEVICE_LABEL, VAR_AVG_CONFIDENCE, confidence_to_send)
                        count_sent = set_ubidots_variable(DEVICE_LABEL, VAR_JUMLAH_HP, num_detections)
                    else:
                        # Opsional: Kirim jumlah 0 jika tidak terdeteksi?
                        # count_sent = set_ubidots_variable(DEVICE_LABEL, VAR_JUMLAH_HP, 0)
                        pass # Atau tidak kirim apa-apa

                    # ---- Update Tampilan Streamlit ----
                    # Konversi BGR ke RGB untuk st.image
                    frame_display = cv2.cvtColor(frame_with_boxes, cv2.COLOR_BGR2RGB)
                    FRAME_WINDOW.image(frame_display, channels="RGB", use_container_width=True)

                    # Update status
                    status_msg = f"FPS: ~{1/api_latency:.1f} (API Latency: {api_latency:.2f}s) | "
                    if num_detections > 0:
                        status_msg += f"HP Terdeteksi: {num_detections} | Ubidots Send (T/C/J): {'OK' if trigger_sent else 'F'}/{'OK' if conf_sent else 'F'}/{'OK' if count_sent else 'F'}"
                    else:
                        status_msg += "HP Tidak Terdeteksi."
                    status_text.info(status_msg)

                except Exception as e:
                    status_text.error(f"Error dalam loop deteksi: {e}")
                    # Beri jeda sedikit jika ada error agar tidak spam
                    time.sleep(1)

                # Penting: Cek lagi status running SEBELUM loop berikutnya
                # Ini agar tombol Stop bisa menghentikan loop
                if not st.session_state.running:
                    break

            cap.release() # Tutup webcam jika loop berhenti
            status_text.info("Deteksi dihentikan. Webcam ditutup.")
else:
    status_text.info("Tekan 'Mulai Deteksi Real-time' untuk membuka webcam.")

# --- Footer ---
st.markdown("---")
st.markdown("Model AI via Roboflow | Data via Ubidots | **Demo Real-time Paksa**")
