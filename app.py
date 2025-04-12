import streamlit as st
from inference_sdk import InferenceHTTPClient
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import io
import os
import pandas as pd
import base64

st.set_page_config(page_title="Deteksi Mobile Phones", layout="wide") # Judul halaman diubah sedikit

# --- Konfigurasi Aplikasi & API Key ---
# WARNING: API Key hardcoded seperti permintaan karena dianggap publik.
# JANGAN lakukan ini dengan API Key privat!
ROBOFLOW_API_KEY = "lx9lvRB6j6sOgQ2u9sZr" # API Key tetap sama sesuai contoh

# --- PERUBAHAN PENTING DI SINI ---
API_URL = "https://serverless.roboflow.com" # <<< URL API BARU
MODEL_ID = "mobilephones-ajdcy/1"         # <<< MODEL ID BARU
# --- AKHIR PERUBAHAN PENTING ---

# --- Inisialisasi Klien Roboflow ---
@st.cache_resource
def get_roboflow_client():
    """Menginisialisasi dan mengembalikan klien Roboflow."""
    if not ROBOFLOW_API_KEY:
         st.error("API Key Roboflow belum didefinisikan dalam kode.")
         return None
    try:
        client = InferenceHTTPClient(
            api_url=API_URL, # Menggunakan URL API yang sudah diperbarui
            api_key=ROBOFLOW_API_KEY
        )
        return client
    except Exception as e:
        st.error(f"Gagal menginisialisasi klien Roboflow: {e}")
        return None

client = get_roboflow_client()

# --- Fungsi untuk Menggambar Bounding Box ---
# (Fungsi draw_boxes tidak perlu diubah, sudah handle nama kelas dinamis)
def draw_boxes(image_bytes, predictions):
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        draw = ImageDraw.Draw(image)

        try:
            font_size = max(15, int(image.width / 50))
            font = ImageFont.load_default(size=font_size)
        except IOError:
            font = ImageFont.load_default()

        box_color = (0, 100, 255)
        text_color = (255, 255, 255)
        text_background = (0, 100, 255)

        if not predictions:
            return image

        for pred in predictions:
            x_center = pred.get('x')
            y_center = pred.get('y')
            width = pred.get('width')
            height = pred.get('height')
            confidence = pred.get('confidence')
            # Ambil nama kelas apa adanya dari hasil, tangani jika tidak ada
            class_name = pred.get('class', 'Unknown')

            if None in [x_center, y_center, width, height, confidence]:
                print(f"Skipping incomplete prediction data: {pred}")
                continue

            x1 = x_center - width / 2
            y1 = y_center - height / 2
            x2 = x_center + width / 2
            y2 = y_center + height / 2

            draw.rectangle([x1, y1, x2, y2], outline=box_color, width=3)

            # Tampilkan nama kelas dan confidence
            label = f"{class_name}: {confidence:.1%}"

            try:
                text_bbox = draw.textbbox((0, 0), label, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
            except AttributeError:
                 text_width = len(label) * int(font_size * 0.6)
                 text_height = font_size + 2

            text_x = x1
            text_y = y1 - text_height - 2

            if text_y < 0:
                text_y = y1 + 2

            bg_x1 = text_x
            bg_y1 = text_y
            bg_x2 = text_x + text_width
            bg_y2 = text_y + text_height
            draw.rectangle([bg_x1, bg_y1, bg_x2, bg_y2], fill=text_background)

            draw.text((text_x, text_y), label, fill=text_color, font=font)

        return image

    except Exception as e:
        st.error(f"Error saat menggambar bounding box: {e}")
        try:
            return Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as img_err:
            st.error(f"Gagal membuka kembali gambar asli: {img_err}")
            return Image.new('RGB', (200, 100), color = 'grey')


# --- Tampilan Utama Aplikasi Streamlit ---
st.title("📱 Deteksi Mobile Phones (Model Baru)") # Judul diubah
st.write(f"Menggunakan model: `{MODEL_ID}`") # Otomatis pakai model ID baru
st.markdown("""
    Unggah gambar, dan AI akan mencoba mendeteksi keberadaan handphone.
    *(API Key disematkan langsung dalam kode untuk demo ini)*
""")

if client is None:
    st.error("Inisialisasi Klien Roboflow gagal. Aplikasi tidak dapat berjalan.")
    st.stop()

uploaded_file = st.file_uploader("Pilih file gambar...", type=["jpg", "jpeg", "png"])

confidence_threshold = st.slider("Minimum Tingkat Keyakinan (Confidence)", 0.0, 1.0, 0.5, 0.05) # Default confidence mungkin perlu disesuaikan

if uploaded_file is not None:
    image_data_bytes = uploaded_file.getvalue()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Gambar Asli")
        try:
            st.image(image_data_bytes, caption='Gambar yang Diunggah.', use_container_width=True)
        except Exception as e:
            st.error(f"Gagal menampilkan gambar asli: {e}")

    if st.button('Deteksi Handphone'):
        with col2:
            with st.spinner('Mengonversi gambar dan melakukan deteksi...'):
                try:
                    base64_image_string = base64.b64encode(image_data_bytes).decode('utf-8')
                    # Memanggil infer dengan model ID yang sudah diperbarui
                    result = client.infer(base64_image_string, model_id=MODEL_ID)

                    all_predictions = []
                    filtered_predictions = []

                    # Logika filter dan tampilan hasil tetap sama
                    if isinstance(result, dict) and 'predictions' in result:
                        all_predictions = result['predictions']
                    elif isinstance(result, list):
                        all_predictions = result
                    else:
                        st.error(f"Format hasil tidak dikenali: {type(result)}")
                        st.json(result)
                        all_predictions = None

                    if isinstance(all_predictions, list):
                        for pred in all_predictions:
                            if isinstance(pred, dict) and isinstance(pred.get('confidence'), (int, float)):
                                if pred['confidence'] >= confidence_threshold:
                                    filtered_predictions.append(pred)

                        image_with_boxes = draw_boxes(image_data_bytes, filtered_predictions)

                        st.subheader("Hasil Deteksi")
                        if not filtered_predictions:
                            st.warning(f"Tidak ada handphone terdeteksi dengan confidence di atas {confidence_threshold:.0%}.")
                            st.image(image_with_boxes, caption='Tidak ada deteksi.', use_container_width=True)
                        else:
                            num_detections = len(filtered_predictions)
                            # Sesuaikan nama objek jika perlu, berdasarkan nama kelas baru
                            obj_name = "objek (handphone)"
                            st.success(f"Terdeteksi {num_detections} {obj_name}.")
                            st.image(image_with_boxes, caption='Gambar dengan Bounding Box.', use_container_width=True)

                        st.subheader("Detail Prediksi (setelah filter):")
                        if filtered_predictions:
                            try:
                                df = pd.DataFrame(filtered_predictions)
                                if 'confidence' in df.columns:
                                     df['confidence'] = df['confidence'].apply(lambda x: f"{x:.1%}" if isinstance(x, (int, float)) else x)
                                relevant_cols = [col for col in ['class', 'confidence', 'x', 'y', 'width', 'height'] if col in df.columns]
                                if relevant_cols:
                                    st.dataframe(df[relevant_cols])
                                else:
                                    st.write("Tidak ada kolom relevan untuk ditampilkan dalam tabel.")
                                    st.json(filtered_predictions)
                            except Exception as df_err:
                                st.error(f"Gagal menampilkan detail sebagai tabel: {df_err}")
                                st.json(filtered_predictions)
                        else:
                            st.write("Tidak ada prediksi lolos filter untuk ditampilkan.")

                except Exception as e:
                    st.error(f"Terjadi kesalahan saat inferensi atau pemrosesan hasil: {e}")
                    if "Unknown type of input" in str(e):
                         st.error("API tidak mengenali format input gambar. Pastikan SDK mendukung pengiriman base64 atau periksa format lain yang didukung.")
                    else:
                         st.error("Pastikan API Key valid, model ID benar, koneksi internet stabil, dan format data gambar benar.")
                    if 'result' in locals():
                         st.json(result)


# --- Footer atau Informasi Tambahan ---
st.markdown("---")
st.markdown("Model dari [Roboflow](https://roboflow.com/)") # Link umum
st.markdown("Dibuat dengan Streamlit & Roboflow Inference SDK.")
