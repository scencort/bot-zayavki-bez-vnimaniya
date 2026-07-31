# Бот для заявок без внимания

Telegram-бот для рассылки заявок без внимания по риэлторам.

## Что умеет сейчас

- Пользователь нажимает `/start`.
- Бот проверяет, привязан ли Telegram ID к риэлтору в `config/realtors.json`.
- Если привязка есть, пользователь попадает в список подписчиков.
- Админ видит кнопку `Выслать заявки без внимания`.
- При нажатии кнопки бот читает Google Docs и отправляет каждому подписчику ссылки его риэлтора.
- Если после ФИО стоит `0` или ссылок нет, сообщение не отправляется.

## Тестовая настройка

Сейчас в проекте добавлена тестовая привязка:

- `540311740` → `Григоренко Анастасия Олеговна`

## Структура

- `app/main.py` — polling-бот и разовая рассылка.
- `app/google_docs.py` — загрузка текста из Google Docs.
- `app/parser.py` — поиск блока риэлтора и извлечение ссылок.
- `app/subscribers.py` — хранение подписчиков.
- `app/telegram_client.py` — работа с Telegram Bot API.
- `config/realtors.json` — боевые соответствия ФИО и Telegram ID.
- `data/subscribers.json` — пользователи, которые нажали `/start`.

## Переменные окружения

- `TELEGRAM_BOT_TOKEN` — токен Telegram-бота.
- `GOOGLE_DOCS_URL` — ссылка на Google Docs.
- `TELEGRAM_ADMIN_IDS` — ID админов через запятую.
- `REALTORS_CONFIG_PATH` — путь к файлу привязок.
- `SUBSCRIBERS_PATH` — путь к файлу подписчиков.
- `POLL_INTERVAL_SECONDS` — пауза между циклами polling.

## Запуск бота

```powershell
$env:TELEGRAM_BOT_TOKEN="123456:example"
$env:GOOGLE_DOCS_URL="https://docs.google.com/document/d/FILE_ID/edit"
$env:TELEGRAM_ADMIN_IDS="540311740"

& "C:\Users\yaros\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m app.main --mode poll
```

## Разовая тестовая рассылка

```powershell
$env:TELEGRAM_BOT_TOKEN="123456:example"
$env:GOOGLE_DOCS_URL="https://docs.google.com/document/d/FILE_ID/edit"
$env:TELEGRAM_ADMIN_IDS="540311740"

& "C:\Users\yaros\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m app.main --mode broadcast-once
```

## Тесты

```powershell
& "C:\Users\yaros\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v
```
