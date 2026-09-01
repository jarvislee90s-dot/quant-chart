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

def test_api_mode_requires_api_section_and_range(tmp_path):
    # mode=api 缺 api 段 / 缺 range 都要定位到字段报错
    base = {"input": {"mode": "api", "excel": {"future": "f", "index": "i"}},
            "strategy": "basis_review"}
    p = tmp_path / "a.yaml"
    p.write_text(yaml.dump(base), encoding="utf-8")
    with pytest.raises(ConfigError) as e:
        load_config(str(p))
    assert "input.api.future" in str(e.value)
    p.write_text(yaml.dump({**base, "input": {**base["input"],
        "api": {"future": "IM2612"}}}), encoding="utf-8")
    with pytest.raises(ConfigError) as e:
        load_config(str(p))
    assert "input.api.index" in str(e.value)
    p.write_text(yaml.dump({**base, "input": {**base["input"],
        "api": {"future": "IM2612", "index": "000852"}}}), encoding="utf-8")
    with pytest.raises(ConfigError) as e:
        load_config(str(p))
    assert "input.range" in str(e.value)


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


def test_row_heights_length_mismatch_rejected_in_chinese():
    # 日内 row_heights 长度校验（对齐日线文案）：与面板数不符报中文错误——
    # 多面板时原落到 plotly 英文报错，单面板时被 _build_single 静默丢弃
    with pytest.raises(ValueError, match=r"row_heights 长度 3 与面板数 2 不符"):
        cfg = dict(CFG)
        cfg["extra_panels"] = [{"title": "仓位", "y_title": "仓位",
                                "layers": [{"type": "line", "col": "fut_close"}]}]
        cfg["row_heights"] = [0.7, 0.2, 0.1]        # 3 ≠ 2 面板
        run_pipeline(cfg)
    with pytest.raises(ValueError, match=r"row_heights 长度 2 与面板数 1 不符"):
        run_pipeline(dict(CFG, row_heights=[0.72, 0.28]))   # 单面板静默丢弃路径


def test_row_heights_from_config():
    # YAML row_heights 对日内多面板同效（CLI 不传参时从 cfg 取，与日线同一路径）
    fig, _ = run_pipeline(dict(CFG_TRADES, row_heights=[0.5, 0.5]), title="t")
    assert fig.layout.yaxis.domain[0] > 0.5     # 对开：主图域底 0.575（默认 0.72 占比时 0.388）
