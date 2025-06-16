from flask import Flask, render_template, request, send_file, url_for, redirect, session
import os
import requests
import shutil
import json
import csv
import time
import re
import html
import io
import zipfile
import re
from bs4 import BeautifulSoup
from flask import session
from urllib.parse import unquote

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Required for session

DEFAULT_FOLDER = r"C:\Apps\flask_bot_manager\python_scripts\rajasthan_gyan"

def clean_old_files(folder_path):
    """Deletes all previous files and folders in the specified directory."""
    if os.path.exists(folder_path):
        # Delete all files and subdirectories
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)  # Remove file or symlink
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)  # Remove directory
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")

# Define sanitize_filename to clean file names
def sanitize_filename(filename):
    """Sanitizes file names by removing invalid characters and keeping Unicode characters."""
    sanitized = re.sub(r'[^\w\s\u0900-\u097F]', '', filename)
    sanitized = re.sub(r'\s+', '_', sanitized).strip()
    return sanitized

def download_image(image_url, folder_path):
    os.makedirs(folder_path, exist_ok=True)
    filename = os.path.basename(image_url)
    full_url = f"https://www.rajasthangyan.com/{image_url}" if not image_url.startswith("http") else image_url
    try:
        response = requests.get(full_url, timeout=10)
        response.raise_for_status()
        with open(os.path.join(folder_path, filename), 'wb') as f:
            f.write(response.content)
    except requests.exceptions.RequestException:
        return ""
    return filename

def extract_question_text(dt_tag):
    if not dt_tag:
        return ""
    strong_tag = dt_tag.find('strong')
    question_text = strong_tag.decode_contents(formatter="html") if strong_tag else dt_tag.decode_contents(formatter="html")
    question_text = re.sub(r'<br\s*/?><img[^>]*>', '', question_text)
    question_text = re.sub(r'</strong>\s*(<br\s*/?>)?', '', question_text)
    question_text = html.unescape(question_text).strip()
    return question_text

def generate_csv(data):
    max_options = max((len(item['options']) for item in data), default=4)
    option_headers = [f"Option {chr(65 + i)}" for i in range(max_options)]
    header = ["Question Number", "Passage", "Question", "Question Image", "Exam Date"] + option_headers + ["Answer", "Explanation"]

    output = io.StringIO()
    writer = csv.writer(output)
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
    return output.getvalue()

def generate_json(data):
    return json.dumps(data, ensure_ascii=False, indent=4)

def scrape_questions(base_url, total_pages, base_folder):
    all_questions = []
    for page in range(1, total_pages + 1):
        url = base_url.format(page=page)
        retries = 5
        while retries > 0:
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                break
            except requests.exceptions.RequestException:
                retries -= 1
                time.sleep(5)
        else:
            continue

        soup = BeautifulSoup(response.text, 'html.parser')
        question_containers = soup.find_all('div', class_='question-container')
        title_element = soup.find('div', style="float: left;")
        title = sanitize_filename(title_element.find('h1').get_text(strip=True)) if title_element and title_element.find('h1') else "Unknown-Title"
        folder_path = os.path.join(base_folder, "images", title)

        for container in question_containers:
            dt_tag = container.find('dt')
            passage = ""
            prev_element = container.find_previous_sibling()
            if prev_element and prev_element.name == "p":
                passage = prev_element.decode_contents()

            exam_date = ""
            if dt_tag:
                exam_date_element = dt_tag.find('span', style="float: right;font-size: 14px;color:#86a1ae;")
                if exam_date_element:
                    exam_date = exam_date_element.get_text(strip=True)
                    exam_date_element.decompose()

            image_name = ""
            if dt_tag:
                image_element = dt_tag.find('img')
                if image_element:
                    image_src = image_element.get('src')
                    if image_src:
                        image_name = download_image(image_src, folder_path)

            question_text = extract_question_text(dt_tag)
            question_number_match = re.match(r'प्रश्न\s*(\d+)', question_text)
            question_number = question_number_match.group(1) if question_number_match else ""
            question_text = re.sub(r'प्रश्न\s*\d+\s*', '', question_text).strip()

            options = []
            for li in container.find_all('li'):
                option_text = li.get_text(strip=True)
                option_text = re.sub(r'^\(\s*[A-Za-z\u0900-\u097F]\s*\)\s*', '', option_text)
                img_tag = li.find('img')
                if img_tag:
                    img_src = img_tag.get('src')
                    if img_src:
                        img_name = download_image(img_src, folder_path)
                        option_text = f"<img src=\"{img_name}\"/>"
                options.append(option_text)

            if len(options) < 4:
                options += [""] * (4 - len(options))

            answer_section = container.find('div', class_='rg-c-content')
            answer = None
            explanation = None
            if answer_section:
                strong_tags = answer_section.find_all('strong')
                if strong_tags:
                    extracted_answer = strong_tags[0].get_text(strip=True).replace('उत्तर :', '').strip()
                    answer = ""
                    for i, option in enumerate(options):
                        if extracted_answer in option:
                            answer = chr(65 + i)
                            break
                explanation_html = answer_section.decode_contents()
                explanation_html = re.sub(r'<strong>\s*उत्तर\s*:\s*', '', explanation_html)
                explanation = explanation_html.strip()

            all_questions.append({
                'question_number': question_number,
                'passage': passage,
                'question': question_text,
                'question_image': image_name,
                'exam_date': exam_date,
                'options': options,
                'answer': answer,
                'explanation': explanation
            })
    return title, all_questions

@app.route("/", methods=["GET", "POST"])
def index():
    """Handles the homepage and form submission for URL scraping."""
    
    def clear_scraped_output():
        """Deletes all files and folders inside the scraped_output directory."""
        output_folder = os.path.join(DEFAULT_FOLDER, "scraped_output")
        if os.path.exists(output_folder):
            for filename in os.listdir(output_folder):
                file_path = os.path.join(output_folder, filename)
                try:
                    if os.path.isdir(file_path):
                        shutil.rmtree(file_path)  # Remove directory
                    else:
                        os.remove(file_path)  # Remove file
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")

    if request.method == "GET":
        clear_scraped_output()
        session.pop("results", None)
        return render_template("index.html")

    if request.method == "POST":
        urls_input = request.form["urls"]
        urls = [url.strip() for url in re.split(r"[,\n]+", urls_input) if url.strip()]
        clear_scraped_output()
        os.makedirs(os.path.join(DEFAULT_FOLDER, "scraped_output"), exist_ok=True)

        results = []
        
        for last_page_url in urls:
            try:
                total_pages = int(last_page_url.split("page=")[-1])
            except ValueError:
                total_pages = 0

            base_url = last_page_url.rsplit("&page=", 1)[0] + "&page={page}"
            title, questions = scrape_questions(base_url, total_pages, DEFAULT_FOLDER)

            # Create a folder for each test title in scraped_output
            sanitized_title = sanitize_filename(title)
            output_folder = os.path.join(DEFAULT_FOLDER, "scraped_output", sanitized_title)
            os.makedirs(output_folder, exist_ok=True)

            # Create subfolders inside the URL folder
            csv_folder = os.path.join(output_folder, "csv")
            json_folder = os.path.join(output_folder, "json")
            images_folder = os.path.join(output_folder, "images")

            os.makedirs(csv_folder, exist_ok=True)
            os.makedirs(json_folder, exist_ok=True)
            os.makedirs(images_folder, exist_ok=True)

            # Save CSV and JSON in the respective folders
            csv_filename = os.path.join(csv_folder, f"{sanitized_title}.csv")
            json_filename = os.path.join(json_folder, f"{sanitized_title}.json")

            with open(csv_filename, "w", encoding="utf-8-sig") as f:
                f.write(generate_csv(questions))
            with open(json_filename, "w", encoding="utf-8") as f:
                f.write(generate_json(questions))

            results.append({
                "test_title": title,
                "csv_filename": csv_filename,
                "json_filename": json_filename,
                "zip_path": output_folder,  # Folder for individual ZIP
            })

        session["results"] = results
        return render_template("result.html", results=results, master_zip_available=True, sanitize_filename=sanitize_filename)

@app.route("/rajasthan_gyan/", methods=["GET", "POST"])
def rajasthan_gyan():
    if request.method == "POST":
        # Handle file upload or button click for /rajasthan_gyan/
        return "Test Book Uploaded Successfully!"
    return render_template("rajasthan_gyan.html")

@app.route("/download/<path:filename>")
def download(filename):
    """Handles file download and decodes the URL-encoded file name."""
    decoded_filename = unquote(filename)
    file_path = os.path.join(DEFAULT_FOLDER, decoded_filename)

    # Check if the file exists after decoding
    if not os.path.exists(file_path):
        return f"Error: The file '{decoded_filename}' was not found.", 404

    return send_file(file_path, as_attachment=True)

def create_master_zip(results):
    """Generates a master ZIP file containing all scraped data for multiple URLs."""
    master_zip_path = os.path.join(DEFAULT_FOLDER, "All_Tests.zip")

    temp_folder = os.path.join(DEFAULT_FOLDER, "temp_zip")
    if os.path.exists(temp_folder):
        shutil.rmtree(temp_folder)
    os.makedirs(temp_folder, exist_ok=True)

    # Add each test folder to temp_folder
    for result in results:
        zip_folder_path = result["zip_path"]
        if os.path.exists(zip_folder_path):
            dest_folder = os.path.join(temp_folder, sanitize_filename(result["test_title"]))
            shutil.copytree(zip_folder_path, dest_folder)

    # Create master ZIP with all folders
    shutil.make_archive(master_zip_path.replace(".zip", ""), 'zip', temp_folder)

    # Clean up temp folder after ZIP creation
    shutil.rmtree(temp_folder)

    return master_zip_path

@app.route("/download_zip/<path:zip_path>")
def download_zip(zip_path):
    """Generates and downloads a ZIP for a single scraped test."""
    decoded_zip_name = unquote(zip_path)
    sanitized_folder_name = sanitize_filename(decoded_zip_name)

    # Correct path to include scraped_output folder
    zip_folder_path = os.path.join(DEFAULT_FOLDER, "scraped_output", sanitized_folder_name)

    if not os.path.exists(zip_folder_path):
        return f"Error: The folder '{decoded_zip_name}' was not found.", 404

    # Create a ZIP if it does not exist
    zip_file_name = f"{sanitized_folder_name}.zip"
    final_zip_path = os.path.join(DEFAULT_FOLDER, "scraped_output", zip_file_name)

    if not os.path.exists(final_zip_path):
        with zipfile.ZipFile(final_zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(zip_folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, zip_folder_path)
                    zip_file.write(file_path, arcname)

    # Send the generated ZIP for download
    return send_file(final_zip_path, as_attachment=True, download_name=zip_file_name)

@app.route("/download_master_zip")
def download_master_zip():
    """Generates and downloads a master ZIP with all files."""
    results = session.get("results", [])
    if not results:
        return "No results to download.", 404

    # Create and download the master ZIP
    master_zip_path = create_master_zip(results)
    return send_file(master_zip_path, as_attachment=True, download_name="All_Tests.zip")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
