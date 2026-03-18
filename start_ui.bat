@echo off
cd /d "%~dp0"
echo ============================================
echo  契約連絡表 自動下書き作成 UI
echo  http://127.0.0.1:8000/  をブラウザで開いてください
echo ============================================
venv\Scripts\python.exe manage.py runserver 8000 --noreload
pause
