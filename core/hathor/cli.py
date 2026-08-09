"""`python -m hathor.cli`용 진입 모듈. 구현은 interfaces에 있다."""

from __future__ import annotations

import sys

from hathor.interfaces.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
