"""
Модуль для работы с базой данных SQLite
Инкапсулирует все операции с БД для приложения ChatList
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from config import DATABASE_PATH, DB_VERSION

logger = logging.getLogger(__name__)


def get_connection():
    """Получить соединение с базой данных"""
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row  # Возвращать результаты как словари
    return conn


def init_database():
    """Инициализация базы данных: создание таблиц, индексов и начальных данных"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Создание таблицы prompts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATETIME DEFAULT CURRENT_TIMESTAMP,
                prompt TEXT NOT NULL,
                tags TEXT
            )
        """)

        # Создание таблицы models
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                api_url TEXT NOT NULL,
                api_id TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                model_type TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Создание таблицы results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_id INTEGER NOT NULL,
                model_id INTEGER NOT NULL,
                response_text TEXT NOT NULL,
                saved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                tokens_used INTEGER,
                response_time REAL,
                FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE,
                FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE RESTRICT
            )
        """)

        # Создание таблицы settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT
            )
        """)

        # Создание индексов для prompts
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_prompts_date ON prompts(date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_prompts_tags ON prompts(tags)
        """)

        # Создание индексов для models
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_models_is_active ON models(is_active)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_models_name ON models(name)
        """)

        # Создание индексов для results
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_prompt_id ON results(prompt_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_model_id ON results(model_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_saved_at ON results(saved_at)
        """)

        # Создание индекса для settings
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key)
        """)

        conn.commit()

        # Инициализация начальных данных
        _init_default_data(cursor, conn)

        logger.info("База данных успешно инициализирована")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при создании базы данных: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def _init_default_data(cursor, conn):
    """Инициализация начальных данных в БД"""
    # Проверка, есть ли уже данные в таблице models
    cursor.execute("SELECT COUNT(*) as count FROM models")
    count = cursor.fetchone()["count"]

    if count == 0:
        # Добавление примеров моделей через OpenRouter
        # Все модели используют один API ключ OPENROUTER_API_KEY
        # В поле name хранится API имя модели (например "openai/gpt-4")
        default_models = [
            ("openai/gpt-4", "https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY", "openrouter"),
            ("openai/gpt-3.5-turbo", "https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY", "openrouter"),
            ("anthropic/claude-3.5-sonnet", "https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY", "openrouter"),
            ("anthropic/claude-3-opus", "https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY", "openrouter"),
            ("deepseek/deepseek-chat", "https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY", "openrouter"),
            ("google/gemini-pro", "https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY", "openrouter"),
            ("meta-llama/llama-3-70b-instruct", "https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY", "openrouter"),
        ]

        for api_model_name, api_url, api_id, model_type in default_models:
            cursor.execute("""
                INSERT INTO models (name, api_url, api_id, model_type, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (api_model_name, api_url, api_id, model_type))

    # Инициализация настроек по умолчанию
    default_settings = [
        ("db_version", DB_VERSION),
        ("theme", "light"),
        ("default_export_format", "markdown"),
        ("auto_save_prompts", "false"),
    ]

    for key, value in default_settings:
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES (?, ?)
        """, (key, value))

    conn.commit()


# ==================== Работа с таблицей prompts ====================

def create_prompt(prompt_text: str, tags: Optional[str] = None) -> int:
    """Создание нового промта"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO prompts (prompt, tags)
            VALUES (?, ?)
        """, (prompt_text, tags))
        conn.commit()
        prompt_id = cursor.lastrowid
        logger.info(f"Создан промт с ID: {prompt_id}")
        return prompt_id
    except sqlite3.Error as e:
        logger.error(f"Ошибка при создании промта: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def get_all_prompts() -> List[Dict]:
    """Получение всех промтов"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, date, prompt, tags
            FROM prompts
            ORDER BY date DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_prompt_by_id(prompt_id: int) -> Optional[Dict]:
    """Получение промта по ID"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, date, prompt, tags
            FROM prompts
            WHERE id = ?
        """, (prompt_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def search_prompts(query: str) -> List[Dict]:
    """Поиск промтов по тексту"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, date, prompt, tags
            FROM prompts
            WHERE prompt LIKE ? OR tags LIKE ?
            ORDER BY date DESC
        """, (f"%{query}%", f"%{query}%"))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def update_prompt_tags(prompt_id: int, tags: Optional[str]) -> bool:
    """Обновление тегов промта"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE prompts
            SET tags = ?
            WHERE id = ?
        """, (tags, prompt_id))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Ошибка при обновлении тегов промта: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def update_prompt(prompt_id: int, prompt_text: str, tags: Optional[str] = None) -> bool:
    """Обновление промта (текст и теги)"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE prompts
            SET prompt = ?, tags = ?
            WHERE id = ?
        """, (prompt_text, tags, prompt_id))
        conn.commit()
        updated = cursor.rowcount > 0
        if updated:
            logger.info(f"Обновлен промт с ID: {prompt_id}")
        return updated
    except sqlite3.Error as e:
        logger.error(f"Ошибка при обновлении промта: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_prompt(prompt_id: int) -> bool:
    """Удаление промта (CASCADE удалит связанные results)"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Удален промт с ID: {prompt_id}")
        return deleted
    except sqlite3.Error as e:
        logger.error(f"Ошибка при удалении промта: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


# ==================== Работа с таблицей models ====================

def get_all_models() -> List[Dict]:
    """Получение всех моделей"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, name, api_url, api_id, is_active, model_type, created_at
            FROM models
            ORDER BY name
        """)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_active_models() -> List[Dict]:
    """Получение только активных моделей"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, name, api_url, api_id, is_active, model_type, created_at
            FROM models
            WHERE is_active = 1
            ORDER BY name
        """)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def add_model(name: str, api_url: str, api_id: str, model_type: str, is_active: int = 1) -> int:
    """Добавление новой модели"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO models (name, api_url, api_id, model_type, is_active)
            VALUES (?, ?, ?, ?, ?)
        """, (name, api_url, api_id, model_type, is_active))
        conn.commit()
        model_id = cursor.lastrowid
        logger.info(f"Добавлена модель с ID: {model_id}")
        return model_id
    except sqlite3.IntegrityError as e:
        logger.error(f"Модель с таким именем уже существует: {e}")
        conn.rollback()
        raise
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении модели: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def update_model_status(model_id: int, is_active: int) -> bool:
    """Изменение статуса модели (активна/неактивна)"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE models
            SET is_active = ?
            WHERE id = ?
        """, (is_active, model_id))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Ошибка при обновлении статуса модели: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def update_model(model_id: int, name: str, api_url: str, api_id: str, model_type: str, is_active: int) -> bool:
    """Обновление всех параметров модели"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE models
            SET name = ?, api_url = ?, api_id = ?, model_type = ?, is_active = ?
            WHERE id = ?
        """, (name, api_url, api_id, model_type, is_active, model_id))
        conn.commit()
        updated = cursor.rowcount > 0
        if updated:
            logger.info(f"Обновлена модель с ID: {model_id}")
        return updated
    except sqlite3.IntegrityError as e:
        logger.error(f"Модель с таким именем уже существует: {e}")
        conn.rollback()
        raise
    except sqlite3.Error as e:
        logger.error(f"Ошибка при обновлении модели: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_model(model_id: int) -> bool:
    """Удаление модели (с проверкой связей через FOREIGN KEY)"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Проверка наличия связанных результатов
        cursor.execute("SELECT COUNT(*) as count FROM results WHERE model_id = ?", (model_id,))
        count = cursor.fetchone()["count"]
        if count > 0:
            logger.warning(f"Невозможно удалить модель: найдено {count} связанных результатов")
            return False

        cursor.execute("DELETE FROM models WHERE id = ?", (model_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Удалена модель с ID: {model_id}")
        return deleted
    except sqlite3.Error as e:
        logger.error(f"Ошибка при удалении модели: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def search_models(query: str) -> List[Dict]:
    """Поиск моделей по названию"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, name, api_url, api_id, is_active, model_type, created_at
            FROM models
            WHERE name LIKE ?
            ORDER BY name
        """, (f"%{query}%",))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


# ==================== Работа с таблицей results ====================

def save_result(prompt_id: int, model_id: int, response_text: str,
                tokens_used: Optional[int] = None, response_time: Optional[float] = None) -> int:
    """Сохранение результата"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO results (prompt_id, model_id, response_text, tokens_used, response_time)
            VALUES (?, ?, ?, ?, ?)
        """, (prompt_id, model_id, response_text, tokens_used, response_time))
        conn.commit()
        result_id = cursor.lastrowid
        logger.info(f"Сохранен результат с ID: {result_id}")
        return result_id
    except sqlite3.Error as e:
        logger.error(f"Ошибка при сохранении результата: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def save_multiple_results(results_list: List[Tuple[int, int, str, Optional[int], Optional[float]]]) -> int:
    """Массовое сохранение результатов (prompt_id, model_id, response_text, tokens_used, response_time)"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.executemany("""
            INSERT INTO results (prompt_id, model_id, response_text, tokens_used, response_time)
            VALUES (?, ?, ?, ?, ?)
        """, results_list)
        conn.commit()
        count = cursor.rowcount
        logger.info(f"Сохранено результатов: {count}")
        return count
    except sqlite3.Error as e:
        logger.error(f"Ошибка при массовом сохранении результатов: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def get_results_by_prompt(prompt_id: int) -> List[Dict]:
    """Получение всех результатов по промту"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT r.id, r.prompt_id, r.model_id, r.response_text, r.saved_at,
                   r.tokens_used, r.response_time, m.name as model_name
            FROM results r
            JOIN models m ON r.model_id = m.id
            WHERE r.prompt_id = ?
            ORDER BY r.saved_at DESC
        """, (prompt_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_all_results() -> List[Dict]:
    """Получение всех сохраненных результатов"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT r.id, r.prompt_id, r.model_id, r.response_text, r.saved_at,
                   r.tokens_used, r.response_time, m.name as model_name, p.prompt as prompt_text
            FROM results r
            JOIN models m ON r.model_id = m.id
            JOIN prompts p ON r.prompt_id = p.id
            ORDER BY r.saved_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def search_results(query: str) -> List[Dict]:
    """Поиск результатов по тексту ответа"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT r.id, r.prompt_id, r.model_id, r.response_text, r.saved_at,
                   r.tokens_used, r.response_time, m.name as model_name, p.prompt as prompt_text
            FROM results r
            JOIN models m ON r.model_id = m.id
            JOIN prompts p ON r.prompt_id = p.id
            WHERE r.response_text LIKE ?
            ORDER BY r.saved_at DESC
        """, (f"%{query}%",))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def delete_result(result_id: int) -> bool:
    """Удаление результата"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM results WHERE id = ?", (result_id,))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Ошибка при удалении результата: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_results_by_prompt(prompt_id: int) -> int:
    """Удаление всех результатов по промту"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM results WHERE prompt_id = ?", (prompt_id,))
        conn.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        logger.error(f"Ошибка при удалении результатов по промту: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


# ==================== Работа с таблицей settings ====================

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Получение настройки"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str) -> bool:
    """Установка настройки"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = ?
        """, (key, value, value))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при установке настройки: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def get_all_settings() -> Dict[str, str]:
    """Получение всех настроек"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT key, value FROM settings")
        return {row["key"]: row["value"] for row in cursor.fetchall()}
    finally:
        conn.close()

