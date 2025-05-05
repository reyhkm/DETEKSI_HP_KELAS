from ultralytics import YOLO
import cv2
import numpy as np
import requests
import json
import time
import argparse
import cloudinary
import cloudinary.uploader
import os
import tempfile

# --- Pengaturan Model & Input ---
MODEL_NAME = "yolov8n.pt"; INPUT_SOURCE = 0; CONFIDENCE_THRESHOLD = 0.40; CLASSES_TO_DETECT = [67]

# --- Konfigurasi Ubidots ---
UBIDOTS_TOKEN = "BBUS-LVmlvNvVLuio2pqxZmPRrAvlGSoMyV"; DEVICE_LABEL = "esp32-sic"; UBIDOTS_BASE_URL = "https://industrial.api.ubidots.com/api/v1.6"
VAR_TRIGGER = "trigger-kirim"; VAR_AVG_CONFIDENCE = "confidence-rata-rata"; VAR_JUMLAH_HP = "jumlah-hp"

# --- Konfigurasi Cloudinary ---
try: cloudinary.config(cloud_name="dvlgbfdtm", api_key="547672786393692", api_secret="8jBsbGc0aggvBOsgJOG1SBQZOSQ", secure=True); print("Cloudinary OK.") # JAGA SECRET
except Exception as e: print(f"GAGAL config Cloudinary: {e}"); exit()
UPLOAD_IMAGE_WIDTH = 480; UPLOAD_JPEG_QUALITY = 80

# --- Konfigurasi Flask API ---
# <<< GANTI 'your-username' DENGAN USERNAME PYTHONANYWHERE KAMU >>>
FLASK_API_URL_UPDATE = "https://oryxn.pythonanywhere.com/update_image"

# --- Load Model YOLOv8 LOKAL ---
try: model = YOLO(MODEL_NAME); print("Model YOLOv8 dimuat.")
except Exception as e: print(f"Gagal memuat model YOLOv8: {e}"); exit()

# --- Fungsi Kirim Data ke Ubidots (KEMBALIKAN LAGI) ---
def send_data_to_ubidots(payload):
    url = f"{UBIDOTS_BASE_URL}/devices/{DEVICE_LABEL}"; headers = {"X-Auth-Token": UBIDOTS_TOKEN, "Content-Type": "application/json"}
    try:
        if not payload: print("Payload Ubidots kosong."); return False
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10) # Timeout bisa lebih pendek
        response.raise_for_status(); print(f"Kirim Ubidots: {list(payload.keys())}. Status: {response.status_code}"); return True
    except requests.exceptions.Timeout: print(f"Timeout Ubidots"); return False
    except requests.exceptions.RequestException as e: print(f"Error API Ubidots: {e}"); return False
    except Exception as e: print(f"Error Ubidots: {e}"); return False

# --- Fungsi Kirim URL ke Flask API (Tetap Sama) ---
def send_url_to_flask(image_url):
    headers = {'Content-Type': 'application/json'}; payload = {'image_url': image_url}
    try:
        response = requests.post(FLASK_API_URL_UPDATE, headers=headers, json=payload, timeout=15)
        response.raise_for_status(); print(f"Kirim URL ke Flask. Status: {response.status_code}, Respon: {response.json()}"); return True
    except Exception as e: print(f"Error kirim ke Flask: {e}"); return False

# --- Fungsi Upload ke Cloudinary (Tetap Sama) ---
def upload_frame_to_cloudinary(frame_to_upload):
    # ... (Kode fungsi upload_frame_to_cloudinary SAMA seperti sebelumnya) ...
    temp_file_path = None; secure_url = None
    try:
        h, w = frame_to_upload.shape[:2]; scale = UPLOAD_IMAGE_WIDTH / w; new_h = int(h * scale)
        small_frame = cv2.resize(frame_to_upload, (UPLOAD_IMAGE_WIDTH, new_h), interpolation=cv2.INTER_AREA)
        temp_file_path = os.path.join(tempfile.gettempdir(), f"deteksi_{int(time.time())}.jpg")
        cv2.imwrite(temp_file_path, small_frame, [cv2.IMWRITE_JPEG_QUALITY, UPLOAD_JPEG_QUALITY])
        upload_result = cloudinary.uploader.upload(temp_file_path, folder="deteksi_hp", overwrite=True)
        secure_url = upload_result.get("secure_url"); print(f"URL Cloudinary Didapat: {secure_url}")
        return secure_url
    except Exception as e: print(f"Error upload Cloudinary: {e}"); return None
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try: os.unlink(temp_file_path)
            except Exception as del_e: print(f"Gagal hapus file temp: {del_e}")

# --- Fungsi Utama Proses ---
def run_detection():
    print(f"Memulai deteksi pada: {INPUT_SOURCE}")
    is_video_or_cam = isinstance(INPUT_SOURCE, int) or (isinstance(INPUT_SOURCE, str) and INPUT_SOURCE.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')))
    last_detection_state = False
    last_url_sent_to_flask = None # Lacak URL terakhir yg dikirim ke Flask

    if is_video_or_cam:
        cap = cv2.VideoCapture(INPUT_SOURCE)
        if not cap.isOpened(): print(f"Error: Gagal membuka video: {INPUT_SOURCE}"); return
        print("Kamera/Video terbuka. Tekan 'q' di window OpenCV untuk keluar.")

        while True:
            ret, frame = cap.read()
            if not ret: print("Stream video berakhir."); break

            results = model.predict(frame, classes=CLASSES_TO_DETECT, conf=CONFIDENCE_THRESHOLD, verbose=False)
            result = results[0]; detections = result.boxes.data.cpu().numpy(); filtered_predictions = detections
            num_detections = len(filtered_predictions)
            current_detection_state = num_detections > 0
            should_send_to_ubidots = False
            payload_ubidots = {}
            uploaded_image_url = None

            if current_detection_state:
                print(f"\rHP Terdeteksi: {num_detections}", end="")
                should_send_to_ubidots = True
                total_confidence = sum(d[4] for d in filtered_predictions)
                average_confidence = total_confidence / num_detections
                confidence_to_send = float(round(average_confidence * 100, 1))
                jumlah_hp_to_send = int(num_detections)

                # Siapkan payload Ubidots (hanya angka/status)
                payload_ubidots = {
                    VAR_TRIGGER: 1,
                    VAR_JUMLAH_HP: jumlah_hp_to_send,
                    VAR_AVG_CONFIDENCE: confidence_to_send
                }

                # Coba upload gambar ke Cloudinary
                uploaded_image_url = upload_frame_to_cloudinary(frame)

                # Kirim URL ke Flask (jika baru dan berhasil)
                if uploaded_image_url and uploaded_image_url != last_url_sent_to_flask:
                    send_url_to_flask(uploaded_image_url)
                    last_url_sent_to_flask = uploaded_image_url

            elif last_detection_state and not current_detection_state:
                print("\rHP Tidak Terdeteksi Lagi.        ", end="") # Spasi untuk clear line
                should_send_to_ubidots = True
                payload_ubidots = { VAR_TRIGGER: 0, VAR_JUMLAH_HP: 0 }
                # Mungkin kirim None/kosong ke Flask untuk hapus gambar terakhir?
                # if last_url_sent_to_flask is not None:
                #    send_url_to_flask(None)
                #    last_url_sent_to_flask = None


            # Kirim data ANGKA/STATUS ke Ubidots jika perlu
            if should_send_to_ubidots:
                print("\nMengirim data status ke Ubidots...") # Pindah baris
                send_data_to_ubidots(payload_ubidots)

            last_detection_state = current_detection_state

            # Tampilkan hasil di window OpenCV (opsional)
            frame_with_detections = result.plot()
            cv2.imshow("Deteksi HP Lokal (Tekan 'q')", frame_with_detections)
            if cv2.waitKey(1) & 0xFF == ord('q'): break

        cap.release(); cv2.destroyAllWindows()

    # Logika untuk gambar tunggal (mirip)
    elif isinstance(INPUT_SOURCE, str) and INPUT_SOURCE.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
        # ... (Kode proses gambar tunggal sama seperti sebelumnya,
        #      pastikan memanggil send_data_to_ubidots dan send_url_to_flask
        #      dengan payload yang sesuai seperti di loop video) ...
        if not os.path.exists(INPUT_SOURCE): print(f"Error: File gambar tidak ditemukan: {INPUT_SOURCE}"); return
        print(f"Memproses gambar: {INPUT_SOURCE}")
        try:
            frame = cv2.imread(INPUT_SOURCE)
            results = model.predict(INPUT_SOURCE, classes=CLASSES_TO_DETECT, conf=CONFIDENCE_THRESHOLD, verbose=True, save=True)
            result = results[0]; detections = result.boxes.data.cpu().numpy(); filtered_predictions = detections
        except Exception as e: print(f"Error inferensi YOLOv8: {e}"); filtered_predictions = []

        num_detections = len(filtered_predictions)
        payload_ubidots = {}; uploaded_image_url = None

        if num_detections > 0:
            print(f"HP Terdeteksi: {num_detections}")
            total_confidence = sum(d[4] for d in filtered_predictions); average_confidence = total_confidence / num_detections
            confidence_to_send = float(round(average_confidence * 100, 1)); jumlah_hp_to_send = int(num_detections)
            payload_ubidots = {VAR_TRIGGER: 1, VAR_JUMLAH_HP: jumlah_hp_to_send, VAR_AVG_CONFIDENCE: confidence_to_send}
            uploaded_image_url = upload_frame_to_cloudinary(frame)
            if uploaded_image_url: send_url_to_flask(uploaded_image_url) # Kirim URL ke Flask
            else: print("Upload gagal, URL tidak dikirim ke Flask.")
        else:
            print("HP Tidak Terdeteksi.")
            payload_ubidots = {VAR_TRIGGER: 0, VAR_JUMLAH_HP: 0}
            # send_url_to_flask(None) # Kirim None ke Flask jika tidak ada deteksi

        print("Mengirim data status ke Ubidots...")
        send_data_to_ubidots(payload_ubidots)
        print("Hasil gambar deteksi disimpan di folder 'runs/detect/predict...'")
    else:
        print(f"Error: Format input tidak didukung: {INPUT_SOURCE}")

    print("Proses selesai untuk input ini.")


# --- Jalankan Fungsi Utama ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deteksi HP lokal, upload Cloudinary, kirim data ke Ubidots & URL ke Flask.")
    parser.add_argument("-i", "--input", dest="input_source", default=0, help="Path gambar/video, atau 0 untuk webcam.")
    args = parser.parse_args()
    try: INPUT_SOURCE = int(args.input_source)
    except ValueError: INPUT_SOURCE = args.input_source

    try: run_detection()
    except KeyboardInterrupt: print("\nDeteksi dihentikan (Ctrl+C).")
    finally: cv2.destroyAllWindows(); print("Script detector selesai.")
