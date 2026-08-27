# tests/conftest.py —— 会话级夹具自举：夹具 xlsx 不入库，缺失时自动生成
import pathlib
import subprocess
import sys

import pytest


@pytest.fixture(scope="session", autouse=True)
def _synth_fixtures():
    here = pathlib.Path(__file__).parent
    need = [here / "fixtures" / "fut.xlsx", here / "fixtures" / "idx.xlsx"]
    if not all(p.exists() for p in need):
        subprocess.run([sys.executable, str(here / "make_fixtures.py")],
                       check=True, cwd=str(here))
