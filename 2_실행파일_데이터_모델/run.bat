@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  WordFreqProj - Watcha Comment Dashboard
echo ============================================
echo [1/2] Installing requirements...
py -m pip install -r requirements.txt
echo [2/2] Launching Streamlit dashboard...
py -m streamlit run WordFreqWebDashboard.py
pause
