@echo off
title AUTO Baner WebApp Run
echo =======================================
echo   Runing up AUTO Baner WebApp
echo =======================================

REM 🔄 Step 0: Try deactivating any active conda environment
echo Deactivating any active conda environment...
call conda deactivate >nul 2>&1
call conda deactivate >nul 2>&1
call conda deactivate >nul 2>&1


echo Running Flask Interface for AUTO Baner
call venv\Scripts\activate
python app.py
pause
