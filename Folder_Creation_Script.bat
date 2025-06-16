@echo off
set BASE_DIR=C:\Apps\flask_bot_manager

:: Create directories
mkdir "%BASE_DIR%\app_venv"
mkdir "%BASE_DIR%\downloads"
mkdir "%BASE_DIR%\python_scripts"
mkdir "%BASE_DIR%\python_scripts_backup"
mkdir "%BASE_DIR%\static"
mkdir "%BASE_DIR%\templates"
mkdir "%BASE_DIR%\uploads"
mkdir "%BASE_DIR%\venv"

:: Create app.py
echo from flask import Flask> "%BASE_DIR%\app.py"
echo.>> "%BASE_DIR%\app.py"
echo app = Flask(__name__)>> "%BASE_DIR%\app.py"
echo.>> "%BASE_DIR%\app.py"
echo @app.route("/")>> "%BASE_DIR%\app.py"
echo def index():>> "%BASE_DIR%\app.py"
echo     return "Hello, World!">> "%BASE_DIR%\app.py"
echo.>> "%BASE_DIR%\app.py"
echo if __name__ == "__main__":>> "%BASE_DIR%\app.py"
echo     app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)>> "%BASE_DIR%\app.py"

:: Create app_venv.bat
echo @echo off> "%BASE_DIR%\app_venv.bat"
echo cd /d C:\Apps\flask_bot_manager\app_venv>> "%BASE_DIR%\app_venv.bat"
echo call Scripts\activate>> "%BASE_DIR%\app_venv.bat"

:: Create requirements.txt
echo flask==2.2.3> "%BASE_DIR%\requirements.txt"

:: Create setup_and_run.bat
echo @echo off> "%BASE_DIR%\setup_and_run.bat"
echo call app_venv\Scripts\activate>> "%BASE_DIR%\setup_and_run.bat"
echo python app.py>> "%BASE_DIR%\setup_and_run.bat"

echo ✅ Folder structure and files created successfully!
