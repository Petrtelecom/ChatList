# Схема базы данных ChatList

База данных использует SQLite и состоит из 4 таблиц.

## Таблицы

### 1. prompts (Промты)

Хранит все введенные пользователем промты с метаданными.

| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Уникальный идентификатор промта |
| date | DATETIME | Дата и время создания промта (DEFAULT CURRENT_TIMESTAMP) |
| prompt | TEXT NOT NULL | Текст промта |
| tags | TEXT | Теги промта (через запятую или JSON) |

**Индексы:**
- `idx_prompts_date` на поле `date`
- `idx_prompts_tags` на поле `tags`

---

### 2. models (Нейросети)

Хранит информацию о доступных нейросетях и их API-настройках.

| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Уникальный идентификатор модели |
| name | TEXT NOT NULL UNIQUE | Название модели (например, "GPT-4", "Claude", "DeepSeek") |
| api_url | TEXT NOT NULL | URL API-эндпоинта модели |
| api_id | TEXT NOT NULL | Имя переменной окружения с API-ключом (хранится в .env файле) |
| is_active | INTEGER DEFAULT 1 | Флаг активности модели (1 - активна, 0 - неактивна) |
| model_type | TEXT | Тип модели (openai, deepseek, groq, anthropic и т.д.) |
| created_at | DATETIME DEFAULT CURRENT_TIMESTAMP | Дата создания записи |

**Индексы:**
- `idx_models_is_active` на поле `is_active`
- `idx_models_name` на поле `name`

---

### 3. results (Результаты)

Хранит сохраненные пользователем ответы от нейросетей.

| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Уникальный идентификатор результата |
| prompt_id | INTEGER NOT NULL | Ссылка на промт из таблицы prompts (FOREIGN KEY) |
| model_id | INTEGER NOT NULL | Ссылка на модель из таблицы models (FOREIGN KEY) |
| response_text | TEXT NOT NULL | Текст ответа от модели |
| saved_at | DATETIME DEFAULT CURRENT_TIMESTAMP | Дата и время сохранения результата |
| tokens_used | INTEGER | Количество использованных токенов (опционально) |
| response_time | REAL | Время ответа в секундах (опционально) |

**Индексы:**
- `idx_results_prompt_id` на поле `prompt_id`
- `idx_results_model_id` на поле `model_id`
- `idx_results_saved_at` на поле `saved_at`

**Внешние ключи:**
- `prompt_id` → `prompts(id) ON DELETE CASCADE`
- `model_id` → `models(id) ON DELETE RESTRICT`

---

### 4. settings (Настройки)

Хранит настройки приложения в формате ключ-значение.

| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Уникальный идентификатор настройки |
| key | TEXT NOT NULL UNIQUE | Ключ настройки |
| value | TEXT | Значение настройки (может быть JSON для сложных настроек) |

**Индексы:**
- `idx_settings_key` на поле `key`

**Предустановленные настройки:**
- `db_version` - версия схемы БД
- `theme` - тема интерфейса
- `default_export_format` - формат экспорта по умолчанию (markdown/json)
- `auto_save_prompts` - автоматическое сохранение промтов (true/false)

---

## Диаграмма связей

```
prompts (1) ──< (N) results
                     │
models (1) ──────────┘

settings (независимая таблица)
```

---

## Инициализация базы данных

При первом запуске программы создается файл `chatlist.db` в корневой директории проекта с таблицами, индексами и начальными данными.

### Начальные данные

В таблицу `models` добавляются примеры популярных моделей:
- OpenAI GPT-4 (api_id: `OPENAI_API_KEY`)
- DeepSeek (api_id: `DEEPSEEK_API_KEY`)
- Groq (api_id: `GROQ_API_KEY`)
- Anthropic Claude (api_id: `ANTHROPIC_API_KEY`)

В таблицу `settings` добавляются настройки по умолчанию.




