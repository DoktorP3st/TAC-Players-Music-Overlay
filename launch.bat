@echo off
cd /d "%~dp0"
echo Vérification des dépendances...
pip install -r requirements.txt --quiet
echo.
echo Lancement de Music Player Overlay...
python main.py
pause
