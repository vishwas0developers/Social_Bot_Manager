@echo off
REM Check if virtual environment exists; if not, create it
IF NOT EXIST "venv\Scripts\activate" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate the virtual environment
echo Activating virtual environment...
call "%~dp0venv\Scripts\activate"

REM Install required packages from updated requirements.txt
echo Installing required packages...
venv\Scripts\python -m pip install -r requirements.txt

REM Upgrade pip to the latest version
echo Upgrading pip...
venv\Scripts\python -m pip install --upgrade pip

pause