.PHONY: install backend frontend seed

install:
	pip install -r requirements.txt
	cd frontend && npm install

backend:
	uvicorn backend.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

seed:
	python backend/seed_test_data.py
