import yaml
import pytest
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


from quantchart.core.config import load_config, ConfigError
import yaml

def _cfg(**over):
    base = {"input": {"mode": "excel",
                      "excel": {"future": "tests/fixtures/fut.xlsx",
                                "index": "tests/fixtures/idx.xlsx"}},
            "strategy": "basis_review"}
    base.update(over)
    return base

def test_trades_field_validation(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(yaml.dump(_cfg(trades=[{"time": "2026-08-21 09:39", "action": "long"}])),
                 encoding="utf-8")
    with pytest.raises(ConfigError) as e:
        load_config(str(p))
    assert "trades[0].action" in str(e.value)

def test_trades_missing_lots(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(yaml.dump(_cfg(trades=[{"time": "2026-08-21 09:39", "action": "buy"}])),
                 encoding="utf-8")
    with pytest.raises(ConfigError) as e:
        load_config(str(p))
    assert "trades[0].lots" in str(e.value)

def test_extra_panels_must_be_list(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(yaml.dump(_cfg(extra_panels={"title": "x"})), encoding="utf-8")
    with pytest.raises(ConfigError) as e:
        load_config(str(p))
    assert "extra_panels" in str(e.value)

def test_trades_and_csv_mutually_ok(tmp_path):        # 二选一，只给其一不报错
    p = tmp_path / "c.yaml"
    p.write_text(yaml.dump(_cfg(trades_csv="E:/t.csv")), encoding="utf-8")
    assert load_config(str(p))["trades_csv"] == "E:/t.csv"

def test_contract_mult_bool_rejected(tmp_path):       # 评审 Minor：bool 是 int 子类，须拒
    p = tmp_path / "c.yaml"
    p.write_text(yaml.dump(_cfg(contract_mult=True)), encoding="utf-8")
    with pytest.raises(ConfigError) as e:
        load_config(str(p))
    assert "contract_mult" in str(e.value)


CFG_TRADES = {
    "input": {"mode": "excel",
              "excel": {"future": "tests/fixtures/fut.xlsx",
                        "index": "tests/fixtures/idx.xlsx"}},
    "strategy": "basis_review",
    "trades": [{"time": "2026-08-19 13:00", "action": "buy", "lots": 1}],
    "contract_mult": 200,
    "extra_panels": [{"title": "仓位", "y_title": "仓位（手）",
                      "range_cols": ["position_lots"], "layers": []}],
}

def test_pipeline_trades_and_extra_panels():
    fig, rep = run_pipeline(CFG_TRADES, title="t")
    # 仓位列已进渲染 df 且面板数=默认1+追加1
    assert fig.layout.xaxis2 is not None          # 第二面板存在
    ann_texts = [a.text for a in fig.layout.annotations if a.text]
    assert any("买1手" in (t or "") for t in ann_texts)

def test_merge_panels_priority():
    from quantchart.core.pipeline import merge_panels
    d, u, e = [{"t": "d"}], [{"t": "u"}], [{"t": "e"}]
    assert merge_panels(d, None, None) == d
    assert merge_panels(d, u, None) == u
    assert merge_panels(d, None, e) == d + e
    assert merge_panels(d, u, e) == u + e
