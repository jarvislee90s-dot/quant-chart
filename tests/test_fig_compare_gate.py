"""fig_compare 回归门禁（--gate）的 pytest 包装。

--gate 语义：既有场景必须 0 diff（回归=0）、probe_* 探针必须有 diff（修复目标仍在）、
dump 齐全——任一不满足退出码 1。包装成 pytest 后随既有测试口径自动进任何 CI/本地验收，
无需单独配置 workflow。需 git 仓库上下文，pip 安装环境自动跳过。
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# 快速子集（1 既有 + 2 探针）控制套件时长；全量 13 场景可手动 `--gate` 复跑
ONLY = "cfg_basis_review,probe_p2_3_to_only,probe_p2_4_negative_floor"


def _gate(ref):
    return subprocess.run(
        [sys.executable, "tools/fig_compare.py", "--gate", ref, "--only", ONLY],
        cwd=str(ROOT), capture_output=True, text=True, timeout=600)


def test_gate_passes_against_baseline():
    if not (ROOT / ".git").exists():
        pytest.skip("需 git 仓库上下文（pip 安装环境无 .git）")
    r = _gate("9fd55e1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "GATE PASS" in r.stdout


def test_gate_detects_lost_fix():
    # 门禁自检：以当前 HEAD 为基线对比（内容相同的工作树）→ 探针 0 diff → 必须判 FAIL，
    # 防止门禁退化成"永远 PASS"
    if not (ROOT / ".git").exists():
        pytest.skip("需 git 仓库上下文（pip 安装环境无 .git）")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True).stdout.strip()
    r = _gate(head)
    assert r.returncode == 1
    assert "FIX_LOST" in r.stdout
