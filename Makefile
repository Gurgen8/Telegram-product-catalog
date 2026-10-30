.DEFAULT_GOAL := help
.PHONY: help start stop restart rebuild status logs logs-bot logs-backend webhook-info clear-catalog reset kill-replicas heal

COMPOSE := docker compose
ENV = $(shell grep -E '^$(1)=' .env | cut -d= -f2-)

help: ## Список команд
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-15s %s\n", $$1, $$2}'

start: ## Запустить всё: туннель, сервисы, вебхук бота
	./start.sh

stop: ## Остановить всё (данные сохраняются)
	./stop.sh

restart: stop start ## Перезапустить всё с новым туннелем

rebuild: ## Пересобрать и перезапустить сервисы после правок кода (туннель не трогает)
	$(COMPOSE) up -d --build

status: ## Статус всех сервисов
	$(COMPOSE) ps -a

logs: ## Логи всех сервисов в реальном времени
	$(COMPOSE) logs -f --tail 50

logs-bot: ## Логи бота
	$(COMPOSE) logs -f --tail 50 bot

logs-backend: ## Логи backend
	$(COMPOSE) logs -f --tail 50 backend

webhook-info: ## Состояние вебхука в Telegram (адрес, очередь, последняя ошибка)
	@curl -s "https://api.telegram.org/bot$(call ENV,BOT_TOKEN)/getWebhookInfo" | python3 -m json.tool

clear-catalog: ## Удалить все товары и картинки (открытые страницы обновятся сами)
	$(COMPOSE) exec -T postgres sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "DELETE FROM products;"'
	$(COMPOSE) exec -T minio sh -c 'mc alias set l http://localhost:9000 "$$MINIO_ROOT_USER" "$$MINIO_ROOT_PASSWORD" >/dev/null && mc rm --recursive --force l/$(or $(call ENV,S3_BUCKET),products)/ >/dev/null 2>&1; true'

reset: ## ОПАСНО: удалить базу и хранилище целиком и запустить с нуля
	@read -p "Удалить ВСЕ данные? [y/N] " ok && [ "$$ok" = "y" ]
	$(COMPOSE) down -v
	./start.sh

kill-replicas: ## Тест отказоустойчивости: убить по одной копии backend, bot, frontend
	docker kill catalog-backend-1 catalog-bot-1 catalog-frontend-1

heal: ## Вернуть убитые копии
	$(COMPOSE) up -d
