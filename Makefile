.PHONY: docs-fix artifacts-audit mutate up up-ml down logs ps mlflow-sync flow sync tidy hygiene gh-setup bot runner smoke check quick lint type arch test cov cov-bump docs size resize clean clean-all setup env doctor apply proposal artifacts-push artifacts-pull artifacts-verify artifacts

up:            ## core 프로파일만 기동 (8GB 노드 기준)
	docker compose up -d
up-ml:         ## mlflow · prefect · labelstudio 기동. 약 2.3GB (D-0224)
	docker compose --profile ml up -d

mlflow-sync:   ## 평가 리포트를 로컬 MLflow(:5000)로 옮긴다. 몇 번 돌려도 같다 (D-0224)
	cd core && uv run --group mlops python ../tools/mlflow_sync.py

flow:          ## 인제스트 → 평가 → MLflow를 Prefect(:4200)로. DRY=1 LIMIT=20 SKIPGPU=1 (D-0224)
	cd core && PREFECT_API_URL=$${PREFECT_API_URL:-http://localhost:4200/api} \
	  uv run --group mlops python ../tools/prefect_flow.py \
	  $(if $(DRY),--plan,) $(if $(LIMIT),--limit $(LIMIT),) $(if $(SKIPGPU),--skip-gpu,)
down:
	docker compose down
logs:
	docker compose logs -f --tail=100
ps:
	docker compose ps

check: docs size lint type arch test  ## CI와 동일한 검사를 로컬에서 수행

sync:          ## 환경을 맞춘다. **이것만 친다** — 묶음을 골라 치면 나머지가 지워진다 (D-0225)
	cd core && uv sync --all-extras --all-groups

tidy:          ## 로컬 찌꺼기 — 브랜치 · 봇 참조 · 적용된 패치. YES=1 치운다 · FIX=1 바이트코드까지 (D-0225 · D-0350)
	python3 tools/tidy.py $(if $(YES),--yes,)
	$(if $(FIX),@$(MAKE) --no-print-directory clean,)

gh-setup:      ## GitHub 설정 — 머지 뒤 브랜치 자동 삭제 · 기획서 배포. gh 필요 · 몇 번 쳐도 같다 (D-0226)
	python3 tools/gh_ops.py setup

bot:           ## 봇 PR · 실행 · 실패 로그. CLOSE=1 이면 열린 봇 PR을 닫고 브랜치를 지운다 (D-0226)
	python3 tools/gh_ops.py bot $(if $(CLOSE),--close,)

runner:        ## GPU 러너 등록 — 토큰은 gh가 받는다 (D-0224 · D-0226)
	bash tools/register_runner.sh

smoke:         ## gpu-smoke를 돌리고 끝날 때까지 본다 (D-0226)
	python3 tools/gh_ops.py smoke

docs:          ## 기록 · 표기 · 비밀정보 · 레이아웃 · 실물 대조 (D-0129 · D-0189)
	python3 tools/check_sight.py --check
	python3 tools/check_decisions.py --check
	python3 tools/check_issue_mentions.py --check
	python3 tools/check_secrets.py --check
	python3 tools/check_doc_style.py --check
	python3 tools/check_retired.py --check
	python3 tools/check_requirements.py --check
	python3 tools/check_args.py --check
	python3 tools/check_egress.py --check
	python3 tools/check_forbidden.py --check
	python3 tools/check_compose.py --check
	python3 tools/check_artifacts.py --check
	python3 tools/check_model_licenses.py --check
	python3 tools/docx_check.py --check
	python3 tools/doc_fsck.py --check
	python3 tools/encoding_check.py --check
	python3 tools/deadcheck.py --ratchet

size:          ## 파일 길이 래칫. 늘어도 줄어도 빨개진다 (D-0117)
	python3 tools/check_file_size.py

docs-fix:      ## 문서가 든 수를 실물로 갈아 넣는다. **관문은 안 고친다** (D-0288)
	python3 tools/doc_fsck.py --fix

resize:        ## 래칫을 내린다. 올리려면 GROW=1 + 결정 기록 (D-0118)
	python3 tools/check_file_size.py --update $(if $(GROW),--allow-growth,)

lint:          ## ruff · 워크플로(actionlint) · 셸(shellcheck) (D-0225)
	cd core && uv run ruff check . ../tools && uv run ruff format --check . ../tools
	cd core && uv run actionlint
	cd core && uv run shellcheck -S warning ../tools/*.sh ../.githooks/pre-commit ../.devcontainer/*.sh
type:          ## 제품 · 관문 도구 · 검사 코드. **셋 다 본다** (D-0263)
	cd core && uv run mypy hathor --strict --cache-dir .mypy_cache_src
	cd core && uv run mypy ../tools --strict --cache-dir .mypy_cache_tools
	python3 tools/check_test_types.py --check
arch:
	cd core && uv run lint-imports
test:
	cd core && uv run pytest --cov=hathor -q -n auto --dist loadgroup
	python3 tools/check_coverage.py

quick:         ## 고치는 동안 도는 고리. **관문이 아니다** — 커버리지·문서·타입은 `make check` (D-0238)
	cd core && uv run ruff check . ../tools
	cd core && uv run pytest -q -n auto --dist loadgroup --no-cov

cov-bump:      ## 커버리지 바닥을 실측 - 1로 올린다. 숫자는 core/pyproject.toml 하나 (D-0223)
	python3 tools/check_coverage.py --update

setup:         ## 기기를 탐지해 .env를 쓴다. 새 기기에서 한 번 (D-0068)
	cd core && uv run python -m hathor.cli setup

env:           ## 해석된 경로와 설정을 찍는다 (D-0066)
	cd core && uv run python -m hathor.cli env

doctor:        ## 기록된 규약과 기기 상태가 맞는지 검사한다 (D-0067)
	cd core && uv run python -m hathor.cli doctor

hygiene:       ## 위생 한 벌 — 기기(doctor) · 저장소(tidy) · 산출물(var-fsck) (D-0243)
	@$(MAKE) --no-print-directory doctor
	@echo
	@$(MAKE) --no-print-directory tidy $(if $(YES),YES=1,) $(if $(FIX),FIX=1,)
	@echo
	@python3 tools/var_fsck.py --ratchet
	@echo
	@python3 tools/check_artifacts.py --audit

var-fsck:      ## 산출물이 무엇인지 찍는다. 판정하지 않는다 (D-0203)
	python3 tools/var_fsck.py

artifacts:     ## 교두보와 저장소에 무엇이 있는지 (D-0118)
	python3 tools/sync_artifacts.py status

artifacts-audit: ## 대장과 실물을 대조한다 — 결손 · 격리 대상 (D-0266)
	python3 tools/check_artifacts.py --audit

artifacts-verify: ## 교두보와 여기가 정말 같은가. FULL=1 이면 내용까지 (D-0242)
	python3 tools/sync_artifacts.py verify $(if $(FULL),--full,)

artifacts-push:  ## 교두보로 보낸다. ONLY=keys 로 O-37 세트만 (D-0119)
	python3 tools/sync_artifacts.py push $(if $(ONLY),--only $(ONLY),)

artifacts-pull:  ## 교두보에서 가져온다. ONLY=keys 로 74MB만 (D-0119)
	python3 tools/sync_artifacts.py pull $(if $(ONLY),--only $(ONLY),)

ship:          ## 내보내도 되는가. make ship [PUSH=1] [FIX=1] (D-0147)
	python3 tools/ship.py $(if $(PUSH),--push,) $(if $(FIX),--fix,)

proposal:      ## 기획서를 MASTER Part I ~ III에서 빌드한다. graphviz · 한글 글꼴 필요 (D-0221)
	cd core && uv run --group docs python ../tools/build_proposal.py

mutate:        ## 관문 도구를 망가뜨려 시험이 우는지 본다. 25분 (D-0259)
	python3 tools/mutate_gate.py

apply:         ## 패치 적용 + 커밋. make apply [PATCH=이름.patch] [WHICH=1] [NOCOMMIT=1] (D-0070 · D-0249)
	@bash tools/apply_patch.sh $(if $(WHICH),--which,) $(PATCH)

patch:         ## 패치를 뽑고 기준 위에서 정·역 검증한다. [REV=] [OUT=] [VERIFY=기존.patch] (D-0351)
	@REV="$(REV)" OUT="$(OUT)" VERIFY="$(VERIFY)" AGAINST="$(AGAINST)" bash tools/make_patch.sh

clean:         ## 저장소의 파이썬 바이트코드만 지운다. **.venv/와 var/는 건드리지 않는다** (D-0148)
	find . -type d \( -name .venv -o -name var -o -name node_modules \) -prune -o \
	     -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

clean-all: clean  ## 검사 도구 캐시까지 지운다. **var/과 .venv/는 남긴다** (D-0067)
	rm -rf core/.ruff_cache core/.mypy_cache core/.mypy_cache_src core/.mypy_cache_tests \
	       core/.mypy_cache_tools core/.pytest_cache core/.import_linter_cache core/.coverage
	@echo "캐시를 지웠다. var/(산출물)과 .venv/(환경)는 그대로다."
	@echo "산출물은 다시 만드는 데 수십 분, 환경은 수 분 걸린다. 지우려면 손으로 지운다."
