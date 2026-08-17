# HATHOR

취향 잠재 표현 기반 종단간 AI 음악 창작 시스템.

## 문서 지도

문서는 4종이다. 각자 다른 질문에 답하며 **같은 내용을 두 곳에 두지 않는다** (D-0039 · D-0043).

| 종류 | 파일 | 답하는 질문 | 언제 보는가 |
|---|---|---|---|
| **규약** | [`CONTRIBUTING.md`](CONTRIBUTING.md) | 어떻게 일하는가 | 작업을 시작할 때, 커밋·PR 전에 |
| **기획** | [`docs/DESIGN.md`](docs/DESIGN.md) | 무엇을 왜 만드는가 | 설계를 확인하거나 바꿀 때 |
| **결정** | [`docs/DECISIONS.md`](docs/DECISIONS.md) | 왜 그렇게 골랐는가 | "이건 왜 이렇게 됐지"가 나올 때 |
| **진입** | 이 문서 | 지금 무엇을 할 수 있는가 | 처음 열었을 때, 명령이 필요할 때 |

- `DESIGN.md`가 **설계의 단일 진실 공급원**이다. 기획서 3부작(제안서 · 요구사항 · 상세설계).
- `DECISIONS.md`는 **추가 전용**이다. 판단이 바뀌면 고쳐 쓰지 않고 새 번호로 정정한다.
- **문서를 먼저 고치고 코드를 고친다 (GR-0.1).** 코드가 앞서면 그 즉시 문서를 맞춘다.
- **도구가 강제하는 것은 문서에 다시 적지 않는다.** 계층 계약은 `core/pyproject.toml`,
  결정 색인은 `tools/sync_decision_index.py`가 진실이다 (D-0042 · D-0043).
- `docs/archive/`는 폐기된 초안이다. 참조용으로만 남긴다.

## 현재 단계

**P1 — 인제스트.** 로컬 음원을 스캔해 정규화된 트랙으로 만든다.

| 단계 | 상태 |
|---|---|
| P0 기반 · P1 인제스트 #1~#14 | 완료 — 상세는 `docs/DESIGN.md`, 근거는 `docs/DECISIONS.md` |
| **다음 작업** | **가사축 신경망 문장 인코더.** O-12 판정 완료 — 분할 정렬은 실재하나 작고 표현이 한계다 (D-0044). 언어 구성 실측이 선행한다 |

정본 뷰는 `var/ingest/mert-layers`의 `layer00` + 중심화다 (D-0027 · D-0031).
실측 수치는 `docs/DESIGN.md` §10 평가 설계에 있다. **여기 옮겨 적지 않는다** — 두 곳이 어긋난다.

## 빠른 실행

```bash
cp .env.example .env          # 값 수정
docker compose up -d          # core: postgres · mongo · redis · rabbitmq · minio
docker compose ps

cd core
uv sync --all-extras --dev
uv run python -m hathor.cli generate --seed 42 --dry-run
make check                    # docs · lint · type · arch · test (CI와 동일)
```

### 검색 평가 (GPU 불필요, CPU 수 초)

```bash
cd core
uv run python -m hathor.cli eval retrieval --out var/ingest            # 혼합 단독
uv run python -m hathor.cli eval retrieval --out var/ingest \
    --keys mixture,drums,bass,other,vocals --label stems-concat        # 스템 concat

# MFCC 베이스라인: 먼저 특징을 뽑고(CPU 배치) 같은 하네스를 --features로 돌린다
uv run python -m hathor.cli eval mfcc --out var/ingest
uv run python -m hathor.cli eval retrieval --out var/ingest \
    --features var/ingest/baseline-mfcc --label mfcc

# MERT 레이어별 추출. 스템 분리 없음 — 1004곡 GPU 약 67분
uv run python -m hathor.cli eval layers --out var/ingest --layers 0,3,6,9

# 현재 기본 뷰 (D-0026). 마지막 레이어(mixture)는 쓰지 않는다
uv run python -m hathor.cli eval retrieval --out var/ingest \
    --features var/ingest/mert-layers --keys layer00 --label mert-layer00

# 두 추출기 결합 (O-8). 서로 다른 추출기는 --block-l2가 필수다
uv run python -m hathor.cli eval retrieval --out var/ingest \
    --features mert=var/ingest --features mfcc=var/ingest/baseline-mfcc \
    --keys mert:mixture,mfcc:mixture --block-l2 --label mert+mfcc
```

### 시드곡 퓨전 검색

```bash
cd core
uv run python -m hathor.cli search --like "밤편지" -k 10
uv run python -m hathor.cli search --like "밤편지" --like "뱅뱅뱅" -k 10   # 퓨전
```

`--like`를 여러 번 주면 시드곡들의 조합에 가까운 곡을 찾는다 (D-0011 · D-0029).
`[반복 m:ss]`는 곡 안에서 반복도가 가장 높은 구간이며 **후렴이라는 보장은 없다**.
중심화는 기본으로 켜져 있다(D-0031). `--raw`로 끄면 허브 곡이 어떤 질의에도 상위에 온다.
시드가 둘 이상이면 `--fusion min`으로 결합 규칙을 바꿀 수 있다 (D-0033).

```bash
uv run python -m hathor.cli eval fusion --out var/ingest   # 규칙 3종 비교 (M4)
```

### 가사축 (CPU, 수 초)

```bash
cd core
uv run python -m hathor.cli lyrics extract --out var/ingest
uv run python -m hathor.cli eval retrieval --out var/ingest \
    --features var/ingest/lyrics-hashed --keys mixture --label lyrics-hashed
```

산출물 규격이 오디오축과 같아 **같은 평가 하네스가 그대로 읽는다** (D-0036).

### M0 분할 규칙 (D-0040)

M0는 곡을 두 조각으로 잘라 한쪽으로 나머지를 찾는다. **자르는 방법이 설정이다.**

```bash
# 오디오축 정본. 기본값
uv run python -m hathor.cli eval retrieval --out var/ingest \
    --features var/ingest/mert-layers --keys layer00

# 무작위 균등 분할 5회 (가사축 대조군)
uv run python -m hathor.cli eval retrieval --out var/ingest \
    --features var/ingest/lyrics-8192 --keys mixture \
    --split random --split-repeats 5 --force
```

`--split random`은 1회 값이 표본 하나다. **`--split-repeats` 없이 인용하지 않는다.**
`--force`로 나온 M1/M2는 게이트 미달 상태의 값이므로 인용하지 않는다.
출력에 top-1과 함께 MRR · R@5 · R@10 · 실패 순위 중앙값이 나온다 (D-0041).

왜 이 축이 필요한지는 D-0040을 본다.

### 취향 라벨 수집 (보조)

```bash
cd core
uv run python -m hathor.cli taste compare --out var/ingest --count 30
uv run python -m hathor.cli taste status --out var/ingest
```

무작위 쌍을 고정 평가 집합으로 먼저 모은다 (D-0028). 적응적 선택은 모델이 선 뒤다.

M0(자기일관성)가 0.95 미만이면 M1/M2를 계산하지 않고 비정상 종료한다 (D-0023).
리포트는 `var/ingest/eval/<시각>-<라벨>.eval.json`에 실행마다 새로 쌓인다.

> `make check`의 mypy 단계는 GPU 엑스트라(`transformers`)가 없는 기기에서
> `mert_feature_extractor.py`의 `type: ignore`를 미사용으로 보고한다.
> CI는 `uv sync --all-extras`를 쓰므로 통과한다. 환경 차이이며 결함이 아니다.

## Compose 프로파일

문서 §4.4는 10개 서비스 일괄 기동을 전제하지만, 8GB RAM 노드에서는 성립하지 않는다.
**프로파일로 분리하고 기본은 core만 띄운다.**

| 프로파일 | 서비스 | 메모리 상한 합 |
|---|---|---|
| (기본) core | postgres · mongo · redis · rabbitmq · minio | 약 2.8GB |
| `ml` | mlflow · prefect · labelstudio | 약 2.3GB |
| `obs` | prometheus · grafana | 약 0.8GB |

MongoDB는 `--wiredTigerCacheSizeGB 0.25`로 캐시를 제한해 core에 포함한다 (D-0001).

## 구조

```
CONTRIBUTING.md     개발 규약 (GROUND RULES)
docs/DESIGN.md      설계 단일 진실 공급원 (기획서 3부작)
core/hathor/        Python 모노레포 (domain · application · engines · infrastructure · interfaces · shared)
core/tests/         unit · integration
infra/              postgres init · prometheus 설정
docker/             mlflow 이미지
docs/DECISIONS.md   결정 기록 (GR-0.2)
tools/step0_check.py  환경·라이브러리 실측 스크립트
tools/sync_decision_index.py  부록 A 색인 생성·검증 (D-0042)
tools/lyrics_language_profile.py  가사 언어 구성 실측 (D-0044)
```

`hathor/cli.py`는 문서 §5.3.3의 `python -m hathor.cli` 명령을 유지하기 위한 진입 모듈이며,
실제 구현은 `hathor/interfaces/cli/main.py`에 있다 (GR-2.2: interfaces에 로직 금지).

## P0에서 구현된 것과 아닌 것

`engines/compose`의 구조·화성 생성기는 **결정성만 보장하는 스텁**이다. 음악적 타당성은 없다.
지금 필요한 것은 파이프라인 관통과 재현성 검증 경로지 품질이 아니다 (GR-6.1). P4에서 교체한다.
