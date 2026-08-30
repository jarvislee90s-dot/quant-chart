"""CLI --project 归档能力：一图一项目文件夹（config 快照/PNG/HTML），-o 显式指定时优先。"""
from pathlib import Path

import yaml
from click.testing import CliRunner

from quantchart.cli import main


def _cfg(tmp_path):
    csv = tmp_path / "d.csv"
    rows = "".join(f"2026-08-{d:02d},{7000+i},{7100+i},{6950+i},{7050+i},100\n"
                   for i, d in enumerate(range(20, 28)))
    csv.write_text("date,open,high,low,close,volume\n" + rows, encoding="utf-8")
    proj = tmp_path / "proj"
    yml = tmp_path / "c.yaml"
    yml.write_text(yaml.safe_dump({
        "input": {"mode": "daily_csv", "csv": str(csv), "range": ["2026-08-20", "2026-08-27"]},
        "strategy": "daily_candle", "title": "T", "project": str(proj),
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return str(yml), str(proj)


def test_cli_project_archives_config_and_outputs(tmp_path):
    yml, proj = _cfg(tmp_path)
    r = CliRunner().invoke(main, ["run", yml, "--project", proj])
    assert r.exit_code == 0, r.output
    assert (Path(proj) / "config.yaml").exists()          # 配置快照归档
    assert (Path(proj) / "chart.png").exists()            # PNG 派生进项目文件夹
    assert (Path(proj) / "chart.html").exists()
    assert "config 快照已归档" in r.output


def test_cli_explicit_output_wins_over_project_derive(tmp_path):
    yml, proj = _cfg(tmp_path)
    custom = tmp_path / "custom.png"
    r = CliRunner().invoke(main, ["run", yml, "--project", proj, "-o", str(custom)])
    assert r.exit_code == 0, r.output
    assert custom.exists()
    assert not (Path(proj) / "chart.png").exists()        # 显式 -o 优先，不派生
    assert (Path(proj) / "config.yaml").exists()          # 快照仍归档
