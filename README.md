# HATHOR

취향 잠재 표현 기반 종단간 AI 음악 창작 시스템.
설계 단일 진실 공급원은 [`docs/PLAN.md`](docs/PLAN.md)(기획서 3부작)다. **문서를 먼저 고치고 코드를 고친다 (GR-0.1).**

## 현재 단계

**P1 — 인제스트.** 로컬 음원을 스캔해 정규화된 트랙으로 만든다.

| 유닛 | 상태 |
|---|---|
| P0 기반 (골격 · 게이트 · compose) | 완료 |
| #1 파일 스캐너 + 태그 추출 | 완료 (실측 1004곡 / 실패 0) |
| #2 아티스트 파서 (D-0014 · D-0016) | 완료 |
| #3 MusicBrainz 조회 | 미착수 |
| #4 오디오 특징 추출 | 미착수 |

## 빠른 실행

```bash
cp .env.example .env          # 값 수정
docker compose up -d          # core: postgres · mongo · redis · rabbitmq · minio
docker compose ps

cd core
uv sync --all-extras --dev
uv run python -m hathor.cli generate --seed 42 --dry-run
make check                    # lint · type · arch · test (CI와 동일)
```

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
docs/MASTER.md      설계 단일 진실 공급원
core/hathor/        Python 모노레포 (domain · application · engines · infrastructure · interfaces · shared)
core/tests/         unit · integration
infra/              postgres init · prometheus 설정
docker/             mlflow 이미지
docs/DECISIONS.md   결정 기록 (GR-0.2)
tools/step0_check.py  환경·라이브러리 실측 스크립트
```

`hathor/cli.py`는 문서 §5.3.3의 `python -m hathor.cli` 명령을 유지하기 위한 진입 모듈이며,
실제 구현은 `hathor/interfaces/cli/main.py`에 있다 (GR-2.2: interfaces에 로직 금지).

## P0에서 구현된 것과 아닌 것

`engines/compose`의 구조·화성 생성기는 **결정성만 보장하는 스텁**이다. 음악적 타당성은 없다.
지금 필요한 것은 파이프라인 관통과 재현성 검증 경로지 품질이 아니다 (GR-6.1). P4에서 교체한다.
