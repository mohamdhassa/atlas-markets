"""Read-only historical news context, never evidence of strategy use."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select

from app.db.models.news import NewsArticle


WINDOW_MS = 24 * 60 * 60 * 1000


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _window(row, stage):
    return int(row.get('opened_at') or 0) if stage == 'entry' else int(row.get('closed_at') or row.get('time') or 0)


def attach_trade_news(db, rows):
    anchors = sorted({_window(row, stage) for row in rows for stage in ('entry', 'exit')} - {0})
    # Merge overlapping windows to keep the SQL small without dropping historical matches.
    windows = []
    for anchor in anchors:
        end = datetime.fromtimestamp(anchor / 1000, tz=timezone.utc)
        start = end - timedelta(hours=24)
        if windows and start <= windows[-1][1]:
            windows[-1] = (windows[-1][0], end)
        else:
            windows.append((start, end))
    published = func.coalesce(NewsArticle.published_at, NewsArticle.created_at)
    articles = list(db.scalars(select(NewsArticle).where(or_(
        *(and_(published >= start, published <= end) for start, end in windows)
    )).order_by(published.desc(), NewsArticle.id)).all()) if windows else []
    by_symbol = {}
    for article in articles:
        date = article.published_at or article.created_at
        if date is None:
            continue
        stamp = int(_utc(date).timestamp() * 1000)
        payload = {
            'id': str(article.id), 'title': article.title, 'source': article.source,
            'url': article.url if str(article.url or '').lower().startswith(('http://', 'https://')) else '#',
            'published_at': _utc(date).isoformat(), 'sentiment_score': article.sentiment_score,
            'relevance_score': article.relevance_score,
        }
        for symbol in {s.strip().upper() for s in (article.symbols_csv or '').split(',')} - {''}:
            by_symbol.setdefault(symbol, []).append((stamp, payload))
    for row in rows:
        candidates = by_symbol.get(str(row.get('symbol') or '').upper(), [])
        for stage in ('entry', 'exit'):
            anchor = _window(row, stage)
            row[f'{stage}_news'] = [payload.copy() for stamp, payload in candidates
                                     if anchor and 0 <= anchor - stamp <= WINDOW_MS][:3]
        combined = {article['id']: article for stage in ('entry', 'exit') for article in row[f'{stage}_news']}
        row['news'] = list(combined.values())
        row['news_attribution'] = 'HISTORICAL_SYMBOL_TIME_CONTEXT' if combined else 'NO_STORED_CONTEXT'
    return rows
