"""
Главное окно приложения ChatList
GUI интерфейс для отправки промтов в несколько нейросетей и сравнения результатов
"""

import sys
import logging
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QLabel, QComboBox, QProgressBar, QMessageBox, QCheckBox, QSplitter,
    QLineEdit, QMenuBar, QMenu, QStatusBar, QAbstractItemView, QDialog,
    QDialogButtonBox, QFormLayout, QGroupBox, QFileDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

import db
import models
import network
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
    
    def __init__(self, parent=None, model_data: Optional[Dict] = None):
        super().__init__(parent)
        self.model_data = model_data
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
        form_layout.addRow("Тип модели:", self.model_type_combo)
        
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
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Подсказка для OpenRouter
        hint_label = QLabel(
            "Примечание: Для моделей типа 'openrouter' используется\n"
            "единый ключ OPENROUTER_API_KEY независимо от значения API ID."
        )
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(hint_label)
    
    def load_model_data(self):
        """Загрузка данных модели в форму"""
        if self.model_data:
            self.name_input.setText(self.model_data.get("name", ""))
            self.api_url_input.setText(self.model_data.get("api_url", ""))
            self.api_id_input.setText(self.model_data.get("api_id", ""))
            
            model_type = self.model_data.get("model_type", "openrouter")
            index = self.model_type_combo.findText(model_type)
            if index >= 0:
                self.model_type_combo.setCurrentIndex(index)
            
            self.is_active_checkbox.setChecked(bool(self.model_data.get("is_active", 1)))
    
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


class ModelManagementDialog(QDialog):
    """Диалог для управления моделями"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Управление моделями")
        self.setModal(True)
        self.setMinimumSize(900, 600)
        self.model_manager = models.get_model_manager()
        self.init_ui()
        self.load_models()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
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
        models_list = self.model_manager.load_models(force_reload=True)
        self.models_table.setRowCount(len(models_list))
        
        for row, model in enumerate(models_list):
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
    
    def on_active_changed(self, model_id: int, state: int):
        """Обработка изменения статуса активности"""
        is_active = 1 if state == Qt.Checked else 0
        try:
            db.update_model_status(model_id, is_active)
            self.model_manager.invalidate_cache()
            logger.info(f"Статус модели {model_id} изменен на {'активна' if is_active else 'неактивна'}")
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
        self.load_prompts()
        self.load_models()
    
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
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Левая панель: работа с промтами
        left_panel = self.create_prompt_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель: результаты
        right_panel = self.create_results_panel()
        splitter.addWidget(right_panel)
        
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
        models_action = settings_menu.addAction('Управление моделями...')
        models_action.triggered.connect(self.manage_models)
        
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
        prompt_buttons.addWidget(self.new_prompt_btn)
        prompt_buttons.addWidget(self.save_prompt_btn)
        layout.addLayout(prompt_buttons)
        
        # Выбор моделей
        models_label = QLabel("Активные модели:")
        layout.addWidget(models_label)
        self.models_list_widget = QWidget()
        models_layout = QVBoxLayout()
        self.models_list_widget.setLayout(models_layout)
        layout.addWidget(self.models_list_widget)
        
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
        layout.addWidget(self.results_table)
        
        # Кнопки управления результатами
        results_buttons = QHBoxLayout()
        self.save_results_btn = QPushButton("Сохранить выбранные")
        self.save_results_btn.clicked.connect(self.save_selected_results)
        self.clear_results_btn = QPushButton("Очистить результаты")
        self.clear_results_btn.clicked.connect(self.clear_results)
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
    
    def load_models(self):
        """Загрузка списка моделей и создание чекбоксов"""
        # Очистка существующих чекбоксов
        layout = self.models_list_widget.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Загрузка моделей
        all_models = self.model_manager.load_models()
        self.model_checkboxes: Dict[int, QCheckBox] = {}
        
        for model in all_models:
            checkbox = QCheckBox(model.get_display_name())
            checkbox.setChecked(model.is_active)
            checkbox.stateChanged.connect(self.on_model_checkbox_changed)
            self.model_checkboxes[model.id] = checkbox
            layout.addWidget(checkbox)
    
    def on_model_checkbox_changed(self, state):
        """Обработка изменения состояния чекбокса модели"""
        # Обновление статуса модели в БД
        checkbox = self.sender()
        model_id = None
        for mid, cb in self.model_checkboxes.items():
            if cb == checkbox:
                model_id = mid
                break
        
        if model_id:
            is_active = 1 if state == Qt.Checked else 0
            db.update_model_status(model_id, is_active)
            self.model_manager.invalidate_cache()
            logger.info(f"Статус модели {model_id} изменен на {'активна' if is_active else 'неактивна'}")
    
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
    
    def send_request(self):
        """Отправка запроса во все выбранные модели"""
        prompt_text = self.prompt_text.toPlainText().strip()
        if not prompt_text:
            QMessageBox.warning(self, "Предупреждение", "Введите промт перед отправкой!")
            logger.warning("Попытка отправить пустой промт")
            return
        
        # Получение выбранных моделей
        selected_models = []
        for model_id, checkbox in self.model_checkboxes.items():
            if checkbox.isChecked():
                model = self.model_manager.get_model_by_id(model_id)
                if model:
                    selected_models.append(model)
        
        if not selected_models:
            QMessageBox.warning(self, "Предупреждение", "Выберите хотя бы одну модель!")
            logger.warning("Попытка отправить запрос без выбранных моделей")
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
            
            # Ответ
            if response.success:
                answer_text = response.response_text
                if response.error:
                    answer_text = f"[ОШИБКА] {response.error}"
            else:
                answer_text = f"[ОШИБКА] {response.error}" if response.error else "[Ошибка при получении ответа]"
            
            answer_item = QTableWidgetItem(answer_text)
            answer_item.setToolTip(answer_text)  # Подсказка для длинного текста
            self.results_table.setItem(row, 2, answer_item)
            
            # Время ответа
            time_text = f"{response.response_time:.2f}с"
            if response.tokens_used:
                time_text += f" ({response.tokens_used} токенов)"
            time_item = QTableWidgetItem(time_text)
            self.results_table.setItem(row, 3, time_item)
            
            # Подсветка ошибок
            if not response.success:
                for col in range(4):
                    item = self.results_table.item(row, col)
                    if item:
                        item.setBackground(Qt.red)
                        item.setForeground(Qt.white)
        
        self.results_table.resizeRowsToContents()
    
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
        self.status_bar.showMessage("Результаты очищены")
    
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
            # Обновление списка моделей в главном окне после изменений
            self.model_manager.invalidate_cache()
            self.load_models()
    
    def show_about(self):
        """Показать информацию о программе"""
        QMessageBox.about(
            self,
            "О программе ChatList",
            "ChatList v1.0\n\n"
            "Программа для сравнения ответов различных нейросетей.\n\n"
            "Позволяет отправлять один промт в несколько нейросетей\n"
            "и сравнивать их ответы."
        )


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
