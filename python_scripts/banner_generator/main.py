import os
import re
import json
import uuid
import zipfile
import shutil
from pathlib import Path
import time
import platform
import traceback

import pandas as pd # Pandas पहले से इम्पोर्टेड है
from flask import (
    Flask, request, render_template, send_file,
    flash, redirect, url_for, abort
)
from werkzeug.utils import secure_filename
from playwright.sync_api import sync_playwright, Error as PlaywrightError

# --- Configuration ---
script_dir = Path(__file__).parent.resolve()
UPLOAD_FOLDER = script_dir / 'uploads'
CONFIG_FOLDER = script_dir / 'configs'
GENERATED_FOLDER = script_dir / 'generated_files'
STATIC_FOLDER = script_dir / 'static'
PREVIEW_FOLDER = STATIC_FOLDER / 'previews'
SAMPLE_FOLDER = script_dir / 'samples' # <<< नया सैंपल फ़ोल्डर

ALLOWED_EXTENSIONS_HTML = {'html'}
ALLOWED_EXTENSIONS_EXCEL = {'xlsx'}

app = Flask(__name__, static_folder=str(STATIC_FOLDER))
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'playwright_is_working_now_finally_v5') # संस्करण बदला

# Ensure necessary folders exist
UPLOAD_FOLDER.mkdir(exist_ok=True)
CONFIG_FOLDER.mkdir(exist_ok=True)
GENERATED_FOLDER.mkdir(exist_ok=True)
STATIC_FOLDER.mkdir(exist_ok=True)
PREVIEW_FOLDER.mkdir(exist_ok=True)
SAMPLE_FOLDER.mkdir(exist_ok=True) # <<< सैंपल फ़ोल्डर बनाएं

# --- Helper Functions ---

def allowed_file(filename, allowed_extensions):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def extract_placeholders(html_content):
    placeholders = re.findall(r'\{\{(.*?)\}\}', html_content)
    unique_placeholders = sorted(list(set(placeholders)), key=placeholders.index)
    return unique_placeholders

def cleanup_generated_files(target_folder: Path):
    # ... (यह फ़ंक्शन अपरिवर्तित है) ...
    print(f"[INFO] Starting cleanup of folder: {target_folder}")
    if not target_folder.exists():
        print(f"[INFO] Folder {target_folder} does not exist. No cleanup needed.")
        return
    if not target_folder.is_dir():
         print(f"[ERROR] Target path {target_folder} is not a directory. Aborting cleanup.")
         return
    errors = []
    for item in target_folder.glob('*'):
        try:
            if item.is_file(): item.unlink()
            elif item.is_dir(): shutil.rmtree(item)
        except OSError as e:
            print(f"[ERROR] Failed to delete {item}: {e}")
            errors.append(item.name)
        except Exception as e:
             print(f"[ERROR] Unexpected error deleting {item}: {e}")
             errors.append(item.name)
    if not errors: print(f"[INFO] Successfully cleaned folder: {target_folder}")
    else: print(f"[WARN] Cleanup of {target_folder} finished with {len(errors)} errors. Failed items: {', '.join(errors)}")


# --- NEW SAMPLE EXCEL FUNCTION ---
def generate_sample_excel(placeholders: list, sample_filepath: Path):
    """Generates an empty Excel file with given placeholders as headers."""
    print(f"[INFO] Generating sample Excel: {sample_filepath.name}")
    try:
        # Ensure parent directory exists (should exist due to startup check, but good practice)
        sample_filepath.parent.mkdir(parents=True, exist_ok=True)
        # Create DataFrame with only headers
        df = pd.DataFrame(columns=placeholders)
        # Save to Excel, requires 'openpyxl' usually installed with pandas
        df.to_excel(sample_filepath, index=False)
        print(f"[SUCCESS] Sample Excel generated: {sample_filepath}")
        return True
    except ImportError:
        print("[ERROR] 'openpyxl' required for Excel writing. Please install it (`pip install openpyxl`)")
        flash("Failed to generate sample Excel: Missing 'openpyxl' library.", "error")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to generate sample Excel {sample_filepath.name}: {e}")
        print(traceback.format_exc())
        # Optionally flash a message, but maybe not critical to stop upload/edit
        # flash(f"Warning: Could not generate sample Excel file: {e}", "warning")
        return False
# --- END NEW SAMPLE EXCEL FUNCTION ---


def generate_preview_image_playwright(template_id, template_html_string, placeholders):
    # ... (यह फ़ंक्शन अपरिवर्तित है) ...
    preview_filename = f"{template_id}.png"
    preview_filepath = PREVIEW_FOLDER / preview_filename
    dummy_data = {p: f'[{p}]' for p in placeholders}
    preview_html = template_html_string
    page = None; browser = None; p_context = None; preview_success = False
    try:
        for placeholder, value in dummy_data.items():
            preview_html = preview_html.replace(f'{{{{{placeholder}}}}}', value)
        p_context = sync_playwright().start()
        browser = p_context.chromium.launch()
        page = browser.new_page()
        page.set_content(preview_html)
        PREVIEW_WIDTH = 1100
        page.set_viewport_size({"width": PREVIEW_WIDTH, "height": 600})
        time.sleep(0.3)
        page.screenshot(path=preview_filepath, type='png', full_page=True)
        preview_success = True
        return True
    except PlaywrightError as pe:
         print(f"[ERROR] Playwright Error during preview generation for {template_id}: {pe}")
         if "Executable doesn't exist" in str(pe):
             print("[FATAL] Playwright browsers not installed. Run 'playwright install'")
             flash("Playwright setup incomplete. Please run 'playwright install' in terminal.", "error")
         return False
    except Exception as e:
        print(f"[ERROR] General Error during preview generation for {template_id}: {e}")
        print(traceback.format_exc()); return False
    finally:
        if page:
            try: page.close()
            except Exception as e: print(f"[WARN] Error closing page: {e}")
        if browser:
            try: browser.close()
            except Exception as e: print(f"[WARN] Error closing browser: {e}")
        if p_context:
            try: p_context.stop()
            except Exception as e: print(f"[WARN] Error stopping playwright context: {e}")
        if not preview_success and preview_filepath and preview_filepath.exists():
            try: preview_filepath.unlink()
            except OSError as e: print(f"[WARN] Could not delete failed preview file {preview_filepath}: {e}")


def get_template_details():
    # ... (यह फ़ंक्शन अपरिवर्तित है) ...
    templates = []
    for config_file in CONFIG_FOLDER.glob('*.json'):
        template_id = config_file.stem
        try:
            with open(config_file, 'r', encoding='utf-8') as f: config_data = json.load(f)
            preview_filename = f"{template_id}.png"
            preview_filepath = PREVIEW_FOLDER / preview_filename
            preview_url = None
            if preview_filepath.exists() and preview_filepath.stat().st_size > 0:
                 preview_url = url_for('static', filename=f'previews/{preview_filename}', t=int(preview_filepath.stat().st_mtime))
            templates.append({
                'id': template_id,
                'name': config_data.get('template_name', template_id + ".html"),
                'placeholders': config_data.get('placeholders', []),
                'preview_url': preview_url
            })
        except Exception as e: print(f"[ERROR] Error reading config file {config_file}: {e}")
    templates.sort(key=lambda x: x['name'])
    return templates


# --- Flask Routes ---

@app.route('/')
def index():
    available_templates = get_template_details()
    return render_template('index.html', templates=available_templates)

@app.route('/upload_template', methods=['POST'])
def upload_template():
    if 'template_file' not in request.files: flash('No file part found.', 'error'); return redirect(url_for('index'))
    file = request.files['template_file']
    if file.filename == '': flash('No file selected.', 'error'); return redirect(url_for('index'))

    if file and allowed_file(file.filename, ALLOWED_EXTENSIONS_HTML):
        original_filename = secure_filename(file.filename)
        template_id = Path(original_filename).stem or f"template_{uuid.uuid4().hex[:8]}"

        html_filepath = UPLOAD_FOLDER / (template_id + ".html")
        json_filepath = CONFIG_FOLDER / (template_id + ".json")
        preview_filepath = PREVIEW_FOLDER / (template_id + ".png")
        sample_filepath = SAMPLE_FOLDER / (template_id + "_sample.xlsx") # <<< सैंपल फ़ाइल पाथ

        if html_filepath.exists() or json_filepath.exists():
             flash(f"Template ID '{template_id}' (from '{original_filename}') already exists.", 'error')
             return redirect(url_for('index'))

        html_content, preview_success = None, False
        sample_success = False # <<< ट्रैक सैंपल जनरेशन
        try:
            html_content = file.read().decode('utf-8')
            with open(html_filepath, 'w', encoding='utf-8') as f: f.write(html_content)
            placeholders = extract_placeholders(html_content)
            config_data = {'template_name': original_filename, 'placeholders': placeholders}
            with open(json_filepath, 'w', encoding='utf-8') as f: json.dump(config_data, f, indent=4)

            # <<< Generate Sample Excel >>>
            sample_success = generate_sample_excel(placeholders, sample_filepath)

            preview_success = generate_preview_image_playwright(template_id, html_content, placeholders)

            # <<< अपडेटेड फ़्लैश संदेश >>>
            if preview_success and sample_success:
                flash(f"Template '{original_filename}' uploaded successfully (with sample)!", 'success')
            elif preview_success:
                 flash(f"Template '{original_filename}' uploaded, but sample Excel generation failed.", 'warning')
            elif sample_success:
                 flash(f"Template '{original_filename}' uploaded (with sample), but preview generation failed.", 'warning')
            else:
                 flash(f"Template '{original_filename}' uploaded, but both preview and sample generation failed.", 'warning')

        except Exception as e:
            print(f"[ERROR] Upload failed for {original_filename}: {e}"); print(traceback.format_exc()); flash(f'Error processing template: {e}', 'error')
            # <<< Cleanup में सैंपल फ़ाइल जोड़ें >>>
            if html_filepath.exists(): html_filepath.unlink(missing_ok=True)
            if json_filepath.exists(): json_filepath.unlink(missing_ok=True)
            if preview_filepath.exists(): preview_filepath.unlink(missing_ok=True)
            if sample_filepath.exists(): sample_filepath.unlink(missing_ok=True) # <<< सैंपल हटाएं अगर त्रुटि हो
        return redirect(url_for('index'))
    else: flash('Invalid file type. Please upload an HTML file.', 'error'); return redirect(url_for('index'))


@app.route('/edit_template/<template_id>', methods=['POST'])
def edit_template(template_id):
    safe_template_id = re.sub(r'[^a-zA-Z0-9_.-]', '', template_id)
    if not safe_template_id or safe_template_id != template_id:
        flash("Invalid characters in template ID.", 'error'); return redirect(url_for('index'))

    if 'new_template_file' not in request.files: flash('No file part found.', 'error'); return redirect(url_for('index'))
    file = request.files['new_template_file']
    if file.filename == '': flash('No file selected for replacement.', 'error'); return redirect(url_for('index'))
    if not allowed_file(file.filename, ALLOWED_EXTENSIONS_HTML): flash('Invalid file type (HTML required).', 'error'); return redirect(url_for('index'))

    html_filepath = UPLOAD_FOLDER / (safe_template_id + ".html")
    json_filepath = CONFIG_FOLDER / (safe_template_id + ".json")
    preview_filepath = PREVIEW_FOLDER / (safe_template_id + ".png")
    sample_filepath = SAMPLE_FOLDER / (safe_template_id + "_sample.xlsx") # <<< सैंपल फ़ाइल पाथ

    if not html_filepath.exists() or not json_filepath.exists():
        flash(f"Original template '{safe_template_id}' not found. Cannot edit.", 'error'); return redirect(url_for('index'))

    new_html_content, original_template_name = None, "Unknown"
    preview_success = False
    sample_success = False # <<< ट्रैक सैंपल जनरेशन
    try:
        new_html_content = file.read().decode('utf-8')
        with open(html_filepath, 'w', encoding='utf-8') as f: f.write(new_html_content)
        new_placeholders = extract_placeholders(new_html_content)
        with open(json_filepath, 'r', encoding='utf-8') as f: config_data = json.load(f); original_template_name = config_data.get("template_name", html_filepath.name)
        config_data['placeholders'] = new_placeholders
        with open(json_filepath, 'w', encoding='utf-8') as f: json.dump(config_data, f, indent=4)

        # <<< Re-generate Sample Excel >>>
        sample_success = generate_sample_excel(new_placeholders, sample_filepath)

        preview_success = generate_preview_image_playwright(safe_template_id, new_html_content, new_placeholders)

        # <<< अपडेटेड फ़्लैश संदेश >>>
        if preview_success and sample_success:
            flash(f"Template '{original_template_name}' updated successfully (with sample)!", 'success')
        elif preview_success:
            flash(f"Template '{original_template_name}' HTML updated, but sample Excel re-generation failed.", 'warning')
        elif sample_success:
            flash(f"Template '{original_template_name}' HTML updated (with sample), but preview re-generation failed.", 'warning')
        else:
            flash(f"Template '{original_template_name}' HTML updated, but both preview and sample re-generation failed.", 'warning')

    except Exception as e:
        print(f"[ERROR] Error during template edit process for {safe_template_id}: {e}"); print(traceback.format_exc()); flash(f"An error occurred while updating template: {e}", 'error')
    return redirect(url_for('index'))


@app.route('/delete_template/<template_id>', methods=['POST'])
def delete_template(template_id):
    safe_template_id = re.sub(r'[^a-zA-Z0-9_.-]', '', template_id)
    if not safe_template_id or safe_template_id != template_id: flash("Invalid template ID.", 'error'); return redirect(url_for('index'))

    html_filepath = UPLOAD_FOLDER / (safe_template_id + ".html")
    json_filepath = CONFIG_FOLDER / (safe_template_id + ".json")
    preview_filepath = PREVIEW_FOLDER / (safe_template_id + ".png")
    sample_filepath = SAMPLE_FOLDER / (safe_template_id + "_sample.xlsx") # <<< सैंपल फ़ाइल पाथ

    deleted_files_count, errors = 0, []
    def safe_delete(filepath):
        nonlocal deleted_files_count; success = False
        try:
            if filepath.exists(): filepath.unlink(); success = True
            else: pass
        except OSError as e: errors.append(f"{filepath.name}: {e}"); print(f"[ERROR] OS Error deleting {filepath}: {e}")
        if success: deleted_files_count += 1

    # <<< सभी संबंधित फ़ाइलों को हटाएं >>>
    safe_delete(html_filepath); safe_delete(json_filepath); safe_delete(preview_filepath); safe_delete(sample_filepath)

    if errors: flash(f"Errors deleting files for '{safe_template_id}': {'; '.join(errors)}", 'error')
    elif deleted_files_count > 0: flash(f"Template '{safe_template_id}' and associated files deleted.", 'success')
    else: flash(f"Template '{safe_template_id}' not found (or already deleted).", 'warning')
    return redirect(url_for('index'))


# --- NEW DOWNLOAD SAMPLE ROUTE ---
@app.route('/download_sample/<template_id>')
def download_sample(template_id):
    """Provides the sample Excel file for download."""
    safe_template_id = re.sub(r'[^a-zA-Z0-9_.-]', '', template_id)
    if not safe_template_id or safe_template_id != template_id:
        flash("Invalid template ID.", 'error'); return redirect(url_for('index'))

    sample_filepath = SAMPLE_FOLDER / (safe_template_id + "_sample.xlsx")
    print(f"[INFO] Request to download sample: {sample_filepath}")

    if sample_filepath.exists() and sample_filepath.is_file():
        try:
            # Try to get original name for better download filename
            json_filepath = CONFIG_FOLDER / (safe_template_id + ".json")
            download_display_name = f"{safe_template_id}_sample.xlsx" # Default
            if json_filepath.exists():
                 with open(json_filepath, 'r', encoding='utf-8') as f: config_data = json.load(f)
                 original_template_name = Path(config_data.get('template_name', f"{safe_template_id}.html")).stem
                 download_display_name = f"{original_template_name}_sample.xlsx"

            return send_file(
                sample_filepath,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=download_display_name
            )
        except Exception as e:
             print(f"[ERROR] Error sending sample file {sample_filepath}: {e}")
             flash("Error sending sample file.", "error")
             return redirect(url_for('index'))
    else:
        print(f"[WARN] Sample file not found: {sample_filepath}")
        flash(f"Sample Excel file for '{safe_template_id}' not found.", 'error')
        abort(404) # या index पर redirect करें: return redirect(url_for('index'))
# --- END NEW DOWNLOAD SAMPLE ROUTE ---


@app.route('/generate/<template_id>', methods=['POST'])
def generate_images(template_id):
    # ... (यह फ़ंक्शन अपरिवर्तित है, केवल टेम्प्लेट ID सैनिटाइजेशन सुनिश्चित करें) ...
    print(f"[INFO] POST /generate/{template_id} (Playwright - Element Screenshot)")
    start_time = time.time()
    if 'excel_file' not in request.files: flash('No Excel file.', 'error'); return redirect(url_for('index'))
    excel_file = request.files['excel_file']
    if excel_file.filename == '': flash('No Excel selected.', 'error'); return redirect(url_for('index'))
    if not allowed_file(excel_file.filename, ALLOWED_EXTENSIONS_EXCEL): flash('Invalid Excel type.', 'error'); return redirect(url_for('index'))
    safe_template_id = re.sub(r'[^a-zA-Z0-9_.-]', '', template_id)
    html_filepath = UPLOAD_FOLDER / (safe_template_id + ".html")
    json_filepath = CONFIG_FOLDER / (safe_template_id + ".json")
    if not html_filepath.exists() or not json_filepath.exists(): flash(f"Template '{safe_template_id}' not found.", 'error'); return redirect(url_for('index'))
    try:
        with open(html_filepath, 'r', encoding='utf-8') as f: template_html_string = f.read()
        with open(json_filepath, 'r', encoding='utf-8') as f: config_data = json.load(f)
        required_placeholders = config_data.get('placeholders', [])
        template_display_name = config_data.get('template_name', html_filepath.name)
    except Exception as e: flash(f"Error loading template: {e}", 'error'); print(f"[ERROR] Load failed: {e}"); return redirect(url_for('index'))
    df = None
    try:
        df = pd.read_excel(excel_file, dtype=str).fillna('')
        excel_headers = df.columns.tolist()
        missing_headers = [p for p in required_placeholders if p not in excel_headers]
        if missing_headers: flash(f"Excel missing columns: {', '.join(missing_headers)}", 'error'); return redirect(url_for('index'))
        extra_headers = [h for h in excel_headers if h not in required_placeholders]
        if extra_headers: flash(f"Note: Excel has extra columns: {', '.join(extra_headers)}", 'info')
    except Exception as e: flash(f"Error reading Excel: {e}", 'error'); print(f"[ERROR] Excel read failed: {e}"); return redirect(url_for('index'))
    temp_dir = None; generated_files_paths = []; run_id = uuid.uuid4().hex; generation_errors = 0; browser = None; p_context = None
    zip_filepath = None
    try:
        temp_dir = GENERATED_FOLDER / run_id; temp_dir.mkdir(exist_ok=True)
        p_context = sync_playwright().start(); browser = p_context.chromium.launch()
        for index, row in df.iterrows():
            row_num = index + 1; current_html = template_html_string; temp_html_filepath, temp_image_filepath, page = None, None, None
            try:
                replace_dict = {f'{{{{{p}}}}}': str(row.get(p, '')) for p in required_placeholders}
                for k, v in replace_dict.items(): current_html = current_html.replace(k, v)
                html_output_filename = f"banner_{row_num}.html"; temp_html_filepath = temp_dir / html_output_filename
                try:
                    with open(temp_html_filepath, 'w', encoding='utf-8') as f_html: f_html.write(current_html)
                except Exception as html_save_err:
                    print(f"[ERROR] Row {row_num} Failed save HTML: {html_save_err}"); temp_html_filepath = None
                image_output_filename = f"banner_{row_num}.png"; temp_image_filepath = temp_dir / image_output_filename
                page = browser.new_page()
                page.set_content(current_html)
                page.set_viewport_size({"width": 1150, "height": 800})
                time.sleep(0.3)
                target_element = page.locator('.container')
                if target_element.count() == 0:
                    raise PlaywrightError(f"Element '.container' not found in rendered HTML for row {row_num}.")
                target_element.screenshot(path=temp_image_filepath, type='png')
                if temp_html_filepath and temp_html_filepath.exists() and temp_image_filepath and temp_image_filepath.exists():
                     generated_files_paths.append((temp_html_filepath, temp_image_filepath))
                elif temp_image_filepath and temp_image_filepath.exists():
                     generated_files_paths.append((None, temp_image_filepath))
                else:
                    print(f"[WARN] Row {row_num}: Neither HTML nor Image path valid after generation attempt.")
                    generation_errors += 1
            except PlaywrightError as pe: generation_errors += 1; print(f"[ERROR] Row {row_num} Playwright Error: {pe}"); traceback.print_exc();
            except Exception as gen_err: generation_errors += 1; print(f"[ERROR] Row {row_num} General Error: {gen_err}"); traceback.print_exc();
            finally:
                 if page:
                     try: page.close()
                     except Exception: pass
        if not generated_files_paths: flash("No files generated successfully.", 'error'); return redirect(url_for('index'))
        if generation_errors > 0: flash(f"Completed generation for {len(generated_files_paths)} files, but {generation_errors} row(s) had errors (check console logs).", 'warning')
        else: flash(f"Successfully generated {len(generated_files_paths)} file pair(s).", 'success')
        zip_filename_base = f"{safe_template_id}_banners_{run_id[:8]}.zip"; zip_filepath = GENERATED_FOLDER / zip_filename_base
        try:
            with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for html_path, img_path in generated_files_paths:
                    if html_path and html_path.exists(): zipf.write(html_path, arcname=html_path.name)
                    if img_path and img_path.exists(): zipf.write(img_path, arcname=img_path.name)
        except Exception as zip_err: print(f"[ERROR] Zip failed: {zip_err}"); flash(f"Error creating Zip file: {zip_err}", "error"); return redirect(url_for('index'))
        end_time = time.time()
        print(f"[INFO] Total generation time: {end_time - start_time:.2f} seconds")
        return send_file(zip_filepath, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=f"{template_display_name}_banners.zip")
    except PlaywrightError as pe: print(f"[FATAL] Playwright Error: {pe}"); traceback.print_exc(); flash(f"Playwright Error: {pe}", "error"); return redirect(url_for('index'))
    except Exception as e: flash(f"Unexpected error: {e}", 'error'); print(f"[ERROR] Unexpected: {e}"); print(traceback.format_exc()); return redirect(url_for('index'))
    finally:
        if browser:
            try: browser.close()
            except Exception as e: print(f"[WARN] Error closing browser: {e}")
        if p_context:
            try: p_context.stop()
            except Exception as e: print(f"[WARN] Error stopping context: {e}")
        if temp_dir and temp_dir.exists():
            zip_created_successfully = zip_filepath and zip_filepath.exists()
            if zip_created_successfully:
                try: shutil.rmtree(temp_dir)
                except Exception as clean_err: print(f"[ERROR] Error cleaning temp: {clean_err}")
            else: print(f"[WARN] Zip not created/found. Not cleaning temp: {temp_dir}")


# --- Main Execution ---
if __name__ == '__main__':
    print("[INFO] Application starting up...")
    # Folder creation and cleanup
    UPLOAD_FOLDER.mkdir(exist_ok=True)
    CONFIG_FOLDER.mkdir(exist_ok=True)
    GENERATED_FOLDER.mkdir(exist_ok=True)
    STATIC_FOLDER.mkdir(exist_ok=True)
    PREVIEW_FOLDER.mkdir(exist_ok=True)
    SAMPLE_FOLDER.mkdir(exist_ok=True) # <<< सैंपल फ़ोल्डर सुनिश्चित करें

    cleanup_generated_files(GENERATED_FOLDER)

    # Check Playwright
    try:
        with sync_playwright().start() as p: pass
        print("[INFO] Playwright context check OK.")
    except Exception:
        print("="*60); print("[WARN] Playwright potentially not installed/configured correctly."); print("[WARN] Run 'playwright install'"); print("="*60)

    print("[INFO] Starting Flask application server...")
    app.run(debug=True, host='0.0.0.0', port=5000)