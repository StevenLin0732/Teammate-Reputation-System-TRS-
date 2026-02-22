# Justfile for TRS development

default:
    @just --list

install-backend:
    pip install -r requirements.txt

install-frontend:
    cd trs-webapp && npm install

install: install-backend install-frontend

dev-backend:
    python app.py

# Run Flask backend (production-like, no debug)
run-backend:
    FLASK_ENV=production python app.py

# Run Next.js frontend (development)
dev-frontend:
    cd trs-webapp && npm run dev

# Run Next.js frontend (production)
run-frontend:
    cd trs-webapp && npm run build && cd trs-webapp && npm start

# Run both backend and frontend for development
dev:
    @echo "Starting backend and frontend in development mode..."
    @just --justfile {{justfile()}} dev-backend &
    @sleep 2
    @just --justfile {{justfile()}} dev-frontend

# Run both backend and frontend for local network deployment
run:
    @echo "Starting backend and frontend for local network..."
    @just --justfile {{justfile()}} run-backend &
    @sleep 2
    @just --justfile {{justfile()}} run-frontend

# Seed the database
seed:
    python seed_db.py

# Clean Python cache
clean-python:
    find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Clean Next.js build artifacts
clean-frontend:
    cd trs-webapp && rm -rf .next node_modules/.cache

# Clean everything
clean: clean-python clean-frontend
