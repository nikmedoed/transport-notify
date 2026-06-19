# Transportation Overlay

Небольшое Windows-приложение: висит в трее, в нужный период показывает микро-окно в нижнем левом углу и обновляет прибытие автобусов раз в 30 секунд.

## Запуск

```powershell
uv sync
uv run python main.py
```

Альтернативно, через установленный console script:

```powershell
uv run transport-overlay
```

Настройки маршрутов, остановки и периода лежат в `config.toml`.

Для разработки период выключен:

```toml
[schedule]
enabled = false
```

Для обычного режима включи период:

```toml
[schedule]
enabled = true
active_from = "18:30"
active_to = "21:00"
```

Окно показывает только номер маршрута и минуты до ближайших автобусов. Двойной клик по иконке в трее показывает или прячет оверлей.

## Структура

- `main.py` — запуск из корня проекта и сборка Qt-приложения.
- `src/transport_overlay/app.py` — entrypoint для console script.
- `src/transport_overlay/config.py` — чтение `config.toml`.
- `src/transport_overlay/poller.py` — фоновое обновление.
- `src/transport_overlay/yandex_source.py` — парсинг данных Яндекса.
- `src/transport_overlay/ui/` — оверлей и иконка в трее.
