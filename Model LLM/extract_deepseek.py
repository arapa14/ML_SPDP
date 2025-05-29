from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
import torch
import fitz  # PyMuPDF
from pdf2image import convert_from_path
import pytesseract
import os
import json

# Path ke tesseract (ubah jika berbeda)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    all_text = ""
    for page in doc:
        all_text += page.get_text()
    return all_text.strip()

def extract_text_with_ocr(pdf_path):
    print("🧠 Teks kosong. Mencoba ekstraksi dengan OCR...")
    images = convert_from_path(pdf_path)
    all_text = ""
    for img in images:
        text = pytesseract.image_to_string(img, lang="eng")
        all_text += text + "\n"
    return all_text.strip()

def build_prompt(document_text):
    limited_text = document_text[:1500]  # batasi untuk token limit
    return f"""
Berikut adalah isi dokumen hukum (SPDP). Bacalah dan ekstrak data penting yang relevan. 
Pastikan untuk mengisi dalam format JSON seperti contoh di bawah. 
Jika suatu elemen tidak ditemukan dalam dokumen, isi dengan nilai null.

Contoh format JSON:
{{
  "nomor_spdp": "SPDP/XX/YYYY",
  "tanggal_spdp": "DD-MM-YYYY",
  "tersangka": "Nama Tersangka",
  "pasal": "Pasal yang disangkakan",
  "penyidik": "Nama Penyidik",
  "pelapor": "Nama Pelapor (jika ada)"
}}

Teks dokumen:
{limited_text}
"""

def run_extraction(pdf_path, model_type="flan-t5"):
    text = extract_text_from_pdf(pdf_path)
    if not text or len(text.strip()) < 100:
        text = extract_text_with_ocr(pdf_path)

    prompt = build_prompt(text)

    if model_type == "flan-t5":
        print("🔍 Menggunakan model: FLAN-T5-Small")
        generator = pipeline("text2text-generation", model="google/flan-t5-small")
        result = generator(prompt, max_length=300, do_sample=True)
        return result[0]['generated_text']

    elif model_type == "deepseek":
        print("🔍 Menggunakan model: DeepSeek-LLM-7B-Base")
        tokenizer = AutoTokenizer.from_pretrained("deepseek-ai/deepseek-llm-7b-base")
        model = AutoModelForCausalLM.from_pretrained(
            "deepseek-ai/deepseek-llm-7b-base",
            torch_dtype=torch.float16,
            device_map="auto"
        )
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True).to(model.device)
        outputs = model.generate(
            **inputs,
            max_new_tokens=300,
            temperature=0.7,
            do_sample=True
        )
        return tokenizer.decode(outputs[0], skip_special_tokens=True)

    elif model_type == "deepseek-small":
        print("🔍 Menggunakan model: DeepSeek-Coder-1.3B-Base")
        tokenizer = AutoTokenizer.from_pretrained("deepseek-ai/deepseek-coder-1.3b-base")
        model = AutoModelForCausalLM.from_pretrained(
            "deepseek-ai/deepseek-coder-1.3b-base",
            torch_dtype=torch.float16,
            device_map="auto"
        )
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True).to(model.device)
        outputs = model.generate(
            **inputs,
            max_new_tokens=300,
            temperature=0.7,
            do_sample=True
        )
        return tokenizer.decode(outputs[0], skip_special_tokens=True)

    else:
        raise ValueError("Model tidak dikenal. Gunakan 'flan-t5', 'deepseek', atau 'deepseek-small'.")

def save_results(output_text, json_path="hasil.json", txt_path="hasil.txt"):
    # Simpan ke file txt
    with open(txt_path, "w", encoding="utf-8") as ftxt:
        ftxt.write(output_text)

    # Coba parsing json dan simpan ke file json
    try:
        json_data = json.loads(output_text.strip())
    except json.JSONDecodeError:
        print("⚠️ Output bukan JSON valid, simpan json dengan null semua.")
        json_data = {
            "nomor_spdp": None,
            "tanggal_spdp": None,
            "tersangka": None,
            "pasal": None,
            "penyidik": None,
            "pelapor": None
        }

    with open(json_path, "w", encoding="utf-8") as fjson:
        json.dump(json_data, fjson, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    # Ganti path jika lokasi file berbeda
    pdf_file = "SPDP Nomor SPDP_43_V_Res.1.2._2025_Reskrim-777a2ead-1e6f-4feb-a979-9563a6cc748a.pdf"

    print("Pilih model ekstraksi:")
    print("1. FLAN-T5 (ringan, cepat)")
    print("2. DeepSeek LLM 7B (canggih, butuh GPU besar)")
    print("3. DeepSeek LLM 1.3B (model kecil, efisien)")
    pilihan = input("Masukkan nomor (1, 2, atau 3): ")

    if pilihan == "1":
        hasil = run_extraction(pdf_file, model_type="flan-t5")
    elif pilihan == "2":
        hasil = run_extraction(pdf_file, model_type="deepseek")
    elif pilihan == "3":
        hasil = run_extraction(pdf_file, model_type="deepseek-small")
    else:
        print("❌ Pilihan tidak valid.")
        exit()

    print("\n=== Hasil Ekstraksi ===")
    print(hasil)

    save_results(hasil)
    print("\n✅ Hasil disimpan ke hasil.json dan hasil.txt")
