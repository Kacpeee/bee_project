-include .env
export

.PHONY: up down build init logs ps reset restart shell shell-db

up:        ## Uruchom wszystkie serwisy
	docker compose up -d

down:      ## Zatrzymaj wszystkie serwisy
	docker compose down

build:     ## Zbuduj obrazy Dockera
	docker compose build

init:      ## Uruchom serwisy i zaladuj dane (pierwsze uruchomienie)
	docker compose up -d
	docker compose run --rm db-init

logs:      ## Sledz logi (Ctrl+C aby wyjsc)
	docker compose logs -f

ps:        ## Pokaz status serwisow
	docker compose ps

reset:     ## Zatrzymaj serwisy i usun dane (volumes)
	docker compose down -v

restart:   ## Zrestartuj serwis (np. make restart s=frontend)
	docker compose restart $(s)

shell:     ## Terminal w kontenerze (np. make shell s=backend)
	docker compose exec $(s) sh

shell-db:  ## Otworz powloke psql
	docker compose exec db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)
