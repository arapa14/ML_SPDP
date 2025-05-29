from pdf2image import convert_from_path
import pytesseract

# Path ke tesseract.exe (pastikan sudah benar)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Path file PDF
# pdf_path = "SPDP Nomor SPDP_43_V_Res.1.2._2025_Reskrim-777a2ead-1e6f-4feb-a979-9563a6cc748a.pdf"
pdf_path = "1746610349000.pdf"

# Path ke poppler
poppler_path = r"C:\poppler-24.08.0\Library\bin"

# Konversi PDF ke gambar
images = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)

# Hasil gabungan teks semua halaman
all_text = ""

# Jalankan OCR untuk tiap halaman
for i, img in enumerate(images):
    text = pytesseract.image_to_string(img, lang='eng')  # Ganti ke 'ind' jika bahasa Indonesia sudah diinstal
    all_text += f"\n=== Halaman {i+1} ===\n{text}\n"

# Simpan ke file .txt
output_file = "hasil_ocr.txt"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(all_text)

print(f"✅ Hasil OCR telah disimpan ke: {output_file}")
