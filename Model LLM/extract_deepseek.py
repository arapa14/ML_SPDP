import os
import json
import torch
import pytesseract
import fitz  # PyMuPDF
import requests
from pdf2image import convert_from_path
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM

# === KONFIGURASI ===
PDF_PATH = "SPDP Nomor SPDP_43_V_Res.1.2._2025_Reskrim-777a2ead-1e6f-4feb-a979-9563a6cc748a.pdf"
POPPLER_PATH = r"C:\poppler-24.08.0\Library\bin"
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
GEMINI_API_KEY = "AIzaSyBB2UtsMZ-o0zKVWdWYoUTXQOI0s8h-vSA"

JSON_TEMPLATE = {
    "nomor_spdp": None,
    "tanggal_spdp": None,
    "tersangka": None,
    "pasal": None,
    "penyidik": None,
    "pelapor": None
}

# === Ekstraksi Teks dari PDF ===
def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    all_text = ""
    for page in doc:
        all_text += page.get_text()
    return all_text.strip()

# === OCR Fallback ===
def extract_text_with_ocr(pdf_path):
    print("🧠 Teks kosong. Mencoba ekstraksi dengan OCR...")
    images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
    all_text = ""
    for i, img in enumerate(images):
        text = pytesseract.image_to_string(img, lang="eng+ind")
        all_text += f"\n=== Halaman {i+1} ===\n{text.strip()}\n"
    return all_text.strip()

# === Prompt Builder ===
def build_prompt(document_text):
    limited_text = document_text[:1500]  # batasi untuk prompt supaya model tidak kelebihan input
    return f"""
Berikut adalah isi dokumen hukum (SPDP). Ekstrak informasi penting dalam format JSON.
Jika informasi tidak ditemukan, isi dengan null.

Format JSON yang diminta:
{json.dumps(JSON_TEMPLATE, indent=2)}

Teks Dokumen:
\"\"\"{limited_text}\"\"\"
""".strip()

# === Jalankan Model Lokal ===
def run_local_model(prompt, model_type):
    if model_type == "flan-t5":
        print("🔍 Menggunakan model: FLAN-T5-Small")
        generator = pipeline("text2text-generation", model="google/flan-t5-small")
        result = generator(prompt, max_length=300, do_sample=True)
        return result[0]["generated_text"]

    model_map = {
        "deepseek": "deepseek-ai/deepseek-llm-7b-base",
        "deepseek-small": "deepseek-ai/deepseek-coder-1.3b-base"
    }
    model_name = model_map[model_type]

    print(f"🔍 Menggunakan model: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
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

# === Jalankan Gemini API ===
def run_gemini(prompt):
    print("🔍 Menggunakan model: Gemini Flash via API")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        try:
            content = response.json()
            return content["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print("❌ Parsing Gemini API response gagal:", e)
            return "Output tidak dapat diambil dari Gemini."
    else:
        print("❌ Error dari Gemini API:", response.status_code, response.text)
        return "Request ke Gemini API gagal."

# === Fungsi bantu ekstrak JSON dari teks model ===
def extract_json_from_text(text):
    """
    Cari substring JSON dalam teks bebas yang mungkin mengandung teks tambahan.
    Menggunakan regex atau parsing sederhana untuk cari objek JSON pertama yang valid.
    """
    stack = []
    start_idx = None
    for i, c in enumerate(text):
        if c == '{':
            if start_idx is None:
                start_idx = i
            stack.append(c)
        elif c == '}' and stack:
            stack.pop()
            if not stack and start_idx is not None:
                candidate = text[start_idx:i+1]
                try:
                    data = json.loads(candidate)
                    if isinstance(data, dict):
                        return data
                except json.JSONDecodeError:
                    start_idx = None
                    continue
                start_idx = None
    return None

# === Simpan Hasil ke Folder Berdasarkan Model ===
def save_results(full_text, output_text, model_folder):
    os.makedirs(model_folder, exist_ok=True)

    txt_path = os.path.join(model_folder, "hasil.txt")
    json_path = os.path.join(model_folder, "hasil.json")

    # Simpan hasil.txt berisi semua teks lengkap dari PDF (atau OCR fallback)
    with open(txt_path, "w", encoding="utf-8") as f_txt:
        f_txt.write(full_text.strip())

    # Bersihkan output_text, cari JSON valid di dalamnya untuk hasil.json
    data = extract_json_from_text(output_text)

    if data is None:
        print("⚠️ Tidak ditemukan JSON valid dalam output. Menggunakan template kosong.")
        data = JSON_TEMPLATE.copy()

    # Pastikan semua key template ada di data
    for key in JSON_TEMPLATE.keys():
        if key not in data:
            data[key] = None

    with open(json_path, "w", encoding="utf-8") as f_json:
        json.dump(data, f_json, ensure_ascii=False, indent=2)

    print(f"\n✅ Hasil disimpan di folder '{model_folder}'")

# === MAIN ===
if __name__ == "__main__":
    print("📘 Pilih model ekstraksi:")
    print("1. FLAN-T5 (cepat & ringan)")
    print("2. DeepSeek LLM 7B (akurasi tinggi)")
    print("3. DeepSeek Coder 1.3B (efisien)")
    print("4. Gemini Flash API (Google, ringan & cepat)")
    pilihan = input("Masukkan nomor (1, 2, 3, atau 4): ").strip()

    model_map = {
        "1": "flan-t5",
        "2": "deepseek",
        "3": "deepseek-small",
        "4": "gemini"
    }
    model_type = model_map.get(pilihan)

    if not model_type:
        print("❌ Pilihan tidak valid.")
        exit()

    print("\n📄 Mengekstrak teks dari PDF...")
    full_text = extract_text_from_pdf(PDF_PATH)
    if not full_text or len(full_text) < 100:
        full_text = extract_text_with_ocr(PDF_PATH)

    prompt = build_prompt(full_text)

    if model_type == "gemini":
        output_text = run_gemini(prompt)
    else:
        output_text = run_local_model(prompt, model_type)

    print("\n=== Hasil Ekstraksi Model (mentah) ===")
    print(output_text)

    # Simpan hasil.txt berisi full_text (semua teks), dan hasil.json berisi data JSON hasil ekstraksi model
    save_results(full_text, output_text, model_type)

    print("\n✅ Ekstraksi selesai.")