# Vanta Deep Research — Docker helpers
# All commands run from repo root.

COMPOSE       := docker compose -f deploy/docker-compose.yml
COMPOSE_DEV   := $(COMPOSE) -f deploy/docker-compose.override.yml
PROJECT       := drapi

.PHONY: help build up down dev logs shell db-shell migrate ps clean

help:          ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Production ──────────────────────────────────────────────────────────────

build:         ## Build the API image
	$(COMPOSE) build --no-cache api

up:            ## Start all services (detached)
	$(COMPOSE) up -d

down:          ## Stop and remove containers
	$(COMPOSE) down

logs:          ## Tail logs for all services
	$(COMPOSE) logs -f --tail=100

ps:            ## Show running containers
	$(COMPOSE) ps

migrate:       ## Run DB migrations inside running api container
	$(COMPOSE) exec api python scripts/migrate.py

shell:         ## Open a shell in the api container
	$(COMPOSE) exec api /bin/bash

db-shell:      ## Open psql in the postgres container
	$(COMPOSE) exec postgres psql -U postgres drapi

# ── Local development ────────────────────────────────────────────────────────

dev:           ## Start in dev mode (hot-reload, no Caddy)
	$(COMPOSE_DEV) up

dev-build:     ## Build then start in dev mode
	$(COMPOSE_DEV) up --build

dev-down:      ## Stop dev services
	$(COMPOSE_DEV) down

# ── Cleanup ──────────────────────────────────────────────────────────────────

clean:         ## Remove containers, volumes, and built images
	$(COMPOSE) down -v --rmi local
