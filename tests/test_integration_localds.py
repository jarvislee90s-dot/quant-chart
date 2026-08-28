# tests/test_integration_localds.py
import pytest

pytestmark = pytest.mark.integration_localds

def test_real_index_minute():
    local_ds = pytest.importorskip("local_datasource")
    from quantchart.adapters.local_ds import load_via_local_ds
    import datetime as dtm
    today = dtm.date.today()
    start = (today - dtm.timedelta(days=3)).isoformat()
    df, rep = load_via_local_ds({"mode": "api",
                                 "api": {"future": "IM2612", "index": "000852"},
                                 "range": [start, today.isoformat()]})
    assert rep.rows > 0