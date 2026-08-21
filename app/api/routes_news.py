from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, require_admin
from app.db.models.auth import User
from app.db.models.news import NewsArticle
from app.db.session import get_db
from app.services.news_intelligence import context_for_symbol, refresh_news

router=APIRouter(prefix="/news",tags=["news"])

@router.get("")
def list_news(symbol:str|None=None,limit:int=Query(50,ge=1,le=200),_:User=Depends(get_current_user),db:Session=Depends(get_db)):
    stmt=select(NewsArticle).order_by(NewsArticle.published_at.desc()).limit(limit)
    if symbol:stmt=stmt.where(NewsArticle.symbols_csv.contains(symbol.upper()))
    rows=db.scalars(stmt).all()
    return [{"id":r.id,"source":r.source,"title":r.title,"url":r.url,"summary":r.summary,"symbols":[x for x in r.symbols_csv.split(',') if x],"sentiment_score":r.sentiment_score,"relevance_score":r.relevance_score,"published_at":r.published_at} for r in rows]

@router.get("/context/{symbol}")
def news_context(symbol:str,hours:int=Query(24,ge=1,le=168),_:User=Depends(get_current_user),db:Session=Depends(get_db)):
    c=context_for_symbol(db,symbol,hours=hours)
    return {"symbol":c.symbol,"article_count":c.article_count,"sentiment":c.sentiment,"relevance":c.relevance,"bias":c.bias,"headlines":c.headlines}

@router.post("/refresh")
async def refresh(_:User=Depends(require_admin),db:Session=Depends(get_db)):
    return await refresh_news(db)
