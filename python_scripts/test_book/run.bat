@echo off
title Textbook Scraping WebApp Run
echo =======================================
echo   Running Textbook Scraping WebApp
echo =======================================

REM 🔄 Step 0: Try deactivating any active conda environment
echo Deactivating any active conda environment...
call conda deactivate >nul 2>&1
call conda deactivate >nul 2>&1
call conda deactivate >nul 2>&1

REM Activate the virtual environment
echo Activating virtual environment...
call C:\Apps\flask_bot_manager\venv\Scripts\activate

REM Navigate to the project directory
echo Navigating to project directory...
cd /d C:\Apps\flask_bot_manager\python_scripts\test_book

REM Run the Flask interface for Textbook Scraping
echo Running Flask Interface for Textbook Scraping...
python main.py

REM Pause to keep the command prompt window open
pause