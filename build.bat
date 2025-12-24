@echo off
echo Проверка виртуального окружения...
if exist .venv\Scripts\activate.bat (
    echo Активация виртуального окружения...
    call .venv\Scripts\activate.bat
) else (
    echo Виртуальное окружение не найдено, используются глобальные пакеты
)

echo.
echo Установка зависимостей...
python -m pip install -r requirements.txt

echo.
echo Сборка исполняемого файла...
python -m PyInstaller --onefile --windowed --name "PyQtApp" main.py

echo.
echo Готово! Исполняемый файл находится в папке dist\PyQtApp.exe
pause

