PY_SRCS = src tests

RADON_MIN_MI = 65

.DEFAULT_GOAL := help

.PHONY: help install lint lint-fix fmt format-check type test test-unit test-integration security cc mi hal raw check docker-up docker-down docker-logs

help:
	@echo "Доступные цели:"
	@echo " install - установить проект и dev-зависимости через uv"
	@echo " lint - проверить код с Ruff"
	@echo " lint-fix - исправить доступные замечания Ruff"
	@echo " fmt - ruff format"
	@echo " format-check - проверить форматирование Ruff"
	@echo " type - mypy (проверка типов)"
	@echo " test - все тесты, coverage gate и HTML-отчет"
	@echo " test-unit - тесты без PostgreSQL"
	@echo " test-integration - integration-тесты на reservation_test"
	@echo " security - bandit (скан безопасности)"
	@echo " cc - radon cc (цикломатическая сложность) + quality gate"
	@echo " mi - radon mi (индекс поддерживаемости) + quality gate"
	@echo " hal - radon hal (метрика халстеда)"
	@echo " raw - radon raw (SLOC, LLOC, комментарии, число функций/классов)"
	@echo " check - локальный quality gate"
	@echo " docker-up - собрать и запустить API с PostgreSQL"
	@echo " docker-down - остановить Compose-сервисы"
	@echo " docker-logs - показать логи Compose-сервисов"

install:
	uv sync --all-groups


# ===============================
# Ruff: линт и форматирование
# ===============================
lint:
	uv run ruff check $(PY_SRCS)

lint-fix:
	uv run ruff check $(PY_SRCS) --fix

fmt:
	uv run ruff format $(PY_SRCS)

format-check:
	uv run ruff format --check $(PY_SRCS)

# ===============================
# Mypy: проверка типов
# ===============================

type:
	uv run mypy

test:
	uv run pytest --cov --cov-report=term-missing --cov-report=html

test-unit:
	uv run pytest -m "not integration"

test-integration:
	uv run pytest -m integration

# ===============================
# Bandit: анализ безопасности
# ===============================
security:
# -r: рекурсивно, -lll: максимум строгости вывода,
# -x: исключения
	uv run bandit -r src -lll -x .venv,venv,build,dist,alembic/versions

# ===============================
# Radon: метрики
# ===============================
# Цикломатическая сложность: подробный вывод (-s), среднее (-a)
cc:
	uv run radon cc -s -a src
	@# QUALITY GATE: проваливаем, если есть элементы со сложностью E/F
	@if uv run radon cc -s src | grep -E -- ' - [EF] \('; then \
		echo "❌ Radon CC: обнаружены функции со сложностью E/F"; \
		exit 1; \
	else \
		echo "✅ Radon CC: нет функций с E/F"; \
	fi

# Индекс поддерживаемости
mi:
	@uv run radon mi src
	@# QUALITY GATE: проваливаем, если есть MI < $(RADON_MIN_MI)
	@MI_BAD=$$(uv run radon mi -s src | awk -F'[()]' 'NF > 1 && $$2+0 < $(RADON_MIN_MI) {print $$0}'); \
	if [ -n "$$MI_BAD" ]; then \
		echo "❌ Radon MI: найден MI < $(RADON_MIN_MI)"; \
		exit 1; \
	else \
		echo "✅ Radon MI: все файлы с MI >= $(RADON_MIN_MI)"; \
	fi
# Метрика халстеда
hal:
	uv run radon hal src
# Метрика Raw
raw:
	uv run radon raw src

# ===============================
# Комплексные цели
# ===============================
# Локальный прогон без изменения файлов
check: lint format-check type test security cc mi

docker-up:
	docker compose up --build --detach

docker-down:
	docker compose down

docker-logs:
	docker compose logs --follow
