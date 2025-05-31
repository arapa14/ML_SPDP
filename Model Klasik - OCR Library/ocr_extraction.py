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
bahasa = 'ind'

# ======== BUAT FOLDER UNTUK GAMBAR ========
output_folder = "halaman_gambar"
os.makedirs(output_folder, exist_ok=True)

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
    image_path = os.path.join(output_folder, f"halaman_{i+1}.png")
    img.save(image_path, "PNG")

    processed = preprocess_image(img)
    text = pytesseract.image_to_string(processed, lang=bahasa)
    all_text += f"\n=== Halaman {i+1} ===\n{text.strip()}\n"
    json_output.append({
        "halaman": i + 1,
        "isi": text.strip()
    })

# Simpan hasil OCR
with open("hasil_ocr.txt", "w", encoding="utf-8") as f_txt:
    f_txt.write(all_text)

with open("hasil_ocr.json", "w", encoding="utf-8") as f_json:
    json.dump(json_output, f_json, ensure_ascii=False, indent=2)

# ======== EKSTRAKSI ENTITAS ========
def ekstrak_entitas(teks):
    hasil = {}

    # Tgl SPDP
    match_tgl = re.search(r"(?:TANGGAL|TGL)[^\w]?\s*(\d{1,2}\s*(?:Mei|Januari|Februari|Maret|April|Juni|Juli|Agustus|September|Oktober|November|Desember)\s*\d{4})", teks, re.IGNORECASE)
    hasil["Tgl SPDP"] = match_tgl.group(1).strip() if match_tgl else "Tidak ditemukan"

    # No SPDP (gunakan pola SPDP/.../.../....)
    match_no = re.search(r"(nomor|SPDP[\/\.\-\w]*)", teks)
    hasil["No SPDP"] = match_no.group(1).strip() if match_no else "Tidak ditemukan"

    # Profile Pelaku (misalnya setelah kata "atas nama", "nama tersangka", "atas diri")
    match_pelaku = re.search(r"(?:atas nama|tersangka|atas diri|terlapor|nama)\s*[:\-]?\s*([A-Z][^\n,]*)", teks, re.IGNORECASE)
    hasil["Profile Pelaku"] = match_pelaku.group(1).strip() if match_pelaku else "Tidak ditemukan"

    # Pasal yg dilanggar
    match_pasal = re.search(r"(?:melanggar|Pasal)\s*(\d+\s*(?:ayat\s*\(\d+\))?\s*KUHP(?:idana)?)", teks, re.IGNORECASE)
    hasil["Pasal yg dilanggar"] = match_pasal.group(1).strip() if match_pasal else "Tidak ditemukan"

    # Jenis Perkara (biasanya muncul dalam kalimat pembuka: “dugaan tindak pidana pencurian”, dll)
    match_jenis = re.search(r"tindak pidana\s*([^\n,\.]*)", teks, re.IGNORECASE)
    hasil["Jenis Perkara"] = match_jenis.group(1).strip() if match_jenis else "Tidak ditemukan"

    # Uraian Perkara (paragraf setelah kata "telah terjadi" atau "perkara tersebut")
    match_uraian = re.search(r"(?:uraian singkat|telah terjadi|perkara tersebut|melakukan penyidikan)[^\n:]*[:\-]?\s*(.{30,500})", teks, re.IGNORECASE)
    hasil["Uraian Perkara"] = match_uraian.group(1).strip() if match_uraian else "Tidak ditemukan"

    # Keterangan Saksi
    match_saksi = re.search(r"keterangan saksi|nama/alias[^\n:]*[:\-]?\s*(.{30,500})", teks, re.IGNORECASE)
    hasil["Keterangan Saksi"] = match_saksi.group(1).strip() if match_saksi else "Tidak ditemukan"

    # Barang Bukti (pola umum: “barang bukti berupa ...” atau setelah kata itu)
    match_bb = re.search(r"barang bukti[^\n:]*[:\-]?\s*(.{20,300})", teks, re.IGNORECASE)
    hasil["Barang Bukti"] = match_bb.group(1).strip() if match_bb else "Tidak ditemukan"

    # Profile Penyidik (nama penyidik biasanya sebelum tanda tangan, atau ditulis di akhir)
    match_penyidik = re.search(r"(AIPTU|BRIPKA|IPTU|AKP|Kompol|diperintahkan kepada)\s+[A-Z ]+", teks)
    hasil["Profile Penyidik"] = match_penyidik.group(0).strip() if match_penyidik else "Tidak ditemukan"

    return hasil


entitas = ekstrak_entitas(all_text)

with open("entitas_ekstrak.json", "w", encoding="utf-8") as f_ent:
    json.dump(entitas, f_ent, ensure_ascii=False, indent=2)

# Cetak hasil
print(json.dumps(entitas, ensure_ascii=False, indent=2))

# ======== OUTPUT ========
print("✅ OCR selesai.")
print("📁 Gambar disimpan di folder:", output_folder)
print("📄 File yang dihasilkan:")
print("- hasil_ocr.txt")
print("- hasil_ocr.json")
print("- entitas_ekstrak.json")
