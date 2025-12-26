"""
Модуль для отправки запросов к API через OpenRouter
Все модели используют единый API ключ OpenRouter
"""

import json
import logging
import time
import threading
import re
from typing import Dict, Optional, List, Callable
import requests
from models import Model
from config import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Исключение для ошибок API"""
    pass


class APIResponse:
    """Класс для представления ответа от API"""

    def __init__(self, model_id: int, model_name: str, response_text: str,
                 tokens_used: Optional[int] = None, response_time: float = 0.0,
                 error: Optional[str] = None):
        self.model_id = model_id
        self.model_name = model_name
        self.response_text = response_text
        self.tokens_used = tokens_used
        self.response_time = response_time
        self.error = error
        self.success = error is None


def send_openai_request(api_key: str, model_name: str, prompt: str, api_url: Optional[str] = None) -> Dict:
    """
    Отправка запроса к OpenAI API (совместимо с DeepSeek)
    
    Args:
        api_key: API ключ
        model_name: Название модели (например, "gpt-4", "gpt-3.5-turbo")
        prompt: Текст промта
        api_url: URL API (по умолчанию OpenAI, можно переопределить для DeepSeek)
    
    Returns:
        Словарь с ответом от API
    """
    url = api_url or "https://api.openai.com/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        # Извлечение текста ответа
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        
        return {
            "text": content,
            "tokens_used": usage.get("total_tokens"),
            "raw_response": data
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса к OpenAI API: {e}")
        raise APIError(f"Ошибка запроса к API: {str(e)}")


def send_deepseek_request(api_key: str, prompt: str, api_url: Optional[str] = None) -> Dict:
    """
    Отправка запроса к DeepSeek API
    
    Args:
        api_key: API ключ DeepSeek
        prompt: Текст промта
        api_url: URL API DeepSeek
    
    Returns:
        Словарь с ответом от API
    """
    # DeepSeek использует тот же формат, что и OpenAI
    return send_openai_request(api_key, "deepseek-chat", prompt, 
                               api_url or "https://api.deepseek.com/v1/chat/completions")


def send_groq_request(api_key: str, model_name: str, prompt: str, api_url: Optional[str] = None) -> Dict:
    """
    Отправка запроса к Groq API
    
    Args:
        api_key: API ключ Groq
        model_name: Название модели (например, "llama3-8b-8192")
        prompt: Текст промта
        api_url: URL API Groq
    
    Returns:
        Словарь с ответом от API
    """
    # Groq использует OpenAI-совместимый API
    return send_openai_request(api_key, model_name, prompt,
                               api_url or "https://api.groq.com/openai/v1/chat/completions")


def send_openrouter_request(api_key: str, model_name: str, prompt: str, api_url: Optional[str] = None) -> Dict:
    """
    Отправка запроса к OpenRouter API
    
    Args:
        api_key: API ключ OpenRouter
        model_name: Название модели (например, "openai/gpt-4", "anthropic/claude-3.5-sonnet")
        prompt: Текст промта
        api_url: URL API OpenRouter
    
    Returns:
        Словарь с ответом от API
    """
    url = api_url or "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com",  # Опционально: URL вашего приложения
        "X-Title": "ChatList"  # Опционально: название вашего приложения
    }
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        # Извлечение текста ответа (OpenRouter использует OpenAI-совместимый формат)
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        
        return {
            "text": content,
            "tokens_used": usage.get("total_tokens"),
            "raw_response": data
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса к OpenRouter API: {e}")
        raise APIError(f"Ошибка запроса к API: {str(e)}")


def send_anthropic_request(api_key: str, prompt: str, api_url: Optional[str] = None) -> Dict:
    """
    Отправка запроса к Anthropic Claude API
    
    Args:
        api_key: API ключ Anthropic
        prompt: Текст промта
        api_url: URL API Anthropic
    
    Returns:
        Словарь с ответом от API
    """
    url = api_url or "https://api.anthropic.com/v1/messages"
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01"
    }
    
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 4096,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        # Извлечение текста ответа
        content = data["content"][0]["text"]
        usage = data.get("usage", {})
        
        return {
            "text": content,
            "tokens_used": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            "raw_response": data
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса к Anthropic API: {e}")
        raise APIError(f"Ошибка запроса к API: {str(e)}")


def send_prompt_to_model(model: Model, prompt: str) -> APIResponse:
    """
    Отправка промта в модель через OpenRouter
    
    Все модели используют единый API ключ OpenRouter
    
    Args:
        model: Объект модели (name содержит API имя модели, например "openai/gpt-4")
        prompt: Текст промта
    
    Returns:
        APIResponse объект с результатом
    """
    start_time = time.time()
    api_key = model.get_api_key()
    
    if not api_key:
        error_msg = "API ключ OPENROUTER_API_KEY не найден. Проверьте файл .env"
        logger.error(error_msg)
        return APIResponse(
            model_id=model.id,
            model_name=model.get_display_name(),
            response_text="",
            response_time=0.0,
            error=error_msg
        )
    
    try:
        # Все модели используют OpenRouter
        result = send_openrouter_request(api_key, model.name, prompt, model.api_url)
        
        response_time = time.time() - start_time
        
        logger.info(f"Успешный ответ от модели '{model.get_display_name()}' за {response_time:.2f}с")
        
        return APIResponse(
            model_id=model.id,
            model_name=model.get_display_name(),
            response_text=result["text"],
            tokens_used=result.get("tokens_used"),
            response_time=response_time
        )
    
    except APIError as e:
        response_time = time.time() - start_time
        error_msg = str(e)
        logger.error(f"Ошибка API для модели '{model.get_display_name()}': {error_msg}")
        return APIResponse(
            model_id=model.id,
            model_name=model.get_display_name(),
            response_text="",
            response_time=response_time,
            error=error_msg
        )
    except Exception as e:
        response_time = time.time() - start_time
        error_msg = f"Неожиданная ошибка: {str(e)}"
        logger.error(f"Неожиданная ошибка для модели '{model.get_display_name()}': {error_msg}")
        return APIResponse(
            model_id=model.id,
            model_name=model.get_display_name(),
            response_text="",
            response_time=response_time,
            error=error_msg
        )


def send_prompts_parallel(models: List[Model], prompt: str,
                         progress_callback: Optional[Callable[[int, int], None]] = None) -> List[APIResponse]:
    """
    Параллельная отправка промта в несколько моделей
    
    Args:
        models: Список моделей
        prompt: Текст промта
        progress_callback: Функция обратного вызова для прогресса (completed, total)
    
    Returns:
        Список APIResponse объектов
    """
    results: List[APIResponse] = []
    threads: List[threading.Thread] = []
    results_lock = threading.Lock()
    
    def send_to_model(model: Model):
        """Внутренняя функция для отправки в одну модель"""
        try:
            response = send_prompt_to_model(model, prompt)
            with results_lock:
                results.append(response)
                if progress_callback:
                    progress_callback(len(results), len(models))
        except Exception as e:
            logger.error(f"Исключение при отправке в модель '{model.name}': {e}")
            error_response = APIResponse(
                model_id=model.id,
                model_name=model.name,
                response_text="",
                response_time=0.0,
                error=f"Исключение: {str(e)}"
            )
            with results_lock:
                results.append(error_response)
                if progress_callback:
                    progress_callback(len(results), len(models))
    
    # Запуск потоков для каждой модели
    for model in models:
        thread = threading.Thread(target=send_to_model, args=(model,))
        thread.daemon = True
        threads.append(thread)
        thread.start()
    
    # Ожидание завершения всех потоков
    for thread in threads:
        thread.join()
    
    logger.info(f"Завершена параллельная отправка в {len(models)} моделей. Получено ответов: {len(results)}")
    return results


# ==================== Функции для улучшения промтов ====================

class PromptImprovementResult:
    """Класс для хранения результатов улучшения промта"""
    
    def __init__(self, original_prompt: str, improved_prompt: str = "", 
                 alternatives: Optional[List[str]] = None,
                 code_version: Optional[str] = None,
                 analysis_version: Optional[str] = None,
                 creative_version: Optional[str] = None,
                 model_name: str = "",
                 error: Optional[str] = None):
        self.original_prompt = original_prompt
        self.improved_prompt = improved_prompt
        self.alternatives = alternatives or []
        self.code_version = code_version
        self.analysis_version = analysis_version
        self.creative_version = creative_version
        self.model_name = model_name
        self.error = error
        self.success = error is None


def create_improvement_prompt(original_prompt: str, include_adaptations: bool = True) -> str:
    """
    Создание промпта для улучшения исходного промта
    
    Args:
        original_prompt: Исходный промт для улучшения
        include_adaptations: Включать ли адаптированные версии для разных типов задач
    
    Returns:
        Текст промпта для отправки модели
    """
    base_prompt = f"""Ты эксперт по созданию и оптимизации промптов для AI-моделей. Твоя задача - улучшить следующий промт, сделав его более четким, эффективным и результативным.

Исходный промт:
"{original_prompt}"

Пожалуйста, предоставь улучшенную версию промта и выполни следующие задачи:

1. Улучшенная версия: Создай оптимизированную версию промта, которая:
   - Более четко формулирует задачу
   - Включает важные детали и контекст
   - Использует эффективные техники промптинга
   - Сохраняет исходный смысл и цель

2. Альтернативные варианты: Предоставь 2-3 альтернативных варианта переформулировки, каждый с разным подходом или акцентом.

3. Адаптированные версии (если применимо):"""
    
    if include_adaptations:
        base_prompt += """
   - Версия для задач программирования: Адаптируй промт для работы с кодом, отладкой, рефакторингом
   - Версия для аналитических задач: Адаптируй промт для анализа данных, исследований, сравнений
   - Версия для креативных задач: Адаптируй промт для творческих задач, генерации идей, контента"""
    
    base_prompt += """

Формат ответа (используй JSON для структурированного ответа):
{
  "improved": "улучшенная версия промта",
  "alternatives": ["вариант 1", "вариант 2", "вариант 3"],
  "code_version": "версия для программирования (если применимо)",
  "analysis_version": "версия для анализа (если применимо)",
  "creative_version": "версия для креатива (если применимо)"
}

Если JSON формат недоступен, используй структурированный текст с четкими разделами."""
    
    return base_prompt


def create_code_optimization_prompt(prompt: str) -> str:
    """Создание промпта для оптимизации промта под задачи программирования"""
    return f"""Ты эксперт по созданию промптов для AI-моделей, специализирующихся на программировании.

Исходный промт:
"{prompt}"

Адаптируй этот промт специально для задач программирования. Промт должен:
- Четко указывать язык программирования и технологии
- Включать требования к стилю кода и лучшим практикам
- Указывать ожидаемый формат ответа (код, объяснение, примеры)
- Учитывать специфику работы с кодом (отладка, оптимизация, рефакторинг)

Предоставь улучшенную версию промта, оптимизированную для программирования."""


def create_analysis_optimization_prompt(prompt: str) -> str:
    """Создание промпта для оптимизации промта под аналитические задачи"""
    return f"""Ты эксперт по созданию промптов для AI-моделей, специализирующихся на анализе данных и исследованиях.

Исходный промт:
"{prompt}"

Адаптируй этот промт специально для аналитических задач. Промт должен:
- Четко определять объект анализа и цели исследования
- Указывать требуемый формат вывода (таблицы, графики, выводы)
- Включать требования к глубине анализа и источникам данных
- Учитывать необходимость сравнений, статистики, выводов

Предоставь улучшенную версию промта, оптимизированную для аналитических задач."""


def create_creative_optimization_prompt(prompt: str) -> str:
    """Создание промпта для оптимизации промта под креативные задачи"""
    return f"""Ты эксперт по созданию промптов для AI-моделей, специализирующихся на творческих задачах.

Исходный промт:
"{prompt}"

Адаптируй этот промт специально для креативных задач. Промт должен:
- Включать описание желаемого стиля, тона, настроения
- Указывать целевую аудиторию и контекст использования
- Стимулировать креативность и оригинальность
- Учитывать формат и структуру желаемого результата

Предоставь улучшенную версию промта, оптимизированную для креативных задач."""


def improve_prompt_via_model(model: Model, original_prompt: str, 
                            include_adaptations: bool = True) -> PromptImprovementResult:
    """
    Отправка запроса на улучшение промта через указанную модель
    
    Args:
        model: Модель для улучшения промта
        original_prompt: Исходный промт для улучшения
        include_adaptations: Включать ли адаптированные версии
    
    Returns:
        PromptImprovementResult объект с результатами
    """
    if not original_prompt or not original_prompt.strip():
        return PromptImprovementResult(
            original_prompt=original_prompt,
            model_name=model.get_display_name(),
            error="Исходный промт пуст"
        )
    
    try:
        improvement_prompt = create_improvement_prompt(original_prompt, include_adaptations)
        api_key = model.get_api_key()
        
        if not api_key:
            return PromptImprovementResult(
                original_prompt=original_prompt,
                model_name=model.get_display_name(),
                error="API ключ OPENROUTER_API_KEY не найден. Проверьте файл .env"
            )
        
        # Отправка запроса через OpenRouter
        result = send_openrouter_request(api_key, model.name, improvement_prompt, model.api_url)
        response_text = result.get("text", "")
        
        # Парсинг ответа
        improvement_result = parse_improvement_response(
            response_text, original_prompt, model.get_display_name()
        )
        
        logger.info(f"Успешно улучшен промт через модель '{model.get_display_name()}'")
        return improvement_result
        
    except APIError as e:
        error_msg = f"Ошибка API: {str(e)}"
        logger.error(f"Ошибка при улучшении промта: {error_msg}")
        return PromptImprovementResult(
            original_prompt=original_prompt,
            model_name=model.get_display_name(),
            error=error_msg
        )
    except Exception as e:
        error_msg = f"Неожиданная ошибка: {str(e)}"
        logger.error(f"Неожиданная ошибка при улучшении промта: {error_msg}")
        return PromptImprovementResult(
            original_prompt=original_prompt,
            model_name=model.get_display_name(),
            error=error_msg
        )


def parse_improvement_response(response_text: str, original_prompt: str, 
                               model_name: str) -> PromptImprovementResult:
    """
    Парсинг ответа от модели на запрос улучшения промта
    
    Args:
        response_text: Текст ответа от модели
        original_prompt: Исходный промт
        model_name: Название модели
    
    Returns:
        PromptImprovementResult объект
    """
    result = PromptImprovementResult(
        original_prompt=original_prompt,
        model_name=model_name
    )
    
    if not response_text or not response_text.strip():
        result.error = "Пустой ответ от модели"
        return result
    
    # Попытка парсинга JSON
    json_match = re.search(r'\{[^{}]*"improved"[^{}]*\}', response_text, re.DOTALL)
    if json_match:
        try:
            json_str = json_match.group(0)
            data = json.loads(json_str)
            
            result.improved_prompt = data.get("improved", "").strip()
            result.alternatives = [alt.strip() for alt in data.get("alternatives", []) if alt.strip()]
            result.code_version = data.get("code_version", "").strip() or None
            result.analysis_version = data.get("analysis_version", "").strip() or None
            result.creative_version = data.get("creative_version", "").strip() or None
            
            if result.improved_prompt:
                return result
        except json.JSONDecodeError:
            logger.warning("Не удалось распарсить JSON в ответе, пробуем текстовый парсинг")
    
    # Текстовый парсинг
    # Ищем улучшенную версию
    improved_patterns = [
        r'(?:улучшенная версия|improved|улучшенный промт)[:\-]?\s*\n?\s*(.+?)(?:\n\n|\n(?:альтернатив|alternative|вариант|code_version|analysis_version|creative_version|$))',
        r'1\.\s*(?:улучшенная версия|improved)[:\-]?\s*\n?\s*(.+?)(?:\n\n|\n2\.)',
        r'##?\s*(?:улучшенная версия|improved)[:\-]?\s*\n?\s*(.+?)(?:\n\n##?|$)',
    ]
    
    for pattern in improved_patterns:
        match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
        if match:
            result.improved_prompt = match.group(1).strip()
            break
    
    # Если не нашли улучшенную версию, берем первые несколько абзацев
    if not result.improved_prompt:
        lines = [line.strip() for line in response_text.split('\n') if line.strip()]
        if lines:
            # Берем первые 3-5 строк как улучшенную версию
            result.improved_prompt = '\n'.join(lines[:5])
    
    # Ищем альтернативные варианты
    alternatives_patterns = [
        r'(?:альтернатив|alternative|вариант)[:\-]?\s*\n?\s*(.+?)(?:\n\n|\n(?:code_version|analysis_version|creative_version|$))',
        r'2\.\s*(?:альтернатив|alternative)[:\-]?\s*\n?\s*(.+?)(?:\n\n|\n3\.)',
        r'##?\s*(?:альтернатив|alternative)[:\-]?\s*\n?\s*(.+?)(?:\n\n##?|$)',
    ]
    
    for pattern in alternatives_patterns:
        match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
        if match:
            alt_text = match.group(1).strip()
            # Разбиваем на варианты по маркерам списка
            alternatives = re.split(r'\n\s*[-*•]\s*|\n\s*\d+\.\s*', alt_text)
            result.alternatives = [alt.strip() for alt in alternatives if alt.strip()][:3]
            break
    
    # Ищем адаптированные версии
    code_match = re.search(r'(?:code_version|версия для.*программирования|для.*код)[:\-]?\s*\n?\s*(.+?)(?:\n\n|\n(?:analysis_version|creative_version|$))', 
                          response_text, re.IGNORECASE | re.DOTALL)
    if code_match:
        result.code_version = code_match.group(1).strip()
    
    analysis_match = re.search(r'(?:analysis_version|версия для.*анализ)[:\-]?\s*\n?\s*(.+?)(?:\n\n|\n(?:creative_version|$))', 
                              response_text, re.IGNORECASE | re.DOTALL)
    if analysis_match:
        result.analysis_version = analysis_match.group(1).strip()
    
    creative_match = re.search(r'(?:creative_version|версия для.*креатив|творческ)[:\-]?\s*\n?\s*(.+?)(?:\n\n|$)', 
                              response_text, re.IGNORECASE | re.DOTALL)
    if creative_match:
        result.creative_version = creative_match.group(1).strip()
    
    # Валидация результата
    if not result.improved_prompt:
        result.error = "Не удалось извлечь улучшенную версию промта из ответа модели"
    
    return result

