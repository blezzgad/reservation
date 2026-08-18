# Reservation Service

Асинхронный API для резервирования товарных остатков. Сервис реализован на FastAPI,
SQLAlchemy 2.x и PostgreSQL.

Основные возможности:

- создание и удаление товаров;
- создание и получение резервирований;
- идемпотентная обработка повторных запросов;
- защита от перепродажи при конкурентном доступе;
- логирование запросов с `X-Request-ID`;
- unit-, API- и integration-тесты.

## Требования

Для запуска в Docker требуются Docker и Docker Compose.

Для локального запуска дополнительно требуются:

- Python 3.11.9;
- [uv](https://docs.astral.sh/uv/);
- PostgreSQL 16.

## Конфигурация

Создайте локальный файл окружения:

```bash
cp .env.example .env
```

Основные параметры находятся в `.env.example`. По умолчанию используются:

- API: `http://localhost:8000`;
- PostgreSQL: `localhost:5433`;
- основная база: `reservation`;
- тестовая база: `reservation_test`.

## Запуск через Docker Compose

Соберите и запустите API вместе с PostgreSQL:

```bash
docker compose up --build --detach
docker compose ps
```

При запуске контейнер API автоматически применяет миграции Alembic.

Проверка доступности:

```bash
curl http://localhost:8000/health
```

Ожидаемый ответ:

```json
{"status":"ok"}
```

Документация OpenAPI доступна по адресу
[http://localhost:8000/docs](http://localhost:8000/docs).

Просмотр логов и остановка сервисов:

```bash
docker compose logs --follow api
docker compose down
```

## Локальный запуск

Установите зависимости, запустите PostgreSQL и примените миграции:

```bash
uv sync --all-groups
docker compose up --detach postgres
uv run alembic upgrade head
uv run uvicorn reservation_service.main:app --reload
```

## API

### Создание товара

```bash
curl -i -X POST http://localhost:8000/api/v1/products \
  -H 'Content-Type: application/json' \
  -d '{"sku":"sku-001","available_quantity":10}'
```

### Создание резервирования

Укажите идентификатор созданного товара в `product_id`:

```bash
curl -i -X POST http://localhost:8000/api/v1/reservations \
  -H 'Content-Type: application/json' \
  -d '{"external_id":"reservation-123","product_id":1,"quantity":3}'
```

Повторный запрос с теми же параметрами вернёт существующее резервирование без повторного
уменьшения остатка. Использование того же `external_id` с другими параметрами вернёт
`409 Conflict`.

### Получение резервирования

```bash
curl -i http://localhost:8000/api/v1/reservations/reservation-123
```

### Удаление товара

```bash
curl -i -X DELETE http://localhost:8000/api/v1/products/1
```

Товар с существующими резервированиями удалить нельзя.

## Миграции

Применить все миграции:

```bash
uv run alembic upgrade head
```

Откатить последнюю миграцию:

```bash
uv run alembic downgrade -1
```

## Тесты и проверки

Для integration-тестов PostgreSQL должен быть запущен. Тесты используют только отдельную
базу `reservation_test`; основная база `reservation` не очищается.

```bash
# Все тесты, проверка покрытия и HTML-отчёт в htmlcov/
make test

# Тесты без PostgreSQL
make test-unit

# Только integration-тесты
make test-integration

# Полный quality gate
make check

# Pre-commit hooks
uv run pre-commit run --all-files
```
