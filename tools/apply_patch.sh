#!/usr/bin/env bash
# 패치 적용 + 커밋. **손으로 파일 목록을 적지 않는다** (GR-0.7 · D-0070).
#
#   make apply                  # 패치 폴더의 가장 최근 .patch
#   make apply PATCH=D0071.patch
#   make apply PATCH=... NOCOMMIT=1   # 붙이기만 하고 커밋하지 않는다
#
# 커밋 메시지는 패치 안의 `# hathor-commit:` 줄에서 읽는다. 없으면 파일 이름을 쓴다.
#
# **되돌리기·멱등성은 git이 진다.** 별도 백업 디렉터리를 만들지 않는다.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

die() { printf '\033[31m실패:\033[0m %s\n' "$1" >&2; exit 1; }
ok()  { printf '\033[32m%s\033[0m\n' "$1"; }

if [[ -f .env && -z "${HATHOR_PATCH_DIR:-}" ]]; then
  line="$(grep -E '^\s*HATHOR_PATCH_DIR\s*=' .env | tail -1 || true)"
  [[ -n "$line" ]] && export HATHOR_PATCH_DIR="${line#*=}"
fi

PATCH="${1:-}"
if [[ -z "$PATCH" ]]; then
  [[ -n "${HATHOR_PATCH_DIR:-}" ]] || die "PATCH를 주거나 .env에 HATHOR_PATCH_DIR을 적는다 (make setup)"
  [[ -d "$HATHOR_PATCH_DIR" ]] || die "패치 폴더가 없다: ${HATHOR_PATCH_DIR}"
  PATCH="$(ls -t "${HATHOR_PATCH_DIR}"/*.patch 2>/dev/null | head -1 || true)"
  [[ -n "$PATCH" ]] || die "${HATHOR_PATCH_DIR}에 .patch가 없다"
elif [[ ! -f "$PATCH" && -n "${HATHOR_PATCH_DIR:-}" && -f "${HATHOR_PATCH_DIR}/${PATCH}" ]]; then
  PATCH="${HATHOR_PATCH_DIR}/${PATCH}"
fi
[[ -f "$PATCH" ]] || die "패치가 없다: ${PATCH}"
printf '패치: %s\n' "$(basename "$PATCH")"

if git apply --reverse --check "$PATCH" >/dev/null 2>&1; then
  ok "이미 적용돼 있다. 아무것도 하지 않는다 (멱등)."
  exit 0
fi

# **작업 트리가 깨끗해야 한다.** 되돌리기를 git에 맡기는 대가다.
if [[ -n "$(git status --porcelain)" ]]; then
  git status --short
  die "커밋되지 않은 변경이 있다. 커밋하거나 stash한 뒤 다시 실행한다"
fi

git apply --check "$PATCH" || die "적용할 수 없다. 브랜치와 기준 커밋을 확인한다"
git apply "$PATCH"
ok "적용 완료"

python3 tools/sync_decision_index.py --check || die "부록 A 색인이 어긋난다"

if [[ -n "${NOCOMMIT:-}" ]]; then
  echo "NOCOMMIT이라 커밋하지 않았다. 되돌리려면: git apply -R '${PATCH}'"
  exit 0
fi

MESSAGE="$(grep -m1 '^# hathor-commit:' "$PATCH" | sed 's/^# hathor-commit:[[:space:]]*//' || true)"
[[ -n "$MESSAGE" ]] || MESSAGE="chore: $(basename "$PATCH" .patch) 적용"

# **패치가 목록을 갖고 있으므로 손으로 적지도, 눈감고 `add -A` 하지도 않는다**
# (D-0072). 패치가 건드린다고 선언한 파일과 실제로 바뀐 파일이 정확히 같아야 한다.
# 다르면 다른 작업이 섞인 것이고, 그대로 커밋하면 남의 변경이 딸려 들어간다.
EXPECTED="$(git apply --numstat "$PATCH" | cut -f3- | sort)"
ACTUAL="$(git status --porcelain | sed 's/^...//' | tr -d '"' | sort)"

if [[ "$EXPECTED" != "$ACTUAL" ]]; then
  echo
  printf '\033[31m패치가 건드린 파일과 실제 변경이 다르다.\033[0m\n' >&2
  diff <(echo "$EXPECTED") <(echo "$ACTUAL") | sed 's/^</  패치에만: /; s/^>/  트리에만: /' >&2
  echo >&2
  echo "  다른 작업이 섞여 있다. 정리한 뒤 다시 실행한다." >&2
  echo "  붙인 것은 그대로 두었다. 되돌리려면: git apply -R '${PATCH}'" >&2
  exit 1
fi

# 검증했으므로 선언된 목록으로만 담는다.
git apply --numstat "$PATCH" | cut -f3- | while IFS= read -r file; do git add -- "$file"; done
git commit -q -m "$MESSAGE"
ok "커밋: ${MESSAGE}"
printf "  파일 %s개 · 패치 선언과 일치\n" "$(echo "$EXPECTED" | wc -l)"

echo
echo "다음:  make check  &&  git push"
echo "되돌리려면:  git reset --hard HEAD~1"
