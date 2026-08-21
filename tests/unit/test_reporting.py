from datetime import date
from types import SimpleNamespace
import uuid
from app.services.reporting import csv_text, date_series

def test_date_series_includes_zero_trade_days():
    pid=uuid.uuid4();row=SimpleNamespace(profile_id=pid,report_date=date(2026,8,20),realized_pnl=25.0,closed_trades=1,wins=1,losses=0,signals_count=4,approved_count=1)
    items=date_series([row],date(2026,8,20),date(2026,8,21))
    assert len(items)==2
    assert items[0]["realized_pnl"]==25.0
    assert items[1]["realized_pnl"]==0.0
    assert items[1]["closed_trades"]==0

def test_csv_export_has_operational_columns():
    text=csv_text([{"profile_id":"p1","date":"2026-08-21","realized_pnl":0.0,"closed_trades":0,"wins":0,"losses":0,"signals":5,"approved":1}])
    assert "profile_id,date,realized_pnl,closed_trades,wins,losses,signals,approved" in text
    assert "2026-08-21" in text
