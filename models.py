"""
Модуль для работы с моделями нейросетей
Управление списком моделей и получение API-ключей
"""

import os
import logging
from typing import List, Dict, Optional
from dotenv import load_dotenv
from config import ENV_FILE_PATH
import db

logger = logging.getLogger(__name__)

# Загрузка переменных окружения из .env файла
load_dotenv(ENV_FILE_PATH)


class Model:
    """Класс для представления модели нейросети"""

    def __init__(self, model_data: Dict):
        """Инициализация модели из словаря данных БД"""
        self.id = model_data["id"]
        self.name = model_data["name"]  # API имя модели (например "openai/gpt-4")
        self.api_url = model_data["api_url"]
        self.api_id = model_data["api_id"]
        self.is_active = bool(model_data["is_active"])
        self.model_type = model_data.get("model_type", "")
        self.created_at = model_data.get("created_at", "")

    def get_display_name(self) -> str:
        """
        Получить читаемое имя модели для отображения
        Преобразует API имя (например "openai/gpt-4") в читаемый формат
        """
        if "/" in self.name:
            parts = self.name.split("/", 1)
            provider = parts[0]
            model_name = parts[1]
            
            # Преобразование имен моделей
            if model_name.startswith("gpt"):
                # GPT-4 -> GPT-4, gpt-3.5-turbo -> GPT-3.5 Turbo
                parts = model_name.replace("gpt-", "").split("-")
                if len(parts) == 1:
                    model_display = f"GPT-{parts[0]}"
                else:
                    version = parts[0].upper()
                    rest = " ".join(word.capitalize() for word in parts[1:])
                    model_display = f"GPT-{version} {rest}"
            elif model_name.startswith("claude"):
                # Для Claude убираем префикс "claude-" если есть
                clean_name = model_name.replace("claude-", "").replace("-", " ")
                model_display = f"Claude {clean_name.title()}"
            elif model_name.startswith("gemini"):
                model_display = model_name.replace("-", " ").title()
            elif model_name.startswith("deepseek"):
                model_display = model_name.replace("-", " ").title()
            elif model_name.startswith("llama"):
                model_display = model_name.replace("-", " ").title()
            else:
                model_display = model_name.replace("-", " ").title()
            
            return model_display
        return self.name

    def get_api_key(self) -> Optional[str]:
        """
        Получить API-ключ модели из переменных окружения
        Все модели используют OPENROUTER_API_KEY
        """
        return get_api_key("OPENROUTER_API_KEY")

    def __repr__(self):
        return f"Model(id={self.id}, name='{self.name}', type='{self.model_type}', active={self.is_active})"


class ModelManager:
    """Менеджер для управления моделями нейросетей"""

    def __init__(self):
        """Инициализация менеджера моделей"""
        self._models_cache: Optional[List[Model]] = None
        self._active_models_cache: Optional[List[Model]] = None

    def load_models(self, force_reload: bool = False) -> List[Model]:
        """Загрузка всех моделей из БД с кэшированием"""
        if self._models_cache is None or force_reload:
            models_data = db.get_all_models()
            self._models_cache = [Model(model_data) for model_data in models_data]
            logger.info(f"Загружено моделей: {len(self._models_cache)}")
        return self._models_cache

    def get_active_models(self, force_reload: bool = False) -> List[Model]:
        """Получить только активные модели с кэшированием"""
        if self._active_models_cache is None or force_reload:
            models_data = db.get_active_models()
            self._active_models_cache = [Model(model_data) for model_data in models_data]
            logger.info(f"Загружено активных моделей: {len(self._active_models_cache)}")
        return self._active_models_cache

    def get_model_by_id(self, model_id: int) -> Optional[Model]:
        """Получить модель по ID"""
        models = self.load_models()
        for model in models:
            if model.id == model_id:
                return model
        return None

    def get_model_by_name(self, name: str) -> Optional[Model]:
        """Получить модель по имени"""
        models = self.load_models()
        for model in models:
            if model.name == name:
                return model
        return None

    def invalidate_cache(self):
        """Сброс кэша моделей (вызывать после изменения моделей в БД)"""
        self._models_cache = None
        self._active_models_cache = None
        logger.debug("Кэш моделей сброшен")

    def validate_api_keys(self, models: Optional[List[Model]] = None) -> Dict[int, bool]:
        """
        Валидация наличия API-ключа для моделей
        Все модели используют OPENROUTER_API_KEY
        Возвращает словарь {model_id: has_key}
        """
        if models is None:
            models = self.get_active_models()

        # Проверяем один раз наличие OPENROUTER_API_KEY
        api_key = get_api_key("OPENROUTER_API_KEY")
        has_key = api_key is not None and api_key.strip() != ""
        
        if not has_key:
            logger.warning("Отсутствует API-ключ OPENROUTER_API_KEY. Проверьте файл .env")

        # Все модели имеют одинаковый результат валидации
        validation_result = {model.id: has_key for model in models}
        return validation_result


# Глобальный экземпляр менеджера моделей
_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Получить глобальный экземпляр менеджера моделей"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager


def get_api_key(api_id: str) -> Optional[str]:
    """
    Получить API-ключ по имени переменной окружения
    
    Args:
        api_id: Имя переменной окружения (например, "OPENAI_API_KEY")
    
    Returns:
        Значение переменной окружения или None, если не найдено
    """
    api_key = os.getenv(api_id)
    if api_key:
        return api_key.strip()
    return None


def validate_api_keys_for_active_models() -> Dict[int, bool]:
    """Валидация наличия API-ключей для всех активных моделей"""
    manager = get_model_manager()
    return manager.validate_api_keys()


def get_models_with_valid_keys() -> List[Model]:
    """Получить список активных моделей с валидными API-ключами"""
    manager = get_model_manager()
    active_models = manager.get_active_models()
    validation = manager.validate_api_keys(active_models)
    
    return [model for model in active_models if validation.get(model.id, False)]

