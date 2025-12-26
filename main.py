"""
Главное окно приложения ChatList
GUI интерфейс для отправки промтов в несколько нейросетей и сравнения результатов
"""

import sys
import logging
import sqlite3
import json
import markdown
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QLabel, QComboBox, QProgressBar, QMessageBox, QCheckBox, QSplitter,
    QLineEdit, QMenuBar, QMenu, QStatusBar, QAbstractItemView, QDialog,
    QDialogButtonBox, QFormLayout, QGroupBox, QFileDialog, QPlainTextEdit,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle, QTabWidget, QListWidget,
    QListWidgetItem
)
from PyQt5.QtGui import QClipboard, QPainter, QFontMetrics
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QRect
from PyQt5.QtGui import QFont

import db
import models
import network
import requests
from config import DATABASE_PATH

# Настройка логирования
def setup_logging():
    """Настройка логирования с сохранением в файл"""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"chatlist_{datetime.now().strftime('%Y%m%d')}.log"
    
    # Формат логов
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Настройка root logger
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

logger = setup_logging()


class ModelComboBoxDelegate(QStyledItemDelegate):
    """Делегат для отображения моделей в QComboBox с двумя столбцами: название и стоимость"""
    
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """Отрисовка элемента с двумя столбцами"""
        # Рисуем фон
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        
        # Получаем данные модели
        model_data = index.data(Qt.UserRole)
        if not model_data:
            # Если нет данных модели, отображаем обычный текст
            super().paint(painter, option, index)
            return
        
        model_name = model_data.get('name', '')
        model_id = model_data.get('id', '')
        pricing = model_data.get('pricing', 'не указана')
        
        # Формируем текст для отображения
        name_text = f"{model_name} ({model_id})"
        
        # Определяем цвета
        if option.state & QStyle.State_Selected:
            text_color = option.palette.highlightedText().color()
        else:
            text_color = option.palette.text().color()
        
        painter.setPen(text_color)
        
        # Вычисляем размеры
        rect = option.rect
        padding = 5
        font_metrics = painter.fontMetrics()
        
        # Рисуем название слева
        name_rect = QRect(rect.left() + padding, rect.top(), 
                         rect.width() // 2, rect.height())
        painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter, name_text)
        
        # Рисуем стоимость справа (серым цветом)
        pricing_color = text_color
        if not (option.state & QStyle.State_Selected):
            pricing_color = text_color.darker(150)  # Чуть темнее для выделения
        
        painter.setPen(pricing_color)
        pricing_rect = QRect(rect.left() + rect.width() // 2, rect.top(),
                            rect.width() // 2 - padding, rect.height())
        painter.drawText(pricing_rect, Qt.AlignRight | Qt.AlignVCenter, pricing)
    
    def sizeHint(self, option: QStyleOptionViewItem, index):
        """Вычисление размера элемента"""
        base_size = super().sizeHint(option, index)
        # Увеличиваем ширину для двух столбцов
        return base_size


def get_openrouter_models() -> List[Dict]:
    """Получение списка доступных моделей из OpenRouter API"""
    try:
        logger.info("Запрос списка моделей к OpenRouter API...")
        response = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Получен ответ от API, статус: {response.status_code}")
        
        models_data = data.get("data", [])
        logger.info(f"Количество моделей в ответе: {len(models_data)}")
        
        if not models_data:
            logger.warning("Ответ API не содержит данных о моделях")
            return []
        
        models_list = []
        for model_data in models_data:
            model_id = model_data.get("id", "")
            if not model_id:
                continue
                
            pricing = model_data.get("pricing", {})
            
            # Формируем информацию о стоимости
            pricing_info = "не указана"
            if pricing:
                prompt_price = pricing.get("prompt")
                completion_price = pricing.get("completion")
                if prompt_price is not None or completion_price is not None:
                    # Преобразуем цены в числа, если они строки
                    try:
                        prompt_price_float = float(prompt_price) if prompt_price is not None else None
                        completion_price_float = float(completion_price) if completion_price is not None else None
                        
                        prompt_str = f"${prompt_price_float:.6f}".rstrip('0').rstrip('.') if prompt_price_float is not None else "не указана"
                        completion_str = f"${completion_price_float:.6f}".rstrip('0').rstrip('.') if completion_price_float is not None else "не указана"
                        pricing_info = f"Вход: {prompt_str}/1M токенов, Выход: {completion_str}/1M токенов"
                    except (ValueError, TypeError):
                        # Если не удалось преобразовать, используем значения как есть
                        prompt_str = str(prompt_price) if prompt_price is not None else "не указана"
                        completion_str = str(completion_price) if completion_price is not None else "не указана"
                        pricing_info = f"Вход: ${prompt_str}/1M токенов, Выход: ${completion_str}/1M токенов"
            
            # Сохраняем исходные числовые значения цен для фильтрации
            prompt_price_num = None
            completion_price_num = None
            if pricing:
                try:
                    prompt_price = pricing.get("prompt")
                    completion_price = pricing.get("completion")
                    prompt_price_num = float(prompt_price) if prompt_price is not None else None
                    completion_price_num = float(completion_price) if completion_price is not None else None
                except (ValueError, TypeError):
                    pass
            
            models_list.append({
                "id": model_id,
                "name": model_data.get("name", model_id),
                "pricing": pricing_info,
                "pricing_prompt": prompt_price_num,  # Числовое значение входной цены
                "pricing_completion": completion_price_num,  # Числовое значение выходной цены
                "context_length": model_data.get("context_length", 0),
                "architecture": model_data.get("architecture", {}),
            })
        
        sorted_models = sorted(models_list, key=lambda x: x["name"])
        logger.info(f"Обработано {len(sorted_models)} моделей")
        return sorted_models
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при получении списка моделей OpenRouter: {e}")
        return []
    except Exception as e:
        logger.error(f"Ошибка при получении списка моделей OpenRouter: {e}", exc_info=True)
        return []


class RequestThread(QThread):
    """Поток для выполнения запросов к API"""
    progress = pyqtSignal(int, int)  # completed, total
    finished = pyqtSignal(list)  # список APIResponse
    
    def __init__(self, models_list: List[models.Model], prompt: str):
        super().__init__()
        self.models_list = models_list
        self.prompt = prompt
    
    def run(self):
        """Выполнение запросов"""
        def progress_callback(completed, total):
            self.progress.emit(completed, total)
        
        results = network.send_prompts_parallel(
            self.models_list,
            self.prompt,
            progress_callback
        )
        self.finished.emit(results)


class ModelEditDialog(QDialog):
    """Диалог для добавления/редактирования модели"""
    
    # Классовые переменные для сохранения настроек фильтрации
    _last_name_filter: str = ""
    _last_pricing_filter: str = ""
    
    def __init__(self, parent=None, model_data: Optional[Dict] = None):
        super().__init__(parent)
        self.model_data = model_data
        self.openrouter_models: List[Dict] = []
        self.setWindowTitle("Редактировать модель" if model_data else "Добавить модель")
        self.setModal(True)
        self.init_ui()
        
        if model_data:
            self.load_model_data()
    
    def init_ui(self):
        """Инициализация интерфейса диалога"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Форма
        form_group = QGroupBox("Параметры модели")
        form_layout = QFormLayout()
        form_group.setLayout(form_layout)
        
        # Название модели (API имя, например "openai/gpt-4")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("openai/gpt-4")
        form_layout.addRow("Название модели (API имя):", self.name_input)
        
        # API URL
        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("https://openrouter.ai/api/v1/chat/completions")
        form_layout.addRow("API URL:", self.api_url_input)
        
        # API ID (имя переменной окружения)
        self.api_id_input = QLineEdit()
        self.api_id_input.setPlaceholderText("OPENROUTER_API_KEY")
        form_layout.addRow("API ID (переменная окружения):", self.api_id_input)
        
        # Тип модели
        self.model_type_combo = QComboBox()
        self.model_type_combo.addItems(["openrouter", "openai", "deepseek", "groq", "anthropic"])
        self.model_type_combo.currentTextChanged.connect(self.on_model_type_changed)
        form_layout.addRow("Тип модели:", self.model_type_combo)
        
        # Фильтры для моделей OpenRouter (только для типа openrouter)
        self.model_name_filter_input = QLineEdit()
        self.model_name_filter_input.setPlaceholderText("Фильтр по названию модели...")
        self.model_name_filter_input.setVisible(False)
        # Восстанавливаем последнее значение фильтра
        self.model_name_filter_input.setText(ModelEditDialog._last_name_filter)
        self.model_name_filter_input.textChanged.connect(self.apply_model_filters)
        form_layout.addRow("Фильтр по названию:", self.model_name_filter_input)
        
        self.model_pricing_filter_input = QLineEdit()
        self.model_pricing_filter_input.setPlaceholderText("Фильтр по стоимости (например: $0.001, <$1, >$0)")
        self.model_pricing_filter_input.setVisible(False)
        # Восстанавливаем последнее значение фильтра
        self.model_pricing_filter_input.setText(ModelEditDialog._last_pricing_filter)
        self.model_pricing_filter_input.textChanged.connect(self.apply_model_filters)
        form_layout.addRow("Фильтр по стоимости:", self.model_pricing_filter_input)
        
        # Выбор модели из OpenRouter (только для типа openrouter)
        self.model_select_combo = QComboBox()
        self.model_select_combo.setVisible(False)
        self.model_select_combo.setItemDelegate(ModelComboBoxDelegate(self.model_select_combo))
        self.model_select_combo.setMinimumWidth(600)  # Увеличиваем ширину для отображения двух столбцов
        self.model_select_combo.currentIndexChanged.connect(self.on_openrouter_model_selected)
        self.model_select_combo.addItem("Загрузка моделей...", None)
        form_layout.addRow("Выберите модель:", self.model_select_combo)
        
        # Стоимость модели (только для чтения)
        self.pricing_label = QLabel("Стоимость: не указана")
        self.pricing_label.setVisible(False)
        self.pricing_label.setStyleSheet("color: #0066cc; font-weight: bold;")
        form_layout.addRow("Стоимость:", self.pricing_label)
        
        # Активна
        self.is_active_checkbox = QCheckBox("Модель активна")
        self.is_active_checkbox.setChecked(True)
        form_layout.addRow("", self.is_active_checkbox)
        
        layout.addWidget(form_group)
        
        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.on_reject)
        layout.addWidget(buttons)
        
        # Подсказка для OpenRouter
        hint_label = QLabel(
            "Примечание: Для моделей типа 'openrouter' используется\n"
            "единый ключ OPENROUTER_API_KEY независимо от значения API ID."
        )
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(hint_label)
        
        # Инициализация состояния для текущего типа модели
        self.on_model_type_changed(self.model_type_combo.currentText())
    
    def load_model_data(self):
        """Загрузка данных модели в форму"""
        if self.model_data:
            model_type = self.model_data.get("model_type", "openrouter")
            index = self.model_type_combo.findText(model_type)
            if index >= 0:
                self.model_type_combo.setCurrentIndex(index)
            
            # Загружаем модели OpenRouter если тип openrouter
            if model_type == "openrouter":
                self.load_openrouter_models()
            
            self.name_input.setText(self.model_data.get("name", ""))
            self.api_url_input.setText(self.model_data.get("api_url", ""))
            self.api_id_input.setText(self.model_data.get("api_id", ""))
            
            # Если модель OpenRouter, пытаемся найти её в списке и показать стоимость
            if model_type == "openrouter" and self.openrouter_models:
                model_name = self.model_data.get("name", "")
                for idx, model in enumerate(self.openrouter_models):
                    if model["id"] == model_name:
                        self.model_select_combo.setCurrentIndex(idx)
                        break
            
            self.is_active_checkbox.setChecked(bool(self.model_data.get("is_active", 1)))
            self.on_model_type_changed(model_type)
    
    def load_openrouter_models(self):
        """Загрузка списка моделей OpenRouter"""
        try:
            logger.info("Начинаю загрузку моделей OpenRouter...")
            self.openrouter_models = get_openrouter_models()
            logger.info(f"Загружено моделей: {len(self.openrouter_models)}")
            
            if not self.openrouter_models:
                logger.warning("Список моделей OpenRouter пуст")
                QMessageBox.warning(
                    self,
                    "Предупреждение",
                    "Не удалось загрузить список моделей OpenRouter.\n"
                    "Проверьте подключение к интернету.\n"
                    "Вы можете ввести название модели вручную."
                )
                return
            
            # После загрузки применяем фильтры для отображения
            self.apply_model_filters()
        except Exception as e:
            logger.error(f"Ошибка при загрузке моделей OpenRouter: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "Предупреждение",
                f"Не удалось загрузить список моделей OpenRouter: {str(e)}\n"
                "Проверьте подключение к интернету.\n"
                "Вы можете ввести название модели вручную."
            )
    
    def on_model_type_changed(self, model_type: str):
        """Обработка изменения типа модели"""
        is_openrouter = model_type == "openrouter"
        self.model_select_combo.setVisible(is_openrouter)
        self.pricing_label.setVisible(is_openrouter)
        self.model_name_filter_input.setVisible(is_openrouter)
        self.model_pricing_filter_input.setVisible(is_openrouter)
        
        if is_openrouter:
            # Если список моделей еще не загружен, загружаем его
            if not self.openrouter_models:
                logger.info("Загрузка моделей OpenRouter при изменении типа на openrouter")
                self.load_openrouter_models()
            else:
                # Если модели уже загружены, убеждаемся что они отображены
                logger.info(f"Модели OpenRouter уже загружены: {len(self.openrouter_models)} моделей")
                self.apply_model_filters()  # Применяем фильтры при переключении
        
        # Автоматически заполняем API URL и API ID для openrouter только если поля пустые
        if is_openrouter:
            if not self.api_url_input.text().strip():
                self.api_url_input.setText("https://openrouter.ai/api/v1/chat/completions")
            if not self.api_id_input.text().strip():
                self.api_id_input.setText("OPENROUTER_API_KEY")
    
    def on_openrouter_model_selected(self, index: int):
        """Обработка выбора модели из списка OpenRouter"""
        if index < 0:
            return
        
        model_data = self.model_select_combo.itemData(index)
        if model_data:
            # Сохраняем текущие значения фильтров
            ModelEditDialog._last_name_filter = self.model_name_filter_input.text()
            ModelEditDialog._last_pricing_filter = self.model_pricing_filter_input.text()
            
            # Заполняем название модели
            self.name_input.setText(model_data["id"])
            
            # Отображаем стоимость
            pricing_text = model_data.get("pricing", "не указана")
            self.pricing_label.setText(f"Стоимость: {pricing_text}")
            
            # Заполняем API URL и API ID
            self.api_url_input.setText("https://openrouter.ai/api/v1/chat/completions")
            self.api_id_input.setText("OPENROUTER_API_KEY")
    
    def apply_model_filters(self):
        """Применение фильтров к списку моделей OpenRouter"""
        if not self.openrouter_models:
            return
        
        # Получаем фильтры
        name_filter = self.model_name_filter_input.text().strip().lower()
        pricing_filter = self.model_pricing_filter_input.text().strip().lower()
        
        # Фильтруем модели
        filtered_models = []
        for model in self.openrouter_models:
            # Фильтр по названию - проверяем, что все слова из фильтра присутствуют
            if name_filter:
                model_name = model.get('name', '').lower()
                model_id = model.get('id', '').lower()
                # Разбиваем фильтр на слова
                filter_words = name_filter.split()
                # Проверяем, что все слова присутствуют либо в названии, либо в ID
                all_words_found = all(
                    word in model_name or word in model_id
                    for word in filter_words
                )
                if not all_words_found:
                    continue
            
            # Фильтр по стоимости
            if pricing_filter:
                if not self._check_pricing_filter(pricing_filter, model):
                    continue
            
            filtered_models.append(model)
        
        # Обновляем список в комбобоксе
        self.model_select_combo.clear()
        if filtered_models:
            for model in filtered_models:
                display_name = f"{model['name']} ({model['id']})"
                self.model_select_combo.addItem(display_name, model)
            logger.info(f"Отфильтровано моделей: {len(filtered_models)} из {len(self.openrouter_models)}")
        else:
            self.model_select_combo.addItem("Нет моделей, соответствующих фильтрам", None)
    
    def _check_pricing_filter(self, filter_text: str, model: Dict) -> bool:
        """Проверка соответствия модели фильтру стоимости"""
        if not filter_text:
            return True
        
        # Получаем числовые значения цен из модели (если доступны)
        prompt_price = model.get('pricing_prompt')
        completion_price = model.get('pricing_completion')
        
        # Если числовые значения недоступны, пытаемся извлечь из текста
        if prompt_price is None and completion_price is None:
            pricing_text = model.get('pricing', 'не указана').lower()
            if filter_text in ['0', 'free', 'бесплатно', 'не указана', 'н/д']:
                return 'не указана' in pricing_text or '0' in pricing_text
            # Если нет числовых значений, делаем текстовый поиск
            return filter_text in pricing_text
        
        # Парсим фильтр
        filter_value = None
        filter_operator = None
        
        # Проверяем операторы сравнения
        filter_text_clean = filter_text.strip()
        if filter_text_clean.startswith('<='):
            filter_operator = '<='
            try:
                filter_value = float(filter_text_clean[2:].replace('$', '').strip())
            except ValueError:
                return True  # Неверный формат - показываем все
        elif filter_text_clean.startswith('>='):
            filter_operator = '>='
            try:
                filter_value = float(filter_text_clean[2:].replace('$', '').strip())
            except ValueError:
                return True
        elif filter_text_clean.startswith('<'):
            filter_operator = '<'
            try:
                filter_value = float(filter_text_clean[1:].replace('$', '').strip())
            except ValueError:
                return True
        elif filter_text_clean.startswith('>'):
            filter_operator = '>'
            try:
                filter_value = float(filter_text_clean[1:].replace('$', '').strip())
            except ValueError:
                return True
        else:
            # Просто число - проверяем, меньше или равно максимальной цене
            try:
                filter_value = float(filter_text_clean.replace('$', '').strip())
                filter_operator = '<='
            except ValueError:
                # Текстовый поиск
                pricing_text = model.get('pricing', '').lower()
                return filter_text.lower() in pricing_text
        
        if filter_value is None:
            return True
        
        # Берем максимальную цену из входной и выходной
        prices = []
        if prompt_price is not None:
            prices.append(prompt_price)
        if completion_price is not None:
            prices.append(completion_price)
        
        if not prices:
            return False
        
        max_price = max(prices)
        
        # Выполняем сравнение
        if filter_operator == '<=':
            return max_price <= filter_value
        elif filter_operator == '>=':
            return max_price >= filter_value
        elif filter_operator == '<':
            return max_price < filter_value
        elif filter_operator == '>':
            return max_price > filter_value
        
        return False
    
    def get_model_data(self) -> Dict:
        """Получение данных модели из формы"""
        return {
            "name": self.name_input.text().strip(),
            "api_url": self.api_url_input.text().strip(),
            "api_id": self.api_id_input.text().strip(),
            "model_type": self.model_type_combo.currentText(),
            "is_active": 1 if self.is_active_checkbox.isChecked() else 0
        }
    
    def accept(self):
        """Валидация перед принятием"""
        # Сохраняем текущие значения фильтров перед закрытием
        ModelEditDialog._last_name_filter = self.model_name_filter_input.text()
        ModelEditDialog._last_pricing_filter = self.model_pricing_filter_input.text()
        
        data = self.get_model_data()
        
        if not data["name"]:
            QMessageBox.warning(self, "Ошибка", "Название модели не может быть пустым!")
            return
        
        if not data["api_url"]:
            QMessageBox.warning(self, "Ошибка", "API URL не может быть пустым!")
            return
        
        if not data["api_id"]:
            QMessageBox.warning(self, "Ошибка", "API ID не может быть пустым!")
            return
        
        super().accept()
    
    def on_reject(self):
        """Сохранение фильтров перед отклонением диалога"""
        # Сохраняем текущие значения фильтров перед закрытием
        ModelEditDialog._last_name_filter = self.model_name_filter_input.text()
        ModelEditDialog._last_pricing_filter = self.model_pricing_filter_input.text()
        self.reject()


class PromptEditDialog(QDialog):
    """Диалог для добавления/редактирования промта"""
    
    def __init__(self, parent=None, prompt_data: Optional[Dict] = None):
        super().__init__(parent)
        self.prompt_data = prompt_data
        self.setWindowTitle("Редактировать промт" if prompt_data else "Добавить промт")
        self.setModal(True)
        self.init_ui()
        
        if prompt_data:
            self.load_prompt_data()
    
    def init_ui(self):
        """Инициализация интерфейса диалога"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Форма
        form_group = QGroupBox("Параметры промта")
        form_layout = QFormLayout()
        form_group.setLayout(form_layout)
        
        # Текст промта
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("Введите текст промта...")
        self.prompt_input.setMinimumHeight(200)
        form_layout.addRow("Текст промта:", self.prompt_input)
        
        # Теги
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("тег1, тег2, ...")
        form_layout.addRow("Теги:", self.tags_input)
        
        layout.addWidget(form_group)
        
        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def load_prompt_data(self):
        """Загрузка данных промта в форму"""
        if self.prompt_data:
            self.prompt_input.setPlainText(self.prompt_data.get("prompt", ""))
            self.tags_input.setText(self.prompt_data.get("tags", "") or "")
    
    def get_prompt_data(self) -> Dict:
        """Получение данных промта из формы"""
        return {
            "prompt": self.prompt_input.toPlainText().strip(),
            "tags": self.tags_input.text().strip() or None
        }
    
    def accept(self):
        """Валидация перед принятием"""
        data = self.get_prompt_data()
        
        if not data["prompt"]:
            QMessageBox.warning(self, "Ошибка", "Текст промта не может быть пустым!")
            return
        
        super().accept()


class PromptManagementDialog(QDialog):
    """Диалог для управления промтами"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Управление промтами")
        self.setModal(True)
        self.setMinimumSize(1000, 600)
        self.all_prompts: List[Dict] = []  # Все промты для фильтрации
        self.init_ui()
        self.load_prompts()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Поиск и сортировка
        search_sort_layout = QHBoxLayout()
        search_sort_layout.addWidget(QLabel("Поиск:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по тексту и тегам...")
        self.search_input.textChanged.connect(self.on_search_changed)
        search_sort_layout.addWidget(self.search_input)
        
        search_sort_layout.addWidget(QLabel("Сортировка:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "По умолчанию", 
            "По ID", 
            "По дате", 
            "По тексту"
        ])
        self.sort_combo.currentIndexChanged.connect(self.on_sort_changed)
        search_sort_layout.addWidget(self.sort_combo)
        layout.addLayout(search_sort_layout)
        
        # Таблица промтов
        self.prompts_table = QTableWidget()
        self.prompts_table.setColumnCount(4)
        self.prompts_table.setHorizontalHeaderLabels([
            "ID", "Дата", "Промт (превью)", "Теги"
        ])
        
        # Настройка таблицы
        header = self.prompts_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Дата
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Промт
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Теги
        
        self.prompts_table.setAlternatingRowColors(True)
        self.prompts_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.prompts_table.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.prompts_table)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("Добавить")
        self.add_btn.clicked.connect(self.add_prompt)
        buttons_layout.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("Редактировать")
        self.edit_btn.clicked.connect(self.edit_prompt)
        buttons_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.clicked.connect(self.delete_prompt)
        buttons_layout.addWidget(self.delete_btn)
        
        buttons_layout.addStretch()
        
        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self.load_prompts)
        buttons_layout.addWidget(self.refresh_btn)
        
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(close_btn)
        
        layout.addLayout(buttons_layout)
    
    def load_prompts(self):
        """Загрузка списка промтов в таблицу"""
        self.all_prompts = db.get_all_prompts()
        self.apply_filter_and_sort()
    
    def apply_filter_and_sort(self):
        """Применение фильтра и сортировки к списку промтов"""
        # Фильтрация
        search_text = self.search_input.text().strip().lower()
        filtered_prompts = self.all_prompts
        
        if search_text:
            filtered_prompts = [
                prompt for prompt in self.all_prompts
                if (search_text in str(prompt.get("id", "")).lower() or
                    search_text in (prompt.get("prompt", "") or "").lower() or
                    search_text in (prompt.get("tags", "") or "").lower() or
                    search_text in str(prompt.get("date", "")).lower())
            ]
        
        # Сортировка
        sort_option = self.sort_combo.currentText()
        if sort_option == "По ID":
            filtered_prompts = sorted(filtered_prompts, key=lambda p: p.get("id", 0))
        elif sort_option == "По дате":
            filtered_prompts = sorted(filtered_prompts, key=lambda p: p.get("date", ""), reverse=True)
        elif sort_option == "По тексту":
            filtered_prompts = sorted(filtered_prompts, key=lambda p: (p.get("prompt", "") or "").lower())
        
        # Отображение в таблице
        self.prompts_table.setRowCount(len(filtered_prompts))
        
        for row, prompt in enumerate(filtered_prompts):
            # ID
            id_item = QTableWidgetItem(str(prompt.get("id", "")))
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            self.prompts_table.setItem(row, 0, id_item)
            
            # Дата
            date_value = prompt.get("date", "")
            if date_value:
                # Форматируем дату для отображения
                try:
                    if isinstance(date_value, str):
                        # Пытаемся преобразовать строку даты
                        date_obj = datetime.strptime(date_value, "%Y-%m-%d %H:%M:%S")
                        date_str = date_obj.strftime("%Y-%m-%d %H:%M")
                    else:
                        date_str = str(date_value)
                except:
                    date_str = str(date_value)
            else:
                date_str = ""
            date_item = QTableWidgetItem(date_str)
            date_item.setFlags(date_item.flags() & ~Qt.ItemIsEditable)
            self.prompts_table.setItem(row, 1, date_item)
            
            # Промт (превью)
            prompt_text = prompt.get("prompt", "") or ""
            # Ограничиваем длину для превью
            preview_text = prompt_text[:100] + "..." if len(prompt_text) > 100 else prompt_text
            prompt_item = QTableWidgetItem(preview_text)
            prompt_item.setFlags(prompt_item.flags() & ~Qt.ItemIsEditable)
            # Добавляем полный текст в tooltip
            prompt_item.setToolTip(prompt_text)
            self.prompts_table.setItem(row, 2, prompt_item)
            
            # Теги
            tags_item = QTableWidgetItem(prompt.get("tags", "") or "")
            tags_item.setFlags(tags_item.flags() & ~Qt.ItemIsEditable)
            self.prompts_table.setItem(row, 3, tags_item)
        
        self.prompts_table.resizeRowsToContents()
    
    def on_search_changed(self, text):
        """Обработка изменения поискового запроса"""
        self.apply_filter_and_sort()
    
    def on_sort_changed(self, index):
        """Обработка изменения сортировки"""
        self.apply_filter_and_sort()
    
    def get_selected_prompt_id(self) -> Optional[int]:
        """Получить ID выбранного промта"""
        current_row = self.prompts_table.currentRow()
        if current_row < 0:
            return None
        id_item = self.prompts_table.item(current_row, 0)
        if id_item:
            return int(id_item.text())
        return None
    
    def add_prompt(self):
        """Добавление нового промта"""
        dialog = PromptEditDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_prompt_data()
            try:
                prompt_id = db.create_prompt(data["prompt"], data["tags"])
                self.load_prompts()
                QMessageBox.information(self, "Успех", "Промт успешно добавлен!")
                logger.info(f"Добавлен промт с ID: {prompt_id}")
            except Exception as e:
                logger.error(f"Ошибка при добавлении промта: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось добавить промт: {str(e)}")
    
    def edit_prompt(self):
        """Редактирование выбранного промта"""
        prompt_id = self.get_selected_prompt_id()
        if not prompt_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите промт для редактирования!")
            return
        
        prompt_data = db.get_prompt_by_id(prompt_id)
        if not prompt_data:
            QMessageBox.warning(self, "Ошибка", "Промт не найден!")
            return
        
        dialog = PromptEditDialog(self, prompt_data)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_prompt_data()
            try:
                db.update_prompt(prompt_id, data["prompt"], data["tags"])
                self.load_prompts()
                QMessageBox.information(self, "Успех", "Промт успешно обновлен!")
                logger.info(f"Обновлен промт с ID: {prompt_id}")
            except Exception as e:
                logger.error(f"Ошибка при обновлении промта: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось обновить промт: {str(e)}")
    
    def delete_prompt(self):
        """Удаление выбранного промта"""
        prompt_id = self.get_selected_prompt_id()
        if not prompt_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите промт для удаления!")
            return
        
        prompt_data = db.get_prompt_by_id(prompt_id)
        if not prompt_data:
            QMessageBox.warning(self, "Ошибка", "Промт не найден!")
            return
        
        # Показываем превью промта в сообщении
        preview = prompt_data.get("prompt", "")[:50] + "..." if len(prompt_data.get("prompt", "")) > 50 else prompt_data.get("prompt", "")
        
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Вы уверены, что хотите удалить промт?\n\n"
            f"Превью: {preview}\n\n"
            "Внимание: Все связанные результаты также будут удалены.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                deleted = db.delete_prompt(prompt_id)
                if deleted:
                    self.load_prompts()
                    QMessageBox.information(self, "Успех", "Промт успешно удален!")
                    logger.info(f"Удален промт с ID: {prompt_id}")
                else:
                    QMessageBox.warning(
                        self,
                        "Ошибка",
                        "Не удалось удалить промт."
                    )
            except Exception as e:
                logger.error(f"Ошибка при удалении промта: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить промт: {str(e)}")


class SettingsDialog(QDialog):
    """Диалог настроек приложения"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.setMinimumSize(400, 250)
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Форма настроек
        form_group = QGroupBox("Внешний вид")
        form_layout = QFormLayout()
        form_group.setLayout(form_layout)
        
        # Выбор темы
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Светлая", "Темная"])
        form_layout.addRow("Тема:", self.theme_combo)
        
        # Выбор размера шрифта
        self.font_size_combo = QComboBox()
        font_sizes = ["8", "9", "10", "11", "12", "14", "16", "18", "20"]
        self.font_size_combo.addItems(font_sizes)
        form_layout.addRow("Размер шрифта:", self.font_size_combo)
        
        layout.addWidget(form_group)
        
        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def load_settings(self):
        """Загрузка текущих настроек"""
        theme = db.get_setting("theme", "light")
        if theme == "dark":
            self.theme_combo.setCurrentIndex(1)
        else:
            self.theme_combo.setCurrentIndex(0)
        
        font_size = db.get_setting("font_size", "10")
        index = self.font_size_combo.findText(font_size)
        if index >= 0:
            self.font_size_combo.setCurrentIndex(index)
    
    def get_settings(self) -> Dict[str, str]:
        """Получение настроек из формы"""
        theme = "dark" if self.theme_combo.currentIndex() == 1 else "light"
        font_size = self.font_size_combo.currentText()
        return {
            "theme": theme,
            "font_size": font_size
        }


class ModelManagementDialog(QDialog):
    """Диалог для управления моделями"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Управление моделями")
        self.setModal(True)
        self.setMinimumSize(900, 600)
        self.model_manager = models.get_model_manager()
        self.all_models: List[models.Model] = []  # Все модели для фильтрации
        self.init_ui()
        self.load_models()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Поиск и сортировка
        search_sort_layout = QHBoxLayout()
        search_sort_layout.addWidget(QLabel("Поиск:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по всем полям...")
        self.search_input.textChanged.connect(self.on_search_changed)
        search_sort_layout.addWidget(self.search_input)
        
        search_sort_layout.addWidget(QLabel("Сортировка:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "По умолчанию", 
            "По ID", 
            "По названию", 
            "По типу", 
            "По активности"
        ])
        self.sort_combo.currentIndexChanged.connect(self.on_sort_changed)
        search_sort_layout.addWidget(self.sort_combo)
        layout.addLayout(search_sort_layout)
        
        # Таблица моделей
        self.models_table = QTableWidget()
        self.models_table.setColumnCount(6)
        self.models_table.setHorizontalHeaderLabels([
            "ID", "Название", "API URL", "API ID", "Тип", "Активна"
        ])
        
        # Настройка таблицы
        header = self.models_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Название
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # API URL
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # API ID
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Тип
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Активна
        
        self.models_table.setAlternatingRowColors(True)
        self.models_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.models_table.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.models_table)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("Добавить")
        self.add_btn.clicked.connect(self.add_model)
        buttons_layout.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("Редактировать")
        self.edit_btn.clicked.connect(self.edit_model)
        buttons_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.clicked.connect(self.delete_model)
        buttons_layout.addWidget(self.delete_btn)
        
        buttons_layout.addStretch()
        
        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self.load_models)
        buttons_layout.addWidget(self.refresh_btn)
        
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(close_btn)
        
        layout.addLayout(buttons_layout)
    
    def load_models(self):
        """Загрузка списка моделей в таблицу"""
        self.all_models = self.model_manager.load_models(force_reload=True)
        self.apply_filter_and_sort()
    
    def apply_filter_and_sort(self):
        """Применение фильтра и сортировки к списку моделей"""
        # Фильтрация
        search_text = self.search_input.text().strip().lower()
        filtered_models = self.all_models
        
        if search_text:
            filtered_models = [
                model for model in self.all_models
                if (search_text in str(model.id).lower() or
                    search_text in model.name.lower() or
                    search_text in (model.api_url or "").lower() or
                    search_text in (model.api_id or "").lower() or
                    search_text in (model.model_type or "").lower() or
                    search_text in ("да" if model.is_active else "нет"))
            ]
        
        # Сортировка
        sort_option = self.sort_combo.currentText()
        if sort_option == "По ID":
            filtered_models = sorted(filtered_models, key=lambda m: m.id)
        elif sort_option == "По названию":
            filtered_models = sorted(filtered_models, key=lambda m: m.name.lower())
        elif sort_option == "По типу":
            filtered_models = sorted(filtered_models, key=lambda m: (m.model_type or "").lower())
        elif sort_option == "По активности":
            filtered_models = sorted(filtered_models, key=lambda m: (not m.is_active, m.name.lower()))
        
        # Отображение в таблице
        self.models_table.setRowCount(len(filtered_models))
        
        for row, model in enumerate(filtered_models):
            # ID
            id_item = QTableWidgetItem(str(model.id))
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            self.models_table.setItem(row, 0, id_item)
            
            # Название
            name_item = QTableWidgetItem(model.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.models_table.setItem(row, 1, name_item)
            
            # API URL
            url_item = QTableWidgetItem(model.api_url)
            url_item.setFlags(url_item.flags() & ~Qt.ItemIsEditable)
            self.models_table.setItem(row, 2, url_item)
            
            # API ID
            api_id_item = QTableWidgetItem(model.api_id)
            api_id_item.setFlags(api_id_item.flags() & ~Qt.ItemIsEditable)
            self.models_table.setItem(row, 3, api_id_item)
            
            # Тип
            type_item = QTableWidgetItem(model.model_type or "")
            type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
            self.models_table.setItem(row, 4, type_item)
            
            # Активна (чекбокс)
            checkbox = QCheckBox()
            checkbox.setChecked(model.is_active)
            checkbox.stateChanged.connect(
                lambda state, mid=model.id: self.on_active_changed(mid, state)
            )
            self.models_table.setCellWidget(row, 5, checkbox)
        
        self.models_table.resizeRowsToContents()
    
    def on_search_changed(self, text):
        """Обработка изменения поискового запроса"""
        self.apply_filter_and_sort()
    
    def on_sort_changed(self, index):
        """Обработка изменения сортировки"""
        self.apply_filter_and_sort()
    
    def on_active_changed(self, model_id: int, state: int):
        """Обработка изменения статуса активности"""
        is_active = 1 if state == Qt.Checked else 0
        try:
            db.update_model_status(model_id, is_active)
            self.model_manager.invalidate_cache()
            # Обновляем статус в локальном списке
            for model in self.all_models:
                if model.id == model_id:
                    model.is_active = bool(is_active)
                    break
            logger.info(f"Статус модели {model_id} изменен на {'активна' if is_active else 'неактивна'}")
            self.apply_filter_and_sort()  # Обновляем отображение с учетом фильтров
        except Exception as e:
            logger.error(f"Ошибка при изменении статуса модели: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось изменить статус модели: {str(e)}")
            self.load_models()  # Перезагрузка для отката изменений
    
    def get_selected_model_id(self) -> Optional[int]:
        """Получить ID выбранной модели"""
        current_row = self.models_table.currentRow()
        if current_row < 0:
            return None
        id_item = self.models_table.item(current_row, 0)
        if id_item:
            return int(id_item.text())
        return None
    
    def add_model(self):
        """Добавление новой модели"""
        dialog = ModelEditDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_model_data()
            try:
                db.add_model(
                    data["name"],
                    data["api_url"],
                    data["api_id"],
                    data["model_type"],
                    data["is_active"]
                )
                self.model_manager.invalidate_cache()
                self.load_models()
                QMessageBox.information(self, "Успех", "Модель успешно добавлена!")
                logger.info(f"Добавлена модель: {data['name']}")
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "Ошибка", "Модель с таким именем уже существует!")
            except Exception as e:
                logger.error(f"Ошибка при добавлении модели: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось добавить модель: {str(e)}")
    
    def edit_model(self):
        """Редактирование выбранной модели"""
        model_id = self.get_selected_model_id()
        if not model_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите модель для редактирования!")
            return
        
        model = self.model_manager.get_model_by_id(model_id)
        if not model:
            QMessageBox.warning(self, "Ошибка", "Модель не найдена!")
            return
        
        model_data = {
            "id": model.id,
            "name": model.name,
            "api_url": model.api_url,
            "api_id": model.api_id,
            "model_type": model.model_type,
            "is_active": 1 if model.is_active else 0
        }
        
        dialog = ModelEditDialog(self, model_data)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_model_data()
            try:
                db.update_model(
                    model_id,
                    data["name"],
                    data["api_url"],
                    data["api_id"],
                    data["model_type"],
                    data["is_active"]
                )
                self.model_manager.invalidate_cache()
                self.load_models()
                QMessageBox.information(self, "Успех", "Модель успешно обновлена!")
                logger.info(f"Обновлена модель: {data['name']}")
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "Ошибка", "Модель с таким именем уже существует!")
            except Exception as e:
                logger.error(f"Ошибка при обновлении модели: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось обновить модель: {str(e)}")
    
    def delete_model(self):
        """Удаление выбранной модели"""
        model_id = self.get_selected_model_id()
        if not model_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите модель для удаления!")
            return
        
        model = self.model_manager.get_model_by_id(model_id)
        if not model:
            QMessageBox.warning(self, "Ошибка", "Модель не найдена!")
            return
        
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Вы уверены, что хотите удалить модель '{model.name}'?\n\n"
            "Внимание: Модель с сохраненными результатами не может быть удалена.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                deleted = db.delete_model(model_id)
                if deleted:
                    self.model_manager.invalidate_cache()
                    self.load_models()
                    QMessageBox.information(self, "Успех", "Модель успешно удалена!")
                    logger.info(f"Удалена модель: {model.name}")
                else:
                    QMessageBox.warning(
                        self,
                        "Ошибка",
                        "Не удалось удалить модель.\n"
                        "Возможно, у неё есть сохраненные результаты."
                    )
            except Exception as e:
                logger.error(f"Ошибка при удалении модели: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить модель: {str(e)}")


class MarkdownViewDialog(QDialog):
    """Диалог для просмотра ответа в форматированном markdown"""
    
    def __init__(self, parent=None, model_name: str = "", response_text: str = ""):
        super().__init__(parent)
        self.setWindowTitle(f"Ответ: {model_name}")
        self.setModal(True)
        self.setMinimumSize(800, 600)
        self.original_text = response_text  # Сохраняем оригинальный текст для копирования
        self.init_ui(model_name, response_text)
    
    def init_ui(self, model_name: str, response_text: str):
        """Инициализация интерфейса диалога"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок с названием модели
        header_label = QLabel(f"<h2>Ответ модели: {model_name}</h2>")
        layout.addWidget(header_label)
        
        # Текстовое поле для отображения markdown
        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        
        # Конвертация markdown в HTML
        try:
            html_content = markdown.markdown(
                response_text,
                extensions=['extra', 'codehilite', 'nl2br', 'sane_lists']
            )
            # Добавляем стили для улучшения отображения
            styled_html = f"""
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    font-size: 14px;
                    line-height: 1.6;
                    color: #333;
                    padding: 10px;
                }}
                pre {{
                    background-color: #f5f5f5;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    padding: 10px;
                    overflow-x: auto;
                }}
                code {{
                    background-color: #f5f5f5;
                    padding: 2px 4px;
                    border-radius: 3px;
                    font-family: 'Courier New', monospace;
                }}
                pre code {{
                    background-color: transparent;
                    padding: 0;
                }}
                h1, h2, h3, h4, h5, h6 {{
                    margin-top: 20px;
                    margin-bottom: 10px;
                }}
                blockquote {{
                    border-left: 4px solid #ddd;
                    margin: 0;
                    padding-left: 20px;
                    color: #666;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 10px 0;
                }}
                table th, table td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                table th {{
                    background-color: #f5f5f5;
                    font-weight: bold;
                }}
                a {{
                    color: #0066cc;
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
            </style>
            <body>
            {html_content}
            </body>
            """
            self.text_view.setHtml(styled_html)
        except Exception as e:
            # Если не удалось отформатировать, показываем как обычный текст
            logger.warning(f"Ошибка при форматировании markdown: {e}")
            self.text_view.setPlainText(response_text)
        
        layout.addWidget(self.text_view)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        copy_btn = QPushButton("Копировать текст")
        copy_btn.clicked.connect(self.copy_text)
        buttons_layout.addWidget(copy_btn)
        buttons_layout.addStretch()
        
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons_layout.addWidget(buttons)
        layout.addLayout(buttons_layout)
    
    def copy_text(self):
        """Копирование текста в буфер обмена"""
        clipboard = QApplication.clipboard()
        # Используем оригинальный текст (markdown), а не HTML
        clipboard.setText(self.original_text)
        QMessageBox.information(self, "Успех", "Текст скопирован в буфер обмена!")
    
    def sizeHint(self):
        """Рекомендуемый размер диалога"""
        return self.minimumSize()


class ImprovementThread(QThread):
    """Поток для улучшения промта через AI"""
    finished = pyqtSignal(object)  # PromptImprovementResult
    error = pyqtSignal(str)  # сообщение об ошибке
    
    def __init__(self, model: models.Model, original_prompt: str, include_adaptations: bool = True):
        super().__init__()
        self.model = model
        self.original_prompt = original_prompt
        self.include_adaptations = include_adaptations
    
    def run(self):
        """Выполнение улучшения промта"""
        try:
            result = network.improve_prompt_via_model(
                self.model,
                self.original_prompt,
                self.include_adaptations
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(f"Ошибка при улучшении промта: {str(e)}")


class PromptImprovementDialog(QDialog):
    """Диалог для улучшения промта с помощью AI"""
    
    def __init__(self, parent=None, original_prompt: str = "", model: Optional[models.Model] = None):
        super().__init__(parent)
        self.original_prompt = original_prompt
        self.model = model
        self.selected_prompt = ""  # Выбранный промт для подстановки
        self.improvement_thread: Optional[ImprovementThread] = None
        self.setWindowTitle("Улучшение промта")
        self.setModal(True)
        self.setMinimumSize(800, 600)
        self.init_ui()
        
        # Автоматически запускаем улучшение, если есть промт и модель
        if original_prompt and model:
            self.start_improvement()
        elif original_prompt and not model:
            # Если есть промт, но нет модели, показываем предупреждение
            self.improved_text.setPlainText("Модель не выбрана. Выберите модель в настройках.")
    
    def init_ui(self):
        """Инициализация интерфейса диалога"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Область исходного промта
        original_group = QGroupBox("Исходный промт")
        original_layout = QVBoxLayout()
        self.original_text = QTextEdit()
        self.original_text.setPlainText(self.original_prompt)
        self.original_text.setReadOnly(True)
        self.original_text.setMaximumHeight(100)
        original_layout.addWidget(self.original_text)
        original_group.setLayout(original_layout)
        layout.addWidget(original_group)
        
        # Область улучшенного промта
        improved_group = QGroupBox("Улучшенный промт")
        improved_layout = QVBoxLayout()
        self.improved_text = QTextEdit()
        self.improved_text.setPlaceholderText("Ожидание ответа от модели...")
        self.improved_text.setMinimumHeight(150)
        improved_layout.addWidget(self.improved_text)
        
        copy_btn = QPushButton("Копировать")
        copy_btn.clicked.connect(self.copy_improved)
        improved_layout.addWidget(copy_btn)
        improved_group.setLayout(improved_layout)
        layout.addWidget(improved_group)
        
        # Область альтернативных вариантов
        alternatives_group = QGroupBox("Альтернативные варианты")
        alternatives_layout = QVBoxLayout()
        self.alternatives_list = QListWidget()
        self.alternatives_list.setMaximumHeight(120)
        self.alternatives_list.itemDoubleClicked.connect(self.use_alternative)
        alternatives_layout.addWidget(self.alternatives_list)
        
        use_alt_btn = QPushButton("Использовать выбранный вариант")
        use_alt_btn.clicked.connect(self.use_selected_alternative)
        alternatives_layout.addWidget(use_alt_btn)
        alternatives_group.setLayout(alternatives_layout)
        layout.addWidget(alternatives_group)
        
        # Область адаптированных версий
        self.adaptations_tabs = QTabWidget()
        
        # Вкладка "Код"
        code_widget = QWidget()
        code_layout = QVBoxLayout()
        self.code_tab = QTextEdit()
        self.code_tab.setPlaceholderText("Версия для задач программирования...")
        code_layout.addWidget(self.code_tab)
        code_use_btn = QPushButton("Использовать эту версию")
        code_use_btn.clicked.connect(lambda: self.use_adapted_version(self.code_tab))
        code_layout.addWidget(code_use_btn)
        code_widget.setLayout(code_layout)
        self.adaptations_tabs.addTab(code_widget, "Код")
        
        # Вкладка "Анализ"
        analysis_widget = QWidget()
        analysis_layout = QVBoxLayout()
        self.analysis_tab = QTextEdit()
        self.analysis_tab.setPlaceholderText("Версия для аналитических задач...")
        analysis_layout.addWidget(self.analysis_tab)
        analysis_use_btn = QPushButton("Использовать эту версию")
        analysis_use_btn.clicked.connect(lambda: self.use_adapted_version(self.analysis_tab))
        analysis_layout.addWidget(analysis_use_btn)
        analysis_widget.setLayout(analysis_layout)
        self.adaptations_tabs.addTab(analysis_widget, "Анализ")
        
        # Вкладка "Креатив"
        creative_widget = QWidget()
        creative_layout = QVBoxLayout()
        self.creative_tab = QTextEdit()
        self.creative_tab.setPlaceholderText("Версия для креативных задач...")
        creative_layout.addWidget(self.creative_tab)
        creative_use_btn = QPushButton("Использовать эту версию")
        creative_use_btn.clicked.connect(lambda: self.use_adapted_version(self.creative_tab))
        creative_layout.addWidget(creative_use_btn)
        creative_widget.setLayout(creative_layout)
        self.adaptations_tabs.addTab(creative_widget, "Креатив")
        
        layout.addWidget(self.adaptations_tabs)
        
        # Индикатор загрузки
        self.loading_label = QLabel("Обработка запроса...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setVisible(False)
        layout.addWidget(self.loading_label)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        self.use_btn = QPushButton("Подставить в поле ввода")
        self.use_btn.clicked.connect(self.use_improved_prompt)
        self.use_btn.setEnabled(False)
        buttons_layout.addWidget(self.use_btn)
        
        buttons_layout.addStretch()
        
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(close_btn)
        layout.addLayout(buttons_layout)
    
    def start_improvement(self):
        """Запуск процесса улучшения промта"""
        if not self.model:
            QMessageBox.warning(self, "Ошибка", "Модель не выбрана!")
            return
        
        self.loading_label.setVisible(True)
        self.use_btn.setEnabled(False)
        self.improved_text.setPlainText("Ожидание ответа от модели...")
        self.alternatives_list.clear()
        
        self.improvement_thread = ImprovementThread(
            self.model,
            self.original_prompt,
            include_adaptations=True
        )
        self.improvement_thread.finished.connect(self.on_improvement_finished)
        self.improvement_thread.error.connect(self.on_improvement_error)
        self.improvement_thread.start()
    
    def on_improvement_finished(self, result: network.PromptImprovementResult):
        """Обработка завершения улучшения"""
        self.loading_label.setVisible(False)
        
        if result.error:
            QMessageBox.warning(self, "Ошибка", f"Ошибка при улучшении промта:\n{result.error}")
            self.improved_text.setPlainText("")
            return
        
        # Отображаем улучшенный промт
        if result.improved_prompt:
            self.improved_text.setPlainText(result.improved_prompt)
            self.selected_prompt = result.improved_prompt
            self.use_btn.setEnabled(True)
        else:
            self.improved_text.setPlainText("Не удалось получить улучшенную версию")
        
        # Отображаем альтернативные варианты
        self.alternatives_list.clear()
        for i, alt in enumerate(result.alternatives, 1):
            item = QListWidgetItem(f"Вариант {i}: {alt[:100]}...")
            item.setData(Qt.UserRole, alt)
            self.alternatives_list.addItem(item)
        
        # Отображаем адаптированные версии
        if result.code_version:
            self.code_tab.setPlainText(result.code_version)
        if result.analysis_version:
            self.analysis_tab.setPlainText(result.analysis_version)
        if result.creative_version:
            self.creative_tab.setPlainText(result.creative_version)
    
    def on_improvement_error(self, error_message: str):
        """Обработка ошибки при улучшении"""
        self.loading_label.setVisible(False)
        QMessageBox.critical(self, "Ошибка", error_message)
        self.improved_text.setPlainText("")
    
    def copy_improved(self):
        """Копирование улучшенного промта в буфер обмена"""
        text = self.improved_text.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            QMessageBox.information(self, "Успех", "Промт скопирован в буфер обмена!")
    
    def use_alternative(self, item: QListWidgetItem):
        """Использование альтернативного варианта при двойном клике"""
        alt_text = item.data(Qt.UserRole)
        if alt_text:
            self.selected_prompt = alt_text
            self.use_improved_prompt()
    
    def use_selected_alternative(self):
        """Использование выбранного альтернативного варианта"""
        current_item = self.alternatives_list.currentItem()
        if current_item:
            alt_text = current_item.data(Qt.UserRole)
            if alt_text:
                self.selected_prompt = alt_text
                self.use_improved_prompt()
        else:
            QMessageBox.warning(self, "Предупреждение", "Выберите вариант из списка!")
    
    def use_improved_prompt(self):
        """Подстановка улучшенного промта в основное поле ввода"""
        if not self.selected_prompt:
            # Если не выбран альтернативный вариант, используем улучшенный
            self.selected_prompt = self.improved_text.toPlainText()
        
        if self.selected_prompt:
            self.accept()
        else:
            QMessageBox.warning(self, "Предупреждение", "Нет промта для подстановки!")
    
    def use_adapted_version(self, text_edit: QTextEdit):
        """Использование адаптированной версии из вкладки"""
        adapted_text = text_edit.toPlainText().strip()
        if adapted_text:
            self.selected_prompt = adapted_text
            self.accept()
        else:
            QMessageBox.warning(self, "Предупреждение", "Эта версия пуста!")
    
    def get_selected_prompt(self) -> str:
        """Получение выбранного промта"""
        return self.selected_prompt if self.selected_prompt else self.improved_text.toPlainText()


class MainWindow(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        self.model_manager = models.get_model_manager()
        self.temp_results: List[network.APIResponse] = []  # Временная таблица результатов
        self.filtered_results: List[network.APIResponse] = []  # Отфильтрованные результаты для отображения
        self.all_prompts: List[Dict] = []  # Все промты для поиска
        self.current_prompt_id: Optional[int] = None
        self.request_thread: Optional[RequestThread] = None
        
        # Инициализация БД при первом запуске
        if not DATABASE_PATH.exists():
            logger.info("Инициализация базы данных...")
            db.init_database()
        
        self.init_ui()
        self.load_settings()  # Загружаем и применяем настройки после создания UI
        self.load_prompts()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        self.setWindowTitle('ChatList - Сравнение ответов нейросетей')
        self.setGeometry(100, 100, 1400, 900)
        
        # Создание центрального виджета
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Создание меню
        self.create_menu_bar()
        
        # Разделитель для основных областей
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)
        
        # Верхняя панель: работа с промтами
        prompt_panel = self.create_prompt_panel()
        splitter.addWidget(prompt_panel)
        
        # Нижняя панель: результаты
        results_panel = self.create_results_panel()
        splitter.addWidget(results_panel)
        
        # Настройка пропорций разделителя
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        # Статус-бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готов к работе")
    
    def create_menu_bar(self):
        """Создание меню"""
        menubar = self.menuBar()
        
        # Меню "Файл"
        file_menu = menubar.addMenu('Файл')
        export_action = file_menu.addAction('Экспорт результатов...')
        export_action.triggered.connect(self.export_results)
        file_menu.addSeparator()
        exit_action = file_menu.addAction('Выход')
        exit_action.triggered.connect(self.close)
        
        # Меню "Настройки"
        settings_menu = menubar.addMenu('Настройки')
        app_settings_action = settings_menu.addAction('Настройки приложения...')
        app_settings_action.triggered.connect(self.show_settings)
        settings_menu.addSeparator()
        models_action = settings_menu.addAction('Управление моделями...')
        models_action.triggered.connect(self.manage_models)
        prompts_action = settings_menu.addAction('Управление промтами...')
        prompts_action.triggered.connect(self.manage_prompts)
        
        # Меню "Справка"
        help_menu = menubar.addMenu('Справка')
        about_action = help_menu.addAction('О программе')
        about_action.triggered.connect(self.show_about)
    
    def create_prompt_panel(self) -> QWidget:
        """Создание панели для работы с промтами"""
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)
        
        # Заголовок
        title_label = QLabel("Промт")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Поиск промтов
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Поиск промтов:"))
        self.prompt_search_input = QLineEdit()
        self.prompt_search_input.setPlaceholderText("Введите текст для поиска...")
        self.prompt_search_input.textChanged.connect(self.on_prompt_search_changed)
        search_layout.addWidget(self.prompt_search_input)
        clear_search_btn = QPushButton("Очистить")
        clear_search_btn.clicked.connect(self.clear_prompt_search)
        search_layout.addWidget(clear_search_btn)
        layout.addLayout(search_layout)
        
        # Выбор сохраненного промта
        load_layout = QHBoxLayout()
        load_layout.addWidget(QLabel("Загрузить промт:"))
        self.prompt_combo = QComboBox()
        self.prompt_combo.currentIndexChanged.connect(self.on_prompt_selected)
        load_layout.addWidget(self.prompt_combo)
        layout.addLayout(load_layout)
        
        # Текстовое поле для ввода промта
        self.prompt_text = QTextEdit()
        self.prompt_text.setPlaceholderText("Введите ваш промт здесь...")
        self.prompt_text.setMinimumHeight(150)
        layout.addWidget(self.prompt_text)
        
        # Поле для тегов
        tags_layout = QHBoxLayout()
        tags_layout.addWidget(QLabel("Теги:"))
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("тег1, тег2, ...")
        tags_layout.addWidget(self.tags_input)
        layout.addLayout(tags_layout)
        
        # Кнопки управления промтом
        prompt_buttons = QHBoxLayout()
        self.new_prompt_btn = QPushButton("Новый промт")
        self.new_prompt_btn.clicked.connect(self.new_prompt)
        self.save_prompt_btn = QPushButton("Сохранить промт")
        self.save_prompt_btn.clicked.connect(self.save_prompt)
        self.improve_prompt_btn = QPushButton("Улучшить промт")
        self.improve_prompt_btn.clicked.connect(self.on_improve_prompt_clicked)
        self.improve_prompt_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        prompt_buttons.addWidget(self.new_prompt_btn)
        prompt_buttons.addWidget(self.save_prompt_btn)
        prompt_buttons.addWidget(self.improve_prompt_btn)
        layout.addLayout(prompt_buttons)
        
        # Кнопки управления запросами
        request_buttons = QHBoxLayout()
        self.send_btn = QPushButton("Отправить запрос")
        self.send_btn.clicked.connect(self.send_request)
        self.send_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.cancel_request)
        self.cancel_btn.setEnabled(False)
        request_buttons.addWidget(self.send_btn)
        request_buttons.addWidget(self.cancel_btn)
        layout.addLayout(request_buttons)
        
        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        layout.addStretch()
        return panel
    
    def create_results_panel(self) -> QWidget:
        """Создание панели для отображения результатов"""
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)
        
        # Заголовок
        title_label = QLabel("Результаты")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Поиск и сортировка результатов
        search_sort_layout = QHBoxLayout()
        search_sort_layout.addWidget(QLabel("Поиск:"))
        self.results_search_input = QLineEdit()
        self.results_search_input.setPlaceholderText("Поиск по модели или тексту ответа...")
        self.results_search_input.textChanged.connect(self.on_results_search_changed)
        search_sort_layout.addWidget(self.results_search_input)
        
        search_sort_layout.addWidget(QLabel("Сортировка:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["По умолчанию", "По модели", "По времени ответа", "По длине ответа"])
        self.sort_combo.currentIndexChanged.connect(self.on_sort_changed)
        search_sort_layout.addWidget(self.sort_combo)
        layout.addLayout(search_sort_layout)
        
        # Таблица результатов
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Выбрано", "Модель", "Ответ", "Время"])
        
        # Настройка таблицы
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Чекбокс
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Модель
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Ответ
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Время
        
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SingleSelection)
        # Двойной клик для открытия результата
        self.results_table.itemDoubleClicked.connect(self.on_result_double_clicked)
        layout.addWidget(self.results_table)
        
        # Кнопки управления результатами
        results_buttons = QHBoxLayout()
        self.open_result_btn = QPushButton("Открыть")
        self.open_result_btn.clicked.connect(self.open_selected_result)
        self.save_results_btn = QPushButton("Сохранить выбранные")
        self.save_results_btn.clicked.connect(self.save_selected_results)
        self.clear_results_btn = QPushButton("Очистить результаты")
        self.clear_results_btn.clicked.connect(self.clear_results)
        results_buttons.addWidget(self.open_result_btn)
        results_buttons.addWidget(self.save_results_btn)
        results_buttons.addWidget(self.clear_results_btn)
        layout.addLayout(results_buttons)
        
        return panel
    
    def load_prompts(self):
        """Загрузка списка промтов из БД"""
        self.all_prompts = db.get_all_prompts()
        self.filter_prompts()
    
    def filter_prompts(self):
        """Фильтрация промтов по поисковому запросу"""
        search_text = self.prompt_search_input.text().strip().lower()
        
        if search_text:
            filtered = db.search_prompts(search_text)
        else:
            filtered = self.all_prompts
        
        self.prompt_combo.clear()
        self.prompt_combo.addItem("-- Новый промт --", None)
        for prompt_data in filtered:
            preview = prompt_data["prompt"][:50] + "..." if len(prompt_data["prompt"]) > 50 else prompt_data["prompt"]
            display_text = f"[{prompt_data['id']}] {preview}"
            self.prompt_combo.addItem(display_text, prompt_data["id"])
    
    def on_prompt_search_changed(self, text):
        """Обработка изменения поискового запроса для промтов"""
        self.filter_prompts()
    
    def clear_prompt_search(self):
        """Очистка поиска промтов"""
        self.prompt_search_input.clear()
        self.filter_prompts()
    
    def on_prompt_selected(self, index):
        """Обработка выбора промта из списка"""
        prompt_id = self.prompt_combo.itemData(index)
        if prompt_id:
            prompt_data = db.get_prompt_by_id(prompt_id)
            if prompt_data:
                self.prompt_text.setPlainText(prompt_data["prompt"])
                self.tags_input.setText(prompt_data.get("tags", "") or "")
                self.current_prompt_id = prompt_id
    
    def new_prompt(self):
        """Создание нового промта"""
        self.prompt_text.clear()
        self.tags_input.clear()
        self.prompt_combo.setCurrentIndex(0)
        self.current_prompt_id = None
        self.clear_results()
        self.status_bar.showMessage("Создан новый промт")
    
    def save_prompt(self):
        """Сохранение промта в БД"""
        prompt_text = self.prompt_text.toPlainText().strip()
        if not prompt_text:
            QMessageBox.warning(self, "Предупреждение", "Промт не может быть пустым!")
            return
        
        tags = self.tags_input.text().strip() or None
        
        try:
            if self.current_prompt_id:
                # Обновление существующего промта (только теги)
                db.update_prompt_tags(self.current_prompt_id, tags)
                QMessageBox.information(self, "Успех", "Теги промта обновлены!")
            else:
                # Создание нового промта
                prompt_id = db.create_prompt(prompt_text, tags)
                self.current_prompt_id = prompt_id
                self.load_prompts()
                # Выбор только что созданного промта
                index = self.prompt_combo.findData(prompt_id)
                if index >= 0:
                    self.prompt_combo.setCurrentIndex(index)
                QMessageBox.information(self, "Успех", "Промт сохранен!")
            logger.info(f"Промт сохранен с ID: {self.current_prompt_id}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении промта: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить промт: {str(e)}")
    
    def on_improve_prompt_clicked(self):
        """Обработчик нажатия кнопки 'Улучшить промт'"""
        prompt_text = self.prompt_text.toPlainText().strip()
        
        if not prompt_text:
            QMessageBox.warning(self, "Предупреждение", "Введите промт для улучшения!")
            return
        
        # Получение модели для улучшения
        improvement_model = self.get_improvement_model()
        
        if not improvement_model:
            QMessageBox.warning(
                self, 
                "Модель не выбрана", 
                "Не выбрана модель для улучшения промтов.\n\nВыберите модель в настройках или используйте первую активную модель."
            )
            # Попытка использовать первую активную модель
            active_models = self.model_manager.get_active_models()
            if active_models:
                improvement_model = active_models[0]
                # Сохраняем как модель по умолчанию
                db.set_improvement_model_id(improvement_model.id)
            else:
                QMessageBox.critical(self, "Ошибка", "Нет активных моделей для улучшения промтов!")
                return
        
        # Открытие диалога улучшения
        dialog = PromptImprovementDialog(self, prompt_text, improvement_model)
        if dialog.exec_() == QDialog.Accepted:
            selected_prompt = dialog.get_selected_prompt()
            if selected_prompt:
                self.prompt_text.setPlainText(selected_prompt)
                logger.info("Улучшенный промт подставлен в поле ввода")
    
    def get_improvement_model(self) -> Optional[models.Model]:
        """Получение модели для улучшения промтов"""
        model_id = db.get_improvement_model_id()
        if model_id:
            model = self.model_manager.get_model_by_id(model_id)
            if model and model.is_active:
                return model
            else:
                # Модель не найдена или неактивна, сбрасываем настройку
                db.set_improvement_model_id(0)
        
        # Если модель не выбрана, используем первую активную
        active_models = self.model_manager.get_active_models()
        if active_models:
            return active_models[0]
        
        return None
    
    def send_request(self):
        """Отправка запроса во все выбранные модели"""
        prompt_text = self.prompt_text.toPlainText().strip()
        if not prompt_text:
            QMessageBox.warning(self, "Предупреждение", "Введите промт перед отправкой!")
            logger.warning("Попытка отправить пустой промт")
            return
        
        # Получение активных моделей
        selected_models = self.model_manager.get_active_models()
        
        if not selected_models:
            QMessageBox.warning(self, "Предупреждение", "Нет активных моделей! Выберите активные модели в меню управления.")
            logger.warning("Попытка отправить запрос без активных моделей")
            return
        
        # Валидация API-ключей
        try:
            validation = self.model_manager.validate_api_keys(selected_models)
            missing_models = [m.name for m, has_key in zip(selected_models, validation.values()) if not has_key]
            
            if missing_models:
                missing_text = "\n".join(f"- {name}" for name in missing_models)
                QMessageBox.warning(
                    self,
                    "Предупреждение",
                    f"Отсутствуют API-ключи для следующих моделей:\n{missing_text}\n\n"
                    "Проверьте файл .env и добавьте необходимые ключи."
                )
                logger.warning(f"Отсутствуют API-ключи для моделей: {missing_models}")
                return
        except Exception as e:
            logger.error(f"Ошибка при валидации API-ключей: {e}")
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось проверить API-ключи: {str(e)}"
            )
            return
        
        # Очистка предыдущих результатов
        self.clear_results()
        
        # Отключение кнопки отправки и включение отмены
        self.send_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(selected_models))
        self.progress_bar.setValue(0)
        self.status_bar.showMessage(f"Отправка запросов в {len(selected_models)} моделей...")
        
        # Запуск потока для отправки запросов
        self.request_thread = RequestThread(selected_models, prompt_text)
        self.request_thread.progress.connect(self.on_request_progress)
        self.request_thread.finished.connect(self.on_request_finished)
        self.request_thread.start()
    
    def on_request_progress(self, completed, total):
        """Обновление прогресса отправки запросов"""
        self.progress_bar.setValue(completed)
        self.status_bar.showMessage(f"Отправлено запросов: {completed} из {total}")
    
    def on_request_finished(self, results: List[network.APIResponse]):
        """Обработка завершения отправки запросов"""
        self.send_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        try:
            self.temp_results = results
            self.display_results(results)
            
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            
            self.status_bar.showMessage(f"Готово! Получено ответов: {successful} из {len(results)}")
            
            # Логирование результатов
            logger.info(f"Запрос завершен: успешно {successful}, ошибок {failed}")
            if failed > 0:
                failed_models = [r.model_name for r in results if not r.success]
                logger.warning(f"Ошибки в моделях: {failed_models}")
            
            if successful < len(results):
                failed_models = [r.model_name for r in results if not r.success]
                failed_text = "\n".join(f"- {name}" for name in failed_models)
                QMessageBox.warning(
                    self,
                    "Предупреждение",
                    f"Некоторые запросы завершились с ошибками.\n\n"
                    f"Успешно: {successful} из {len(results)}\n\n"
                    f"Ошибки в моделях:\n{failed_text}"
                )
        except Exception as e:
            logger.error(f"Ошибка при обработке результатов: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось обработать результаты: {str(e)}"
            )
    
    def cancel_request(self):
        """Отмена отправки запросов"""
        try:
            if self.request_thread and self.request_thread.isRunning():
                logger.info("Отмена отправки запросов пользователем")
                self.request_thread.terminate()
                self.request_thread.wait(5000)  # Ждем до 5 секунд
                
                if self.request_thread.isRunning():
                    logger.warning("Поток не завершился, принудительное завершение")
                    self.request_thread.terminate()
        except Exception as e:
            logger.error(f"Ошибка при отмене запроса: {e}")
        finally:
            self.send_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress_bar.setVisible(False)
            self.status_bar.showMessage("Отправка отменена")
    
    def display_results(self, results: List[network.APIResponse]):
        """Отображение результатов в таблице"""
        self.temp_results = results
        self.apply_results_filter_and_sort()
    
    def apply_results_filter_and_sort(self):
        """Применение фильтра и сортировки к результатам"""
        # Фильтрация
        search_text = self.results_search_input.text().strip().lower()
        filtered_results = self.temp_results
        
        if search_text:
            filtered_results = [
                r for r in self.temp_results
                if search_text in r.model_name.lower() or 
                   (r.success and search_text in r.response_text.lower()) or
                   (r.error and search_text in r.error.lower())
            ]
        
        # Сортировка
        sort_type = self.sort_combo.currentText()
        if sort_type == "По модели":
            filtered_results = sorted(filtered_results, key=lambda x: x.model_name)
        elif sort_type == "По времени ответа":
            filtered_results = sorted(filtered_results, key=lambda x: x.response_time, reverse=True)
        elif sort_type == "По длине ответа":
            filtered_results = sorted(filtered_results, key=lambda x: len(x.response_text) if x.success else 0, reverse=True)
        
        # Сохранение отфильтрованных результатов
        self.filtered_results = filtered_results
        
        # Отображение
        self.results_table.setRowCount(len(filtered_results))
        
        for row, response in enumerate(filtered_results):
            # Чекбокс
            checkbox = QCheckBox()
            checkbox.setChecked(True)  # По умолчанию все выбраны
            self.results_table.setCellWidget(row, 0, checkbox)
            
            # Модель
            model_item = QTableWidgetItem(response.model_name)
            self.results_table.setItem(row, 1, model_item)
            
            # Ответ (многострочное поле)
            if response.success:
                answer_text = response.response_text
                if response.error:
                    answer_text = f"[ОШИБКА] {response.error}"
            else:
                answer_text = f"[ОШИБКА] {response.error}" if response.error else "[Ошибка при получении ответа]"
            
            # Используем QPlainTextEdit для многострочного отображения
            answer_widget = QPlainTextEdit()
            answer_widget.setPlainText(answer_text)
            answer_widget.setReadOnly(True)
            answer_widget.setFrameStyle(0)  # Убираем рамку
            answer_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            answer_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            
            # Настройка высоты виджета
            font_metrics = answer_widget.fontMetrics()
            line_height = font_metrics.lineSpacing()
            
            # Подсчитываем примерное количество строк в тексте
            # Учитываем переносы строк и длину текста
            lines = answer_text.split('\n')
            estimated_lines = sum(max(1, len(line) // 80) for line in lines)  # Примерно 80 символов на строку
            
            min_height = line_height * 3  # Минимум 3 строки
            max_height = line_height * 15  # Максимум 15 строк
            
            # Вычисляем оптимальную высоту
            widget_height = min(max(estimated_lines * line_height + 20, min_height), max_height)
            answer_widget.setMinimumHeight(min_height)
            answer_widget.setMaximumHeight(widget_height)
            
            # Подсветка ошибок
            if not response.success:
                answer_widget.setStyleSheet("background-color: #ffebee; color: #c62828;")
            
            self.results_table.setCellWidget(row, 2, answer_widget)
            
            # Время ответа
            time_text = f"{response.response_time:.2f}с"
            if response.tokens_used:
                time_text += f" ({response.tokens_used} токенов)"
            time_item = QTableWidgetItem(time_text)
            self.results_table.setItem(row, 3, time_item)
            
            # Подсветка ошибок для других колонок
            if not response.success:
                # Подсветка колонки "Модель"
                model_item = self.results_table.item(row, 1)
                if model_item:
                    model_item.setBackground(Qt.red)
                    model_item.setForeground(Qt.white)
                # Подсветка колонки "Время"
                if time_item:
                    time_item.setBackground(Qt.red)
                    time_item.setForeground(Qt.white)
        
        # Автоматическая настройка высоты строк на основе содержимого
        self.results_table.resizeRowsToContents()
        
        # Устанавливаем минимальную высоту строк для многострочных ответов
        for row in range(self.results_table.rowCount()):
            self.results_table.setRowHeight(row, max(self.results_table.rowHeight(row), 100))
    
    def on_results_search_changed(self, text):
        """Обработка изменения поискового запроса для результатов"""
        self.apply_results_filter_and_sort()
    
    def on_sort_changed(self, index):
        """Обработка изменения сортировки результатов"""
        self.apply_results_filter_and_sort()
    
    def save_selected_results(self):
        """Сохранение выбранных результатов в БД"""
        if not self.temp_results:
            QMessageBox.warning(self, "Предупреждение", "Нет результатов для сохранения!")
            return
        
        # Получение выбранных строк из отфильтрованных результатов
        selected_results = []
        for row in range(self.results_table.rowCount()):
            checkbox = self.results_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                if row < len(self.filtered_results):
                    selected_results.append(self.filtered_results[row])
        
        if not selected_results:
            QMessageBox.warning(self, "Предупреждение", "Выберите хотя бы один результат для сохранения!")
            return
        
        # Сохранение промта, если он новый
        prompt_text = self.prompt_text.toPlainText().strip()
        if not self.current_prompt_id:
            try:
                tags = self.tags_input.text().strip() or None
                self.current_prompt_id = db.create_prompt(prompt_text, tags)
                self.load_prompts()
                logger.info(f"Создан новый промт с ID: {self.current_prompt_id}")
            except Exception as e:
                logger.error(f"Ошибка при создании промта: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить промт: {str(e)}")
                return
        
        # Сохранение выбранных результатов
        results_to_save = []
        for response in selected_results:
            if response.success:  # Сохраняем только успешные ответы
                results_to_save.append((
                    self.current_prompt_id,
                    response.model_id,
                    response.response_text,
                    response.tokens_used,
                    response.response_time
                ))
        
        if results_to_save:
            try:
                db.save_multiple_results(results_to_save)
                QMessageBox.information(
                    self,
                    "Успех",
                    f"Сохранено результатов: {len(results_to_save)}"
                )
                logger.info(f"Сохранено результатов: {len(results_to_save)}")
                self.clear_results()
            except Exception as e:
                logger.error(f"Ошибка при сохранении результатов: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить результаты: {str(e)}")
        else:
            QMessageBox.warning(self, "Предупреждение", "Нет успешных результатов для сохранения!")
    
    def clear_results(self):
        """Очистка временной таблицы результатов"""
        self.results_table.setRowCount(0)
        self.temp_results = []
        self.filtered_results = []
        self.status_bar.showMessage("Результаты очищены")
    
    def open_selected_result(self):
        """Открытие выбранного результата в диалоге markdown"""
        current_row = self.results_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите результат для просмотра!")
            return
        
        self._open_result_at_row(current_row)
    
    def on_result_double_clicked(self, item):
        """Обработка двойного клика по результату"""
        row = item.row()
        self._open_result_at_row(row)
    
    def _open_result_at_row(self, row: int):
        """Открытие результата в указанной строке"""
        if row < 0 or row >= len(self.filtered_results):
            QMessageBox.warning(self, "Ошибка", "Не удалось найти выбранный результат!")
            return
        
        response = self.filtered_results[row]
        
        if not response.success:
            QMessageBox.warning(
                self,
                "Предупреждение",
                f"Не удалось открыть результат с ошибкой.\n\nОшибка: {response.error or 'Неизвестная ошибка'}"
            )
            return
        
        # Открываем диалог с форматированным markdown
        dialog = MarkdownViewDialog(
            self,
            model_name=response.model_name,
            response_text=response.response_text
        )
        dialog.exec_()
    
    def export_results(self):
        """Экспорт результатов в файл"""
        if not self.temp_results:
            QMessageBox.warning(self, "Предупреждение", "Нет результатов для экспорта!")
            return
        
        # Получение выбранных результатов из таблицы
        selected_results = []
        for row in range(self.results_table.rowCount()):
            checkbox = self.results_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                # Используем отфильтрованные результаты, так как таблица показывает их
                if row < len(self.filtered_results):
                    selected_results.append(self.filtered_results[row])
        
        if not selected_results:
            QMessageBox.warning(self, "Предупреждение", "Выберите хотя бы один результат для экспорта!")
            return
        
        # Получение формата экспорта из настроек
        export_format = db.get_setting("default_export_format", "markdown")
        
        # Диалог выбора формата
        format_dialog = QDialog(self)
        format_dialog.setWindowTitle("Выбор формата экспорта")
        layout = QVBoxLayout()
        format_dialog.setLayout(layout)
        
        layout.addWidget(QLabel("Выберите формат экспорта:"))
        format_combo = QComboBox()
        format_combo.addItems(["Markdown (.md)", "JSON (.json)"])
        if export_format == "json":
            format_combo.setCurrentIndex(1)
        layout.addWidget(format_combo)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(format_dialog.accept)
        buttons.rejected.connect(format_dialog.reject)
        layout.addWidget(buttons)
        
        if format_dialog.exec_() != QDialog.Accepted:
            return
        
        selected_format = format_combo.currentText()
        is_markdown = "Markdown" in selected_format
        
        # Диалог выбора файла
        file_ext = ".md" if is_markdown else ".json"
        default_filename = f"chatlist_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_ext}"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить результаты",
            str(Path.home() / default_filename),
            f"{'Markdown' if is_markdown else 'JSON'} файлы (*{file_ext});;Все файлы (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            if is_markdown:
                self._export_to_markdown(selected_results, file_path)
            else:
                self._export_to_json(selected_results, file_path)
            
            # Сохранение формата в настройках
            db.set_setting("default_export_format", "markdown" if is_markdown else "json")
            
            QMessageBox.information(
                self,
                "Успех",
                f"Результаты успешно экспортированы в файл:\n{file_path}"
            )
            logger.info(f"Экспортировано {len(selected_results)} результатов в {file_path}")
        except Exception as e:
            logger.error(f"Ошибка при экспорте результатов: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать результаты: {str(e)}")
    
    def _export_to_markdown(self, results: List[network.APIResponse], file_path: str):
        """Экспорт результатов в Markdown формат"""
        prompt_text = self.prompt_text.toPlainText().strip()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("# Экспорт результатов ChatList\n\n")
            f.write(f"**Дата экспорта:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Промт:**\n\n```\n{prompt_text}\n```\n\n")
            f.write(f"**Количество результатов:** {len(results)}\n\n")
            f.write("---\n\n")
            
            for i, result in enumerate(results, 1):
                f.write(f"## {i}. {result.model_name}\n\n")
                
                if result.success:
                    f.write(f"**Ответ:**\n\n{result.response_text}\n\n")
                else:
                    f.write(f"**Ошибка:** {result.error or 'Неизвестная ошибка'}\n\n")
                
                f.write(f"**Время ответа:** {result.response_time:.2f}с")
                if result.tokens_used:
                    f.write(f" | **Токенов использовано:** {result.tokens_used}")
                f.write("\n\n")
                f.write("---\n\n")
    
    def _export_to_json(self, results: List[network.APIResponse], file_path: str):
        """Экспорт результатов в JSON формат"""
        prompt_text = self.prompt_text.toPlainText().strip()
        
        export_data = {
            "export_date": datetime.now().isoformat(),
            "prompt": prompt_text,
            "results_count": len(results),
            "results": []
        }
        
        for result in results:
            result_data = {
                "model_name": result.model_name,
                "model_id": result.model_id,
                "success": result.success,
                "response_text": result.response_text if result.success else None,
                "error": result.error if not result.success else None,
                "response_time": result.response_time,
                "tokens_used": result.tokens_used
            }
            export_data["results"].append(result_data)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    def manage_models(self):
        """Управление моделями"""
        dialog = ModelManagementDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # Обновление кэша моделей после изменений
            self.model_manager.invalidate_cache()
    
    def manage_prompts(self):
        """Управление промтами"""
        dialog = PromptManagementDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # Обновление списка промтов после изменений
            self.load_prompts()
    
    def show_settings(self):
        """Открытие диалога настроек"""
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()
            # Сохраняем настройки в БД
            db.set_setting("theme", settings["theme"])
            db.set_setting("font_size", settings["font_size"])
            # Применяем настройки
            self.apply_settings(settings)
            QMessageBox.information(self, "Успех", "Настройки сохранены!")
            logger.info(f"Настройки обновлены: {settings}")
    
    def load_settings(self):
        """Загрузка настроек из БД и применение их"""
        theme = db.get_setting("theme", "light")
        font_size = db.get_setting("font_size", "10")
        settings = {
            "theme": theme,
            "font_size": font_size
        }
        self.apply_settings(settings)
    
    def apply_settings(self, settings: Dict[str, str]):
        """Применение настроек к интерфейсу"""
        # Применение темы
        theme = settings.get("theme", "light")
        if theme == "dark":
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QGroupBox {
                    border: 1px solid #555555;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
                QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
                    background-color: #3c3c3c;
                    color: #ffffff;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    padding: 5px;
                }
                QPushButton {
                    background-color: #404040;
                    color: #ffffff;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #505050;
                }
                QPushButton:pressed {
                    background-color: #353535;
                }
                QTableWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                    gridline-color: #555555;
                    alternate-background-color: #333333;
                }
                QHeaderView::section {
                    background-color: #404040;
                    color: #ffffff;
                    padding: 5px;
                    border: 1px solid #555555;
                }
                QLabel {
                    color: #ffffff;
                }
            """)
        else:
            # Светлая тема - сбрасываем стили
            self.setStyleSheet("")
        
        # Применение размера шрифта
        font_size = int(settings.get("font_size", "10"))
        app_font = QFont()
        app_font.setPointSize(font_size)
        self.setFont(app_font)
        
        # Применяем шрифт ко всем виджетам панелей
        self.apply_font_to_panels(font_size)
    
    def apply_font_to_panels(self, font_size: int):
        """Применение размера шрифта к панелям"""
        font = QFont()
        font.setPointSize(font_size)
        
        # Применяем к основным виджетам панелей
        widgets_to_update = [
            'prompt_text', 'results_table', 'prompt_combo', 
            'prompt_search_input', 'results_search_input',
            'sort_combo', 'tags_input'
        ]
        
        for widget_name in widgets_to_update:
            if hasattr(self, widget_name):
                widget = getattr(self, widget_name)
                if widget:
                    widget.setFont(font)
        
        # Применяем шрифт ко всем дочерним виджетам
        def apply_font_recursive(widget, font):
            """Рекурсивное применение шрифта ко всем дочерним виджетам"""
            widget.setFont(font)
            for child in widget.findChildren(QWidget):
                if isinstance(child, (QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QLabel, QTableWidget)):
                    child.setFont(font)
        
        # Применяем к центральному виджету и его детям
        central = self.centralWidget()
        if central:
            apply_font_recursive(central, font)
    
    def show_about(self):
        """Показать информацию о программе"""
        about_text = """
        <h2>ChatList v1.0</h2>
        <p><b>Программа для сравнения ответов различных нейросетей</b></p>
        
        <p>ChatList позволяет отправлять один промт в несколько нейросетей 
        одновременно и сравнивать их ответы в удобной таблице.</p>
        
        <h3>Основные возможности:</h3>
        <ul>
            <li>Отправка промта в несколько моделей параллельно</li>
            <li>Сравнение ответов от разных нейросетей</li>
            <li>Сохранение промтов и результатов в базу данных</li>
            <li>Работа через OpenRouter API - один ключ для всех моделей</li>
            <li>Поддержка моделей от OpenAI, Anthropic, DeepSeek, Google, Meta и других</li>
            <li>Улучшение промтов с помощью AI-ассистента</li>
            <li>Экспорт результатов в Markdown и JSON</li>
        </ul>
        
        <h3>Технологии:</h3>
        <ul>
            <li>Python 3.11+</li>
            <li>PyQt5 для интерфейса</li>
            <li>SQLite для хранения данных</li>
            <li>OpenRouter API для доступа к моделям</li>
        </ul>
        
        <p><i>© 2024 ChatList</i></p>
        """
        
        msg = QMessageBox(self)
        msg.setWindowTitle("О программе ChatList")
        msg.setTextFormat(Qt.RichText)
        msg.setText(about_text)
        msg.setIcon(QMessageBox.Information)
        msg.exec_()


def main():
    """Главная функция приложения"""
    app = QApplication(sys.argv)
    
    # Настройка стиля приложения
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
