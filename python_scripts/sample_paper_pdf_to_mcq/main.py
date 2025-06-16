import os
import re
import zipfile
import fitz
import json
import pandas as pd
from flask import Flask, request, render_template, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ✅ Use absolute path relative to this file for safety
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def clean_text(text):
    text = re.sub(r'\b1\.0\b|\b0\.00\b', '', text)
    text = re.sub(r'\bTRADE THEORY\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bNUMERICAL ABILITY AND REASONING\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Max Marks.*?(?=\n|$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'ALL INDIA TRADE TEST.*?(?=\n[A-Z]|$)', '', text, flags=re.DOTALL)
    text = re.sub(r'INSTRUCTOR TRAINING SCHEME.*?(?=Note:|\Z)', '', text, flags=re.DOTALL)
    text = re.sub(r'Note:.*?(?=\n\d+\s+|\Z)', '', text, flags=re.DOTALL)
    text = re.sub(r'\n+', '\n', text)
    return text.strip()

def clean_option(text):
    for key in ["Correct Answer Key", "S.No.", "Computer Hardware", "Exam Date", "Note:"]:
        if key in text:
            text = text.split(key)[0]
    lines = text.strip().splitlines()
    unique = []
    for line in lines:
        line = line.strip()
        if line and not re.search(r'\b\d+\s+\d+\b', line) and line not in unique:
            unique.append(line)
    return ' '.join(unique)

def split_en_hi(text):
    match = re.search(r'[\u0900-\u097F]', text.strip())
    if match:
        idx = match.start()
        return text[:idx].strip(), text[idx:].strip()
    return text.strip(), text.strip()

def process_pdf(filepath):
    filename = os.path.basename(filepath)
    doc = fitz.open(filepath)
    full_text = "\n".join(page.get_text() for page in doc)
    pattern = re.findall(
        r'(\d+)\s+\d+\s+(.*?)\s*A1\s*:\s*(.*?)\s*A2\s*:\s*(.*?)\s*A3\s*:\s*(.*?)\s*A4\s*:\s*(.*?)(?=\n\d+\s+\d+|\Z)',
        full_text, re.DOTALL
    )

    all_questions = []
    for qno_str, question, a1, a2, a3, a4 in pattern:
        qno = int(qno_str.strip())
        q_en, q_hi = split_en_hi(clean_text(question))
        a1_en, a1_hi = split_en_hi(clean_text(clean_option(a1)))
        a2_en, a2_hi = split_en_hi(clean_text(clean_option(a2)))
        a3_en, a3_hi = split_en_hi(clean_text(clean_option(a3)))
        a4_en, a4_hi = split_en_hi(clean_text(clean_option(a4)))

        all_questions.append({
            "Question No.": qno,
            "Question_EN": q_en, "Question_HI": q_hi,
            "Option_A_EN": a1_en, "Option_A_HI": a1_hi,
            "Option_B_EN": a2_en, "Option_B_HI": a2_hi,
            "Option_C_EN": a3_en, "Option_C_HI": a3_hi,
            "Option_D_EN": a4_en, "Option_D_HI": a4_hi,
            "Correct Answer": ""
        })

    answer_map = dict(re.findall(r'(\d{1,3})\s+(A[1-4])', doc[-1].get_text()))
    code_to_option = {"A1": "Option_A_EN", "A2": "Option_B_EN", "A3": "Option_C_EN", "A4": "Option_D_EN"}
    letter_map = {"Option_A_EN": "A", "Option_B_EN": "B", "Option_C_EN": "C", "Option_D_EN": "D"}

    for q in all_questions:
        opt_key = code_to_option.get(answer_map.get(str(q["Question No."])))
        if opt_key:
            q["Correct Answer"] = letter_map.get(opt_key, "")

    base = os.path.splitext(filename)[0]
    json_path = os.path.join(OUTPUT_FOLDER, base + "_MCQ_EN_HI.json")
    excel_path = os.path.join(OUTPUT_FOLDER, base + "_MCQ_EN_HI.xlsx")
    zip_path = os.path.join(OUTPUT_FOLDER, base + "_MCQ_EN_HI.zip")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=2)
    pd.DataFrame(all_questions).to_excel(excel_path, index=False)

    with zipfile.ZipFile(zip_path, "w") as z:
        z.write(json_path, arcname=os.path.basename(json_path))
        z.write(excel_path, arcname=os.path.basename(excel_path))

    return {"name": filename, "json": os.path.basename(json_path), "excel": os.path.basename(excel_path), "zip": os.path.basename(zip_path)}

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # 🧹 Clean previous files before processing new uploads
        for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
            for f in os.listdir(folder):
                fp = os.path.join(folder, f)
                if os.path.isfile(fp):
                    os.remove(fp)

        files = request.files.getlist("pdfs")
        if not files:
            return render_template("index.html", error="Please upload at least one PDF.")
        
        results = []
        for file in files:
            if file.filename.lower().endswith(".pdf"):
                filepath = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
                file.save(filepath)
                results.append(process_pdf(filepath))

        master_zip = os.path.join(OUTPUT_FOLDER, "master.zip")
        with zipfile.ZipFile(master_zip, "w") as z:
            for res in results:
                z.write(os.path.join(OUTPUT_FOLDER, res["json"]), arcname=res["json"])
                z.write(os.path.join(OUTPUT_FOLDER, res["excel"]), arcname=res["excel"])

        return render_template("results.html", results=results, master="master.zip")

    return render_template("index.html")

@app.route("/clear")
def clear_and_redirect():
    for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
        for f in os.listdir(folder):
            fp = os.path.join(folder, f)
            if os.path.isfile(fp):
                os.remove(fp)
    return redirect(url_for("index"))

@app.route("/download/<filename>")
def download(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)
