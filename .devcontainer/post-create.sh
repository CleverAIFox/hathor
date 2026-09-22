#!/usr/bin/env bash
# 데브 컨테이너가 처음 뜰 때 한 번 돈다 (D-0223).
set -euo pipefail

sudo apt-get update
# ffmpeg — 디코더 시험 · graphviz · 한글 글꼴 — 기획서 빌드
sudo apt-get install -y --no-install-recommends make ffmpeg graphviz fonts-noto-cjk

pip install --user uv
# CI와 같은 묶음에 docs · mlops까지다. GPU 묶음을 빼면 mypy가 `type: ignore`를 미사용으로 잡아
# make check이 CI와 갈린다 — 무겁지만 같은 것을 본다. 명령은 Makefile 한 곳에 산다 (D-0225)
make sync

# 저장소 훅을 직접 건다. WSL에서는 전역 훅이 이것을 부르지만 컨테이너에는 전역 훅이 없다
git config core.hooksPath .githooks
echo "준비 완료 — make check"
