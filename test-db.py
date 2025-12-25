"""
Тестовая программа для работы с SQLite базами данных
Позволяет просматривать таблицы, выполнять CRUD операции с пагинацией
"""

import sys
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
                             QFileDialog, QListWidget, QListWidgetItem, QMessageBox,
                             QDialog, QFormLayout, QLineEdit, QTextEdit, QLabel,
                             QComboBox, QSpinBox, QHeaderView, QGroupBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon


class DatabaseManager:
    """Класс для управления подключением к базе данных"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
    
    def connect(self):
        """Подключение к базе данных"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            return True
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Ошибка подключения", f"Не удалось подключиться к БД:\n{e}")
            return False
    
    def disconnect(self):
        """Отключение от базы данных"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def get_tables(self) -> List[str]:
        """Получить список таблиц в базе данных"""
        if not self.conn:
            return []
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        return [row[0] for row in cursor.fetchall()]
    
    def get_table_info(self, table_name: str) -> List[Dict]:
        """Получить информацию о колонках таблицы"""
        if not self.conn:
            return []
        
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        return [dict(row) for row in cursor.fetchall()]
    
    def get_table_data(self, table_name: str, limit: int = 100, offset: int = 0) -> Tuple[List[Dict], int]:
        """Получить данные из таблицы с пагинацией"""
        if not self.conn:
            return [], 0
        
        cursor = self.conn.cursor()
        
        # Получаем общее количество записей
        cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
        total_count = cursor.fetchone()["count"]
        
        # Получаем данные с пагинацией
        cursor.execute(f"SELECT * FROM {table_name} LIMIT ? OFFSET ?", (limit, offset))
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows], total_count
    
    def insert_row(self, table_name: str, columns: List[str], values: List[str]) -> bool:
        """Вставить новую строку в таблицу"""
        if not self.conn:
            return False
        
        try:
            cursor = self.conn.cursor()
            placeholders = ", ".join(["?" for _ in values])
            columns_str = ", ".join(columns)
            cursor.execute(f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})", values)
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Ошибка", f"Не удалось вставить запись:\n{e}")
            self.conn.rollback()
            return False
    
    def update_row(self, table_name: str, primary_key_col: str, primary_key_val: str, 
                   columns: List[str], values: List[str]) -> bool:
        """Обновить строку в таблице"""
        if not self.conn:
            return False
        
        try:
            cursor = self.conn.cursor()
            set_clause = ", ".join([f"{col} = ?" for col in columns])
            all_values = values + [primary_key_val]
            cursor.execute(f"UPDATE {table_name} SET {set_clause} WHERE {primary_key_col} = ?", all_values)
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Ошибка", f"Не удалось обновить запись:\n{e}")
            self.conn.rollback()
            return False
    
    def delete_row(self, table_name: str, primary_key_col: str, primary_key_val: str) -> bool:
        """Удалить строку из таблицы"""
        if not self.conn:
            return False
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"DELETE FROM {table_name} WHERE {primary_key_col} = ?", (primary_key_val,))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Ошибка", f"Не удалось удалить запись:\n{e}")
            self.conn.rollback()
            return False
    
    def get_primary_key(self, table_name: str) -> Optional[str]:
        """Получить имя первичного ключа таблицы"""
        info = self.get_table_info(table_name)
        for col in info:
            if col.get("pk", 0) == 1:
                return col["name"]
        return None


class EditRowDialog(QDialog):
    """Диалог для редактирования строки (Create/Update)"""
    
    def __init__(self, parent, table_name: str, db_manager: DatabaseManager, 
                 row_data: Optional[Dict] = None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.table_name = table_name
        self.row_data = row_data
        self.is_new = row_data is None
        
        self.setWindowTitle("Создать запись" if self.is_new else "Редактировать запись")
        self.setModal(True)
        self.resize(500, 400)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        form_layout = QFormLayout()
        self.fields = {}
        
        table_info = db_manager.get_table_info(table_name)
        primary_key = db_manager.get_primary_key(table_name)
        
        for col_info in table_info:
            col_name = col_info["name"]
            col_type = col_info["type"].upper()
            
            # Пропускаем PRIMARY KEY AUTOINCREMENT при создании
            if self.is_new and col_info.get("pk", 0) == 1 and "AUTOINCREMENT" in col_type:
                continue
            
            # Пропускаем первичный ключ при редактировании (он будет в WHERE)
            if not self.is_new and col_name == primary_key:
                continue
            
            # Определяем тип виджета ввода
            if "TEXT" in col_type or "CHAR" in col_type or "CLOB" in col_type:
                widget = QTextEdit()
                widget.setMaximumHeight(100)
                if not self.is_new and row_data:
                    widget.setText(str(row_data.get(col_name, "")))
            elif "INTEGER" in col_type or "REAL" in col_type or "NUMERIC" in col_type:
                widget = QLineEdit()
                if not self.is_new and row_data:
                    widget.setText(str(row_data.get(col_name, "")))
            else:
                widget = QLineEdit()
                if not self.is_new and row_data:
                    widget.setText(str(row_data.get(col_name, "")))
            
            form_layout.addRow(f"{col_name}:", widget)
            self.fields[col_name] = widget
        
        layout.addLayout(form_layout)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        btn_save = QPushButton("Сохранить")
        btn_cancel = QPushButton("Отмена")
        
        btn_save.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        
        buttons_layout.addWidget(btn_save)
        buttons_layout.addWidget(btn_cancel)
        layout.addLayout(buttons_layout)
    
    def get_values(self) -> Dict[str, str]:
        """Получить значения из полей"""
        values = {}
        for col_name, widget in self.fields.items():
            if isinstance(widget, QTextEdit):
                values[col_name] = widget.toPlainText()
            else:
                values[col_name] = widget.text()
        return values


class TableViewWindow(QMainWindow):
    """Окно для просмотра и редактирования таблицы"""
    
    def __init__(self, db_manager: DatabaseManager, table_name: str):
        super().__init__()
        self.db_manager = db_manager
        self.table_name = table_name
        self.current_page = 0
        self.page_size = 50
        self.table_info = db_manager.get_table_info(table_name)
        self.primary_key = db_manager.get_primary_key(table_name)
        
        self.setWindowTitle(f"Таблица: {table_name}")
        self.setMinimumSize(800, 600)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Информация о таблице
        info_label = QLabel(f"Таблица: {table_name}")
        layout.addWidget(info_label)
        
        # Панель инструментов
        toolbar = QGroupBox("Действия")
        toolbar_layout = QHBoxLayout()
        
        btn_create = QPushButton("Создать")
        btn_refresh = QPushButton("Обновить")
        
        btn_create.clicked.connect(self.create_row)
        btn_refresh.clicked.connect(self.refresh_table)
        
        toolbar_layout.addWidget(btn_create)
        toolbar_layout.addWidget(btn_refresh)
        toolbar_layout.addStretch()
        
        toolbar.setLayout(toolbar_layout)
        layout.addWidget(toolbar)
        
        # Таблица
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        
        # Пагинация
        pagination_layout = QHBoxLayout()
        
        btn_prev = QPushButton("◀ Назад")
        btn_next = QPushButton("Вперед ▶")
        self.page_label = QLabel()
        page_size_label = QLabel("Записей на странице:")
        self.page_size_spin = QSpinBox()
        self.page_size_spin.setMinimum(10)
        self.page_size_spin.setMaximum(500)
        self.page_size_spin.setValue(self.page_size)
        self.page_size_spin.valueChanged.connect(self.change_page_size)
        
        btn_prev.clicked.connect(self.prev_page)
        btn_next.clicked.connect(self.next_page)
        
        pagination_layout.addWidget(btn_prev)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(btn_next)
        pagination_layout.addStretch()
        pagination_layout.addWidget(page_size_label)
        pagination_layout.addWidget(self.page_size_spin)
        
        layout.addLayout(pagination_layout)
        
        # Кнопки действий с выбранной строкой
        actions_layout = QHBoxLayout()
        
        btn_edit = QPushButton("Редактировать")
        btn_delete = QPushButton("Удалить")
        
        btn_edit.clicked.connect(self.edit_row)
        btn_delete.clicked.connect(self.delete_row)
        
        actions_layout.addWidget(btn_edit)
        actions_layout.addWidget(btn_delete)
        actions_layout.addStretch()
        
        layout.addLayout(actions_layout)
        
        # Загружаем данные
        self.refresh_table()
    
    def change_page_size(self, new_size: int):
        """Изменить размер страницы"""
        self.page_size = new_size
        self.current_page = 0
        self.refresh_table()
    
    def refresh_table(self):
        """Обновить данные в таблице"""
        offset = self.current_page * self.page_size
        rows, total_count = self.db_manager.get_table_data(self.table_name, self.page_size, offset)
        
        if not rows:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.page_label.setText("Нет данных")
            return
        
        # Получаем названия колонок
        columns = list(rows[0].keys())
        
        # Настраиваем таблицу
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        
        # Заполняем данные
        for row_idx, row_data in enumerate(rows):
            for col_idx, col_name in enumerate(columns):
                value = str(row_data.get(col_name, ""))
                # Ограничиваем длину отображаемого текста
                if len(value) > 100:
                    value = value[:100] + "..."
                item = QTableWidgetItem(value)
                self.table.setItem(row_idx, col_idx, item)
        
        # Обновляем информацию о пагинации
        total_pages = (total_count + self.page_size - 1) // self.page_size if total_count > 0 else 1
        current_page_display = self.current_page + 1 if total_count > 0 else 0
        self.page_label.setText(f"Страница {current_page_display} из {total_pages} (Всего записей: {total_count})")
        
        # Настраиваем ширину колонок
        self.table.resizeColumnsToContents()
    
    def prev_page(self):
        """Предыдущая страница"""
        if self.current_page > 0:
            self.current_page -= 1
            self.refresh_table()
    
    def next_page(self):
        """Следующая страница"""
        offset = (self.current_page + 1) * self.page_size
        rows, total_count = self.db_manager.get_table_data(self.table_name, 1, offset)
        if rows:  # Если есть данные на следующей странице
            self.current_page += 1
            self.refresh_table()
    
    def get_selected_row_data(self) -> Optional[Dict]:
        """Получить данные выбранной строки"""
        current_row = self.table.currentRow()
        if current_row < 0:
            return None
        
        row_data = {}
        offset = self.current_page * self.page_size
        rows, _ = self.db_manager.get_table_data(self.table_name, self.page_size, offset)
        
        if current_row < len(rows):
            return rows[current_row]
        return None
    
    def create_row(self):
        """Создать новую строку"""
        dialog = EditRowDialog(self, self.table_name, self.db_manager)
        if dialog.exec_() == QDialog.Accepted:
            values_dict = dialog.get_values()
            columns = list(values_dict.keys())
            values = list(values_dict.values())
            
            if self.db_manager.insert_row(self.table_name, columns, values):
                QMessageBox.information(self, "Успех", "Запись успешно создана")
                self.refresh_table()
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось создать запись")
    
    def edit_row(self):
        """Редактировать выбранную строку"""
        row_data = self.get_selected_row_data()
        if not row_data:
            QMessageBox.warning(self, "Предупреждение", "Выберите строку для редактирования")
            return
        
        if not self.primary_key:
            QMessageBox.warning(self, "Ошибка", "Не удалось определить первичный ключ таблицы")
            return
        
        primary_key_val = str(row_data[self.primary_key])
        
        dialog = EditRowDialog(self, self.table_name, self.db_manager, row_data)
        if dialog.exec_() == QDialog.Accepted:
            values_dict = dialog.get_values()
            columns = list(values_dict.keys())
            values = list(values_dict.values())
            
            if self.db_manager.update_row(self.table_name, self.primary_key, primary_key_val, columns, values):
                QMessageBox.information(self, "Успех", "Запись успешно обновлена")
                self.refresh_table()
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось обновить запись")
    
    def delete_row(self):
        """Удалить выбранную строку"""
        row_data = self.get_selected_row_data()
        if not row_data:
            QMessageBox.warning(self, "Предупреждение", "Выберите строку для удаления")
            return
        
        if not self.primary_key:
            QMessageBox.warning(self, "Ошибка", "Не удалось определить первичный ключ таблицы")
            return
        
        primary_key_val = str(row_data[self.primary_key])
        
        reply = QMessageBox.question(self, "Подтверждение", 
                                      "Вы уверены, что хотите удалить эту запись?",
                                      QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            if self.db_manager.delete_row(self.table_name, self.primary_key, primary_key_val):
                QMessageBox.information(self, "Успех", "Запись успешно удалена")
                self.refresh_table()
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось удалить запись")


class MainWindow(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        self.db_manager = None
        self.open_windows = []  # Список открытых окон для предотвращения удаления сборщиком мусора
        self.setWindowTitle("Тестовая программа для работы с SQLite")
        self.setMinimumSize(400, 500)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Заголовок
        title_label = QLabel("SQLite Database Viewer")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Кнопка выбора файла
        btn_select_file = QPushButton("Выбрать файл базы данных")
        btn_select_file.clicked.connect(self.select_database_file)
        layout.addWidget(btn_select_file)
        
        # Информация о выбранном файле
        self.file_label = QLabel("Файл не выбран")
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)
        
        # Список таблиц
        tables_label = QLabel("Таблицы:")
        layout.addWidget(tables_label)
        
        self.tables_list = QListWidget()
        self.tables_list.itemDoubleClicked.connect(self.open_table)
        layout.addWidget(self.tables_list)
        
        # Кнопка "Открыть"
        btn_open = QPushButton("Открыть")
        btn_open.clicked.connect(self.open_selected_table)
        layout.addWidget(btn_open)
    
    def select_database_file(self):
        """Выбрать файл базы данных"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл базы данных SQLite",
            "",
            "SQLite Database (*.db *.sqlite *.sqlite3);;Все файлы (*.*)"
        )
        
        if file_path:
            self.load_database(file_path)
    
    def load_database(self, file_path: str):
        """Загрузить базу данных"""
        if self.db_manager:
            self.db_manager.disconnect()
        
        self.db_manager = DatabaseManager(file_path)
        if self.db_manager.connect():
            self.file_label.setText(f"Файл: {Path(file_path).name}")
            
            # Загружаем список таблиц
            tables = self.db_manager.get_tables()
            self.tables_list.clear()
            for table in tables:
                self.tables_list.addItem(QListWidgetItem(table))
            
            if not tables:
                QMessageBox.information(self, "Информация", "В базе данных нет таблиц")
        else:
            self.file_label.setText("Ошибка загрузки файла")
            self.tables_list.clear()
    
    def open_selected_table(self):
        """Открыть выбранную таблицу"""
        current_item = self.tables_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Предупреждение", "Выберите таблицу из списка")
            return
        
        table_name = current_item.text()
        self.open_table_by_name(table_name)
    
    def open_table(self, item: QListWidgetItem):
        """Открыть таблицу по двойному клику"""
        table_name = item.text()
        self.open_table_by_name(table_name)
    
    def open_table_by_name(self, table_name: str):
        """Открыть окно с таблицей"""
        if not self.db_manager:
            QMessageBox.warning(self, "Ошибка", "База данных не загружена")
            return
        
        table_window = TableViewWindow(self.db_manager, table_name)
        # Сохраняем ссылку на окно, чтобы оно не было удалено сборщиком мусора
        self.open_windows.append(table_window)
        # Удаляем из списка при закрытии окна
        def remove_window():
            if table_window in self.open_windows:
                self.open_windows.remove(table_window)
        table_window.destroyed.connect(remove_window)
        table_window.show()


def main():
    """Главная функция"""
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

