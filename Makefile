.PHONY: install install-frontend dev test eval lint demo demo-frontend clean

install:
	cd backend && python3 -m pip install -r requirements.txt pytest ruff

install-frontend:
	cd frontend && npm install

dev:            ## run the FastAPI backend on :8000
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend:   ## run the Next.js dev server on :3000 (proxies /api to :8000)
	cd frontend && npm run dev

test:           ## backend test suite
	cd backend && python3 -m pytest tests -q

eval:           ## run the 56-question evaluation suite (writes eval/results.md)
	cd backend && python3 -m app.evaluator.runner --demo --out ../eval

lint:
	cd backend && ruff check app tests

demo:           ## print a full transcript of all five agents
	cd backend && python3 scripts/demo.py

build-frontend:
	cd frontend && npm run build

clean:
	find backend -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/.repopilot
