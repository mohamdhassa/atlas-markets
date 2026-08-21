from app.services.news_intelligence import NewsContext, apply_news_context, detect_symbols, parse_rss, score_sentiment
from app.services.signal_risk import GeneratedSignal


def test_detect_symbols_and_sentiment():
    assert "BTCUSDT" in detect_symbols("Bitcoin rally reaches a record breakout")
    assert score_sentiment("bullish rally gain growth") > 0
    assert score_sentiment("bearish crash hack drop") < 0


def test_parse_rss_normalizes_article():
    xml='''<rss><channel><item><title>Bitcoin rally gains strength</title><link>https://example.com/a</link><guid>a-1</guid><description>BTC adoption growth</description><pubDate>Fri, 21 Aug 2026 10:00:00 GMT</pubDate></item></channel></rss>'''
    rows=parse_rss(xml,"Example")
    assert len(rows)==1
    assert rows[0]["source"]=="Example"
    assert "BTCUSDT" in rows[0]["symbols"]
    assert rows[0]["sentiment_score"]>0


def test_news_agreement_can_increase_buy_strength():
    signal=GeneratedSignal(decision="BUY",classification="SIGNAL",score=70,strength=70,reasons=[])
    context=NewsContext("BTCUSDT",3,0.8,0.8,"POSITIVE",[])
    adjusted=apply_news_context(signal,context)
    assert adjusted.score>signal.score
    assert adjusted.strength>signal.strength
    assert "news_positive" in adjusted.reasons


def test_news_disagreement_cannot_change_direction():
    signal=GeneratedSignal(decision="BUY",classification="SIGNAL",score=70,strength=70,reasons=[])
    context=NewsContext("BTCUSDT",3,-0.9,0.9,"NEGATIVE",[])
    adjusted=apply_news_context(signal,context)
    assert adjusted.decision=="BUY"
    assert adjusted.score<signal.score
