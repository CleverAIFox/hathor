.PHONY: up down logs ps check lint type arch test cov clean

up:            ## core 프로파일만 기동 (8GB 노드 기준)
	docker compose up -d
up-ml:
	docker compose --profile ml up -d
down:
	docker compose down
logs:
	docker compose logs -f --tail=100
ps:
	docker compose ps

check: lint type arch test  ## CI와 동일한 검사를 로컬에서 수행

lint:
	cd core && uv run ruff check . && uv run ruff format --check .
type:
	cd core && uv run mypy hathor --strict
arch:
	cd core && uv run lint-imports
test:
	cd core && uv run pytest --cov=hathor --cov-fail-under=75 -q

clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
