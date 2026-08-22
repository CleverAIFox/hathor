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
| **다음 작업** | **O-31 실측 (D-0083).** 도구는 섰다 — `eval degree-restriction`이 다이어토닉 제한이 버리는 몫을 치환 귀무선과 견준다. **사전 벡터만 읽어 1초 이내다.** 결과에 따라 O-32(순서 조건화) 설계가 갈린다 — 버리는 칸이 곡 고유하면 어휘 표현부터 고쳐야 한다 |

정본 뷰는 `var/ingest/mert-layers`의 `layer00` + 중심화다 (D-0027 · D-0031).
실측 수치는 `docs/DESIGN.md` §10 평가 설계에 있다. **여기 옮겨 적지 않는다** — 두 곳이 어긋난다.

## 생성 (D-0052)

```bash
cd core
uv run python -m hathor.cli generate --seed 7 --midi var/out/demo.mid
uv run python -m hathor.cli generate --seed 7 --midi var/out/demo.mid \
    --reference "10CM-폰서트" --reference "10CM-스토커" --tempo 108
uv run python -m hathor.cli generate --seed 7 --midi var/out/demo.mid \
    --no-key-estimation          # 음원 없이. C장조 고정
```

참조곡 음원에서 **조성을 추정한다** (D-0054). 배치가 필요 없고 그 자리에서
1~5곡만 디코딩한다. 나란한 장·단조 혼동은 원리적 한계라 격차가 작으면 `(애매)`로
표시한다. 참조곡 상한은 5개다 (D-0011) — 그 이상은 퓨전이 아니라 코퍼스 평균이 된다.

참조곡 가사에서 반복 패턴을 뽑아 구조를 만들고, 화성을 붙여 마디에 배치한 뒤
SMF 바이트로 쓴다. **참조를 주지 않으면 코퍼스에서 시드로 고른다.**

MIDI 라이브러리를 쓰지 않고 직접 인코딩한다 — 외부 라이브러리는 버전마다
바이트가 달라져 재현성 검증(D-0009)이 깨진다.

**아직 가락도 리듬도 없다.** 3화음을 마디마다 울릴 뿐이며, 지금 필요한 것은
관통이지 음악적 완성도가 아니다.

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

### 기기를 옮겼다면 (D-0066)

**저장소는 양쪽 기기에서 `~/projects/hathor`다.** 윈도우 드라이브(`/mnt/c`)에 두지 않는다 —
`uv sync`가 105초에서 105밀리초로 줄었다.

```bash
cd ~/projects/hathor
make setup                # 기기를 탐지해 .env를 쓴다. 기기당 한 번
make doctor               # 규약과 맞는지 검사한다
```

`make setup`이 윈도우 사용자 이름(광인사 `foxlo` · 리전 `Fox`)과 음원 루트를 찾아
`.env`에 적는다. **손으로 치지 않는다.** 이미 있는 값은 두고 `--force`로 덮는다.
후보를 파일 수와 함께 보여주므로 틀렸으면 `.env`를 고치면 된다.

`make doctor`가 위치 규약(D-0004), **설치본이 이 저장소를 가리키는지**, `.env`와 필수 키,
음원 루트 실재 여부, git 상태, 산출물 현황, **설치 프로파일**을 본다. 광인사(`--dev`)는
ML 검사를 건너뛰므로 **거기서 초록이어도 리전에서 깨질 수 있다** — `doctor`가 그것을 알린다. 고칠 것이 있으면 고치는 명령까지 낸다.
`make env`는 경로만 짧게 찍는다.

`make env`가 저장소 루트, `.env` 유무, 음원 루트가 실제로 있는지, 산출물이 몇 건인지를
찍는다. **경로를 셸에 export하지 않는다** — `.env` 한 곳에만 적는다.

패치는 `HATHOR_PATCH_DIR`에 받아 두고:

```bash
make apply                    # 가장 최근 .patch
make apply PATCH=D0067.patch
```

작업 트리가 깨끗한지 보고, 이미 적용됐으면 아무것도 하지 않는다. 되돌리기는
`git apply -R`이다 — **별도 백업 디렉터리를 만들지 않는다** (GR-0.7).

### 크로마 대비 개선 실측 (O-27 · D-0064)

```bash
cd core
export HATHOR_LIBRARY_ROOT=/mnt/d/노래/노래

# (b) 창별 중앙값. 같은 200곡을 같은 조건으로 다시 뽑는다
uv run python -m hathor.cli ingest keys --out var/ingest --halves --limit 200 \
    --aggregate median --window-seconds 10

uv run python -m hathor.cli eval harmony-prior --replay var/ingest/keys-<새 스탬프>.keys.jsonl
```

**볼 것은 `달성 가능 폭` 한 줄이다.** `mean` 0.0187 · `median` 0.0198 · K-K 장조 0.0616.
**(b)는 사전 등록 기준 0.031에 못 미쳐 기각했다** (D-0065).

**(a) 타악 분리 — 리전에서만 돈다** (D-0073):

```bash
cd core
uv run python -m hathor.cli ingest keys --out var/ingest --halves --separate --limit 200
for set in other other+bass other+bass+vocals; do
  uv run python -m hathor.cli eval harmony-prior \
      --replay var/ingest/keys-<스탬프>.keys.jsonl --stem-set "$set"
done
```

스템 조합 셋을 한 번에 뽑으므로 판정은 재분리 없이 돈다. **셋 중 하나도 0.031을 못
넘으면 (a) 기각이고, 그러면 크로마 경로 자체를 접는다.**

### 스템 사전으로 생성 (O-21 · D-0074 · D-0078)

**Demucs를 생성할 때 돌리지 않는다.** 미리 뽑아 둔 스템 크로마를 조회하므로
GPU 없는 기기에서도 돈다.

```bash
cd core
# 리전에서 한 번 (약 1시간 40분, 1004곡). 끊겨도 이어받고 둘이 동시에 못 돈다
uv run python -m hathor.cli ingest keys --out var/ingest --separate

# 어느 기기에서든
uv run python -m hathor.cli generate --seed 7 --midi var/out/a.mid \
    --reference "10CM-폰서트" --key "C major"
```

화성 줄에 `(참조곡 반영 · other 스템)`이 찍힌다. `(참조곡 반영 · 전체 믹스)`면
스템 사전이 없어 물러난 것이고, `make doctor`가 그것을 알린다.
`--stem-set mix`로 전체 믹스를 강제할 수 있다.

**`other`가 실측으로 고른 값이다** — 달성 가능 폭이 `other` 0.0534 · `other+bass`
0.0497 · `other+bass+vocals` 0.0373으로 **넣을수록 나빠진다** (D-0074).

### 출력 차이 측정 (O-29 · D-0079)

**음원도 GPU도 필요 없다.** 저장된 크로마만 읽는다. 약 16초.

```bash
cd core
# other 스템 사전과 전체 믹스 사전을 같은 곡·같은 쌍·같은 시드로 짝지어 비교한다
uv run python -m hathor.cli eval harmony-output

# 8마디가 표본인지 확인한다. 실측이 극한으로 내려가야 한다
uv run python -m hathor.cli eval harmony-output --bar-sweep 8,16,32,64

uv run python -m hathor.cli eval harmony-output --against none --stem-set mix
```

**`극한` 열이 상한이다.** 사전 가중치 벡터 자체의 거리이며 마디 수를 무한히
늘렸을 때의 값이다. **8마디 실측은 항상 그보다 크고 초과분은 전달된 정보가
아니라 유한 표본의 되튐이다** — 1004곡 실측에서 재는 값의 34%였다.

**조건화 이득(교차 엔트로피)과 이 거리(전변동)는 눈금이 다르다.** CE 폭은 균등에서
벗어난 정도의 **제곱**에, TV 거리는 그 자체에 비례한다. D-0074의 "세 배"는 여기서
1.77배에 해당하며, **"3배가 안 왔다"로 읽으면 틀린다** (D-0082).

`identical`이 0, `onehot`이 1.0이어야 한다. 아니면 하네스가 고장이므로 나머지
숫자를 읽지 않는다. `random`은 아무 사전 둘이라 느슨하고, **`shuffled`가 뾰족함을
맞춘 귀무선이다** — 실측이 그보다 작으면 곡들이 화성 어휘를 공유한다는 뜻이다.

**`마디 환산`이 지난 세션의 "다른 마디 수"와 같은 단위다.** 8마디 한 번을 세는
것으로는 아무것도 판정할 수 없다 (D-0078).

### 도수 제한 손실 (O-31 · D-0083)

**사전 벡터만 읽는다.** 생성도 음원도 GPU도 필요 없고 1초 이내다.

```bash
cd core
uv run python -m hathor.cli eval degree-restriction
uv run python -m hathor.cli eval degree-restriction --key "A minor"
```

**칸 수 비율(6/12)을 기준선으로 읽지 않는다.** 사전 질량이 다이어토닉에 몰려 있으면
몫도 자연히 낮아진다. 질량을 그대로 두고 칸 정체성만 지운 `shuffled`가 기준선이며,
실측이 그보다 **작으면** 버리는 칸이 곡 고유 대비를 덜 담는다는 뜻이다.

`순위상관`은 진단이다. **판정에 쓰지 않는다** — 곡 고유 성분이 없을 때도 0.54가
나와 갈리지 않는다.

### 참조곡 화성 조건화 듣기 (O-21 · D-0063)

```bash
cd core
export HATHOR_LIBRARY_ROOT=/mnt/d/노래/노래   # 기기마다 다르다 (D-0009)

# 조성까지 참조곡을 따른다
uv run python -m hathor.cli generate --seed 7 --midi var/out/a.mid --reference "10CM-폰서트"

# **조성을 고정해 화성만 갈리게 한다.** 통제된 비교는 이쪽이다
uv run python -m hathor.cli generate --seed 7 --midi var/out/fixed-a.mid \
    --reference "10CM-폰서트" --key "C major"
```

CLI가 화성 줄에 `(참조곡 반영)` 또는 `(시드만)`을 찍는다.

**효과는 작다.** 사전이 거의 평평하므로 같은 시드에서 두 참조곡의 진행이 몇 마디만
다르거나 같을 수도 있다. 결함이 아니라 D-0063이 측정한 크기다.

### 화성 어휘 조건화 판정 (O-21 · D-0062)

```bash
cd core
# 1. 리전 — 앞뒤 반쪽 크로마를 뽑는다. CPU이며 200곡이면 판정에 충분하다
uv run python -m hathor.cli ingest keys --out var/ingest --halves --limit 200

# 2. 광인사 — 음원도 GPU도 필요 없다
uv run python -m hathor.cli eval harmony-prior --replay var/ingest/keys-<스탬프>.keys.jsonl
uv run python -m hathor.cli eval harmony-prior --replay <같은 파일> --confident-only
```

곡을 앞뒤로 갈라 **앞반쪽으로 뒷반쪽을 예측한다.** 뒷반쪽은 어느 비교선도 보지 못한
자료이므로 네 선(`uniform` · `corpus` · `other` · `self`)이 전부 질 수 있다.

**산출물은 λ\* 하나다.** `(1-λ)·corpus + λ·self`의 중앙값 교차 엔트로피 최소점이며,
0이면 참조곡이 보탤 것이 없어 O-21의 크로마 접근을 기각한다. 0보다 크면 **그 값이
그대로 생성기의 혼합 계수다.**

**생성물을 채점하지 않는 이유는 조건화가 질 수 없기 때문이다** — "생성된 진행이
참조곡 크로마와 맞는가"의 argmax가 곧 조건화 생성기라 코퍼스 베이스라인이 정의상
진다. 자세한 것은 D-0062에 있다.

### 가사축 (CPU, 수 초)

```bash
cd core
uv run python -m hathor.cli lyrics extract --out var/ingest              # 해싱 (기본)
uv run python -m hathor.cli lyrics extract --out var/ingest \
    --encoder bge-m3 --features var/ingest/lyrics-bge-m3                # 신경망 CLS (D-0045)
uv run python -m hathor.cli lyrics extract --out var/ingest \
    --encoder bge-m3 --pooling mean \
    --features var/ingest/lyrics-bge-m3-mean                            # 평균 풀링 (D-0046)
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

```text
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
tools/lyrics_exclusion_probe.py   가사 제외 곡 원인 진단 (D-0048)
```

`hathor/cli.py`는 문서 §5.3.3의 `python -m hathor.cli` 명령을 유지하기 위한 진입 모듈이며,
실제 구현은 `hathor/interfaces/cli/main.py`에 있다 (GR-2.2: interfaces에 로직 금지).

## P0에서 구현된 것과 아닌 것

`engines/compose`의 구조·화성 생성기는 **결정성만 보장하는 스텁**이다. 음악적 타당성은 없다.
지금 필요한 것은 파이프라인 관통과 재현성 검증 경로지 품질이 아니다 (GR-6.1). P4에서 교체한다.
