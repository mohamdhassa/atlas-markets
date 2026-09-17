/* ATLAS v67.1 — separate read-only News Intelligence workspace. */
(()=>{'use strict';
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=v=>Number.isFinite(Number(v))?`${Math.round(Math.abs(Number(v))*100)}%`:'—';
const tone=b=>String(b||'NEUTRAL').toUpperCase();

function installNav(){
  const existing=[...document.querySelectorAll('.nav-button')].find(b=>b.dataset.page==='News Intelligence');
  if(existing)return;
  const anchor=[...document.querySelectorAll('.nav-button')].find(b=>b.dataset.page==='Signals');
  if(!anchor)return;
  const b=document.createElement('button');b.className='nav-button';b.textContent='News Intelligence';b.dataset.page='News Intelligence';b.onclick=()=>renderPage('News Intelligence');anchor.insertAdjacentElement('afterend',b);
}

async function newsPage(){
  content.innerHTML='<div class="panel empty-state">Loading stored news intelligence…</div>';
  try{
    const [strategies,actions]=await Promise.all([api('/strategies/symbols'),api('/automation/actions?limit=500')]);
    const rows=(strategies||[]).filter(x=>x.enabled),latest=new Map();
    for(const a of actions||[]){const k=String(a.symbol||'').toUpperCase();if(k&&!latest.has(k))latest.set(k,a)}
    const contexts=await Promise.all(rows.map(async s=>{try{return await api(`/news/context/${encodeURIComponent(s.symbol)}?hours=24`)}catch(e){return {symbol:s.symbol,article_count:0,sentiment:0,relevance:0,bias:'UNAVAILABLE',headlines:[]}}}));
    const withNews=contexts.filter(c=>Number(c.article_count)>0);
    const cards=withNews.map(c=>{const a=latest.get(String(c.symbol).toUpperCase()),heads=(c.headlines||[]).slice(0,5).map(h=>`<li><span>${esc(h.source)}</span><strong>${esc(h.title)}</strong></li>`).join('');return `<article class="v67-card"><div class="v67-top"><div><small>${esc(c.symbol)}</small><h4>${esc(tone(c.bias))} NEWS</h4></div><span class="v67-bias ${tone(c.bias).toLowerCase()}">${esc(c.article_count)} articles</span></div><div class="v67-metrics"><span>Sentiment <b>${pct(c.sentiment)}</b></span><span>Relevance <b>${pct(c.relevance)}</b></span><span>Latest recorded automation status <b>${esc(a?.status||'—')}</b></span></div>${heads?`<ul class="v67-headlines">${heads}</ul>`:''}</article>`}).join('');
    content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">MARKET INTELLIGENCE</p><h3>News Intelligence</h3><p class="muted">Stored 24-hour news context for monitored instruments. Symbols with no matching articles are hidden.</p></div><span class="badge ${withNews.length?'good':''}">${withNews.length} WITH NEWS</span></div><div class="panel v67-news"><div class="v67-grid">${cards||'<div class="v67-empty-page"><strong>No matching news is currently stored.</strong><span>The news page will populate when the existing news service records articles matching monitored symbols.</span></div>'}</div><div class="v67-page-foot">Informational market context only. News displayed here does not place or modify orders.</div></div>`;
  }catch(e){content.innerHTML=`<div class="panel empty-state">News intelligence unavailable: ${esc(e.message)}</div>`}
}

const priorBuild=buildNav;buildNav=function(){const r=priorBuild();installNav();return r};
const priorRender=renderPage;renderPage=async function(page){if(page==='News Intelligence'){setActive(page);await newsPage();return}return priorRender(page)};
setTimeout(installNav,0);
window.AtlasNewsDecisionContextV67={newsPage};
})();