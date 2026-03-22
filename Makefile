.PHONY: install dev backend frontend migrate

install:
	pip install -r requirements.txt
	cd frontend && npm install

migrate:
	python -m backend.migrate_old_db

backend:
	uvicorn backend.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

dev:
	@echo "Avvia in 2 terminali separati:"
	@echo "  make backend"
	@echo "  make frontend"
