#!/usr/bin/env bash
# 셀프호스티드 러너 등록 · 점검 (D-0224 · D-0226 · D-0227). WSL에서. **몇 번 쳐도 같다.**
#
#   make runner                          # 토큰은 gh가 받는다 (gh auth login 된 상태)
#   bash tools/register_runner.sh <토큰>  # gh가 없으면 웹 화면(Linux · x64)의 --token 값
#   RUNNER_RECONFIGURE=1 make runner     # 등록을 지우고 다시 한다
#
# 이미 등록돼 있으면 등록은 건너뛰고 **라벨 · 서비스만 맞춘다.** 손으로 등록한 러너는 `gpu` 라벨이
# 없어 gpu-smoke가 대기열에서 영원히 기다린다 — 그 라벨을 API로 붙인다.
#
# 환경 변수: RUNNER_DIR (기본 ~/actions-runner) · RUNNER_NAME (기본 <호스트>-gpu) ·
#           RUNNER_LABELS (기본 gpu,1660ti — 장비를 바꾸면 뒤 라벨을 바꾼다)
set -euo pipefail
cd "$(dirname "$0")/.."   # gh가 저장소를 알아보는 자리

here="$(pwd)"
dir="${RUNNER_DIR:-$HOME/actions-runner}"
name="${RUNNER_NAME:-$(hostname)-gpu}"
labels="${RUNNER_LABELS:-gpu,1660ti}"
has_gh() { command -v gh >/dev/null && gh auth status >/dev/null 2>&1; }
api() { (cd "$here" && gh api "$@"); }

token="${1:-}"
fresh_token() {
  # 한 시간짜리 등록권. 화면에 찍지 않는다.
  if [ -z "$token" ] && has_gh; then
    token="$(api -X POST 'repos/{owner}/{repo}/actions/runners/registration-token' --jq .token)"
  fi
  if [ -z "$token" ]; then
    sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
  fi
}

remote="$(git -C "$here" remote get-url origin)"
slug="$(printf '%s' "$remote" | sed -E 's#^(git@github\.com:|https://github\.com/)##; s#\.git$##')"
case "$slug" in
  */*) ;;
  *) echo "origin이 GitHub 저장소가 아니다: $remote" >&2; exit 1 ;;
esac
url="https://github.com/$slug"

if ! command -v nvidia-smi >/dev/null; then
  echo "경고: nvidia-smi가 없다. 등록은 하지만 gpu-smoke가 첫 단계에서 멈춘다." >&2
fi

mkdir -p "$dir"
cd "$dir"
if [ ! -x ./config.sh ]; then
  version="$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest \
    | python3 -c 'import json, sys; print(json.load(sys.stdin)["tag_name"].lstrip("v"))')"
  echo "actions/runner $version 을 $dir 에 받는다"
  curl -fsSL -o runner.tar.gz \
    "https://github.com/actions/runner/releases/download/v$version/actions-runner-linux-x64-$version.tar.gz"
  tar xzf runner.tar.gz
  rm runner.tar.gz
fi

systemd=0
[ "$(ps -o comm= -p 1)" = "systemd" ] && systemd=1
installed=0
ls .service >/dev/null 2>&1 && installed=1

if [ -f .runner ] && [ -n "${RUNNER_RECONFIGURE:-}" ]; then
  echo "등록을 지우고 다시 한다"
  if [ "$installed" = 1 ]; then sudo ./svc.sh stop || true; sudo ./svc.sh uninstall; installed=0; fi
  has_gh || { echo "지우려면 gh가 필요하다. gh auth login" >&2; exit 2; }
  ./config.sh remove --token "$(api -X POST 'repos/{owner}/{repo}/actions/runners/remove-token' --jq .token)"
fi

if [ -f .runner ]; then
  name="$(python3 -c 'import json; print(json.load(open(".runner", encoding="utf-8-sig"))["agentName"])')"
  echo "이미 등록돼 있다: $name — 등록은 건너뛰고 라벨 · 서비스만 맞춘다"
else
  fresh_token
  ./config.sh --unattended --replace \
    --url "$url" --token "$token" \
    --name "$name" --labels "$labels" --work _work
fi

# 라벨 — 손으로 등록했으면 없다. 없는 것만 붙인다.
if has_gh; then
  id="$(api 'repos/{owner}/{repo}/actions/runners' --jq ".runners[] | select(.name == \"$name\") | .id")"
  if [ -n "$id" ]; then
    have="$(api "repos/{owner}/{repo}/actions/runners/$id/labels" --jq '.labels[].name')"
    for label in ${labels//,/ }; do
      if ! grep -qxi "$label" <<<"$have"; then
        api -X POST "repos/{owner}/{repo}/actions/runners/$id/labels" -f "labels[]=$label" >/dev/null
        echo "라벨을 붙였다: $label"
      fi
    done
  fi
fi

if [ "$systemd" = 1 ]; then
  [ "$installed" = 1 ] || sudo ./svc.sh install "$USER"
  sudo ./svc.sh start
  echo "서비스로 돈다. 상태: sudo $dir/svc.sh status"
else
  echo "systemd가 없다. 창을 열어 둔 동안만 돈다:  $dir/run.sh"
  echo "상시로 두려면 /etc/wsl.conf에 [boot] systemd=true → wsl --shutdown → 이 명령 다시."
fi
if has_gh; then
  echo "등록된 러너:"
  api 'repos/{owner}/{repo}/actions/runners' \
    --jq '.runners[] | "  \(.name) \(.status) [\([.labels[].name] | join(","))]"'
fi
