import importlib.util
import importlib
from flask import Flask, render_template, request, jsonify, redirect, url_for, Blueprint, session, send_from_directory
import os
import shutil
import json
import zipfile
import subprocess
import sys
import psutil
import time
from datetime import datetime
from werkzeug.middleware.dispatcher import DispatcherMiddleware

app = Flask(__name__)
app.secret_key = "541cs65g6reghk;tlh3241d65fytxcn"  # Required for session management

# Base paths
BASE_PATH = r"C:\Apps\flask_bot_manager\python_scripts"
BASE_DIR = "C:\\Apps\\flask_bot_manager"
SCRIPT_DIR = os.path.join(BASE_DIR, "python_scripts")
BACKUP_DIR = os.path.join(BASE_DIR, "python_scripts_backup")
# IMAGE_PATH = os.path.join(app.static_folder, "images") # No longer needed for central app logos
VENV_PATH = "venv"
JSON_FILE = os.path.join(BASE_PATH, "buttons.json")
TEMP_EXTRACT_PATH = os.path.join(BASE_PATH, "temp_extract")

os.makedirs(BASE_PATH, exist_ok=True)
# os.makedirs(IMAGE_PATH, exist_ok=True) # No longer needed for central app logos

# Step 1: Blueprint define karo
manager_bp = Blueprint('manager_bp', __name__)

@manager_bp.before_request
def require_login():
    if not request.path.startswith("/login") and not request.path.startswith("/static/"):
        if 'user_logged_in' not in session:
            return redirect(url_for('manager_bp.login'))

@manager_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "admin" and password == "admin123":
            session['user_logged_in'] = True
            return redirect(url_for("manager_bp.index"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@manager_bp.route("/logout")
def logout():
    session.pop('user_logged_in', None)
    return redirect(url_for('manager_bp.login'))

def create_backup(folder_name):
    """Creates a backup of the specified Python script folder with date and time."""
    script_dir = os.path.join(BASE_PATH, folder_name)
    if not os.path.exists(script_dir):
        print(f"❌ Folder '{folder_name}' not found. Skipping backup.")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_folder_name = f"{folder_name}_{timestamp}"
    backup_path = os.path.join(BACKUP_DIR, backup_folder_name)

    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    shutil.copytree(script_dir, backup_path)
    print(f"✅ Backup created at: {backup_path}")

def load_buttons():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r") as f:
            return json.load(f)
    return {}

def save_buttons(data):
    with open(JSON_FILE, "w") as f:
        json.dump(data, f, indent=4)

def terminate_process_by_pid(pid):
    """Kill the running process using the stored PID."""
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(timeout=5)
    except psutil.NoSuchProcess:
        print(f"Process with PID {pid} not found.")
    except Exception as e:
        print(f"Failed to terminate PID {pid}: {e}")

def create_button(folder_name):
    buttons_data = load_buttons()
    info = buttons_data.get(folder_name, {})
    # Use url_for for the default image to ensure correct path resolution
    default_image_url = url_for('static', filename='images/default.png')
    return info.get("button_name", folder_name), folder_name, info.get("image", default_image_url)

# New route to serve images dynamically from app folders
@manager_bp.route('/app_logo/<app_name>/<image_filename>')
def serve_app_logo(app_name, image_filename):
    """Serves the logo image from the specific app's folder."""
    app_dir = os.path.join(BASE_PATH, app_name)
    try:
        # Basic security check to prevent directory traversal
        # Ensure the requested file path is truly a descendant of the app_dir
        requested_path = os.path.realpath(os.path.join(app_dir, image_filename))
        if not requested_path.startswith(os.path.realpath(app_dir) + os.sep):
             print(f"Attempted directory traversal: {image_filename} in {app_name}")
             return jsonify({"status": "error", "message": "Invalid file path."}), 400

        return send_from_directory(app_dir, image_filename)
    except FileNotFoundError:
        print(f"Image file not found: {image_filename} in {app_dir}")
        # Return 404 Not Found if the image does not exist
        return jsonify({"status": "error", "message": "Image not found."}), 404
    except Exception as e:
        print(f"Error serving image {image_filename} from {app_dir}: {e}")
        return jsonify({"status": "error", "message": f"Error serving image: {e}"}), 500

@manager_bp.route("/")
def index():
    buttons_data = load_buttons()
    buttons = [(info["button_name"], folder, info["image"]) for folder, info in buttons_data.items()]
    return render_template("index.html", buttons=buttons)

@manager_bp.route('/upload', methods=['POST'])
def upload():
    zip_file = request.files["zip_file"]
    image_file = request.files.get("image")
    button_name = request.form.get("button_name", "").strip()

    if zip_file and button_name:
        folder_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in button_name).lower()
        script_dir = os.path.join(BASE_PATH, folder_name)

        if os.path.exists(script_dir):
            print(f"⚠️ Folder '{folder_name}' already exists. Removing existing folder.")
            # Optional: Add backup logic here if you want backup on overwrite too
            # create_backup(folder_name)
            shutil.rmtree(script_dir)
        os.makedirs(script_dir, exist_ok=True)
        print(f"✅ Created script directory: {script_dir}")

        zip_path = os.path.join(BASE_PATH, f"{folder_name}_temp.zip") # Use a temp name
        zip_file.save(zip_path)
        print(f"Saved uploaded zip to: {zip_path}")

        temp_extract_target = os.path.join(BASE_PATH, f"temp_extract_{folder_name}")
        if os.path.exists(temp_extract_target):
            shutil.rmtree(temp_extract_target)
        os.makedirs(temp_extract_target, exist_ok=True)
        print(f"Created temporary extraction directory: {temp_extract_target}")

        # Extract zip with progress tracking (optional, kept from original)
        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                total_files = len(zip_ref.infolist())
                print(f"Extracting {total_files} files from zip...")
                for i, file_info in enumerate(zip_ref.infolist()):
                    zip_ref.extract(file_info, temp_extract_target)
                    # Simple progress update, avoid flooding logs too much
                    if (i + 1) % max(1, total_files // 10) == 0 or (i + 1) == total_files:
                         progress = (i + 1) / total_files * 100
                         print(f"Extraction Progress: {progress:.2f}%")
            print(f"✅ Extraction complete.")
        except zipfile.BadZipFile:
            print(f"❌ Error: Uploaded file is not a valid ZIP archive.")
            os.remove(zip_path)
            shutil.rmtree(temp_extract_target)
            shutil.rmtree(script_dir) # Clean up created script dir
            return "Error: Invalid ZIP file provided.", 400
        except Exception as e:
            print(f"❌ Error during zip extraction: {e}")
            os.remove(zip_path)
            shutil.rmtree(temp_extract_target)
            shutil.rmtree(script_dir) # Clean up created script dir
            return f"Error during extraction: {e}", 500
        finally:
             if os.path.exists(zip_path):
                os.remove(zip_path) # Clean up the temporary zip file


        # Handle nested directories within the zip
        extracted_items = os.listdir(temp_extract_target)
        source_dir_for_move = temp_extract_target
        if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_extract_target, extracted_items[0])):
            # If ZIP contains a single top-level folder, use its content
            source_dir_for_move = os.path.join(temp_extract_target, extracted_items[0])
            print(f"Detected nested folder '{extracted_items[0]}' in ZIP. Using its contents.")

        print(f"Moving files from {source_dir_for_move} to {script_dir}")
        for item in os.listdir(source_dir_for_move):
            shutil.move(os.path.join(source_dir_for_move, item), script_dir)

        # Clean up extraction directory
        shutil.rmtree(temp_extract_target)
        print(f"Cleaned up temporary extraction directory.")

        # Rename the first .py file to main.py
        py_files = [f for f in os.listdir(script_dir) if f.endswith(".py") and f != '__init__.py'] # Exclude __init__.py
        main_py_path = os.path.join(script_dir, "main.py")
        if not os.path.exists(main_py_path) and py_files:
            os.rename(os.path.join(script_dir, py_files[0]), main_py_path)
            print(f"Renamed '{py_files[0]}' to 'main.py'.")
        elif not os.path.exists(main_py_path) and not py_files:
            print("❌ Error: No .py file found in the extracted content.")
            shutil.rmtree(script_dir)
            return "Error: No Python script found in ZIP", 400
        elif os.path.exists(main_py_path):
             print("Found 'main.py'. No rename needed.")


        # --- Start: Install requirements using venv.bat ---
        req_path = os.path.join(script_dir, "requirements.txt")
        if os.path.exists(req_path):
            print(f"Found requirements.txt at {req_path}. Attempting installation via batch script.")
            source_bat_path = os.path.join(BASE_DIR, "venv.bat") # Path to your master batch file
            dest_bat_path = os.path.join(script_dir, "venv.bat")   # Path to copy it inside the script dir

            if os.path.exists(source_bat_path):
                try:
                    shutil.copy2(source_bat_path, dest_bat_path) # copy2 preserves metadata
                    print(f"Copied '{source_bat_path}' to '{dest_bat_path}'.")

                    print(f"Attempting to run batch file: '{dest_bat_path}' from CWD: '{script_dir}'")
                    # Execute the copied batch file FROM the script directory
                    result = subprocess.run(
                        [dest_bat_path],      # Command is the path to the .bat
                        check=True,           # Raise error on failure
                        capture_output=True,  # Capture stdout and stderr
                        text=True,            # Decode output as text
                        shell=False,          # Better not to use shell=True if not needed
                        cwd=script_dir        # CRUCIAL: Run from the script's directory
                    )
                    print(f"✅ Batch file execution successful for '{folder_name}':")
                    print("--- Batch Script Output Start ---")
                    print(result.stdout)
                    print("--- Batch Script Output End ---")

                    # Optional: Clean up the copied batch file after successful run
                    # try:
                    #    os.remove(dest_bat_path)
                    #    print(f"Removed temporary batch file: {dest_bat_path}")
                    # except OSError as e:
                    #    print(f"⚠️ Warning: Could not remove temporary batch file {dest_bat_path}: {e}")

                except FileNotFoundError:
                    print(f"❌ Error: Batch file '{dest_bat_path}' not found or cannot be executed. Installation skipped.")
                    # Decide if this is a fatal error or just a warning
                    # shutil.rmtree(script_dir) # Uncomment to treat as fatal
                    # return "Error: Installation script not found.", 500
                except subprocess.CalledProcessError as e:
                    print(f"❌ Error running batch file {dest_bat_path}:")
                    print(f"Return code: {e.returncode}")
                    print("--- Batch Script Stderr Start ---")
                    print(e.stderr)
                    print("--- Batch Script Stderr End ---")
                    print("--- Batch Script Stdout Start ---")
                    print(e.stdout) # Also show stdout on error
                    print("--- Batch Script Stdout End ---")
                    # Clean up the failed upload
                    shutil.rmtree(script_dir)
                    # Also remove button data if already added? Not added yet, so OK.
                    return "Error: Failed to execute dependency installation script.", 500
                except Exception as e: # Catch other potential errors like permissions
                    print(f"❌ An unexpected error occurred while copying or running the batch file: {e}")
                    shutil.rmtree(script_dir)
                    return "Error: Unexpected issue during dependency installation.", 500
            else:
                print(f"⚠️ Warning: Source batch file '{source_bat_path}' not found. Skipping dependency installation.")
        else:
            print("No requirements.txt found. Skipping dependency installation.")
        # --- End: Install requirements using venv.bat ---

        # Update buttons.json and save image to app folder
        buttons_data = load_buttons()
        # Default image path (using static for the default image)
        default_image_url = url_for('static', filename='images/default.png')
        img_path_for_json = default_image_url # Initialize with default
        img_filename = None

        if image_file and image_file.filename: # Check if a file was actually uploaded
            try:
                # Determine image filename (use folder name for consistency, keeping original extension if desired, but .png is assumed here)
                # A more robust solution might check the actual file extension
                # Let's use the original filename to allow for different image types (jpg, png, etc.)
                original_filename = image_file.filename
                # Sanitize filename to prevent issues
                img_filename = "".join(c if c.isalnum() or c in "_-" else "_" for c in original_filename)
                # Ensure a non-empty filename
                if not img_filename:
                     img_filename = f"{folder_name}_uploaded_image"

                image_save_path = os.path.join(script_dir, img_filename)

                # Ensure the app's directory exists before saving the image (should exist from zip extraction)
                os.makedirs(script_dir, exist_ok=True)

                # Save the image file inside the app's directory
                image_file.save(image_save_path)

                # Generate the dynamic URL for the image using the new route
                img_path_for_json = url_for('manager_bp.serve_app_logo', app_name=folder_name, image_filename=img_filename)
                print(f"Saved image to: {image_save_path} and set path in json to {img_path_for_json}")

            except Exception as e:
                print(f"⚠️ Warning: Could not save image file to app folder during upload: {e}. Using default image.")
                img_path_for_json = default_image_url # Fallback to default
                img_filename = None # Indicate that custom image was not saved

        # Update buttons_data with the button name and the determined image path
        # If a new image was saved successfully, img_path_for_json holds the dynamic URL.
        # If no new image was uploaded or saving failed, it holds the default_image_url.
        buttons_data[folder_name] = {"button_name": button_name, "image": img_path_for_json}

        save_buttons(buttons_data)
        print(f"Updated buttons.json for '{folder_name}'.")


        # --- Dynamically register the app ---

        # Dynamically register the app
        # IMPORTANT: As discussed, if the batch file installed new dependencies,
        # this registration might still fail within the *same running process*
        # due to Python's import caching. A restart of the main app might be needed.
        print("Attempting to register apps after upload...")
        try:
            register_all_apps()
            print("✅ App registration process completed.")
        except Exception as e:
             print(f"⚠️ Error during dynamic app registration after upload: {e}")
             print("ℹ️ A manual restart of the Flask Bot Manager might be required for the new app to function correctly.")


    else:
        # Handle cases where zip or button name is missing
        if not zip_file:
             print("Upload failed: No ZIP file provided.")
        if not button_name:
             print("Upload failed: Button name was empty.")
        # Consider adding a Flask flash message here for the user
        return redirect(url_for("manager_bp.index")) # Redirect back, maybe with an error message

    return redirect(url_for("manager_bp.index"))

@manager_bp.route("/delete/<folder_name>")
def delete_script(folder_name):
    script_dir = os.path.join(BASE_PATH, folder_name)
    buttons_data = load_buttons()

    # Attempt to get the image filename from buttons_data to delete it from the app folder
    image_filename_to_delete = None
    if folder_name in buttons_data and "image" in buttons_data[folder_name]:
        image_url = buttons_data[folder_name]["image"]
        # Extract filename from the dynamic URL if it exists
        # The URL format is expected to be like /app_logo/<app_name>/<image_filename>
        if '/app_logo/' in image_url:
            try:
                # Split the URL by / and get the last part as filename
                url_parts = image_url.split('/')
                if len(url_parts) > 0:
                    image_filename_to_delete = url_parts[-1]
                    # Basic check to ensure it doesn't look like a path traversal attempt
                    if '..' in image_filename_to_delete or '/' in image_filename_to_delete or '\\' in image_filename_to_delete:
                         image_filename_to_delete = None # Treat as invalid filename
            except Exception as e:
                print(f"Error extracting filename from URL {image_url}: {e}")
                image_filename_to_delete = None

    # Construct the potential image path within the app folder
    image_path_in_app_folder = None
    if image_filename_to_delete:
         image_path_in_app_folder = os.path.join(script_dir, image_filename_to_delete)

    if folder_name in buttons_data and "pid" in buttons_data[folder_name]:
        pid = buttons_data[folder_name]["pid"]
        terminate_process_by_pid(pid)
        del buttons_data[folder_name]["pid"]

    # Unregister blueprint and clean up sys.modules
    if folder_name in app.blueprints:
        app.blueprints.pop(folder_name, None)
    mod_name = f"{folder_name}_app"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    # Increase wait time to allow resources (like file handles) to be released
    print(f"Waiting for resources to release for '{folder_name}'...")
    time.sleep(2) # Increased from 0.5 seconds to 2 seconds

    # Create backup before deletion
    create_backup(folder_name)

    try:
        # Attempt to delete the script directory using shutil.rmtree first
        if os.path.exists(script_dir):
            print(f"Attempting to delete script directory with shutil.rmtree: {script_dir}")
            shutil.rmtree(script_dir)
            print(f"✅ Successfully deleted script directory with shutil.rmtree: {script_dir}")

        # If shutil.rmtree succeeds, the image file is also deleted, so no need for separate deletion.
        # Proceed to update buttons.json
        if folder_name in buttons_data:
            del buttons_data[folder_name]
        save_buttons(buttons_data)

        return jsonify({"status": "success", "message": f"Deleted '{folder_name}'"})

    except PermissionError as e:
        # If shutil.rmtree fails due to PermissionError (file in use), try forceful deletion via rmdir command
        print(f"❌ Permission Error during shutil.rmtree deletion of '{folder_name}': {e}")
        print(f"Attempting forceful deletion using rmdir /S /Q: {script_dir}")
        try:
            # Use rmdir /S /Q for forceful deletion on Windows
            # /S: Deletes a directory tree (the specified directory and all its subdirectories and files).
            # /Q: Specifies quiet mode. Does not ask for confirmation when deleting a directory tree.
            result = subprocess.run(
                ["rmdir", "/S", "/Q", script_dir], # Command and arguments as a list
                check=False, # Do not raise CalledProcessError immediately, check stderr for specific message
                capture_output=True, # Capture stdout and stderr
                text=True, # Decode output as text
                shell=True # Use shell=True for rmdir command (necessary for rmdir on some systems)
            )
            print(f"✅ Forceful deletion command attempted for '{folder_name}'. Return Code: {result.returncode}")
            print("--- rmdir Output Start ---")
            print(result.stdout)
            print(result.stderr)
            print("--- rmdir Output End ---")

            # Check if the error indicates a file is still in use (WinError 32)
            # This message might be in stderr even with a 0 or non-zero return code depending on exact scenario
            if "The process cannot access the file because it is being used by another process" in result.stderr or result.returncode != 0:
                 print(f"❌ Forceful deletion failed or encountered errors for '{folder_name}'. Stderr indicates a problem.")
                 # Provide a simplified error message instructing the user to restart
                 return jsonify({"status": "error", "message": f"Could not delete app directory '{folder_name}': A file is in use. Please restart the Flask Bot Manager application to release file locks and try again."}), 500


            # If rmdir command executed without the specific file-in-use error and returned 0, assume success
            if not os.path.exists(script_dir):
                 print(f"✅ Confirmed directory '{script_dir}' is deleted after forceful attempt.")

                 # Forceful deletion worked, now update buttons.json
                 if folder_name in buttons_data:
                    del buttons_data[folder_name]
                 save_buttons(buttons_data)
                 return jsonify({"status": "success", "message": f"Deleted '{folder_name}'. (Note: Forceful deletion was required.)"})
            else:
                 # If directory still exists despite successful rmdir execution (unlikely but possible)
                 print(f"⚠️ rmdir /S /Q command executed successfully but directory '{script_dir}' still exists.")
                 return jsonify({"status": "error", "message": f"Failed to delete app directory '{folder_name}' even with forceful attempt. Directory still exists."}), 500

        except FileNotFoundError:
             print(f"❌ Error: rmdir command not found.") # Should not happen on Windows
             return jsonify({"status": "error", "message": f"Could not execute deletion command for '{folder_name}'. rmdir command not found."}), 500
        except Exception as e:
             # Catch any other unexpected exceptions during the forceful deletion attempt
             print(f"❌ An unexpected error occurred during forceful deletion of '{folder_name}': {e}")
             return jsonify({"status": "error", "message": f"An unexpected error occurred during forceful deletion: {str(e)}. Please restart the Flask Bot Manager application and try again."}), 500

    except Exception as e:
        # Catch any other exceptions during the initial shutil.rmtree attempt
        print(f"❌ An unexpected error occurred during deletion of '{folder_name}': {e}")
        return jsonify({"status": "error", "message": f"An unexpected error occurred during deletion: {str(e)}"}), 500

    if folder_name in buttons_data and "pid" in buttons_data[folder_name]:
        pid = buttons_data[folder_name]["pid"]
        terminate_process_by_pid(pid)
        del buttons_data[folder_name]["pid"]

    # Unregister blueprint and clean up sys.modules
    if folder_name in app.blueprints:
        app.blueprints.pop(folder_name, None)
    mod_name = f"{folder_name}_app"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    time.sleep(0.5)

    # Create backup before deletion
    create_backup(folder_name)

    try:
        if os.path.exists(script_dir):
            shutil.rmtree(script_dir)
        if os.path.exists(image_path):
            os.remove(image_path)
        if folder_name in buttons_data:
            del buttons_data[folder_name]
        save_buttons(buttons_data)

        return jsonify({"status": "success", "message": f"Deleted '{folder_name}'"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@manager_bp.route("/edit/<folder_name>", methods=["POST"])
def edit_script(folder_name):
    new_button_name = request.form.get("button_name", "").strip()
    new_zip_file = request.files.get("zip_file")
    new_image_file = request.files.get("image")

    original_script_dir = os.path.join(BASE_PATH, folder_name) # Keep original path for checks/backup
    buttons_data = load_buttons()

    if folder_name not in buttons_data:
        return jsonify({"status": "error", "message": "App not found."}), 404

    # --- Prepare for update ---
    # Terminate existing process if running (PID logic - keep as is)
    if "pid" in buttons_data[folder_name]:
        pid = buttons_data[folder_name]["pid"]
        print(f"Attempting to terminate running process PID: {pid} for app '{folder_name}' before edit.")
        terminate_process_by_pid(pid)
        # Remove PID regardless of termination success, as the code is changing
        del buttons_data[folder_name]["pid"]
        # Save button data immediately after removing PID
        save_buttons(buttons_data)

    # Unregister blueprint/module (keep as is)
    if folder_name in app.blueprints:
        app.blueprints.pop(folder_name, None)
    mod_name = f"{folder_name}_app"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    time.sleep(0.5) # Allow time for resources to release

    # Create backup before making changes (keep as is)
    print(f"Creating backup for '{folder_name}' before editing.")
    create_backup(folder_name)

    # --- Apply Changes ---
    script_dir = os.path.join(BASE_PATH, folder_name) # Use consistent variable name

    # If new ZIP is uploaded, replace the entire script directory content
    if new_zip_file and new_zip_file.filename:
        print(f"New ZIP file provided for '{folder_name}'. Replacing content.")
        # Remove existing script directory content
        if os.path.exists(script_dir):
            shutil.rmtree(script_dir)
        os.makedirs(script_dir, exist_ok=True)

        # Save and extract the new zip (similar logic to upload)
        zip_path = os.path.join(BASE_PATH, f"{folder_name}_temp_edit.zip")
        new_zip_file.save(zip_path)
        print(f"Saved uploaded zip for edit to: {zip_path}")

        temp_extract_target = os.path.join(BASE_PATH, f"temp_extract_edit_{folder_name}")
        if os.path.exists(temp_extract_target):
            shutil.rmtree(temp_extract_target)
        os.makedirs(temp_extract_target, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                print(f"Extracting new zip file for '{folder_name}'...")
                zip_ref.extractall(temp_extract_target)
                print(f"✅ Extraction complete.")
        except Exception as e:
            print(f"❌ Error extracting new zip for edit: {e}")
            if os.path.exists(zip_path): os.remove(zip_path)
            if os.path.exists(temp_extract_target): shutil.rmtree(temp_extract_target)
            # Optionally restore from backup here if needed, or just fail
            return jsonify({"status": "error", "message": f"Failed to extract new ZIP: {e}"}), 500
        finally:
             if os.path.exists(zip_path): os.remove(zip_path)

        # Handle nested dir in new zip
        extracted_items = os.listdir(temp_extract_target)
        source_dir_for_move = temp_extract_target
        if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_extract_target, extracted_items[0])):
            source_dir_for_move = os.path.join(temp_extract_target, extracted_items[0])

        print(f"Moving new files from {source_dir_for_move} to {script_dir}")
        for item in os.listdir(source_dir_for_move):
            shutil.move(os.path.join(source_dir_for_move, item), script_dir)
        shutil.rmtree(temp_extract_target)

        # Rename to main.py if necessary
        py_files = [f for f in os.listdir(script_dir) if f.endswith(".py") and f != '__init__.py']
        main_py_path = os.path.join(script_dir, "main.py")
        if not os.path.exists(main_py_path) and py_files:
             try:
                os.rename(os.path.join(script_dir, py_files[0]), main_py_path)
                print(f"Renamed '{py_files[0]}' to 'main.py'.")
             except Exception as e:
                 print(f"❌ Error renaming python file to main.py: {e}")
                 # Decide how critical this is - maybe return error?
        elif not os.path.exists(main_py_path) and not py_files:
            print(f"❌ Error: No .py file found in the new ZIP for '{folder_name}'.")
            # Cleanup potentially broken state? Or rely on user to fix.
            return jsonify({"status": "error", "message": "No Python script found in new ZIP."}), 400

        # --- Install requirements using venv.bat (NEW logic) ---
        req_path = os.path.join(script_dir, "requirements.txt")
        if os.path.exists(req_path):
            print(f"Found requirements.txt in new ZIP for '{folder_name}'. Attempting installation via batch script.")
            source_bat_path = os.path.join(BASE_DIR, "venv.bat")
            dest_bat_path = os.path.join(script_dir, "venv.bat")

            if os.path.exists(source_bat_path):
                try:
                    shutil.copy2(source_bat_path, dest_bat_path)
                    print(f"Copied '{source_bat_path}' to '{dest_bat_path}'.")

                    print(f"Attempting to run batch file: '{dest_bat_path}' from CWD: '{script_dir}' for edited app.")
                    result = subprocess.run(
                        [dest_bat_path], check=True, capture_output=True, text=True,
                        shell=False, cwd=script_dir
                    )
                    print(f"✅ Batch file execution successful for edited '{folder_name}':")
                    print("--- Batch Script Output Start ---")
                    print(result.stdout)
                    print("--- Batch Script Output End ---")
                    # Optional: remove dest_bat_path

                except Exception as e: # Catch broadly during edit
                    print(f"❌ Error installing dependencies for edited '{folder_name}': {e}")
                    # Print details if CalledProcessError
                    if isinstance(e, subprocess.CalledProcessError):
                         print(f"Return code: {e.returncode}")
                         print(f"Stderr: {e.stderr}")
                         print(f"Stdout: {e.stdout}")
                    # Decide whether to stop the edit process
                    return jsonify({"status": "error", "message": f"Failed to install dependencies from new ZIP: {e}"}), 500
            else:
                 print(f"⚠️ Warning: Source batch file '{source_bat_path}' not found. Skipping dependency installation for edited app.")
        else:
             print(f"No requirements.txt found in new ZIP for '{folder_name}'. Skipping dependency installation.")
        # --- End install requirements ---

    # --- Update metadata (Image and Button Name) ---
    buttons_data = load_buttons() # Reload data in case it changed
    if folder_name not in buttons_data: # Should exist, but check again
         buttons_data[folder_name] = {} # Initialize if somehow missing

    # Update image if a new one was uploaded
    if new_image_file and new_image_file.filename:
        try:
            # Determine image filename (using original filename for type, but sanitizing)
            original_filename = new_image_file.filename
            img_filename = "".join(c if c.isalnum() or c in "_-" else "_" for c in original_filename)
            if not img_filename:
                 img_filename = f"{folder_name}_edited_image"

            image_save_path = os.path.join(script_dir, img_filename)

            # Remove old image in the app folder if it exists and is different from the new one
            # This part is tricky. We only want to remove the *old* custom image if a *new* custom image is provided.
            # If the user is just editing the button name, we keep the existing image.
            # If the user uploads a new image, we replace the old one.

            # Get the current image path from buttons_data
            current_image_url = buttons_data[folder_name].get("image")
            old_image_filename = None
            if current_image_url and '/app_logo/' in current_image_url:
                 try:
                    url_parts = current_image_url.split('/')
                    if len(url_parts) > 0:
                         old_image_filename = url_parts[-1]
                         if '..' in old_image_filename or '/' in old_image_filename or '\\' in old_image_filename:
                              old_image_filename = None # Invalid filename
                 except Exception as e:
                    print(f"Error extracting old filename from URL {current_image_url}: {e}")
                    old_image_filename = None

            # If a new image was uploaded AND its filename is different from the old one,
            # OR if there was an old image and the new upload filename is the same (implying replacement),
            # AND the old image was a custom one (not the default static),
            # then remove the old image file from the app's directory.
            if old_image_filename and old_image_filename != img_filename and os.path.exists(os.path.join(script_dir, old_image_filename)):
                 try:
                    os.remove(os.path.join(script_dir, old_image_filename))
                    print(f"Removed old image file: {os.path.join(script_dir, old_image_filename)}")
                 except Exception as e:
                    print(f"⚠️ Warning: Could not remove old image file during edit: {e}.")

            new_image_file.save(image_save_path)
            # Update the image path in buttons.json to the new dynamic URL
            buttons_data[folder_name]["image"] = url_for('manager_bp.serve_app_logo', app_name=folder_name, image_filename=img_filename)
            print(f"Updated image for '{folder_name}' to {buttons_data[folder_name]['image']}.")

        except Exception as e:
            print(f"⚠️ Warning: Could not save new image file to app folder during edit: {e}.")
            # If saving fails, keep the existing image path in buttons.json if one exists,
            # otherwise it will fall back to the default later if not set.

    # Update button name if a new one was provided (this happens regardless of image upload)
    if new_button_name:
        buttons_data[folder_name]["button_name"] = new_button_name
        print(f"Updated button name for '{folder_name}' to '{new_button_name}'.")

    # Ensure essential keys exist after potential updates
    if "button_name" not in buttons_data[folder_name]:
         buttons_data[folder_name]["button_name"] = folder_name # Default if missing
    # If 'image' key is missing after potential update/failure, set to default static image
    if "image" not in buttons_data[folder_name]:
         buttons_data[folder_name]["image"] = url_for('static', filename='images/default.png')

    save_buttons(buttons_data) # Save all accumulated changes

    # --- Finalize ---
    print(f"Attempting to register apps after editing '{folder_name}'...")
    try:
        register_all_apps() # Re-register to load the updated app
        print("✅ App registration process completed after edit.")
    except Exception as e:
         print(f"⚠️ Error during dynamic app registration after edit: {e}")
         print("ℹ️ A manual restart of the Flask Bot Manager might be required for the edited app to function correctly.")

    return jsonify({"status": "success", "message": "App updated successfully"})

def load_uploaded_app(folder_name):
    """Load an app's main.py from the folder and return its Flask instance."""
    script_dir = os.path.join(BASE_PATH, folder_name)
    main_script = os.path.join(script_dir, "main.py")

    if not os.path.exists(main_script):
        print(f"⚠️ main.py not found in {script_dir}")
        return None

    print(f"Attempting to invalidate import caches before loading {folder_name}_app...")
    importlib.invalidate_caches()

    spec = importlib.util.spec_from_file_location(f"{folder_name}_app", main_script)
    if spec is None or spec.loader is None:
         print(f"❌ Could not create module spec for {main_script}")
         return None

    module = importlib.util.module_from_spec(spec)
    # Crucially, register the module *before* modifying sys.path if possible,
    # although exec_module is where the import happens.
    sys.modules[spec.name] = module

    # --- Temporarily modify sys.path ---
    original_sys_path = list(sys.path) # Make a copy
    path_added = False
    if script_dir not in sys.path:
        print(f"Adding '{script_dir}' to sys.path for module execution.")
        sys.path.insert(0, script_dir) # Add to the beginning
        path_added = True
    # --- End temporary modification ---

    try:
        print(f"Executing module: {spec.name}")
        print(f"DEBUG: sys.path before exec_module for {spec.name}: {sys.path}")
        # This is where imports inside main.py (like 'import utils') happen
        spec.loader.exec_module(module)
        print(f"✅ Successfully executed module: {spec.name}")
    except ImportError as e: # Catch ImportError specifically now
        print(f"❌ ImportError during exec_module for {spec.name}: {e}")
        # Check if it's the utils import again or something else
        if 'utils' in str(e):
             print(f"Checklist: Does '{os.path.join(script_dir, 'utils')}' exist? Does it contain '__init__.py'?")
        print(f"Current sys.path: {sys.path}")
        if spec.name in sys.modules: del sys.modules[spec.name]
        module = None # Failed to load
    except Exception as e:
        print(f"❌ Unexpected error during exec_module for {spec.name}: {e}")
        if spec.name in sys.modules: del sys.modules[spec.name]
        module = None # Failed to load
    finally:
        # --- Restore original sys.path ---
        if path_added: # Only restore if we actually added it
            print(f"Restoring original sys.path.")
            sys.path = original_sys_path
        # --- End restore ---

    # Return the Flask app instance if available *and* module loaded successfully
    if module and hasattr(module, "app"):
        return module.app
    elif module:
        print(f"⚠️ Module {spec.name} loaded but has no 'app' attribute.")
        return None
    else:
        # Module loading failed in the except block
        return None

def register_all_apps():
    """Register all apps dynamically using DispatcherMiddleware."""
    mapping = {}

    for folder in os.listdir(BASE_PATH):
        script_dir = os.path.join(BASE_PATH, folder)
        if os.path.isdir(script_dir) and os.path.exists(os.path.join(script_dir, "main.py")):
            uploaded_app = load_uploaded_app(folder)
            if uploaded_app:
                mapping[f"/{folder}"] = uploaded_app
            else:
                print(f"⚠️ Failed to load app for {folder}")

    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, mapping)

if __name__ == "__main__":
    app.register_blueprint(manager_bp, url_prefix="/")
    register_all_apps()
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
