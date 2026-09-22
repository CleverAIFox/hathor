#!/usr/bin/env bash
# 셀프호스티드 러너 등록 (D-0224). WSL에서 기기당 한 번.
#
# 토큰: GitHub → 저장소 Settings → Actions → Runners → New self-hosted runner
#       화면의 `./config.sh ... --token XXXX`에서 XXXX. 한 시간 뒤 만료된다.
#
#   bash tools/register_runner.sh <토큰>
#
# 러너는 `gpu-smoke.yml`만 받는다 — 손으로 누를 때만 돈다 (D-0224).
# 장비를 바꾸면 같은 명령을 새 기기에서 다시 친다. `--replace`가 같은 이름을 갈아 끼운다.
#
# 환경 변수로 바꿀 수 있다:
#   RUNNER_DIR     설치 위치       (기본 ~/actions-runner)
#   RUNNER_NAME    러너 이름       (기본 <호스트>-gpu)
#   RUNNER_LABELS  추가 라벨       (기본 gpu,1660ti — 장비를 바꾸면 뒤 라벨을 바꾼다)
set -euo pipefail

token="${1:-}"
if [ -z "$token" ]; then
  sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
fi

here="$(cd "$(dirname "$0")/.." && pwd)"
dir="${RUNNER_DIR:-$HOME/actions-runner}"
name="${RUNNER_NAME:-$(hostname)-gpu}"
labels="${RUNNER_LABELS:-gpu,1660ti}"

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

./config.sh --unattended --replace \
  --url "$url" --token "$token" \
  --name "$name" --labels "$labels" --work _work

if [ "$(ps -o comm= -p 1)" = "systemd" ]; then
  sudo ./svc.sh install "$USER"
  sudo ./svc.sh start
  echo "서비스로 올렸다. 상태: sudo $dir/svc.sh status"
else
  echo "systemd가 없다. 창을 열어 둔 동안만 돈다:  $dir/run.sh"
  echo "상시로 두려면 /etc/wsl.conf에 [boot] systemd=true → wsl --shutdown → 이 명령 다시."
fi
echo "확인: GitHub → Settings → Actions → Runners에 $name (Idle)"
