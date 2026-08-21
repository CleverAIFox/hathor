#!/usr/bin/env bash
# 패치 적용. **검증·되돌리기·멱등성을 git이 진다** (GR-0.7 · D-0066).
#
#   make apply                  # 패치 폴더의 가장 최근 .patch
#   make apply PATCH=D0067.patch
#   make apply PATCH=/절대/경로.patch
#
# 별도 백업 디렉터리를 만들지 않는다. 작업 트리가 깨끗하면 `git apply -R`이
# 되돌리기이고, `git apply --reverse --check`가 멱등 판정이다.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

die() { printf '\033[31m실패:\033[0m %s\n' "$1" >&2; exit 1; }

# .env에서 패치 폴더를 읽는다. 셸에 이미 있으면 그쪽이 우선한다.
if [[ -f .env ]]; then
  while IFS='=' read -r key value; do
    [[ "$key" == "HATHOR_PATCH_DIR" && -z "${HATHOR_PATCH_DIR:-}" ]] && export HATHOR_PATCH_DIR="${value%\"}"
  done < <(grep -E '^\s*HATHOR_PATCH_DIR\s*=' .env || true)
fi

PATCH="${1:-}"
if [[ -z "$PATCH" ]]; then
  [[ -n "${HATHOR_PATCH_DIR:-}" ]] || die "PATCH를 주거나 .env에 HATHOR_PATCH_DIR을 적는다"
  [[ -d "$HATHOR_PATCH_DIR" ]] || die "패치 폴더가 없다: ${HATHOR_PATCH_DIR}"
  PATCH="$(ls -t "${HATHOR_PATCH_DIR}"/*.patch 2>/dev/null | head -1 || true)"
  [[ -n "$PATCH" ]] || die "${HATHOR_PATCH_DIR}에 .patch가 없다"
  printf '가장 최근 패치를 쓴다: %s\n' "$(basename "$PATCH")"
elif [[ ! -f "$PATCH" && -n "${HATHOR_PATCH_DIR:-}" && -f "${HATHOR_PATCH_DIR}/${PATCH}" ]]; then
  PATCH="${HATHOR_PATCH_DIR}/${PATCH}"
fi
[[ -f "$PATCH" ]] || die "패치가 없다: ${PATCH}"

if git apply --reverse --check "$PATCH" >/dev/null 2>&1; then
  echo "이미 적용돼 있다. 아무것도 하지 않는다 (멱등)."
  exit 0
fi

# **작업 트리가 깨끗해야 한다.** 되돌리기를 git에 맡기는 대가다.
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  git status --short
  die "커밋되지 않은 변경이 있다. 커밋하거나 stash한 뒤 다시 실행한다"
fi

git apply --check "$PATCH" || die "적용할 수 없다. 브랜치와 기준 커밋을 확인한다"
git apply "$PATCH"
printf '\033[32m적용 완료:\033[0m %s\n' "$(basename "$PATCH")"

python3 tools/sync_decision_index.py --check || die "부록 A 색인이 어긋난다"
echo
echo "되돌리려면:  git apply -R '${PATCH}'"
echo "다음:        make check"
