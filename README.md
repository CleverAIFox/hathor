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
**「섰다」가 「다 맞다」는 아니다** — 분석 쪽에서 판정 **다섯**이 뒤집혔다
(D-0315 온셋 자 · D-0322 창 길이 · D-0325 사전 가림 · D-0327 단조 차용 기각 ·
**D-0340 「달성 가능 폭」은 곡 고유성이 아니라 뾰족함을 잰다**).
목표는 **남들이 쓰는 제품**이다 (D-0215). 취향은 가창·음색·프로덕션에 살고, 기호 생성의
상한은 «편곡 스케치»라서 **오디오 생성 엔진이 핵심 경로**가 됐다 (D-0214).

| 영역 | 상태 |
|---|---|
| 인제스트 · 분석 | **완료.** 1004곡을 한 패스로 뽑았다 (D-0203) — MERT 13층 × 5소스 · 크로마 · 온셋 · 음고 · 무음. 곡마다 manifest |
| 검색 (취향 축) | M2 아티스트 검색 P@10 **무작위 대비 14.3배** (D-0027) — **앨범 효과를 뺀 수이고 밖에 낼 수는 이것이다** (D-0284). 앨범 검색 M1은 20.4배인데 그 과제가 곧 앨범 효과다. **MERT가 비상업이라 제품 경로에 못 간다.** CLAP으로 다시 쟀고 **MERT의 27%다** (O-68 닫힘 D-0235). MFCC 단독 41.9%가 CLAP+MFCC 38%보다 높다 (D-0299) |
| 기호 생성 | 구조 → 화성 → 가락 → 베이스 → 반주를 SMF로 쓴다. 참조곡 조성·화성 사전으로 조건화. **기준선으로 동결** (D-0214) |
| 생성 엔진 | 서류 관문으로 일곱을 걸러 **ACE-Step 1.5(MIT)** 1순위 (D-0217). 실측 G0에서 **기기가 떨어졌다** — GTX 1660 Ti에서 fp16은 NaN, fp32는 메모리 부족. **VRAM 16GB 이상 장비를 기다린다** |
| 규약 | `make check` · CI 3잡 · 커밋 훅. 셋이 같은 것을 보는지 차집합으로 대조한다 (D-0219) |
| 기획서 | `MASTER.md` Part I ~ III에서 빌드한다 (D-0221). **쪽수를 여기 안 적는다** — docx가 `Pages`에 1을 쓰고 아무도 안 센다. 그림·표 수는 `make proposal`이 찍는다 (D-0332). main에 들어가면 **검사를 지난 뒤** GitHub Pages로 배포한다 (D-0222) |
| **다음 작업** | **정본은 [`docs/PLAN.md`](docs/PLAN.md) §1이며 여기 적지 않는다** (D-0130 · D-0202). 여기 옮겨 적었다가 O-57이 닫힌 뒤에도 남아 **지시서가 죽은 작업을 가리켰다.** |

정본 뷰는 **축마다 다르다** — 검색은 `layer00`, 화성은 **`layer03`**이다 (D-0027 · D-0181).
산출물은 `var/ingest/audio/*.npz`의 `mert/<소스>/layer<번호>`이며 **열세 층이 전부 있다** (D-0203).
실측 수치는 `docs/MASTER.md` §10 평가 설계에 있다. **여기 옮겨 적지 않는다** — 두 곳이 어긋난다.

> **아래 명령 예시 중 `keys-*`를 가리키는 것은 `ingest keys --from-bundles`를 한 번
> 돌린 뒤에 돈다** (D-0211). 조합·반쪽을 요구하는 것은 아직 안 돈다.
> `mert-layers` 폴더에는 **벡터 1004개가 있다** (348M · D-0350이 실측했다). 층은
> 묶음 안에도 있으므로 `eval retrieval`에는 **중복이고** `probe_latent`에는 아니다
> (D-0203). 그 폴더가 읽는 **기본값**이던 것을 O-69가 잡았고 (닫힘 D-0274), 잔해
> 쌓임은 O-62가 잡았다 (닫힘 D-0203 · D-0245).

## 빠른 실행

```bash
cd ~/projects/hathor
make setup                    # 기기를 탐지해 .env를 쓴다. 한 번 (D-0068)
make doctor                   # 규약 · 설치 · 음원 루트 · 산출물을 본다 (D-0067)
make sync                     # 환경. **이것만 친다** — 묶음을 골라 치면 나머지가 지워진다 (D-0225)
make check                    # CI와 같은 검사 — 문서 · 길이 · 린트 · 타입 · 계약 · 시험
```

**데브 컨테이너**(`.devcontainer/`)로 열면 위 설치가 자동이다 — CI와 같은 묶음 · 저장소 훅 · 기획서 빌드
도구까지. GPU는 없으므로 분석 배치는 WSL에서 돈다 (D-0223).

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
    --keys layer00 --label mert-layer00   # 층은 묶음에서 읽는다 (D-0203)

# 상업 가능한 축으로 같은 하네스 (O-68 · D-0231)
uv run python -m hathor.cli eval clap --limit 20        # 배치. 빼면 전량
uv run python -m hathor.cli eval retrieval --out var/ingest \
    --features mert=var/ingest --features clap=var/ingest/clap \
    --keys mert:mixture,clap:mixture --label clap-vs-mert
```

중심화가 기본이다 (D-0031) — `--raw`로 끄면 허브 곡이 어떤 질의에도 상위에 온다. 시드가 둘
이상이면 `--fusion min`으로 결합 규칙을 바꾼다 (D-0033). 평가는 M0 게이트(0.95)를 못 넘으면
M1 · M2를 안 낸다 (D-0023). 리포트는 `var/ingest/eval/<시각>-<라벨>.eval.json`에 쌓인다.

## 기획서 (D-0221 · D-0222)

```bash
sudo apt install graphviz fonts-noto-cjk                 # 한 번
make sync                                                # 한 번 (docs 묶음 포함)
make proposal                                            # MASTER Part I ~ III → docs/proposal.docx
```

**`MASTER.md` Part I ~ III를 고치면 다시 빌드한다.** 빌드가 정본 지문을 docx에 적고
`render_proposal.py --check`이 맞대므로, 안 하면 `make check`이 멈춘다. main에 푸시하면
`.github/workflows/proposal.yml`이 **CI를 먼저 통과시키고** GitHub Pages에 올린다.
배포는 docx를 **PDF로 구워** 웹에 보여 주고 docx도 같이 올린다 — 브라우저가 docx를 직접 그리면
표와 글꼴이 무너진다 (D-0229). Pages 켜기와 첫 배포는 `make gh-setup`이 한다.

## 패치 파이프 · 내보내기

```bash
make apply                    # 패치 폴더의 가장 최근 **hathor** .patch (D-0249)
make apply PATCH=D0221.patch
make apply WHICH=1            # 무엇을 집을지만 찍는다
make check && git push
make patch                    # 뽑는 쪽 — 머리 셋을 손으로 안 적고 기준 위에서 검증한다 (D-0351)
make patch VERIFY=D0350.patch # 받은 패치가 어느 판 위에 서는지 찍는다
make patch STAMP=1            # 나간 패치에 기준을 소급해 박는다 (찍기만) · YES=1로 박는다 (D-0352)
make ship                     # 규약 · git 상태 · 위생 · 산출물을 한 번에 (D-0147)
make mutate WIRING=1          # 관문의 배선을 끊어 시험이 우는지 본다 (D-0353)
make mutate WIRING=1 ONLY=doc_fsck   # 그 도구만. 6초 (D-0358)
make load                     # 관문 전부를 부하 아래서 돌린다. 1분 · CI도 돈다 (D-0355)
make tidy                     # 로컬 찌꺼기를 센다 — 사라진 브랜치 · 봇 추적 참조 · 적용된 패치
make tidy YES=1               # 치운다. 패치는 지우지 않고 applied/로 옮긴다 (D-0225)
```

**WSL 파이프 한 바퀴는 `make apply && make ship PUSH=1`이다.** `ship`이 `make check`을 부르고
git 상태 · **빚** · **CI** · 위생(`tidy`가 센 것 포함) · 산출물을 본 뒤 통과하면 push한다.
`core/`에서 쳐도 된다 — `core/Makefile`이 뿌리로 넘긴다 (D-0226).

**빚은 축마다 세고 막지 않는다** (D-0328 · `tools/debts.py`). 한 축이 0이 되자 화면이
「빚 없다」고 말했고 그것이 거짓이었다 — **안 세는 것은 0으로 보이고 0은 다 끝난 것으로
읽힌다.** 지금 여덟 축이고, **다른 축의 부분집합인 것은 `↳`로 찍고 합계에서 뺀다**
(D-0342). 「문서 뒤처짐」은 한 세션어치(10판)를 넘겨야 뜬다.

**CI 절은 우리 워크플로만 본다** (D-0341). `Dependabot Updates`처럼 **워크플로 파일이
없는 실행**은 GitHub이 돌리는 것이라 코드 상태가 아니다 — 섞었더니 **우리 CI 넷이
전부 초록인데 화면이 「빨강」을 찍었다.** 봇 쪽 실패는 별도 줄로 든다.

### GitHub 쪽 일 — 웹 화면 대신 `gh` (D-0226)

```bash
sudo apt install gh && gh auth login   # 한 번
make gh-setup                          # 머지 뒤 브랜치 자동 삭제 · 기획서 배포. 몇 번 쳐도 같다
make bot                               # 열린 봇 PR · 최근 봇 실행 · 실패 로그 끝 40줄
make bot CLOSE=1                       # 열린 봇 PR을 닫고 브랜치까지 지운다
```

`make apply`는 작업 트리가 깨끗한지 보고, 이미 적용됐으면 아무것도 안 한다. **패치가 선언한
파일과 실제로 바뀐 파일이 같아야 커밋한다** (D-0072). 되돌리기는 `git reset --hard HEAD~1` —
별도 백업 폴더를 만들지 않는다 (GR-0.7).

**패치 머리는 셋이고 `make patch`가 전부 커밋에서 뽑는다** (D-0351). 손으로 적으면 틀린다.

| 머리 | 무엇 | 받는 쪽이 |
|---|---|---|
| `# hathor-commit:` | 커밋 제목 | 커밋 메시지로 쓴다. **표식도 겸한다** — 폴더를 여러 저장소가 나눠 쓴다 (D-0249) |
| `# hathor-needs:` | **부모의** 마지막 결정 번호 | 그 표제가 대장에 있는지 본다 (D-0287) |
| `# hathor-base:` | **부모의 트리 해시** | 제 `HEAD`의 트리와 대조하고, 다르면 **둘을 같이 찍는다** (D-0351) |

**번호는 판을 가르지 못한다.** `D0349.patch`가 세 판 나갔고 셋 다 `D-0349`라 선행 검사는
전부 통과한다 — 다음 패치가 안 붙자 `git apply`는 *"브랜치와 기준 커밋을 확인한다"*고만
했고 어느 기준인지는 말하지 않았다. **트리 해시는 이력이 안 들어가 미러와 실물에서 같다**
(실측: 커밋 350개와 1개가 같은 트리를 냈다).

**D-0351 이후를 선행으로 선언한 패치는 기준 머리를 반드시 갖는다** (D-0352). 그 앞의 350판에는
없고 **소급은 `make patch STAMP=1`이 한다** — 커밋 제목(없으면 번호)으로 이력에서 그 판을 찾아
부모의 트리를 박는다. 본문은 한 바이트도 안 건드리고 멱등이다. 머리 없는 것을 영원히
통과시키면 관문이 선택 사항이 되고, 선택 사항인 관문은 관문이 아니다 (D-0126).

## 릴리스 · 커버리지 (D-0223)

**태그는 결정 번호다.** 결정이 main에 들어가면 `release.yml`이 CI를 지난 뒤 `D-0223` 같은 태그와
GitHub Release를 단다. 본문은 그 결정의 «결과» · «남기는 것»이다 (`tools/release_notes.py`).

**커버리지 바닥은 `core/pyproject.toml` 한 곳에 있다.** 실측이 바닥보다 3%p 넘게 앞서면
`make check`이 멈추고 `make cov-bump`가 바닥을 실측 - 1로 올린다 — 톱니는 되돌아가지 않는다.

## 실험 추적 · 흐름 · GPU 러너 (D-0224)

```bash
make sync                                            # 한 번 (mlops 묶음 포함)
make up-ml                                           # mlflow :5000 · prefect :4200
make mlflow-sync                                     # var/ingest/eval/*.eval.json → MLflow. 몇 번 돌려도 같다
make flow LIMIT=20                                   # scan → all(GPU) → eval retrieval → MLflow
make flow DRY=1                                      # 명령만 찍는다
```

**정본은 JSON과 CLI다.** MLflow · Prefect는 보는 창이며 지워도 결과가 선다. 둘 다 **로컬 주소만**
받고 사용 통계를 끈다 — 망 접점 검사가 센다.

**GPU 러너는 손으로만 돈다.** 등록 토큰은 `gh`가 받는다 — 웹 화면이 필요 없다.

```bash
make runner      # ~/actions-runner-hathor 에 등록 · 라벨 · 서비스. 몇 번 쳐도 같다. 남의 저장소 러너는 안 건드린다
make smoke       # 켜진 GPU 러너가 있을 때만 건다. 끝날 때까지 보고, Ctrl-C면 실행을 취소한다
```

`gpu-smoke`가 드라이버 · 환경 · 엔진 재개 조건을 잰다. push · PR에는
안 걸린다 — 공개 저장소에서 남의 PR이 이 기기에서 돌지 않게 시험이 막는다. 장비를 바꾸면 새
기기에서 같은 명령을 다시 치고 `RUNNER_LABELS`의 뒤 라벨만 바꾼다.

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

**파이썬은 3.12로 못 박혀 있다** (`requires-python = ">=3.12,<3.13"` · D-0341). 상한을
빼면 `uv`가 3.13 · 3.14 · 3.15 칸까지 한 잠금에 풀고, 최신 패키지가 아직 그 파이썬용
휠을 안 내면 **해가 없어진다** — 그렇게 Dependabot이 다섯 번 죽었다. 올릴 때는 그 줄을
**고의로** 고친다. 잠금은 **리눅스 x86_64 하나**로 푼다 (D-0227) — 다른 아키텍처에서
`uv sync`를 처음 돌리면 여기부터 막힌다.

## 실측 재현 — 닫힌 질문

**명령의 정본은 결정 기록의 `재현` 줄이다** (D-0135). 여기에는 무엇을 재는 도구인지만 둔다 —
같은 명령을 두 곳에 두면 한쪽만 고쳐진다.

| 질문 | 도구 | 결정 |
|---|---|---|
| 크로마 대비 — 창별 중앙값 · 타악 분리 (O-27) | `ingest keys --halves` · `eval harmony-prior --against` | D-0064 · D-0065 · D-0073 · D-0074 · **D-0337 ~ D-0340** |
| 참조곡이 화성 어휘에 반영되는가 (O-21) | `eval harmony-prior --replay` | D-0062 · D-0063 · **D-0338 (1004곡 확인)** |
| 화음 칸이 새로운가 — 반음계 대 다이어토닉 | `eval harmony-output --compare-vocabulary` | D-0333 · **D-0334 (합성이 수준을 못 맞췄다)** |
| 참조곡을 바꾸면 출력이 갈리는가 (O-29) | `eval harmony-output` | D-0079 · D-0082 |
| 다이어토닉 제한이 버리는 몫 (O-31) | `eval degree-restriction` | D-0083 ~ D-0088 |
| 반음계 질량의 정체 (O-33 · O-35) | `eval chromatic-origin` | D-0089 ~ D-0093 |
| 순서 조건화 게이트 · 배열 (O-32) | `eval time-drift` · `generate --transitions` | D-0098 ~ D-0113 |
| 화성 리듬 (O-37) | `tools/probe_chord_rhythm.py` | D-0123 ~ D-0125 |
| 박 · 온셋 (O-47) | `eval onsets` · `--phase` | D-0143 ~ D-0173 · **D-0314 ~ D-0318** |
| 어느 층이 화성을 담는가 (O-52) | `tools/probe_latent.py` | D-0179 ~ D-0181 |
| 가사축 | `lyrics extract` · `eval retrieval` | D-0036 ~ D-0048 |
| M0 분할 규칙 | `eval retrieval --split random --split-repeats 5` | D-0040 · D-0041 |
| 취향 라벨 (보조) | `taste compare` · `taste status` | D-0028 · D-0029 |
| 참조곡 스템이 층에 줄 수 있는 것 | `tools/probe_stems.py` | D-0214 |
| 화음이 3화음뿐이다 (O-64) | `eval chord-quality` | D-0300 ~ D-0306 |
| 전이 조건화가 도수 누설과 갈리는가 (O-72) | `eval harmony-output` 짝지은 이득 | D-0311 · D-0312 |
| 창 길이가 분석 인자인가 | `eval window-length` | D-0320 · **D-0322 (전제가 깨졌다)** |
| 단조 차용인가 누설인가 (O-35) | `eval chromatic-origin` | D-0089 ~ D-0093 · **D-0327 (기각)** |

## Compose 프로파일

8GB RAM 노드에서 전부 띄우면 안 선다. **기본은 core만 띄운다.**

| 프로파일 | 서비스 | 메모리 상한 합 |
|---|---|---|
| (기본) core | postgres · mongo · redis · rabbitmq · minio | 약 2.8GB |
| `ml` | mlflow · prefect · labelstudio — 앞의 둘은 연결됨 (D-0224) | 약 2.3GB |
| `obs` | prometheus · grafana | 약 0.8GB |

MongoDB는 `--wiredTigerCacheSizeGB 0.25`로 캐시를 제한해 core에 둔다 (D-0001).

## 구조

```text
docs/               MASTER(현재) · PLAN(미래) · DECISIONS(과거) · proposal.docx(빌드 산출물)
core/hathor/        domain · application · engines · infrastructure · interfaces · shared
core/tests/         unit · integration
tools/              검사 · 탐침 · 운영 · 기획서 빌드
site/               기획서 웹 뷰어 — **PDF로 구워** 보여 주고 docx도 같이 올린다 (D-0229)
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
| `tools/check_egress.py` | 망 접점 — 허용 목록 4곳 (밖 2 · 로컬 2) |
| `tools/check_model_licenses.py` | 모델 가중치 라이선스 · 상업 불가 집합 |
| `tools/render_proposal.py` | 기획서 화면을 낸다 · 정본 ↔ docx ↔ 화면 대조 |
| `tools/check_script.py` | 화면 스크립트 문법 (`node --check`) |
| `tools/doc_fsck.py` | 문서가 가리키는 것이 실물로 있는가 |
| `tools/check_file_size.py` | 파일 길이 래칫 · 양방향 |
| `tools/check_test_types.py` | 시험 코드 타입 오류 래칫 |
| `tools/check_coverage.py` | 커버리지 바닥 래칫 · 양방향 |
| `tools/check_sight.py` | **관문의 시야에 못을 박는다** — 상수가 조용히 줄면 막는다. `--update`는 조이는 쪽으로만 (D-0349) |
| `tools/check_retired.py` | 지운 말이 근거 없이 살아 있나 — 같은 줄에 지운 결정이 있으면 통과 (D-0349) |
| `tools/check_requirements.py` | **요구사항 정의서가 자기 규약을 지키나** — 상태 집합 · 그룹 양방향 · 결번 · 선언 안 된 M/P5+ · 끝났는데 근거 없는 행 (D-0350) |
| `tools/check_args.py` | **주는 인자를 받는 쪽이 받나** — 플래그 · `$(MAKE)` 넘기기 · **화면이 알려 주는 명령이 그 일을 하나** (D-0350) |
| `tools/deadcheck.py` | 검사가 죽었는가 — 프로브 6종 · 양방향 래칫 |
| `tools/encoding_check.py` | BOM · CRLF · 비 UTF-8 · 끝 개행 (`--fix`) |
| `tools/release_notes.py` | 결정 기록에서 태그 · 릴리스 본문 |
| `tools/proposal_source.py` | 기획서 정본 구간 · 표 읽기 · 지문 |
| `tools/proposal_body.py` | 기획서 본문 조립 — 정본 + 그림 → 마크다운 |
| `tools/build_proposal.py` | 기획서 docx 쓰기 (pandoc · python-docx) |
| `tools/render_figures.py` | 기획서 구조도 (graphviz) |
| `tools/render_charts.py` | 기획서 수치 그림 (matplotlib) |
| `tools/apply_patch.sh` | `make apply` — 패치 적용 · 기준 대조 · 선언 대조 · 커밋 |
| `tools/make_patch.sh` | `make patch` — 패치 뽑기 · 머리 셋 · 기준 위에서 검증 |
| `tools/check_patch.py` | 패치 머리가 네 곳에서 같은가 · `HEAD`를 실제로 뽑아 본다 |
| `tools/check_ratchets.py` | 래칫이 느슨해진 자리 — **가장 조였던 값**과 대조한다 |
| `tools/check_under_load.py` | 부하에서만 거짓 실패하는 관문 — `make load` · CI가 돈다 |
| `tools/ship.py` | `make ship` — 내보내도 되는가 |
| `tools/sync_artifacts.py` | 산출물 백업 · 복원 · 추가 전용 |
| `tools/var_fsck.py` | 산출물이 무엇인지 찍는다 |
| `tools/step0_check.py` | 환경 · 라이브러리 실측 |
| `tools/mlflow_sync.py` | `make mlflow-sync` — 평가 리포트 → 로컬 MLflow |
| `tools/prefect_flow.py` | `make flow` — 인제스트 → 평가 → MLflow 흐름 |
| `tools/gpu_smoke.py` | 엔진 재개 조건(VRAM · bf16) 판정 — 러너가 돈다 |
| `tools/register_runner.sh` | 셀프호스티드 러너 등록 — 토큰은 `gh`가 받는다 |
| `tools/gh_ops.py` | GitHub 설정 · 봇 PR · 봇 로그 · 스모크를 터미널에서 |
| `tools/check_forbidden.py` | 금지 부류 — D-0003 실존 가수 음색 복제·보간 |
| `tools/check_compose.py` | compose 메모리 상한 — 8GB 노트북이 기준이다 |
| `tools/check_artifacts.py` | 산출물 대장 ↔ 실물 · 재생성 가능 여부 |
| `tools/decision_ledger.py` | 결정 기록 긁기 · 대장 생성 — **긁는 자리가 하나다** |
| `tools/decision_evidence.py` | `자료` 칸 검사 · 갚을 수 있는 빚 명단 |
| `tools/doc_counts.py` | **문서가 적은 수 ↔ 실물** 축 열다섯 — `doc_fsck`가 부른다. 정본이 사라지면 **0을 안 내고 터진다** (D-0349) |
| `tools/debts.py` | **빚을 축마다 센다** — 한 축만 세고 「없다」를 찍고 있었다 (D-0328) |
| `tools/tidy.py` | git 찌꺼기 · 바이트코드 — `make tidy` |
| `tools/mutate_gate.py` | 검사가 진짜로 잡는가 — 일부러 깨 본다 |
| `tools/repro_from_artifacts.py` | 산출물만으로 결정 기록의 수를 다시 내는가 |
| `tools/bake_proposal.py` | 기획서 PDF 굽기 — 배포용 (D-0229) |
| `SECURITY.md` | **이 저장소에서 취약점이 무엇인가** — 오디오 비이동이 중심이다 (D-0329) |
| `.github/workflows/codeql.yml` | 코드 수준 결함 — `make check`가 안 보는 부류 (D-0329) |
| `tools/probe_id3.py` · `tools/probe_artist.py` · `tools/probe_musicbrainz.py` | 코퍼스 실측 탐침 (일회성) |
| `tools/probe_chord_rhythm.py` · `tools/probe_onsets.py` · `tools/probe_latent.py` · `tools/probe_stems.py` | 화성 · 박 · 잠재 표현 · 스템 탐침 |
| `tools/lyrics_language_profile.py` · `tools/lyrics_exclusion_probe.py` | 가사 언어 구성 · 제외 곡 진단 |
