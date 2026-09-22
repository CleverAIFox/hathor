# HATHOR

취향 잠재 표현 기반 종단간 AI 음악 창작 시스템. **내 라이브러리로 내 취향의 곡을 만든다.**

기획서 — [`docs/proposal.docx`](docs/proposal.docx) ·
[웹에서 보기](https://cleveraifox.github.io/hathor/proposal.html) (D-0222)

## 문서 지도

문서는 4종에 기획서 하나다. 각자 다른 질문에 답하며 **같은 내용을 두 곳에 두지 않는다** (D-0039 · D-0043).

| 종류 | 파일 | 답하는 질문 | 언제 보는가 |
|---|---|---|---|
| **현재** | [`docs/MASTER.md`](docs/MASTER.md) | 지금 무엇이 어떤 값인가 | 설계를 확인하거나 바꿀 때 |
| **미래** | [`docs/PLAN.md`](docs/PLAN.md) | 다음에 무엇을 하는가 | 착수할 때 |
| **결정** | [`docs/DECISIONS.md`](docs/DECISIONS.md) | 왜 그렇게 골랐는가 | "이건 왜 이렇게 됐지"가 나올 때 |
| **진입** | 이 문서 | 지금 무엇을 할 수 있는가 | 처음 열었을 때, 명령이 필요할 때 |
| **기획서** | [`docs/proposal.docx`](docs/proposal.docx) | 무엇을 왜 만드는가 — 밖에 내는 판. `MASTER.md` Part I ~ III에서 `make proposal`로 빌드한다 (D-0221) | 제출·면접·소개할 때 |

- `docs/MASTER.md`가 **설계의 단일 진실 공급원**이다. 뿌리의 `MASTER.md`는 **없다** — D-0189가 흡수했다.
- `DECISIONS.md`는 **추가 전용**이다. 판단이 바뀌면 고쳐 쓰지 않고 새 번호로 정정한다.
- **문서를 먼저 고치고 코드를 고친다 (GR-0.1).** 코드가 앞서면 그 즉시 문서를 맞춘다.
- **도구가 강제하는 것은 문서에 다시 적지 않는다.** 계층 계약은 `core/pyproject.toml`,
  결정 대장은 `tools/check_decisions.py`가 진실이다 (D-0042 · D-0043 · D-0189).

## 현재 단계

**분석과 기호 생성은 섰고, 생성 엔진은 장비를 기다린다** (D-0218).
목표는 **남들이 쓰는 제품**이다 (D-0215). 취향은 가창·음색·프로덕션에 살고, 기호 생성의
상한은 «편곡 스케치»라서 **오디오 생성 엔진이 핵심 경로**가 됐다 (D-0214).

| 영역 | 상태 |
|---|---|
| 인제스트 · 분석 | **완료.** 1004곡을 한 패스로 뽑았다 (D-0203) — MERT 13층 × 5소스 · 크로마 · 온셋 · 음고 · 무음. 곡마다 manifest |
| 검색 (취향 축) | M1 앨범 검색 P@10 **무작위 대비 20.4배** (D-0027). **MERT가 비상업이라 제품 경로에 못 간다** — CLAP로 다시 잰다 (O-68) |
| 기호 생성 | 구조 → 화성 → 가락 → 베이스 → 반주를 SMF로 쓴다. 참조곡 조성·화성 사전으로 조건화. **기준선으로 동결** (D-0214) |
| 생성 엔진 | 서류 관문으로 일곱을 걸러 **ACE-Step 1.5(MIT)** 1순위 (D-0217). 실측 G0에서 **기기가 떨어졌다** — GTX 1660 Ti에서 fp16은 NaN, fp32는 메모리 부족. **VRAM 16GB 이상 장비를 기다린다** |
| 규약 | `make check` · CI 3잡 · 커밋 훅. 셋이 같은 것을 보는지 차집합으로 대조한다 (D-0219) |
| 기획서 | `MASTER.md` Part I ~ III에서 빌드한다 — 64쪽 · 그림 28장 (D-0221). main에 들어가면 **검사를 지난 뒤** GitHub Pages로 배포한다 (D-0222) |
| **다음 작업** | **정본은 [`docs/PLAN.md`](docs/PLAN.md) §1이며 여기 적지 않는다** (D-0130 · D-0202). 여기 옮겨 적었다가 O-57이 닫힌 뒤에도 남아 **지시서가 죽은 작업을 가리켰다.** |

정본 뷰는 **축마다 다르다** — 검색은 `layer00`, 화성은 **`layer03`**이다 (D-0027 · D-0181).
산출물은 `var/ingest/audio/*.npz`의 `mert/<소스>/layer<번호>`이며 **열세 층이 전부 있다** (D-0203).
실측 수치는 `docs/MASTER.md` §10 평가 설계에 있다. **여기 옮겨 적지 않는다** — 두 곳이 어긋난다.

> **아래 명령 예시 중 `keys-*`를 가리키는 것은 `ingest keys --from-bundles`를 한 번
> 돌린 뒤에 돈다** (D-0211). 조합·반쪽을 요구하는 것과 `mert-layers`는 아직 안 돈다 (O-62).

## 빠른 실행

```bash
cd ~/projects/hathor
make setup                    # 기기를 탐지해 .env를 쓴다. 한 번 (D-0068)
make doctor                   # 규약 · 설치 · 음원 루트 · 산출물을 본다 (D-0067)
cd core && uv sync --all-extras --dev && cd ..
make check                    # CI와 같은 검사 — 문서 · 길이 · 린트 · 타입 · 계약 · 시험
```

`docker compose up -d`는 DB · 큐 · 오브젝트 저장소를 띄운다. **지금 코드는 쓰지 않는다** —
산출물은 `var/`의 npz · JSONL이고 DB는 P4에서 붙는다 (MASTER Part III §2).

## 생성 (D-0052)

```bash
cd core
uv run python -m hathor.cli generate --seed 7 --midi var/out/demo.mid
uv run python -m hathor.cli generate --seed 7 --midi var/out/demo.mid \
    --reference "10CM-폰서트" --reference "10CM-스토커" --tempo 108
uv run python -m hathor.cli generate --seed 7 --midi var/out/demo.mid \
    --no-key-estimation          # 음원 없이. C장조 고정
```

참조곡에서 **조성을 추정하고**(D-0054) 가사 반복으로 구조를 뽑는다(D-0049). 화성 도수 사전과
으뜸음 기준으로 회전한 배열 사전을 걸고(D-0063 · D-0213), 가락이 박마다 화음 구성음을 짚으며
(D-0141) 성부 진행 · 베이스 · 층별 세기 · 박 분할까지 들어간다(D-0137 ~ D-0207). SMF는 라이브러리
없이 직접 쓴다 — 같은 시드는 같은 바이트다. 참조곡 상한은 5곡이다 (D-0011).

**기준선으로 동결했다** (D-0214). 한 축만 바꾼 두 판을 귀가 가르지 못했다 — 다음은 오디오 엔진이다.

## 검색 · 퓨전

```bash
cd core
uv run python -m hathor.cli search --like "밤편지" -k 10
uv run python -m hathor.cli search --like "밤편지" --like "뱅뱅뱅" -k 10   # 시드 퓨전
uv run python -m hathor.cli eval retrieval --out var/ingest \
    --features var/ingest/mert-layers --keys layer00 --label mert-layer00
```

중심화가 기본이다 (D-0031) — `--raw`로 끄면 허브 곡이 어떤 질의에도 상위에 온다. 시드가 둘
이상이면 `--fusion min`으로 결합 규칙을 바꾼다 (D-0033). 평가는 M0 게이트(0.95)를 못 넘으면
M1 · M2를 안 낸다 (D-0023). 리포트는 `var/ingest/eval/<시각>-<라벨>.eval.json`에 쌓인다.

## 기획서 (D-0221 · D-0222)

```bash
sudo apt install graphviz fonts-noto-cjk                 # 한 번
cd core && uv sync --all-extras --dev --group docs && cd ..   # 한 번. --all-extras를 빼면 GPU 묶음이 지워진다
make proposal                                            # MASTER Part I ~ III → docs/proposal.docx
```

**`MASTER.md` Part I ~ III를 고치면 다시 빌드한다.** 빌드가 정본 지문을 docx에 적고
`docx_check.py`가 맞대므로, 안 하면 `make check`이 멈춘다. main에 푸시하면
`.github/workflows/proposal.yml`이 **CI를 먼저 통과시키고** GitHub Pages에 올린다.
Pages는 한 번 켠다 — 저장소 설정 → Pages → Source: **GitHub Actions**.

## 패치 파이프 · 내보내기

```bash
make apply                    # HATHOR_PATCH_DIR(윈도 다운로드)의 가장 최근 .patch
make apply PATCH=D0221.patch
make check && git push
make ship                     # 규약 · git 상태 · 위생 · 산출물을 한 번에 (D-0147)
```

`make apply`는 작업 트리가 깨끗한지 보고, 이미 적용됐으면 아무것도 안 한다. **패치가 선언한
파일과 실제로 바뀐 파일이 같아야 커밋한다** (D-0072). 커밋 메시지는 패치의 `# hathor-commit:`
줄이다. 되돌리기는 `git reset --hard HEAD~1` — 별도 백업 폴더를 만들지 않는다 (GR-0.7).

## 산출물 백업 (D-0118 · D-0122)

**`var/`는 커밋하지 않는다.** 외장 SSD가 유일한 사본이며 기기가 하나라 **백업이다.**

```bash
make artifacts                # 양쪽에 무엇이 있는지
make artifacts-push           # var/ingest -> SSD
make artifacts-pull           # SSD -> var/ingest. 복원 17192개 · 4분 12초 (실측)
make artifacts-push ONLY=keys # 화성 작업이 읽는 keys-*만 (74MB)
```

**덮어쓰지 않는다.** 같은 이름은 건너뛰므로 몇 번을 돌려도 같다. `doctor`가 사전이 없다고
하면 재추출(GPU 1시간 40분) 전에 **묶음부터 본다** — `ingest keys --from-bundles` (D-0211).

## 기기 설정 (D-0066)

저장소는 `~/projects/hathor`다. 윈도 드라이브(`/mnt/c`)에 두지 않는다 — `uv sync`가 105초에서
105밀리초로 줄었다. **기기마다 다른 값은 `.env` 한 곳에만 적는다** — 음원 루트
(`HATHOR_LIBRARY_ROOT`) · 패치 폴더(`HATHOR_PATCH_DIR`) · 산출물 백업(`HATHOR_ARTIFACT_STORE`).
`make setup`이 탐지해 채우고 `make env`가 해석된 값을 찍는다. 셸에 export하지 않는다.

> `mypy`는 GPU 묶음(`transformers`)이 없는 설치에서 `mert_feature_extractor.py`의
> `type: ignore`를 미사용으로 보고한다. CI는 `--all-extras`라 통과한다. 환경 차이다.

## 실측 재현 — 닫힌 질문

**명령의 정본은 결정 기록의 `재현` 줄이다** (D-0135). 여기에는 무엇을 재는 도구인지만 둔다 —
같은 명령을 두 곳에 두면 한쪽만 고쳐진다.

| 질문 | 도구 | 결정 |
|---|---|---|
| 크로마 대비 — 창별 중앙값 · 타악 분리 (O-27) | `ingest keys --halves` · `eval harmony-prior` | D-0064 · D-0065 · D-0073 · D-0074 |
| 참조곡이 화성 어휘에 반영되는가 (O-21) | `eval harmony-prior --replay` | D-0062 · D-0063 |
| 참조곡을 바꾸면 출력이 갈리는가 (O-29) | `eval harmony-output` | D-0079 · D-0082 |
| 다이어토닉 제한이 버리는 몫 (O-31) | `eval degree-restriction` | D-0083 ~ D-0088 |
| 반음계 질량의 정체 (O-33 · O-35) | `eval chromatic-origin` | D-0089 ~ D-0093 |
| 순서 조건화 게이트 · 배열 (O-32) | `eval time-drift` · `generate --transitions` | D-0098 ~ D-0113 |
| 화성 리듬 (O-37) | `tools/probe_chord_rhythm.py` | D-0123 ~ D-0125 |
| 박 · 온셋 (O-47) | `tools/probe_onsets.py` | D-0143 ~ D-0173 |
| 어느 층이 화성을 담는가 (O-52) | `tools/probe_latent.py` | D-0179 ~ D-0181 |
| 가사축 | `lyrics extract` · `eval retrieval` | D-0036 ~ D-0048 |
| M0 분할 규칙 | `eval retrieval --split random --split-repeats 5` | D-0040 · D-0041 |
| 취향 라벨 (보조) | `taste compare` · `taste status` | D-0028 · D-0029 |
| 참조곡 스템이 층에 줄 수 있는 것 | `tools/probe_stems.py` | D-0214 |

## Compose 프로파일

8GB RAM 노드에서 전부 띄우면 안 선다. **기본은 core만 띄운다.**

| 프로파일 | 서비스 | 메모리 상한 합 |
|---|---|---|
| (기본) core | postgres · mongo · redis · rabbitmq · minio | 약 2.8GB |
| `ml` | mlflow · prefect · labelstudio | 약 2.3GB |
| `obs` | prometheus · grafana | 약 0.8GB |

MongoDB는 `--wiredTigerCacheSizeGB 0.25`로 캐시를 제한해 core에 둔다 (D-0001).

## 구조

```text
docs/               MASTER(현재) · PLAN(미래) · DECISIONS(과거) · proposal.docx(빌드 산출물)
core/hathor/        domain · application · engines · infrastructure · interfaces · shared
core/tests/         unit · integration
tools/              검사 · 탐침 · 운영 · 기획서 빌드
site/               기획서 웹 뷰어 — docx를 브라우저가 그대로 그린다 (D-0222)
infra/ · docker/    postgres init · prometheus · mlflow 이미지
```

`hathor/cli.py`는 `python -m hathor.cli`의 진입 모듈이고 구현은 `interfaces/cli/main.py`에
있다 (GR-2.2). **산출물을 읽고 쓰는 것은 인프라에 있다** (D-0116). `main.py`의 길이는 파일 길이
래칫이 못 박고 있다 — 늘면 빨개진다 (D-0117).

| 도구 | 하는 일 |
|---|---|
| `tools/check_decisions.py` | 결정 기록 · 미해결표 검사, 결정 대장 생성 |
| `tools/check_issue_mentions.py` | 닫힌 질문을 열린 것처럼 적었는가 |
| `tools/check_secrets.py` | 추적 중인 비밀정보 |
| `tools/check_doc_style.py` | 문서 레이아웃 · 여섯 번째 문서 |
| `tools/check_egress.py` | 망 접점 — 허용 목록 2곳 |
| `tools/check_model_licenses.py` | 모델 가중치 라이선스 · 상업 불가 집합 |
| `tools/docx_check.py` | 기획서 ↔ 정본 지문 · 숫자 · 폐기어 |
| `tools/doc_fsck.py` | 문서가 가리키는 것이 실물로 있는가 |
| `tools/check_file_size.py` | 파일 길이 래칫 · 양방향 |
| `tools/check_test_types.py` | 시험 코드 타입 오류 래칫 |
| `tools/proposal_source.py` | 기획서 정본 구간 · 표 읽기 · 지문 |
| `tools/build_proposal.py` | 기획서 빌드 (pandoc) |
| `tools/render_figures.py` | 기획서 구조도 (graphviz) |
| `tools/render_charts.py` | 기획서 수치 그림 (matplotlib) |
| `tools/apply_patch.sh` | `make apply` — 패치 적용 · 선언 대조 · 커밋 |
| `tools/ship.py` | `make ship` — 내보내도 되는가 |
| `tools/sync_artifacts.py` | 산출물 백업 · 복원 · 추가 전용 |
| `tools/var_fsck.py` | 산출물이 무엇인지 찍는다 |
| `tools/step0_check.py` | 환경 · 라이브러리 실측 |
| `tools/probe_id3.py` · `tools/probe_artist.py` · `tools/probe_musicbrainz.py` | 코퍼스 실측 탐침 (일회성) |
| `tools/probe_chord_rhythm.py` · `tools/probe_onsets.py` · `tools/probe_latent.py` · `tools/probe_stems.py` | 화성 · 박 · 잠재 표현 · 스템 탐침 |
| `tools/lyrics_language_profile.py` · `tools/lyrics_exclusion_probe.py` | 가사 언어 구성 · 제외 곡 진단 |
