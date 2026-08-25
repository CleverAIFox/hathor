.PHONY: up down logs ps check lint type arch test cov docs size resize split clean clean-all setup env doctor apply

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

check: docs size lint type arch test  ## CI와 동일한 검사를 로컬에서 수행

docs:          ## 부록 A 색인이 결정 기록과 일치하는지 (D-0042)
	python3 tools/sync_decision_index.py --check

size:          ## 파일 길이 래칫. 늘어도 줄어도 빨개진다 (D-0117)
	python3 tools/check_file_size.py

resize:        ## 래칫을 현재 값으로 내린다. make size가 "줄었다"고 하면
	python3 tools/check_file_size.py --update

split:         ## 결정 기록을 번호대별로 다시 나눈다. make docs가 빨개지면 (O-30)
	python3 tools/split_decisions.py
lint:
	cd core && uv run ruff check . && uv run ruff format --check .
type:
	cd core && uv run mypy hathor --strict
arch:
	cd core && uv run lint-imports
test:
	cd core && uv run pytest --cov=hathor --cov-fail-under=83 -q

setup:         ## 기기를 탐지해 .env를 쓴다. 새 기기에서 한 번 (D-0068)
	cd core && uv run python -m hathor.cli setup

env:           ## 해석된 경로와 설정을 찍는다 (D-0066)
	cd core && uv run python -m hathor.cli env

doctor:        ## 기록된 규약과 기기 상태가 맞는지 검사한다 (D-0067)
	cd core && uv run python -m hathor.cli doctor

apply:         ## 패치 적용 + 커밋. make apply [PATCH=이름.patch] [NOCOMMIT=1] (D-0070)
	@bash tools/apply_patch.sh $(PATCH)

clean:         ## 파이썬 바이트코드만 지운다
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

clean-all: clean  ## 검사 도구 캐시까지 지운다. **var/과 .venv/는 남긴다** (D-0067)
	rm -rf core/.ruff_cache core/.mypy_cache core/.pytest_cache \
	       core/.import_linter_cache core/.coverage
	@echo "캐시를 지웠다. var/(산출물)과 .venv/(환경)는 그대로다."
	@echo "산출물은 다시 만드는 데 수십 분, 환경은 수 분 걸린다. 지우려면 손으로 지운다."
