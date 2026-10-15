@echo off
echo Build with Python in a fresh virtual environment. See README for instructions.
python -m PyInstaller --noconfirm --clean --onefile --windowed --noupx --name LocalVoiceStudio --add-data "events.json;." --collect-submodules tinytuya --distpath dist --workpath build app.py
if errorlevel 1 pause
