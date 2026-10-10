from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models.news import NewsArticle
from app.services.trade_news_context import attach_trade_news


BASE = datetime(2026, 9, 1, tzinfo=timezone.utc)


def article(key, date, symbol='MSFT', url='https://example.com/news'):
    return NewsArticle(external_id=key, source='Test', title=key, url=url,
                       symbols_csv=symbol, published_at=date, created_at=date,
                       sentiment_score=0, relevance_score=1)


def ms(date):
    return int(date.timestamp() * 1000)


def test_historical_entry_and_exit_survive_more_than_500_newer_articles():
    engine = create_engine('sqlite://')
    NewsArticle.__table__.create(engine)
    with Session(engine) as db:
        db.add_all([article(str(i), BASE + timedelta(days=40, minutes=i)) for i in range(501)])
        db.add_all([article('entry', BASE - timedelta(hours=1), ' msft, AAPL '),
                    article('exit', BASE + timedelta(days=9, hours=23)),
                    article('future', BASE + timedelta(days=10, seconds=1)),
                    article('wrong-symbol', BASE, 'XMSFT'),
                    article('unsafe', BASE - timedelta(hours=2), url='javascript:alert(1)')])
        db.commit()
        row = {'symbol': 'MSFT', 'opened_at': ms(BASE), 'closed_at': ms(BASE + timedelta(days=10))}
        attach_trade_news(db, [row])
        assert [n['title'] for n in row['entry_news']] == ['entry', 'unsafe']
        assert [n['title'] for n in row['exit_news']] == ['exit']
        assert row['entry_news'][1]['url'] == '#'
        assert row['news_attribution'] == 'HISTORICAL_SYMBOL_TIME_CONTEXT'


def test_unknown_entry_and_created_at_fallback_with_per_window_limit_and_dedup():
    engine = create_engine('sqlite://')
    NewsArticle.__table__.create(engine)
    with Session(engine) as db:
        db.add_all([article(str(i), BASE - timedelta(minutes=i)) for i in range(5)])
        fallback = article('fallback', BASE + timedelta(minutes=1))
        fallback.published_at = None
        db.add(fallback)
        db.commit()
        unknown = {'symbol': 'MSFT', 'time': ms(BASE + timedelta(minutes=1))}
        both = {'symbol': 'MSFT', 'opened_at': ms(BASE), 'closed_at': ms(BASE)}
        attach_trade_news(db, [unknown, both])
        assert unknown['entry_news'] == []
        assert unknown['exit_news'][0]['title'] == 'fallback'
        assert len(unknown['exit_news']) == 3
        assert len(both['news']) == 3
        assert both['entry_news'] == both['exit_news']
        assert both['entry_news'] is not both['exit_news']


def test_empty_windows_do_not_query_and_frontend_keeps_existing_table():
    assert attach_trade_news(None, [{'symbol': 'MSFT'}])[0]['news'] == []
    script = Path('app/static/live-pages.js').read_text()
    assert "render('Entry',trade.entry_news" in script
    assert "render('Exit',trade.exit_news" in script
    assert 'Historical context · not evidence of strategy use' in script
    assert '<th>News context</th>' in script
    assert 'live-pages.js?v=84.4' in Path('app/static/index.html').read_text()
