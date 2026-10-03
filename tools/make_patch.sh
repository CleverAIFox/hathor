#!/usr/bin/env bash
# 패치를 뽑는다. **머리 셋을 손으로 적지 않는다** (GR-0.7 · D-0351).
#
#   make patch                       # HEAD 커밋 하나
#   make patch REV=25d1505
#   make patch OUT=/mnt/d/patches/D0351.patch
#   make patch VERIFY=D0350.patch    # 이미 있는 패치를 그 기준 위에서 검증만 한다
#
# 머리 셋은 전부 커밋에서 나온다:
#   `# hathor-commit:`  커밋 제목 (적용 쪽이 커밋 메시지로 쓴다)
#   `# hathor-needs:`   **부모의** 대장 마지막 결정 번호 (D-0287)
#   `# hathor-base:`    **부모의 트리 해시** (D-0351)
#
# **뽑고 나서 부모 위에서 정·역으로 붙여 본다.** 손으로 하던 일이고, 손으로 하면
# 빼먹는다 — D-0350 패치가 틀린 부모 위에서 뽑혀 나갔고 아무것도 그것을 안 봤다.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

die() { printf '\033[31m실패:\033[0m %s\n' "$1" >&2; exit 1; }
ok()  { printf '\033[32m%s\033[0m\n' "$1"; }

# **부모를 꺼내 거기서 붙여 본다.** 지금 트리 위에서 역검사만 하면 「이미 붙어 있다」가
# 통과로 보여 **틀린 부모를 못 잡는다** — D-0350이 정확히 그 꼴로 나갔다.
#   $1 패치 · $2 부모 커밋 · $3 도달해야 하는 커밋(없으면 트리 대조를 건너뛴다)
verify_on_parent() {
  local patch="$1" parent="$2" want="${3:-}" work code
  work="$(mktemp -d)"
  git worktree add -q --detach "${work}/v" "$parent" >/dev/null 2>&1 || {
    rm -rf "$work"
    die "검증용 작업 트리를 못 만들었다 (부모 ${parent:0:7})"
  }
  # **붙인 뒤에 역검사를 넣지 않는다.** `git apply`는 부분 적용을 거부하므로 방금 붙인
  # 것의 역검사는 늘 통과한다 — 심은 결함 열셋 중 그 자리만 **어떤 시험으로도 빨개지지
  # 않았다.** 못 빨개지는 검사는 덮은 척하는 그물이다 (D-0230 · GR-0.8). 받는 쪽의
  # 역방향 경로는 거기서 센다 (`test_apply_patch.py`의 멱등 시험).
  code=0
  (
    cd "${work}/v"
    git apply --check --binary "$patch" || exit 11
    git apply --binary "$patch" || exit 12
    [[ -z "$want" ]] && exit 0
    git add -A >/dev/null
    git diff-index --quiet --cached "$want" || exit 14
  ) || code=$?
  git worktree remove --force "${work}/v" >/dev/null 2>&1 || true
  rm -rf "$work"
  case "$code" in
    0)  return 0 ;;
    11) die "기준 위에 안 붙는다 — 기준이 ${parent:0:7}의 트리가 맞는지 본다" ;;
    12) die "검사는 통과했는데 붙이다 터졌다" ;;
    14) die "붙인 결과가 ${want:0:7}의 트리와 다르다. 패치가 변경 전부를 안 담았다" ;;
    *)  die "검증이 알 수 없는 까닭으로 멈췄다 (${code})" ;;
  esac
}

# ------------------------------------------------- 이미 있는 패치를 검증만 한다
# **그의 손에 있는 패치가 어느 판 위에 서는지 물어볼 수 있다.** 기준 트리로 내 이력을
# 훑어 그 커밋을 찾는다 — 트리 해시는 내용이라 미러에서도 같다 (D-0351).
if [[ -n "${VERIFY:-}" ]]; then
  [[ -f "$VERIFY" ]] || die "패치가 없다: ${VERIFY}"
  VERIFY="$(cd "$(dirname "$VERIFY")" && printf '%s/%s' "$(pwd)" "$(basename "$VERIFY")")"
  WANT="$(grep -m1 '^# hathor-base:' "$VERIFY" | sed 's/^# hathor-base:[[:space:]]*//' || true)"
  [[ -n "$WANT" ]] || die "$(basename "$VERIFY")에 \`# hathor-base:\` 머리가 없다 — 어느 기준인지 알 수 없다"
  STANDS=""
  while IFS= read -r one; do
    if [[ "$(git rev-parse "${one}^{tree}")" == "$WANT" ]]; then STANDS="$one"; break; fi
  done < <(git rev-list --all)
  [[ -n "$STANDS" ]] || die "기준 트리 ${WANT:0:12}를 이 저장소에서 못 찾았다 — 그 판이 여기 없다"
  # `AGAINST=<무언가>`를 주면 **붙인 결과가 그 커밋의 트리와 같은지도** 본다.
  if [[ -n "${AGAINST:-}" ]]; then
    git rev-parse --verify -q "${AGAINST}^{commit}" >/dev/null || die "그런 커밋이 없다: ${AGAINST}"
    verify_on_parent "$VERIFY" "$STANDS" "$(git rev-parse "${AGAINST}^{commit}")"
  else
    verify_on_parent "$VERIFY" "$STANDS"
  fi
  ok "$(basename "$VERIFY") · 붙는다"
  printf '  기준  %s\n' "$WANT"
  printf '  그것은  %s  %s\n' "${STANDS:0:7}" "$(git log -1 --format=%s "$STANDS")"
  printf '  검증  기준 위에서 정방향%s\n' "${AGAINST:+ · 트리 일치}"
  exit 0
fi

REV="${REV:-HEAD}"
git rev-parse --verify -q "${REV}^{commit}" >/dev/null || die "그런 커밋이 없다: ${REV}"
git rev-parse --verify -q "${REV}^^{commit}" >/dev/null || die "${REV}에 부모가 없다 — 첫 커밋은 패치로 못 뽑는다"

REV="$(git rev-parse "${REV}^{commit}")"
PARENT="$(git rev-parse "${REV}^")"
SUBJECT="$(git log -1 --format=%s "$REV")"
BASE="$(git rev-parse "${PARENT}^{tree}")"

# **번호는 커밋 제목에서 읽는다.** 번호가 없으면 뽑지 않는다 — 패치 이름이 번호이고
# 받는 쪽의 선행 검사도 번호로 돈다 (D-0287).
NUMBER="$(printf '%s' "$SUBJECT" | grep -oE '^D-[0-9]{4}' || true)"
[[ -n "$NUMBER" ]] || die "커밋 제목이 \`D-XXXX.\`로 시작하지 않는다: ${SUBJECT}"

# **번호를 적었다고 말하고 안 적었을 수 있다.** 그 커밋의 대장에 그 표제가 있어야 한다.
git show "${REV}:docs/DECISIONS.md" | grep -q "^## ${NUMBER}\." \
  || die "${NUMBER}이 그 커밋의 대장에 없다. 기록을 같이 담는다 (D-0039)"

# 선행은 **부모의** 마지막 번호다. 내 번호를 적으면 제 자신을 기다린다.
NEEDS="$(git show "${PARENT}:docs/DECISIONS.md" | grep -oE '^## D-[0-9]{4}\.' | tail -1 \
         | sed 's/^## //; s/\.$//')"
[[ -n "$NEEDS" ]] || die "부모의 대장에서 선행 번호를 못 읽었다"

OUT="${OUT:-${NUMBER//D-/D}.patch}"
mkdir -p "$(dirname "$OUT")"
{
  printf '# hathor-commit: %s\n' "$SUBJECT"
  printf '# hathor-needs: %s\n' "$NEEDS"
  printf '# hathor-base: %s\n' "$BASE"
  # `--binary`가 아니면 docx가 *"binary files differ"* 한 줄로 나가고 못 붙는다.
  git format-patch --stdout --binary --no-signature --no-stat -1 "$REV" \
    | sed -n '/^diff --git/,$p'
} > "$OUT"
OUT="$(cd "$(dirname "$OUT")" && printf '%s/%s' "$(pwd)" "$(basename "$OUT")")"

grep -q '^diff --git' "$OUT" || die "뽑은 패치에 변경이 없다: ${OUT}"

# ---------------------------------------------------------------- 뽑은 것을 붙여 본다
verify_on_parent "$OUT" "$PARENT" "$REV"

ok "$(basename "$OUT")"
printf '  메시지  %s\n' "$SUBJECT"
printf '  선행    %s\n' "$NEEDS"
printf '  기준    %s  (부모 %s의 트리)\n' "$BASE" "${PARENT:0:7}"
printf '  파일    %s개 · %s\n' "$(grep -c '^diff --git' "$OUT")" "$(du -h "$OUT" | cut -f1)"
printf '  검증    부모 위에서 정방향 · 트리 일치\n'
printf '  경로    %s\n' "$OUT"

if [[ -n "$(git status --porcelain)" ]]; then
  echo
  printf '\033[33m주의:\033[0m 작업 트리에 커밋 안 된 변경이 있다. 패치에는 안 담겼다.\n'
fi
