REM deactivating any active conda environment
echo Deactivating any active conda environment...
call conda deactivate >nul 2>&1
call conda deactivate >nul 2>&1
call conda deactivate >nul 2>&1

@echo off
SETLOCAL

REM Fixed path for virtual environment
SET VENV_PATH=C:\Apps\flask_bot_manager\venv

REM Get current directory where the script is run from
SET CURRENT_DIR=%CD%

REM Check if virtual environment exists; if not, create it
IF NOT EXIST "%VENV_PATH%\Scripts\activate" (
    echo Creating virtual environment at '%VENV_PATH%'...
    python -m venv "%VENV_PATH%"
)

REM Activate the virtual environment
echo Activating virtual environment...
call "%VENV_PATH%\Scripts\activate"

REM Install required packages from requirements.txt in current folder
echo Installing required packages from %CURRENT_DIR%\requirements.txt ...
"%VENV_PATH%\Scripts\python.exe" -m pip install -r "%CURRENT_DIR%\requirements.txt"

REM Upgrade pip to the latest version
echo Upgrading pip...
"%VENV_PATH%\Scripts\python.exe" -m pip install --upgrade pip
