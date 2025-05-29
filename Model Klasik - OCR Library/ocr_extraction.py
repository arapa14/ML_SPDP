from pdf2image import convert_from_path
import pytesseract
import cv2
import numpy as np
import json
import re
import os
from PIL import Image

# ======== KONFIGURASI ========
pdf_path = "SPDP Nomor SPDP_43_V_Res.1.2._2025_Reskrim-777a2ead-1e6f-4feb-a979-9563a6cc748a.pdf"
poppler_path = r"C:\poppler-24.08.0\Library\bin"
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
bahasa = 'ind'  # Ganti ke 'eng' jika 'ind' belum tersedia

# ======== BUAT FOLDER UNTUK GAMBAR ========
output_folder = "halaman_gambar"
os.makedirs(output_folder, exist_ok=True)  # Buat folder jika belum ada

# ======== FUNGSI PREPROCESSING ========
def preprocess_image(pil_img, enable=False):
    if not enable:
        return pil_img
    img = np.array(pil_img)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (3,3), 0)
    thresh = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    return Image.fromarray(thresh)

# ======== PROSES OCR ========
images = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)

all_text = ""
json_output = []

for i, img in enumerate(images):
    # Simpan gambar asli ke folder khusus
    image_path = os.path.join(output_folder, f"halaman_{i+1}.png")
    img.save(image_path, "PNG")

    # Pra-proses gambar jika perlu
    processed = preprocess_image(img)

    # Jalankan OCR
    text = pytesseract.image_to_string(processed, lang=bahasa)

    # Gabungkan hasil teks
    all_text += f"\n=== Halaman {i+1} ===\n{text.strip()}\n"

    # Simpan per halaman ke JSON
    json_output.append({
        "halaman": i + 1,
        "isi": text.strip()
    })

# Simpan hasil .txt
with open("hasil_ocr.txt", "w", encoding="utf-8") as f_txt:
    f_txt.write(all_text)

# Simpan hasil .json
with open("hasil_ocr.json", "w", encoding="utf-8") as f_json:
    json.dump(json_output, f_json, ensure_ascii=False, indent=2)

# ======== EKSTRAKSI ENTITAS ========
def ekstrak_entitas(teks):
    hasil = {}

    match_nomor = re.search(r"Nomor\s*[:\-]?\s*(SPDP[^\n]*)", teks, re.IGNORECASE)
    if match_nomor:
        hasil["nomor_spdp"] = match_nomor.group(1).strip()

    match_tgl = re.search(r"(?:tanggal|tgl)\s*[:\-]?\s*(\d{1,2}\s*[a-zA-Z]+\s*\d{4})", teks, re.IGNORECASE)
    if match_tgl:
        hasil["tanggal"] = match_tgl.group(1).strip()

    match_tersangka = re.search(r"tersangka\s*[:\-]?\s*([A-Z][^\n,]*)", teks, re.IGNORECASE)
    if match_tersangka:
        hasil["tersangka"] = match_tersangka.group(1).strip()

    match_pasal = re.search(r"pasal\s*[:\-]?\s*(\d+.*?KUHP[^.\n]*)", teks, re.IGNORECASE)
    if match_pasal:
        hasil["pasal"] = match_pasal.group(1).strip()

    match_penyidik = re.search(r"penyidik\s*[:\-]?\s*([A-Z][^\n]*)", teks, re.IGNORECASE)
    if match_penyidik:
        hasil["penyidik"] = match_penyidik.group(1).strip()

    match_instansi = re.search(r"(?:dari satuan kerja|instansi|unit kerja)\s*[:\-]?\s*(.*)", teks, re.IGNORECASE)
    if match_instansi:
        hasil["instansi"] = match_instansi.group(1).strip()

    return hasil

entitas = ekstrak_entitas(all_text)

# Simpan hasil entitas ke file
with open("entitas_ekstrak.json", "w", encoding="utf-8") as f_ent:
    json.dump(entitas, f_ent, ensure_ascii=False, indent=2)

# ======== OUTPUT ========
print("✅ OCR selesai.")
print("📁 Gambar disimpan di folder:", output_folder)
print("📄 File yang dihasilkan:")
print("- hasil_ocr.txt")
print("- hasil_ocr.json")
print("- entitas_ekstrak.json")
