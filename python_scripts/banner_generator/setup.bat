@echo off
title AUTO Baner WebApp Setup
echo =======================================
echo   Setting up AUTO Baner WebApp Project
echo =======================================

REM Step 0: Try deactivating any active conda environment
echo Deactivating any active conda environment...
call conda deactivate >nul 2>&1
call conda deactivate >nul 2>&1
call conda deactivate >nul 2>&1

REM Step 1: Create virtual environment if not exists
set "VENV_DIR=venv"
if not exist "%VENV_DIR%" (
    echo [1/7] Creating virtual environment...
    python -m venv venv
) else (
    echo [1/7] Virtual environment already exists. Skipping...
)

REM Step 2: Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate

REM Step 3: Install dependencies
echo [3/7] Installing Python packages...
python -m pip install --upgrade pip
pip install -r requirements.txt

REM Step 3.5: Install Playwright browsers
echo [3.5/7] Installing Playwright browsers...
playwright install

REM 📁 Step 4: Create required folders
for %%F in (uploads output static templates) do (
    if not exist "%%F" (
        mkdir "%%F"
        echo Created folder: %%F
    ) else (
        echo Folder already exists: %%F
    )
)

REM Step 5: Create placeholder files if not exist
echo [4/7] Creating initial files...

if not exist "app.py" (
    echo # app.py placeholder > app.py
    echo Created: app.py
) else (
    echo app.py already exists.
)

if not exist "templates\index.html" (
    echo <!-- index.html placeholder --> > templates\index.html
    echo Created: templates/index.html
) else (
    echo templates/index.html already exists.
)

if not exist "static\style.css" (
    echo /* style.css placeholder */ > static\style.css
    echo Created: static/style.css
) else (
    echo static/style.css already exists.
)

if not exist "uploads" (
    echo /* Stores user-uploaded HTML templates */ > uploads
    echo Created:  uploads
) else (
    echo uploads already exists.
)

if not exist "configs" (
    echo /* Stores user-uploaded HTML templates */ > configs
    echo Created:  configs
) else (
    echo configs already exists.
)

if not exist "generated_files" (
    echo /* Stores user-uploaded HTML templates */ > generated_files
    echo Created:  generated_files
) else (
    echo generated_files already exists.
)


REM Final
echo.
echo Setup complete.
echo ---------------------------------------
echo To run the app:
echo cd AUTO Baner_webapp
echo call venv\Scripts\activate
echo python app.py
echo ---------------------------------------
pause
