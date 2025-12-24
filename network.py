"""
Модуль для отправки запросов к API через OpenRouter
Все модели используют единый API ключ OpenRouter
"""

import json
import logging
import time
import threading
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

