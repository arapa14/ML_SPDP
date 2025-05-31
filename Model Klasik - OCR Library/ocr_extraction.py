from pdf2image import convert_from_path
import pytesseract
import cv2
import numpy as np
import json
import re
import os
from PIL import Image

# ======== KONFIGURASI ========
folder_pdf = "SPDP"
poppler_path = r"C:\poppler-24.08.0\Library\bin"
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
bahasa = 'ind'

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

# ======== FUNGSI EKSTRAKSI ENTITAS ========
import re

def ekstrak_entitas(teks):
    hasil = {}

    def safe_extract(match):
        return match.group(1).strip() if match and match.lastindex else "Tidak ditemukan"

    hasil["Tgl SPDP"] = safe_extract(re.search(
        r"(?:takalar)[^\w]?\s*(\d{1,2}\s*(?:Mei|Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s*\d{4})",
        teks, re.IGNORECASE))

    hasil["No SPDP"] = safe_extract(re.search(
        r"Nomor\s*[:\-]?\s*([A-Za-z0-9/\-. ]+)",
        teks, re.IGNORECASE))

    # ====== PROFILE PELAKU (multi orang) ======
    # Ambil hanya blok teks di antara "Identitas Tersangka" dan sebelum "Saksi" atau "Keterangan Saksi"
    blok_pelaku_raw = re.search(
        r"(?:Identitas Tersangka|Tersangka|Data Pelaku).*?(?=(?:Keterangan Saksi|Saksi|Barang Bukti|Perkara|Uraian|Pasal))",
        teks,
        re.IGNORECASE | re.DOTALL
    )

    profile_pelaku = []
    if blok_pelaku_raw:
        blok_pelaku = blok_pelaku_raw.group(0)

        pelaku_blocks = re.findall(
            r"(Nama\s*[:\-]?\s*[^\n]*\n.*?)(?=(?:\nNama\s*[:\-]|$))",
            blok_pelaku,
            re.IGNORECASE | re.DOTALL
        )

        for block in pelaku_blocks:
            pelaku = {
                "Nama": safe_extract(re.search(r"Nama\s*[:\-]?\s*([A-Z\s'.\-]+)", block, re.IGNORECASE)),
                "NIK": safe_extract(re.search(r"NIK(?:/No\.?\s*Identitas)?\s*[:\-]?\s*([0-9]{8,20})", block, re.IGNORECASE)),
                "Kewarganegaraan": safe_extract(re.search(r"Kewarganegaraan\s*[:\-]?\s*([A-Z ]+)", block, re.IGNORECASE)),
                "Jenis Kelamin": safe_extract(re.search(r"Jenis\s*Kelamin\s*[:\-]?\s*([A-Za-z ]+)", block, re.IGNORECASE)),
                "Tempat/Tanggal Lahir": safe_extract(re.search(r"tempat\s*/?\s*tanggal\s*lahir\s*[:\-]?\s*([A-Za-z ,0-9\-]+)", block, re.IGNORECASE)),
                "Pekerjaan": safe_extract(re.search(r"Pekerjaan\s*[:\-]?\s*([^\n,]+)", block, re.IGNORECASE)),
                "Agama": safe_extract(re.search(r"Agama\s*[:\-]?\s*([A-Za-z ]+)", block, re.IGNORECASE)),
                "Alamat": safe_extract(re.search(r"Alamat\s*[:\-]?\s*([^\n]+)", block, re.IGNORECASE)),
            }
            if any(value != "Tidak ditemukan" for value in pelaku.values()):
                profile_pelaku.append(pelaku)

    hasil["Profile Pelaku"] = profile_pelaku if profile_pelaku else "Tidak ditemukan"



    # Temukan kalimat yang mengandung konteks pelanggaran
    context = re.search(
        r"(?:melanggar|sebagaimana dimaksud dalam|tindak pidana yang dimaksud).*?(Pasal\s+\d+[^\n]*)",
        teks,
        re.IGNORECASE | re.DOTALL
    )

    if context:
        pasal_list = re.findall(
            r"Pasal\s+\d+(?:\s+Ayat\s*\(?\d+\)?)?(?:\s+Subs\s+Pasal\s+\d+(?:\s+Ayat\s*\(?\d+\)?)?)?(?:\s+Jo\s+Pasal\s+\d+(?:\s+Ayat\s*\(?\d+\)?)?)?",
            context.group(0),
            re.IGNORECASE
        )
        hasil["Pasal yg dilanggar"] = " | ".join(dict.fromkeys(pasal_list))  # hapus duplikat
    else:
        hasil["Pasal yg dilanggar"] = "Tidak ditemukan"




    hasil["Jenis Perkara"] = safe_extract(re.search(
        r"(?:tindak pidana|perkara)\s*(.*?)\s*(?=sebagaimana dimaksud|yang terjadi pada|Pasal \d+)",
        teks, re.IGNORECASE | re.DOTALL
    ))

    hasil["Uraian Perkara"] = safe_extract(re.search(
        r"(Bahwa pada hari.*?)\s*(?=(?:barang bukti|nama/alias|Demikian untuk menjadi maklum|Dugaan Peredaran|TINDAKAN YANG|^#|^\n|$))",
        teks,
        re.IGNORECASE | re.DOTALL
    ))

    hasil["Keterangan Saksi"] = safe_extract(re.search(
        r"(?:Keterangan Saksi|nama/alias)[^\n:]*[:\-]?\s*(.{30,500})",
        teks, re.IGNORECASE))

    hasil["Barang Bukti"] = safe_extract(re.search(
        r"(?:Barang Bukti|BARANG BUKTI)[^\n:]*[:\-]?\s*(.*?)(?=\n\s*\w+\.|\n\n|TINDAKAN YANG|Yang menerima|Dikeluarkan di|Demikian untuk)",
        teks,
        re.IGNORECASE | re.DOTALL
    ))

    penyidik_matches = re.findall(
    r"(?:IPDA|AIPDA|BRIPKA|BRIGPOL|BRIPDA)\s+[A-Z.,' \-]+NRP\s+\d{6,}", teks, re.IGNORECASE)

    hasil["Profile Penyidik"] = penyidik_matches if penyidik_matches else "Tidak ditemukan"

    return hasil


# ======== PROSES SEMUA PDF ========
for filename in os.listdir(folder_pdf):
    if filename.endswith(".pdf"):
        nama_file = os.path.splitext(filename)[0]  # contoh: spdp_1
        folder_output = f"hasil_{nama_file}"
        os.makedirs(folder_output, exist_ok=True)

        pdf_path = os.path.join(folder_pdf, filename)
        images = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)

        all_text = ""
        json_output = []

        for i, img in enumerate(images):
            image_path = os.path.join(folder_output, f"halaman_{i+1}.png")
            img.save(image_path, "PNG")

            processed = preprocess_image(img)
            text = pytesseract.image_to_string(processed, lang=bahasa)
            all_text += f"\n=== Halaman {i+1} ===\n{text.strip()}\n"
            json_output.append({
                "halaman": i + 1,
                "isi": text.strip()
            })

        # Simpan hasil OCR
        with open(os.path.join(folder_output, "hasil_ocr.txt"), "w", encoding="utf-8") as f_txt:
            f_txt.write(all_text)

        with open(os.path.join(folder_output, "hasil_ocr.json"), "w", encoding="utf-8") as f_json:
            json.dump(json_output, f_json, ensure_ascii=False, indent=2)

        # Simpan hasil ekstraksi entitas
        entitas = ekstrak_entitas(all_text)
        with open(os.path.join(folder_output, "entitas_ekstrak.json"), "w", encoding="utf-8") as f_ent:
            json.dump(entitas, f_ent, ensure_ascii=False, indent=2)

        # Cetak log
        print(f"✅ OCR selesai untuk {filename}")
        print(f"📁 Output disimpan di folder: {folder_output}\n")
