"""
Конфигурационные настройки приложения ChatList
"""

import os
from pathlib import Path

# Путь к корневой директории проекта
BASE_DIR = Path(__file__).parent

# Путь к файлу базы данных
DATABASE_PATH = BASE_DIR / "chatlist.db"

# Путь к файлу с переменными окружения
ENV_FILE_PATH = BASE_DIR / ".env"

# Таймаут для HTTP-запросов (в секундах)
REQUEST_TIMEOUT = 60

# Максимальное количество одновременных запросов
MAX_CONCURRENT_REQUESTS = 10

# Версия схемы базы данных
DB_VERSION = "1.0"




