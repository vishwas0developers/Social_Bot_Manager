from flask import Flask, render_template, request, send_file, session, jsonify
import os
import requests
from bs4 import BeautifulSoup
import json
import csv
import time
import re
import html
import io
import zipfile
from urllib.parse import unquote
from werkzeug.utils import safe_join

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session handling

# --- Corrected Path Configuration ---
BASE_PATH = r"C:\Apps\flask_bot_manager\python_scripts"
DEFAULT_FOLDER = os.path.join(BASE_PATH, "rajasthan_gyan", "scraped_output")
UPLOAD_FOLDER = os.path.join(BASE_PATH, "rajasthan_gyan", "downloads")

# Ensure directories exist
os.makedirs(DEFAULT_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Helper Functions ---
def sanitize_filename(filename):
    """Sanitize file name by removing unwanted characters."""
    sanitized = re.sub(r'[^\w\s\u0900-\u097F]', '_', filename)  # Hindi characters allowed
    sanitized = re.sub(r'\s+', '_', sanitized).strip()
    return sanitized


def download_image(image_url, folder_path):
    """Download and save image from URL."""
    os.makedirs(folder_path, exist_ok=True)
    filename = os.path.basename(image_url)
    full_url = f"https://www.rajasthangyan.com/{image_url}" if not image_url.startswith("http") else image_url
    try:
        response = requests.get(full_url, timeout=10)
        response.raise_for_status()
        with open(os.path.join(folder_path, filename), 'wb') as f:
            f.write(response.content)
    except requests.exceptions.RequestException as e:
        print(f"Error downloading image {full_url}: {e}")
    return filename


def generate_csv(data, title):
    """Generate CSV file from scraped data."""
    max_options = max((len(item['options']) for item in data), default=4)
    option_headers = [f"Option {chr(65 + i)}" for i in range(max_options)]
    header = [
        "Question Number",
        "Passage",
        "Question",
        "Question Image",
        "Exam Date"
    ] + option_headers + ["Answer", "Explanation"]

    file_name = f"{sanitize_filename(title)}.csv"
    file_path = os.path.join(DEFAULT_FOLDER, file_name)
    with open(file_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for item in data:
            options = item['options'][:]
            if len(options) < max_options:
                options += [""] * (max_options - len(options))
            writer.writerow([
                item['question_number'],
                item.get('passage', ''),
                item['question'],
                item.get('question_image', ''),
                item.get('exam_date', '')
            ] + options + [item.get('answer', ''), item.get('explanation', '')])
    return file_path


def generate_json(data, title):
    """Generate JSON file from scraped data."""
    file_name = f"{sanitize_filename(title)}.json"
    file_path = os.path.join(DEFAULT_FOLDER, file_name)
    with open(file_path, 'w', encoding="utf-8") as json_file:
        json.dump(data, json_file, ensure_ascii=False, indent=4)
    return file_path


def create_master_zip(results):
    """Create a master ZIP containing all tests."""
    master_zip_path = os.path.join(DEFAULT_FOLDER, "All_Tests.zip")
    with zipfile.ZipFile(master_zip_path, 'w', zipfile.ZIP_DEFLATED) as master_zip:
        for title, questions in results.items():
            json_path = generate_json(questions, title)
            csv_path = generate_csv(questions, title)
            master_zip.write(json_path, os.path.basename(json_path))
            master_zip.write(csv_path, os.path.basename(csv_path))
    return master_zip_path


def scrape_questions(base_url, total_pages, base_folder):
    """Scrape questions from the target website."""
    all_questions = []
    for page in range(1, total_pages + 1):
        url = base_url.format(page=page)
        retries = 5
        while retries > 0:
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                retries -= 1
                time.sleep(5)
        else:
            continue

        soup = BeautifulSoup(response.text, 'html.parser')
        question_containers = soup.find_all('div', class_='question-container')
        title_element = soup.find('div', style="float: left;")
        title = "Unknown-Title"
        if title_element and title_element.find('h1'):
            title = title_element.find('h1').get_text(strip=True)
        title = sanitize_filename(title)
        folder_path = os.path.join(DEFAULT_FOLDER, "images", title)
        os.makedirs(folder_path, exist_ok=True)

        for container in question_containers:
            dt_tag = container.find('dt')
            passage = ""
            prev_element = container.find_previous_sibling()
            if prev_element and prev_element.name == "p":
                passage = prev_element.decode_contents()

            image_name = ""
            if dt_tag:
                image_element = dt_tag.find('img')
                if image_element:
                    image_src = image_element.get('src')
                    if image_src:
                        image_name = download_image(image_src, folder_path)

            question_text = dt_tag.get_text(strip=True) if dt_tag else ""
            options = [li.get_text(strip=True) for li in container.find_all('li')]

            all_questions.append({
                'question_number': len(all_questions) + 1,
                'passage': passage,
                'question': question_text,
                'question_image': image_name,
                'exam_date': "",
                'options': options,
                'answer': "",
                'explanation': ""
            })
    
    # Save JSON and CSV after scraping
    generate_json(all_questions, title)
    generate_csv(all_questions, title)
    return title, all_questions


@app.route('/', methods=['GET', 'POST'])
def index():
    """Home page for scraping input."""
    if request.method == 'POST':
        urls_input = request.form['urls'].strip()
        if not urls_input:
            return render_template('index.html', error="Please enter at least one URL.")

        urls = [u.strip() for u in urls_input.split(',') if u.strip()]
        results = {}

        for last_page_url in urls:
            base_url = last_page_url.rsplit("&page=", 1)[0] + "&page={page}"
            try:
                total_pages = int(last_page_url.split("page=")[-1])
            except ValueError:
                total_pages = 0

            title, questions = scrape_questions(base_url, total_pages, DEFAULT_FOLDER)
            results[title] = questions

        session['results'] = results
        return render_template('results.html', success="Scraping completed!", results=results)

    return render_template('index.html')

@app.route('/results')
def results():
    """Displays results and download options."""
    results = session.get("results", [])
    master_zip_available = bool(results)
    return render_template("results.html", results=results, master_zip_available=master_zip_available)

@app.route('/rajasthan_gyan/', methods=['GET', 'POST'])
def rajasthan_gyan():
    """Displays results and download options."""
    results = session.get("results", {})
    master_zip_available = bool(results)
    return render_template("results.html", results=results, master_zip_available=master_zip_available)


@app.route('/download/<path:filename>')
def download(filename):
    """Serves files from the correct directory."""
    # Decode the filename to handle special characters properly
    decoded_filename = unquote(filename)

    # Safely join the path to prevent directory traversal attacks
    file_path = safe_join(DEFAULT_FOLDER, decoded_filename)

    # Debugging to check if the correct file path is being checked
    print(f"Trying to download file: {file_path}")

    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "File not found", 404

@app.route('/download_master_zip')
def download_master_zip():
    """Generates and downloads a master ZIP with all files."""
    results = session.get("results", [])
    if not results:
        return "No results to download.", 404

    master_zip_path = create_master_zip(results)

    if master_zip_path and os.path.exists(master_zip_path):
        return send_file(master_zip_path, as_attachment=True, download_name="All_Tests.zip")
    else:
        return "Error: Master ZIP file was not generated or not found.", 404

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
