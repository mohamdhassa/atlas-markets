from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET
import httpx
from sqlalchemy import select

from app.db.models.news import NewsArticle
from app.services.signal_risk import GeneratedSignal

DEFAULT_FEEDS=(
    ("CoinDesk","https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph","https://cointelegraph.com/rss"),
)
SYMBOL_TERMS={
    "BTCUSDT":("bitcoin","btc"),"ETHUSDT":("ethereum","ether","eth"),"SOLUSDT":("solana","sol"),
    "XRPUSDT":("xrp","ripple"),"BNBUSDT":("bnb","binance coin"),
}
POSITIVE={"surge","gain","gains","bullish","rally","rise","rises","growth","approval","record","breakout","adoption","upgrade","strong"}
NEGATIVE={"fall","falls","drop","drops","bearish","crash","hack","lawsuit","ban","outflow","liquidation","weak","fraud","exploit"}

@dataclass(frozen=True)
class NewsContext:
    symbol:str
    article_count:int
    sentiment:float
    relevance:float
    bias:str
    headlines:list[dict]


def score_sentiment(text:str)->float:
    words=re.findall(r"[a-zA-Z]+",text.lower());pos=sum(w in POSITIVE for w in words);neg=sum(w in NEGATIVE for w in words)
    if not pos and not neg:return 0.0
    return max(-1.0,min(1.0,(pos-neg)/max(1,pos+neg)))

def detect_symbols(text:str)->list[str]:
    t=text.lower();return [symbol for symbol,terms in SYMBOL_TERMS.items() if any(re.search(rf"\b{re.escape(term)}\b",t) for term in terms)]

def relevance_for(text:str,symbols:list[str])->float:
    if not symbols:return 0.0
    t=text.lower();matches=sum(sum(t.count(term) for term in SYMBOL_TERMS[s]) for s in symbols)
    return min(1.0,0.35+(matches*0.15))

def parse_rss(xml_text:str,source:str)->list[dict]:
    root=ET.fromstring(xml_text);rows=[]
    for item in root.findall(".//item")[:50]:
        title=(item.findtext("title") or "").strip();url=(item.findtext("link") or "").strip();summary=(item.findtext("description") or "").strip();raw_date=(item.findtext("pubDate") or "").strip();published=None
        if raw_date:
            try: published=parsedate_to_datetime(raw_date).astimezone(timezone.utc)
            except Exception: pass
        text=f"{title} {re.sub('<[^>]+>',' ',summary)}";symbols=detect_symbols(text)
        external_id=(item.findtext("guid") or url or hashlib.sha256(text.encode()).hexdigest()).strip()
        if title and url: rows.append({"source":source,"external_id":external_id[:512],"title":title[:512],"url":url,"summary":re.sub('<[^>]+>',' ',summary)[:4000],"symbols":symbols,"sentiment_score":score_sentiment(text),"relevance_score":relevance_for(text,symbols),"published_at":published})
    return rows

async def refresh_news(db,feeds=DEFAULT_FEEDS)->dict:
    inserted=0;errors=[]
    async with httpx.AsyncClient(timeout=10.0,follow_redirects=True,headers={"User-Agent":"ATLAS-MARKETS/0.12"}) as client:
        for source,url in feeds:
            try:
                r=await client.get(url);r.raise_for_status();rows=parse_rss(r.text,source)
                for row in rows:
                    if db.scalar(select(NewsArticle).where(NewsArticle.external_id==row["external_id"])):continue
                    db.add(NewsArticle(source=row["source"],external_id=row["external_id"],title=row["title"],url=row["url"],summary=row["summary"],symbols_csv=",".join(row["symbols"]),sentiment_score=row["sentiment_score"],relevance_score=row["relevance_score"],published_at=row["published_at"]));inserted+=1
                db.commit()
            except Exception as exc:
                db.rollback();errors.append(f"{source}: {str(exc)[:120]}")
    return {"inserted":inserted,"errors":errors}

def context_for_symbol(db,symbol:str,hours:int=24,limit:int=20)->NewsContext:
    symbol=symbol.upper();since=datetime.now(timezone.utc)-timedelta(hours=hours)
    rows=list(db.scalars(select(NewsArticle).where(NewsArticle.published_at>=since,NewsArticle.symbols_csv.contains(symbol)).order_by(NewsArticle.published_at.desc()).limit(limit)).all())
    if not rows:return NewsContext(symbol,0,0.0,0.0,"NEUTRAL",[])
    weights=[max(0.05,r.relevance_score) for r in rows];total=sum(weights);sent=sum(r.sentiment_score*w for r,w in zip(rows,weights))/total;rel=sum(r.relevance_score for r in rows)/len(rows);bias="POSITIVE" if sent>=0.2 else "NEGATIVE" if sent<=-0.2 else "NEUTRAL"
    headlines=[{"source":r.source,"title":r.title,"url":r.url,"sentiment_score":r.sentiment_score,"relevance_score":r.relevance_score,"published_at":r.published_at} for r in rows[:10]]
    return NewsContext(symbol,len(rows),round(sent,4),round(rel,4),bias,headlines)

def apply_news_context(signal:GeneratedSignal,context:NewsContext,max_adjustment:float=8.0)->GeneratedSignal:
    if context.article_count==0 or context.bias=="NEUTRAL":return signal
    direction=1 if context.sentiment>0 else -1;technical=1 if signal.decision=="BUY" else -1 if signal.decision=="SELL" else 0
    agreement=direction*technical
    adjustment=max_adjustment*abs(context.sentiment)*max(0.25,context.relevance)
    score=signal.score+(adjustment if technical>=0 and agreement>0 else -adjustment if technical>0 and agreement<0 else adjustment if technical<0 and agreement<0 else -adjustment if technical<0 and agreement>0 else 0)
    score=max(0.0,min(100.0,score));strength=score if signal.decision=="BUY" else 100.0-score if signal.decision=="SELL" else 50.0
    reasons=list(signal.reasons)+[f"news_{context.bias.lower()}"]
    classification="NO_SIGNAL" if signal.decision=="HOLD" else "STRONG_SIGNAL" if strength>=80 else "SIGNAL" if strength>=65 else "WATCH"
    return replace(signal,score=score,strength=strength,reasons=reasons,classification=classification)
