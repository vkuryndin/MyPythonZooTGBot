# PythonZoo — сессионное задание по дисциплине «Язык программирования Python»

В рамках задания был сделан Telegram-бот с викториной, который помогает пользователю узнать своё «тотемное животное» из Московского зоопарка и познакомиться с программой опеки «Возьми животное под опеку».

Проект сделан в рамках учебного кейса для реального заказчика. Основной сценарий: пользователь проходит викторину, получает результат с животным, может узнать об опеке, поделиться результатом, связаться с сотрудником и оставить отзыв.

---

## Возможности бота

- запуск викторины через меню;
- вопросы с вариантами ответов;
- перемешивание вопросов и вариантов;
- подсчёт баллов;
- определение итогового животного;
- показ результата с описанием и фотографией;
- сохранение результата в PostgreSQL;
- просмотр последнего результата через `/result`;
- информация о программе опеки Московского зоопарка;
- ссылка и контакты программы опеки;
- шаринг результата в Telegram, VK, WhatsApp и MAX;
- отправка сообщения сотруднику зоопарка;
- сбор обратной связи по викторине;
- генерация отдельной AI-картинки по результату;
- read-only админский режим;
- запуск на сервере AWS через Docker Compose.

---

## Команды пользователя

- `/start` — открыть стартовый экран;
- `/help` — справка;
- `/result` — показать последний результат;
- `/cancel` — отменить текущее действие.

## Команды администратора

- `/admin` — админский режим;
- `/admin_stats` — статистика проекта;
- `/admin_contacts` — последние обращения;
- `/admin_feedback` — последние отзывы.

Админские команды доступны только пользователю, чей Telegram ID указан в `ADMIN_CHAT_ID`.

---

## Структура проекта

Проект имеет модульную архитектуру: обработчики Telegram-событий отделены от бизнес-логики, работы с PostgreSQL, Redis и внешними сервисами.

```text
    MyPythonZoo/
    ├── assets/
    │   └── images/
    │       ├── elephant.jpg
    │       ├── flamingo.jpg
    │       ├── manul.jpg
    │       ├── meerkat.jpg
    │       ├── mz_logo.jpg
    │       ├── OPEKA.JPG
    │       ├── otter.jpg
    │       ├── sea_lion.jpg
    │       ├── sloth.jpg
    │       └── tiger.jpg
    │
    ├── bot/
    │   ├── __init__.py
    │   ├── config.py
    │   │
    │   ├── handlers/
    │   │   ├── __init__.py
    │   │   ├── admin.py
    │   │   ├── commands.py
    │   │   ├── fallback.py
    │   │   ├── menu.py
    │   │   ├── quiz.py
    │   │   ├── result_actions.py
    │   │   ├── result_view.py
    │   │   └── start.py
    │   │
    │   ├── keyboards/
    │   │   ├── __init__.py
    │   │   ├── action_keyboards.py
    │   │   ├── main_menu.py
    │   │   └── quiz_keyboards.py
    │   │
    │   ├── repositories/
    │   │   ├── __init__.py
    │   │   ├── admin_repository.py
    │   │   ├── contact_repository.py
    │   │   ├── database.py
    │   │   ├── feedback_repository.py
    │   │   ├── quiz_result_repository.py
    │   │   ├── quiz_session_repository.py
    │   │   └── redis_client.py
    │   │
    │   ├── services/
    │   │   ├── __init__.py
    │   │   ├── action_names.py
    │   │   ├── email_service.py
    │   │   ├── image_generation_service.py
    │   │   ├── message_utils.py
    │   │   ├── quiz_service.py
    │   │   ├── rate_limit_service.py
    │   │   └── result_service.py
    │   │
    │   └── states/
    │       ├── __init__.py
    │       └── user_states.py
    │
    ├── data/
    │   ├── animals.json
    │   └── questions.json
    │
    ├── migrations/
    │   └── 001_init.sql
    │
    ├── scripts/
    │   └── check_project.py
    │
    ├── .dockerignore
    ├── .env.example
    ├── docker-compose.yml
    ├── Dockerfile
    ├── main.py
    ├── README.md
    └── requirements.txt
```

### Основные директории

| Директория | Назначение |
|---|---|
| `assets/images/` | Изображения для бота: фотографии животных, логотип и картинка для раздела опеки. |
| `bot/handlers/` | Обработчики команд, сообщений и callback-кнопок. |
| `bot/keyboards/` | Inline-клавиатуры для меню, викторины, результата, контактов, отзывов и шаринга. |
| `bot/repositories/` | Работа с PostgreSQL и Redis. |
| `bot/services/` | Бизнес-логика и внешние интеграции. |
| `bot/states/` | FSM-состояния для сценариев контакта с сотрудником и обратной связи. |
| `data/` | Данные викторины: животные, вопросы, варианты ответов, баллы и теги для AI-картинок. |
| `migrations/` | SQL-миграция для создания таблиц PostgreSQL. |
| `scripts/` | Вспомогательные скрипты для проверки проекта перед сдачей. |

### Ключевые компоненты

| Файл | Назначение |
|---|---|
| `main.py` | Точка входа: инициализирует PostgreSQL, Redis, FSM-хранилище, router-ы и запускает polling. |
| `bot/config.py` | Загрузка и валидация настроек из `.env`. |
| `bot/handlers/quiz.py` | Прохождение викторины, обработка ответов, защита от двойных кликов. |
| `bot/handlers/result_actions.py` | Действия после результата: шаринг, контакт с сотрудником, отзыв, AI-картинка. |
| `bot/handlers/admin.py` | Read-only админский режим. |
| `bot/repositories/quiz_session_repository.py` | Redis-сессии викторины, баллы, `image_tags`, lock для ответа. |
| `bot/repositories/quiz_result_repository.py` | Сохранение и получение результатов викторины. |
| `bot/services/quiz_service.py` | Загрузка JSON-данных и расчёт итогового животного. |
| `bot/services/image_generation_service.py` | Генерация AI-картинки через Hugging Face. |
| `bot/services/rate_limit_service.py` | Redis cooldown для защиты от частых действий. |
| `scripts/check_project.py` | Проверка JSON-данных, картинок, зависимостей, `.env.example`, `.gitignore` и миграции. |

---

## Технологии

- Python 3.12;
- aiogram 3.x;
- PostgreSQL;
- Redis;
- asyncpg;
- pydantic-settings;
- Docker Compose;
- Hugging Face Inference API;
- SMTP.

### Версии используемого ПО

#### Основной стек

- Python — 3.12;
- aiogram — `>=3.13,<4`;
- PostgreSQL — 16;
- Redis — 7;
- asyncpg — `>=0.29,<1`;
- pydantic-settings — `>=2.6,<3`;
- python-dotenv — `>=1.0,<2`.

#### Изображения и AI-генерация

- Hugging Face Hub SDK — `>=0.24`;
- Pillow — `>=10.0`;
- модель генерации по умолчанию — `black-forest-labs/FLUX.1-schnell`;
- provider по умолчанию — `hf-inference`.

#### Инфраструктура

- Docker;
- Docker Compose;
- PostgreSQL Docker image — `postgres:16-alpine`;
- Redis Docker image — `redis:7-alpine`.

#### Разворачивание

- AWS EC2;
- запуск через Docker Compose;
- режим работы Telegram-бота — polling.

---
## Хранение данных

PostgreSQL используется для постоянных данных:

- результаты викторины;
- контактные заявки;
- отзывы пользователей.

Redis используется для временных данных:

- FSM-состояния aiogram;
- активные сессии викторины;
- защита от двойных кликов;
- cooldown для частых действий.

---
## Безопасность

В проекте предусмотрены базовые меры защиты:

- секреты хранятся в `.env`;
- `.env` не попадает в репозиторий;
- настройки читаются через `pydantic-settings`;
- `BOT_LINK` валидируется;
- пользовательский текст ограничивается по длине;
- email и Telegram username проходят проверку;
- служебные сообщения сотруднику отправляются без HTML/Markdown-разметки;
- для контактов, отзывов и AI-генерации используется Redis cooldown;
- ответы викторины защищены Redis lock;
- ошибки внешних сервисов логируются и не ломают пользовательский сценарий.

---
## Логирование

В проекте используется стандартное логирование Python.

Логируются:

- запуск и остановка бота;
- подключение к PostgreSQL;
- подключение к Redis;
- регистрация router-ов;
- запуск polling;
- ошибки SMTP;
- ошибки Hugging Face;
- длительность AI-генерации.

В логи не выводятся токены, пароли, пользовательские сообщения, email, Telegram-контакты, prompt и image tags.

---
## Настройка `.env`

```env
```env
BOT_TOKEN=Пример
BOT_LINK=Пример
ADMIN_CHAT_ID=Пример

DB_HOST=Пример
DB_PORT=Пример
DB_NAME=Пример
DB_USER=Пример
DB_PASSWORD=Пример

SMTP_HOST=Пример
SMTP_PORT=Пример
SMTP_USER=Пример
SMTP_PASSWORD=Пример
STAFF_EMAIL=Пример

REDIS_URL=Пример

HUGGINGFACE_API_TOKEN=Пример
HF_IMAGE_MODEL=Пример
HF_IMAGE_CACHE_DIR=Пример
HF_PROVIDER=Пример

```
---

### Локальный запуск

```
    pip install -r requirements.txt
```
Запустить PostgreSQL и Redis локально или указать доступы к уже запущенным сервисам в .env.
Применить миграцию из файла:

```
    migrations/001_init.sql
```

Запустить бота:

```
     python main.py
```


### Запуск через Docker Compose


Проект можно запустить через Docker Compose. В этом режиме поднимаются три сервиса:

- `bot` — Telegram-бот;
- `postgres` — PostgreSQL;
- `redis` — Redis.

Перед запуском нужно создать файл `.env` рядом с `docker-compose.yml`.

Для Docker Compose в `.env` важно указать:

```env
    DB_HOST=postgres
   REDIS_URL=redis://redis:6379/0
```

Запуск:

```
    docker compose up -d --build
```
Проверка контейнеров:

```
   docker compose ps
```

Просмотр логов бота:

```
   docker compose logs -f bot
```

Остановить только бота:

```
    docker compose stop bot
```

Запустить бота обратно:

```
    docker compose start bot
```
Остановить все контейнеры без удаления данных:
```
    docker compose down
```
Не использовать без необходимости:

```
docker compose down -v
```

Флаг -v удаляет Docker volumes, в которых хранятся данные PostgreSQL, Redis и сгенерированные изображения.

### Обновление на сервере

После изменения кода локально:

```bash
git add .
git commit -m "Update project"
git push
```
На сервере:
```
cd ~/MyPythonZooTGBot
git pull
docker compose up -d --build bot
docker compose logs -f bot
```
При таком обновлении пересобирается только контейнер бота. PostgreSQL и Redis не пересоздаются, данные сохраняются в Docker volumes.

--- 
## Самопроверка проекта

В проект добавлен скрипт самопроверки:

```
python scripts/check_project.py
```

Скрипт проверяет:

- корректность `animals.json`;
- корректность `questions.json`;
- наличие изображений животных;
- наличие `image_tags`;
- корректность `scores`;
- достижимость всех животных по баллам;
- наличие нужных переменных в `.env.example`;
- отсутствие похожих на реальные секретов в `.env.example`;
- наличие важных правил в `.gitignore`;
- что `.env` не отслеживается Git;
- наличие ключевых зависимостей;
- наличие основных таблиц и полей в миграции.

## Проверка перед сдачей

Пример.

Перед отправкой проекта нужно вручную проверить:

- `/start`;
- прохождение викторины;
- просмотр результата;
- повторное прохождение;
- `/cancel`;
- информацию об опеке;
- отправку сообщения сотруднику;
- отправку отзыва;
- шаринг результата;
- AI-картинку;
- админские команды.

## Примеры работы

Пример.

## Статус проекта

Проект развернут на AWS EC2 через Docker Compose.

На сервере работают:

- контейнер с Telegram-ботом;
- PostgreSQL;
- Redis.

Бот запускается в режиме polling. Осозннано было принято решение не использовать webhook в связи со сложностью реализации данного механизма