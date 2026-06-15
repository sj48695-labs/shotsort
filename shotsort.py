#!/usr/bin/env python3
"""shotsort — 스크린샷을 프로젝트별로 묶고, 지워도 되는 것을 한꺼번에 정리하는 CLI.

이 파일은 하위호환 shim 이다. 실제 로직은 engine.py, CLI 는 cli.py 에 있다.
  python shotsort.py scan ...   # == python cli.py scan ...
"""
from cli import main

if __name__ == "__main__":
    main()
