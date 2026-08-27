import yaml
from quantchart.core.pipeline import run_pipeline
from quantchart.core.config import load_config, ConfigError

CFG = {
    "input": {"mode": "excel",
              "excel": {"future": "tests/fixtures/fut.xlsx",
                        "index": "tests/fixtures/idx.xlsx"},
              "range": ["2026-08-19", "2026-08-20"]},
    "strategy": "basis_zones",
    "params": {"trigger": 260.0,
               "zones": [{"from": "2026-08-19 11:30", "to": "2026-08-20 11:30",
                          "price": [6900, 7200], "label": "Z1"}]},
}

def test_config_rejects_missing_field(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(yaml.dump({"input": {"mode": "excel"}}), encoding="utf-8")
    try:
        load_config(str(p))
        assert False
    except ConfigError as e:
        assert "strategy" in str(e)

def test_pipeline_end_to_end(tmp_path):
    fig, rep = run_pipeline(CFG, title="测试")
    assert rep.days == 2
    png = tmp_path / "o.png"
    fig.write_image(str(png), width=1600, height=900)
    assert png.stat().st_size > 30_000

def test_config_rejects_missing_excel_keys(tmp_path):
    p = tmp_path / "c2.yaml"
    p.write_text(yaml.dump({"input": {"mode": "excel",
                                      "excel": {"future": "a.xlsx"}},
                            "strategy": "basis_review"}), encoding="utf-8")
    try:
        load_config(str(p))
        assert False
    except ConfigError as e:
        assert "index" in str(e)
