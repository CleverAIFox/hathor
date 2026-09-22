# `core/`에서 `make`를 쳐도 뿌리 Makefile로 넘긴다 (D-0226).
# `uv run` 뒤에 셸이 여기 남아 있는 일이 잦다 — 목표는 뿌리 한 곳에만 산다.
.DEFAULT_GOAL := check
Makefile: ;
%:
	@$(MAKE) --no-print-directory -C .. $@
