# Проверка виртуального окружения
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Активация виртуального окружения..." -ForegroundColor Green
    & .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "Виртуальное окружение не найдено, используются глобальные пакеты" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Установка зависимостей..." -ForegroundColor Green
python -m pip install -r requirements.txt

Write-Host ""
Write-Host "Сборка исполняемого файла..." -ForegroundColor Green
python -m PyInstaller --onefile --windowed --name "PyQtApp" main.py

Write-Host ""
Write-Host "Готово! Исполняемый файл находится в папке dist\PyQtApp.exe" -ForegroundColor Green
Read-Host "Нажмите Enter для выхода"

