@echo off

REM Activate the virtual environment
echo Activating virtual environment...
call "%~dp0venv\Scripts\activate"

REM Run Flask app
echo Running Flask app...
venv\Scripts\python app.py

pause