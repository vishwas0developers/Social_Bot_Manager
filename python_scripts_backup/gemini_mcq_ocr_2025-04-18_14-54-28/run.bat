@echo off
title Gemini MCQ Ocr WebApp Run
echo =======================================
echo   Runing up Gemini MCQ Ocr WebApp
echo =======================================

REM 🔄 Step 0: Try deactivating any active conda environment
echo Deactivating any active conda environment...
call conda deactivate >nul 2>&1
call conda deactivate >nul 2>&1
call conda deactivate >nul 2>&1


echo Running Flask Interface for Gemini Ocr
call venv\Scripts\activate
python app.py
pause
