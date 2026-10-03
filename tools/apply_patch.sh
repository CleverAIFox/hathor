#!/usr/bin/env bash
# 패치 적용 + 커밋. **손으로 파일 목록을 적지 않는다** (GR-0.7 · D-0070).
#
#   make apply                  # 패치 폴더의 가장 최근 **hathor** .patch
#   make apply PATCH=D0071.patch
#   make apply WHICH=1          # 무엇을 집을지만 찍고 끝낸다 (D-0249)
#   make apply PATCH=... NOCOMMIT=1   # 붙이기만 하고 커밋하지 않는다
#
# 커밋 메시지는 패치 안의 `# hathor-commit:` 줄에서 읽는다. 없으면 파일 이름을 쓴다.
# **그 줄은 표식도 겸한다** — 패치 폴더를 여러 저장소가 나눠 쓰므로 (D-0249).
#
# **되돌리기·멱등성은 git이 진다.** 별도 백업 디렉터리를 만들지 않는다.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

die() { printf '\033[31m실패:\033[0m %s\n' "$1" >&2; exit 1; }

# 패치가 건드린다고 선언한 경로 전부. **이름 바꾸기는 두 줄이 된다** (D-0237).
declared_paths() {
  awk '/^diff --git /{
         from = $3; to = $4
         sub(/^a\//, "", from); sub(/^b\//, "", to)
         print from
         if (to != from) print to
       }' "$1" | sort -u
}
ok()  { printf '\033[32m%s\033[0m\n' "$1"; }

# **패치 폴더는 저장소 하나의 것이 아니다** (D-0249). 윈도 다운로드 폴더 하나에 여러
# 저장소의 패치가 같이 떨어지므로 «가장 최근»이 남의 것일 수 있다. 실제로 그랬고
# `git apply`가 *"No such file or directory"* 다섯 줄을 뱉은 뒤에야 알았다.
# **표식은 이미 있었다** — 커밋 메시지를 담은 `# <저장소>-commit:` 머리다.
MARKER='# hathor-commit:'

# 이 패치가 선언한 저장소. 없으면 빈 문자열(옛 패치일 수 있으므로 막지 않는다).
patch_origin() {
  grep -m1 -oE '^# [a-z][a-z0-9-]*-commit:' "$1" 2>/dev/null || true
}

# 폴더에서 **우리 것 중 가장 최근**을 고른다. 하나도 없으면 1을 낸다.
newest_ours() {
  local file
  while IFS= read -r file; do
    if grep -qF -m1 "$MARKER" "$file" 2>/dev/null; then
      printf '%s' "$file"
      return 0
    fi
  done < <(ls -t "$1"/*.patch 2>/dev/null)
  return 1
}

WHICH=""
if [[ "${1:-}" == "--which" ]]; then
  WHICH=1
  shift
fi

# **`.env`를 읽는 자리는 하나다** (D-0199). 예전에는 여기서 `grep`으로 직접
# 갈랐고 `paths.load_dotenv`와 규약이 달랐다 — CRLF · 따옴표 · `=` 주변 공백
# 셋에서 **다른 값이 나왔다.** WSL에서 `.env`를 윈도 편집기로 고치면 값 끝에
# `\r`이 붙어 *"패치 폴더가 없다: /mnt/d/patches"*가 뜬다. 폴더는 눈앞에 있다.
#
# `paths.py`는 서드파티 의존이 없어 **맨 `python3`으로 임포트된다** — venv 없이 돈다.
if [[ -f .env && -z "${HATHOR_PATCH_DIR:-}" ]]; then
  value="$(python3 - <<'PY' 2>/dev/null || true
import sys

sys.path.insert(0, "core")
from hathor.shared.config.paths import load_dotenv

print(load_dotenv().get("HATHOR_PATCH_DIR", ""), end="")
PY
)"
  [[ -n "$value" ]] && export HATHOR_PATCH_DIR="$value"
fi

PATCH="${1:-}"
if [[ -z "$PATCH" ]]; then
  [[ -n "${HATHOR_PATCH_DIR:-}" ]] || die "PATCH를 주거나 .env에 HATHOR_PATCH_DIR을 적는다 (make setup)"
  [[ -d "$HATHOR_PATCH_DIR" ]] || die "패치 폴더가 없다: ${HATHOR_PATCH_DIR}"
  PATCH="$(newest_ours "$HATHOR_PATCH_DIR" || true)"
  [[ -n "$PATCH" ]] || die "${HATHOR_PATCH_DIR}에 hathor 패치가 없다 — \`${MARKER}\` 머리로 가른다. 이름을 주면 그대로 붙인다"
else
  if [[ ! -f "$PATCH" && -n "${HATHOR_PATCH_DIR:-}" && -f "${HATHOR_PATCH_DIR}/${PATCH}" ]]; then
    PATCH="${HATHOR_PATCH_DIR}/${PATCH}"
  fi
  # 이름을 줬어도 남의 것이면 막는다. **`git apply`가 실패하기 전에 말해야 한다** —
  # 그 실패는 «브랜치를 확인하라»고 하고, 브랜치에는 아무 문제가 없다.
  if [[ -f "$PATCH" ]]; then
    origin="$(patch_origin "$PATCH")"
    if [[ -n "$origin" && "$origin" != "$MARKER" ]]; then
      die "$(basename "$PATCH")은 다른 저장소의 패치다 (\`${origin}\`)"
    fi
  fi
fi
[[ -f "$PATCH" ]] || die "패치가 없다: ${PATCH}"

if [[ -n "$WHICH" ]]; then
  printf '%s\n' "$PATCH"
  exit 0
fi
printf '패치: %s\n' "$(basename "$PATCH")"

# **이 패치가 무엇 위에 서는가** (D-0287). 패치는 직전 판 위에서 뽑히는데 **그 사실이
# 패치 어디에도 안 적혀 있었다.** 그래서 사람이 *"D0283을 붙이고 D0284를 붙여라"*는
# 지시를 받고 D0283이 **이미 붙어 있는지** 알 길이 없었다 — 실제로 이미 붙어 있었고
# 그 판 전체가 헛돌았다. 선행을 결정 번호로 적는다. **커밋 해시가 아니다** — 미러와
# 실물 저장소는 이력이 달라 커밋 해시가 안 맞는다. 결정 번호는 내용이라 어디서나 같다.
# **번호는 판을 가르지 못한다** (D-0351) — 같은 번호로 패치를 두 번 보내면 둘 다 통과한다.
# 그 자리는 `# hathor-base:`가 본다.
NEEDS="$(grep -m1 '^# hathor-needs:' "$PATCH" 2>/dev/null | sed 's/^# hathor-needs:[[:space:]]*//' || true)"
if [[ -n "$NEEDS" ]]; then
  for want in $NEEDS; do
    if ! grep -q "^## ${want}\." docs/DECISIONS.md; then
      die "선행 ${want}이 대장에 없다. 그 패치를 먼저 붙인다 (D-0287)"
    fi
  done
fi

if git apply --reverse --check "$PATCH" >/dev/null 2>&1; then
  ok "이미 적용돼 있다. 아무것도 하지 않는다 (멱등)."
  exit 0
fi

# **결정 번호는 어느 판인지 가르지 못한다** (D-0351). D-0349 패치가 세 판 나갔고
# 사람은 첫째를 붙였다고 했는데 실제로는 둘째가 들어가 있었다. 셋 다 `D-0349`라
# 위의 선행 검사는 전부 통과한다. 다음 패치가 안 붙자 `git apply`는 *"브랜치와
# 기준 커밋을 확인한다"*고 했고 **어느 기준인지는 말하지 않았다** — 어긋난 blob
# 해시를 손으로 좇아서야 알았다.
#
# **트리 해시를 쓴다.** D-0287이 *"해시가 아니다"*라고 쓴 것은 **커밋 해시** 얘기였고
# 거기까지가 맞다. 트리 해시는 파일 이름·모드·내용만으로 정해져 이력이 안 들어간다 —
# 실측: 커밋 350개인 미러와 커밋 1개인 새 저장소가 같은 트리 `4201d34a`를 냈고 커밋
# 해시만 달랐다. 그의 터미널이 찍은 blob `93b65907`도 미러와 같았다. 내용이라 어디서나
# 같은 것은 결정 번호와 똑같고, 해상도는 번호보다 높다.
BASE="$(grep -m1 '^# hathor-base:' "$PATCH" 2>/dev/null | sed 's/^# hathor-base:[[:space:]]*//' || true)"
if [[ -n "$BASE" ]]; then
  HERE="$(git rev-parse 'HEAD^{tree}')"
  if [[ "$BASE" != "$HERE" ]]; then
    echo >&2
    printf '\033[31m기준이 다르다 (D-0351).\033[0m\n' >&2
    printf '  이 패치가 서는 트리: %s\n' "$BASE" >&2
    printf '  네 HEAD의 트리:      %s\n' "$HERE" >&2
    echo >&2
    echo "  트리 해시는 내용이라 저장소가 달라도 같다 — 같은 번호의 다른 판을 붙이려는 것이다." >&2
    echo "  이 두 줄을 그대로 보내면 어느 판인지 가른다. 아무것도 붙이지 않았다." >&2
    exit 1
  fi
fi

# **작업 트리가 깨끗해야 한다.** 되돌리기를 git에 맡기는 대가다.
if [[ -n "$(git status --porcelain)" ]]; then
  git status --short
  die "커밋되지 않은 변경이 있다. 커밋하거나 stash한 뒤 다시 실행한다"
fi

git apply --check "$PATCH" || die "적용할 수 없다. 브랜치와 기준 커밋을 확인한다"
git apply "$PATCH"
ok "적용 완료"

python3 tools/check_decisions.py --check || die "결정 기록 검사가 어긋난다"

if [[ -n "${NOCOMMIT:-}" ]]; then
  echo "NOCOMMIT이라 커밋하지 않았다. 되돌리려면: git apply -R '${PATCH}'"
  exit 0
fi

MESSAGE="$(grep -m1 '^# hathor-commit:' "$PATCH" | sed 's/^# hathor-commit:[[:space:]]*//' || true)"
[[ -n "$MESSAGE" ]] || MESSAGE="chore: $(basename "$PATCH" .patch) 적용"

# **패치가 목록을 갖고 있으므로 손으로 적지도, 눈감고 `add -A` 하지도 않는다**
# (D-0072). 패치가 건드린다고 선언한 파일과 실제로 바뀐 파일이 정확히 같아야 한다.
# 다르면 다른 작업이 섞인 것이고, 그대로 커밋하면 남의 변경이 딸려 들어간다.
# **이름을 바꾼 파일은 `--numstat`에 한 줄로 온다** — 간 곳만 찍히고 **떠난 곳은 안 찍힌다**
# (D-0237). D-0236이 파일 다섯을 옮기자 트리에는 삭제 둘이 더 있었고 검사가 «다른 작업이
# 섞였다»며 막았다. 섞인 것이 없었다. 그래서 목록은 **패치의 `diff --git` 머리**에서 읽는다 —
# 거기에는 떠난 곳(`a/`)과 간 곳(`b/`)이 둘 다 있다.
EXPECTED="$(declared_paths "$PATCH")"
# **새 폴더는 폴더 하나로 접혀 나온다** — `site/`가 생기면 `site/proposal.html` 대신
# `site/`가 찍혀 선언과 어긋났다 (D-0222). 추적 안 된 파일을 전부 펼친다.
ACTUAL="$(git status --porcelain --untracked-files=all | sed 's/^...//' | tr -d '"' | sort)"

if [[ "$EXPECTED" != "$ACTUAL" ]]; then
  echo
  printf '\033[31m패치가 건드린 파일과 실제 변경이 다르다.\033[0m\n' >&2
  diff <(echo "$EXPECTED") <(echo "$ACTUAL") | sed 's/^</  패치에만: /; s/^>/  트리에만: /' >&2
  echo >&2
  echo "  다른 작업이 섞여 있다. 정리한 뒤 다시 실행한다." >&2
  echo "  붙인 것은 그대로 두었다. 되돌리려면: git apply -R '${PATCH}'" >&2
  exit 1
fi

# **도구 체인을 바꾸면 번호를 단다** (D-0039 · D-0286). D-0039가 *"문서 체계·개발 규약·
# 도구 체인 변경은 부수 결정으로 처리하지 않는다"*고 적고 **세는 것을 안 만들었다.**
# D-0015가 MASTER.md를 다른 주제의 부수 항목으로 강등했고 **나중에 아무도 못 찾았다.**
# 실측: 도구 체인을 건드린 커밋 25건 중 결정 기록 없이 간 것이 0건이다 — 구멍이 0이라
# 못을 박는다 (D-0134). 막는다: 여기서 막으면 패치를 다시 짜면 되고, 안 막으면 그 판단은
# 영영 번호가 없다.
TOOLCHAIN="$(echo "$EXPECTED" | grep -E '^(Makefile|\.github/workflows/|\.githooks/)' || true)"
if [[ -n "$TOOLCHAIN" ]] && ! echo "$EXPECTED" | grep -qx 'docs/DECISIONS.md'; then
  echo
  printf '\033[31m도구 체인을 바꾸면서 결정 기록이 없다 (D-0039).\033[0m\n' >&2
  echo "$TOOLCHAIN" | sed 's/^/  /' >&2
  echo >&2
  echo "  부수 결정으로 처리하지 않는다. 별도 번호를 달고 다시 짠다." >&2
  echo "  붙인 것은 그대로 두었다. 되돌리려면: git apply -R '${PATCH}'" >&2
  exit 1
fi

# 검증했으므로 선언된 목록으로만 담는다. 떠난 곳을 담아야 삭제가 커밋에 들어간다.
declared_paths "$PATCH" | while IFS= read -r file; do git add -- "$file"; done
git commit -q -m "$MESSAGE"
ok "커밋: ${MESSAGE}"
printf "  파일 %s개 · 패치 선언과 일치\n" "$(echo "$EXPECTED" | wc -l)"

echo
echo "다음:  make check  &&  git push"
echo "되돌리려면:  git reset --hard HEAD~1"
