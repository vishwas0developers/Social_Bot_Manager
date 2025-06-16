@echo off
REM Step 0: Try deactivating any active conda environment
echo Deactivating any active conda environment...
call conda deactivate >nul 2>&1
call conda deactivate >nul 2>&1
call conda deactivate >nul 2>&1

REM Step 1: Create virtual environment if not exists
set "VENV_DIR=venv"
if not exist "%VENV_DIR%" (
    echo [1/3] Creating virtual environment...
    python -m venv venv
) else (
    echo [1/3] Virtual environment already exists. Skipping...
)

REM Step 2: Activate virtual environment
echo [2/3] Activating virtual environment...
call venv\Scripts\activate

REM Step 3: Install dependencies
echo [3/3] Installing Python packages...
python -m pip install --upgrade pip
pip install -r requirements.txt

REM Final
echo.
echo Setup complete.
echo ---------------------------------------
echo To run the app:
echo cd Gemini Ocr_webapp
echo call venv\Scripts\activate
echo python app.py
echo ---------------------------------------
pause
