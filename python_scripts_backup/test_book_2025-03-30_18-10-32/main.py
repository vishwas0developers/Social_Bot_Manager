from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
import os
import re
import html
import io
import json
import csv
import requests
import uuid
from bs4 import BeautifulSoup
import zipfile

app = Flask(__name__)
app.secret_key = "super_secret_key"

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Helper Functions ---
def sanitize_filename(filename):
    """Replaces unsupported characters in filenames with a space, preserving Hindi and alphanumeric characters."""
    import re
    sanitized = re.sub(r"[^\w\s\u0900-\u097F]", " ", filename)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized

def download_image(image_url, folder_path):
    """Downloads an image from image_url and saves it in folder_path."""
    os.makedirs(folder_path, exist_ok=True)
    if image_url.startswith("//"):
        image_url = "https:" + image_url
    filename = os.path.basename(image_url)
    file_path = os.path.join(folder_path, filename)

    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        with open(file_path, "wb") as f:
            f.write(response.content)
        return filename
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Error downloading image {image_url}: {e}")
        return None

def generate_csv(data):
    """Generates CSV content from the scraped data."""
    max_options = max((len(item.get("options", [])) for item in data), default=4)
    option_headers = [f"Option {chr(65 + i)}" for i in range(max_options)]
    header = ["Question Number", "Section", "Question"] + option_headers + [
        "Answer",
        "Explanation",
        "Image",
    ]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    for item in data:
        opts = item.get("options", [])
        if len(opts) < max_options:
            opts += [""] * (max_options - len(opts))
        writer.writerow(
            [
                item.get("question_number", ""),
                item.get("section", ""),
                item.get("question", ""),
            ]
            + opts
            + [
                item.get("answer", ""),
                item.get("explanation", ""),
                item.get("image", ""),
            ]
        )
    return output.getvalue()

def generate_json(data):
    """Generates JSON content from the scraped data."""
    return json.dumps(data, ensure_ascii=False, indent=4)

def scrape_test(api_url, language):
    """Fetches test data from the Testbook API."""
    response = requests.get(api_url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch test data. Status code: {response.status_code}")
    json_data = response.json()
    if not json_data.get("success"):
        raise Exception("Test API response unsuccessful.")
    data = json_data.get("data", {})
    test_title = data.get("title", "test")
    questions_data = []
    question_number = 1
    sections = data.get("sections", [])
    for section in sections:
        section_title = section.get("title", "")
        questions = section.get("questions", [])
        for q in questions:
            lang_data = q.get("hn", {}) if language == "Hindi" else q.get("en", {})
            if not lang_data.get("value", "").strip():
                lang_data = q.get("en", {})
            q_text = html.unescape(lang_data.get("value", ""))
            options = [opt.get("value", "") for opt in lang_data.get("options", [])]
            questions_data.append(
                {
                    "question_number": question_number,
                    "qid": q.get("_id", ""),
                    "section": section_title,
                    "question": q_text,
                    "options": options,
                    "answer": "",
                    "explanation": "",
                    "image": "",
                }
            )
            question_number += 1
    return test_title, questions_data

def scrape_answers(api_url, language):
    """Fetches answer data from the Testbook API."""
    response = requests.get(api_url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch answers data. Status code: {response.status_code}")
    json_data = response.json()
    if not json_data.get("success"):
        raise Exception("Answers API response unsuccessful.")
    answers_data = json_data.get("data", {})
    lang_map = {"English": "en", "Hindi": "hn"}
    lang_key = lang_map.get(language, language.lower())
    answers_mapping = {}
    for qid, details in answers_data.items():
        answer = details.get("correctOption", "")
        sol = details.get("sol", {}).get(lang_key, {}).get("value", "")
        answers_mapping[qid] = {"answer": answer, "explanation": sol}
    return answers_mapping

def create_zip_from_folder(folder_path):
    """Creates a ZIP archive and returns the file path."""
    zip_filename = f"{sanitize_filename(os.path.basename(folder_path))}_{uuid.uuid4().hex}.zip"
    zip_path = os.path.join(UPLOAD_FOLDER, zip_filename)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=folder_path)
                zf.write(file_path, arcname=arcname)
    return zip_path

def create_master_zip(results):
    """Creates a master ZIP archive containing all test results."""
    master_zip_filename = f"all_tests_{uuid.uuid4().hex}.zip"
    master_zip_path = os.path.join(UPLOAD_FOLDER, master_zip_filename)

    # ✅ Debugging: Check ZIP path before writing
    print(f"Creating Master ZIP at: {master_zip_path}")

    # Check if results are empty
    if not results:
        print("⚠️ No results to zip.")
        return None

    # Create the ZIP archive
    with zipfile.ZipFile(master_zip_path, "w", zipfile.ZIP_DEFLATED) as mzip:
        for res in results:
            test_folder = sanitize_filename(res["test_title"])
            test_folder_path = os.path.join(UPLOAD_FOLDER, test_folder)

            # Add CSV file
            if os.path.exists(res["csv_filename"]):
                csv_filename = os.path.basename(res["csv_filename"])
                mzip.write(res["csv_filename"], arcname=os.path.join(test_folder, csv_filename))
                print(f"✅ Added: {csv_filename} to Master ZIP")

            # Add JSON file
            if os.path.exists(res["json_filename"]):
                json_filename = os.path.basename(res["json_filename"])
                mzip.write(res["json_filename"], arcname=os.path.join(test_folder, json_filename))
                print(f"✅ Added: {json_filename} to Master ZIP")

            # Add Image ZIP if available and not empty
            if res["zip_path"] and os.path.exists(res["zip_path"]):
                zip_filename = os.path.basename(res["zip_path"])
                mzip.write(res["zip_path"], arcname=os.path.join(test_folder, zip_filename))
                print(f"✅ Added: {zip_filename} to Master ZIP")

    # ✅ Check if the master ZIP file was created
    if os.path.exists(master_zip_path):
        print("✅ Master ZIP Created Successfully!")
        return master_zip_path
    else:
        print("❌ Master ZIP Creation Failed!")
        return None

def cleanup_downloads():
    """Deletes all files and folders inside the 'downloads' folder."""
    if os.path.exists(UPLOAD_FOLDER):
        for root, dirs, files in os.walk(UPLOAD_FOLDER, topdown=False):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"⚠️ Error deleting file {file_path}: {e}")

        print("✅ All old scraped files deleted.")
    else:
        print("⚠️ No downloads folder found. Skipping cleanup.")

@app.route("/", methods=["GET", "POST"])
def index():
    """Main page for input and data scraping."""
    # Cleanup old files before starting a new scrape
    cleanup_downloads()

    if request.method == "POST":
        urls_input = request.form["urls"]
        language = request.form["language"]
        urls = [url.strip() for url in re.split(r"[,\n]+", urls_input) if url.strip()]

        if not urls:
            flash("Please enter at least one URL.", "error")
            return redirect(url_for("index"))

        # ✅ Correct auth_code added here
        auth_code = (
            "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJpc3MiOiJodHRwczovL3Rlc3Rib29rLmNvbSIsInN1YiI6IjYzYjgzZTI3OGVkNGFhNTc3ZjUxOTNjNiIsImF1ZCI6IlRCIiwiZXhwIjoiMjAyNS0wNC0yMVQwNTozMDowOC45NTAyOTIyMDVaIiwiaWF0IjoiMjAyNS0wMy0yMlQwNTozMDowOC45NTAyOTIyMDVaIiwibmFtZSI6IkthbWxlc2ggamkgU2lyIiwiZW1haWwiOiJrZGhha2FyLmRoYWthckBnbWFpbC5jb20iLCJvcmdJZCI6IiIsImlzTE1TVXNlciI6ZmFsc2UsInJvbGVzIjoic3R1ZGVudCJ9."
            "H-hjIx2CNsi0Her5c0D3UvKpX5hJhyWAj4Cvjx_unYJTn54WalnMrjXtZVL0OwRQJ0NcV9Maj57uh90gzdcocs0QkCROGuuWii9jysOVw3F4Ci_SDKgJX9wk9-G9mQQtONggAVKjf7Z_5U1tVoPUnVbvkZXXp9A5BWNZeE82Ka8"
        )

        X_Tb_Client = "web,1.2"
        attempt_no = "1"

        results = []
        for url in urls:
            match = re.search(r"/tests/([^?]+)", url)
            if not match:
                continue
            test_id = match.group(1).rstrip("/")
            test_api_url = (
                f"https://api.testbook.com/api/v2/tests/{test_id}"
                f"?auth_code={auth_code}&X-Tb-Client={X_Tb_Client}&language={language}&attemptNo={attempt_no}"
            )
            answers_api_url = (
                f"https://api.testbook.com/api/v2/tests/{test_id}/answers"
                f"?auth_code={auth_code}&X-Tb-Client={X_Tb_Client}&language={language}&attemptNo={attempt_no}"
            )

            try:
                test_title, questions_data = scrape_test(test_api_url, language)
                answers_mapping = scrape_answers(answers_api_url, language)

                for q in questions_data:
                    qid = q.get("qid")
                    if qid and qid in answers_mapping:
                        q["answer"] = answers_mapping[qid].get("answer", "")
                        q["explanation"] = answers_mapping[qid].get("explanation", "")

                folder_name = os.path.join(UPLOAD_FOLDER, sanitize_filename(test_title))
                os.makedirs(folder_name, exist_ok=True)

                csv_filename = os.path.join(folder_name, sanitize_filename(test_title) + ".csv")
                json_filename = os.path.join(folder_name, sanitize_filename(test_title) + ".json")

                csv_content = generate_csv(questions_data)
                json_content = generate_json(questions_data)

                with open(csv_filename, "w", encoding="utf-8", newline="") as f:
                    f.write(csv_content)
                with open(json_filename, "w", encoding="utf-8") as f:
                    f.write(json_content)

                # --- Handle Image Downloads ---
                image_folder = os.path.join(folder_name, "images")
                image_found = False

                # Download images in questions and options
                for q in questions_data:
                    # Download images in questions
                    soup = BeautifulSoup(q["question"], "html.parser")
                    img_tags = soup.find_all("img")
                    for img_tag in img_tags:
                        img_url = img_tag.get("src", "")
                        if img_url:
                            local_img = download_image(img_url, image_folder)
                            if local_img:
                                image_found = True
                                q["image"] = os.path.join("images", local_img)

                    # Download images in options
                    updated_options = []
                    for opt in q["options"]:
                        opt_soup = BeautifulSoup(opt, "html.parser")
                        opt_img_tags = opt_soup.find_all("img")
                        for opt_img in opt_img_tags:
                            opt_img_url = opt_img.get("src", "")
                            if opt_img_url:
                                local_opt_img = download_image(opt_img_url, image_folder)
                                if local_opt_img:
                                    image_found = True
                                    opt_img["src"] = os.path.join("images", local_opt_img)
                        updated_options.append(str(opt_soup))
                    q["options"] = updated_options

                # Create image ZIP only if images exist
                images_zip_path = None
                if image_found and os.path.exists(image_folder) and any(os.listdir(image_folder)):
                    images_zip_path = create_zip_from_folder(image_folder)

                results.append(
                    {
                        "test_title": test_title,
                        "csv_filename": csv_filename,
                        "json_filename": json_filename,
                        "zip_path": images_zip_path,
                    }
                )
            except Exception as e:
                flash(f"Error processing URL {url}: {e}", "error")
                continue

        session["results"] = results
        return redirect(url_for("results"))
    return render_template("index.html")

@app.route("/test_book/", methods=["GET", "POST"])
def test_book():
    if request.method == "POST":
        # Handle file upload or button click for /test_book/
        return "Test Book Uploaded Successfully!"
    return render_template("test_book.html")

@app.route("/results")
def results():
    """Displays results and download options."""
    results = session.get("results", [])
    for res in results:
        res["image_available"] = res["zip_path"] is not None and os.path.exists(res["zip_path"])
    master_zip_available = bool(results)
    return render_template("result.html", results=results, master_zip_available=master_zip_available)

@app.route("/download/<path:filename>")
def download(filename):
    """Serves files from the downloads directory."""
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return "File not found", 404

@app.route("/download_zip/<path:zip_path>")
def download_zip(zip_path):
    """Serves the generated ZIP file."""
    if os.path.exists(zip_path):
        return send_file(zip_path, as_attachment=True)
    else:
        return "ZIP file not found", 404

@app.route("/download_master_zip")
def download_master_zip():
    """Generates and downloads a master ZIP with all files."""
    results = session.get("results", [])

    # ✅ Debugging: Check if results exist
    print(f"Results Data: {results}")

    if not results:
        return "❌ No results to download.", 404

    master_zip_path = create_master_zip(results)

    # ✅ Debugging: Check if ZIP path is generated correctly
    print(f"Master ZIP Path: {master_zip_path}")

    # ✅ Check if the file exists before sending
    if master_zip_path and os.path.exists(master_zip_path):
        return send_file(master_zip_path, as_attachment=True, download_name="All_Tests.zip")
    else:
        return "❌ Error: Master ZIP file was not generated or not found.", 404

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
