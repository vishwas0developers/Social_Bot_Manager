import os
import zipfile
import fitz
import re
import pandas as pd
from flask import Flask, render_template, request, send_file

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

answer_map = {"A1": "A", "A2": "B", "A3": "C", "A4": "D"}

def extract_mcqs_from_pdf(file_path, output_filename):
    doc = fitz.open(file_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()

    # Extract Answer Key
    answer_key_section = re.findall(r"S\.?No\.?\s+Correct Answer Key(.*?)(?:\n\n|\Z)", full_text, re.DOTALL)
    answer_key_raw = answer_key_section[0] if answer_key_section else ""
    raw_answers = re.findall(r"(\d+)\s+(A\d)", answer_key_raw)
    answer_key = {int(q): answer_map.get(opt, "") for q, opt in raw_answers} if raw_answers else {}

    # Extract questions and 2-line options
    pattern = re.findall(
        r"(?:TRADE THEORY|NUMERICAL ABILITY AND REASONING)\s+(\d+)\s+\d+\s+(.*?)"
        r"\s+A1\s*:\s*(.*?)\n\s*(.*?)\s+A2\s*:\s*(.*?)\n\s*(.*?)"
        r"\s+A3\s*:\s*(.*?)\n\s*(.*?)\s+A4\s*:\s*(.*?)\n\s*(.*?)(?:\s+1\.0|\s*$)",
        full_text, re.DOTALL
    )

    data = []
    for entry in pattern:
        q_no = int(entry[0])
        question_block = entry[1].strip()
        q_en = question_block.split("\n")[0].strip()
        q_hi = question_block.split("\n")[1].strip() if "\n" in question_block else ""

        data.append({
            "Question No.": q_no,
            "Question_EN": q_en,
            "Question_HI": q_hi,
            "Option_A_EN": entry[2].strip(), "Option_A_HI": entry[3].strip(),
            "Option_B_EN": entry[4].strip(), "Option_B_HI": entry[5].strip(),
            "Option_C_EN": entry[6].strip(), "Option_C_HI": entry[7].strip(),
            "Option_D_EN": entry[8].strip(), "Option_D_HI": entry[9].strip(),
            "Correct Answer": answer_key.get(q_no, "Not Available")
        })

    df = pd.DataFrame(data).sort_values("Question No.")
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)
    df.to_excel(output_path, index=False)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        uploaded_files = request.files.getlist("pdfs")
        zip_path = os.path.join(OUTPUT_FOLDER, "All_Extracted.zip")

        with zipfile.ZipFile(zip_path, "w") as zipf:
            for pdf in uploaded_files:
                filename = os.path.splitext(pdf.filename)[0]
                pdf_path = os.path.join(UPLOAD_FOLDER, pdf.filename)
                pdf.save(pdf_path)

                excel_filename = filename + "_MCQ_EN_HI.xlsx"
                extract_mcqs_from_pdf(pdf_path, excel_filename)

                zipf.write(os.path.join(OUTPUT_FOLDER, excel_filename), excel_filename)

        return send_file(zip_path, as_attachment=True)

    return render_template("index.html")
