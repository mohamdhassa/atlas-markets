/* Final presentation-only polish for Signals. Existing APIs and trading logic remain unchanged. */
(()=>{
'use strict';
const h=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n=(v,d=1)=>Number.isFinite(Number(v))?Number(v).toFixed(d):'—';
async function polishedSignals(){
 content.innerHTML='<div class="panel empty-state">Calculating market analysis…</div>';
 const symbols=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT'];
 try{
  const rows=await Promise.all(symbols.map(s=>api(`/analysis/${s}?interval=5m&category=linear&limit=200`)));
  const long=rows.filter(x=>x.bias==='LONG').length, short=rows.filter(x=>x.bias==='SHORT').length;
  content.innerHTML=`<div class="polish-hero"><div><p class="eyebrow">TECHNICAL ANALYSIS</p><h1>Signals</h1><p>5-minute deterministic technical analysis across the configured crypto watchlist.</p></div><span class="accounts-count">${rows.length} MARKETS</span></div><div class="polish-metrics signal-summary"><div><span>Markets</span><strong>${rows.length}</strong></div><div><span>Long bias</span><strong>${long}</strong></div><div><span>Short bias</span><strong>${short}</strong></div><div><span>Neutral</span><strong>${rows.length-long-short}</strong></div></div><section class="signal-polish-grid">${rows.map(a=>{const bias=String(a.bias||'NEUTRAL'),cls=bias==='LONG'?'good':bias==='SHORT'?'warn':'';return `<article class="signal-polish-card"><div class="signal-card-head"><div><span class="signal-symbol">${h(a.symbol)}</span><small>5 MINUTE</small></div><span class="badge ${cls}">${h(bias)}</span></div><div class="signal-score"><strong>${h(a.score)}/100</strong><span>Signal score</span></div><div class="signal-facts"><div><span>Trend</span><strong>${h(a.trend)}</strong></div><div><span>Structure</span><strong>${h(a.structure)}</strong></div><div><span>RSI 14</span><strong>${n(a.rsi14)}</strong></div><div><span>Volatility</span><strong>${h(a.volatility)}</strong></div></div><div class="signal-meter"><i style="width:${Math.max(0,Math.min(100,Number(a.score)||0))}%"></i></div></article>`}).join('')}</section><p class="signal-note">Technical signals are analytical outputs, not guaranteed outcomes. Execution remains subject to ATLAS risk and provider gates.</p>`;
 }catch(err){content.innerHTML=`<div class="panel empty-state">Signals unavailable: ${h(err.message)}</div>`}
}
const previous=renderPage;
renderPage=function(page){if(page==='Signals'){setActive(page);return polishedSignals()}return previous(page)};
window.AtlasFinalPolish={signals:polishedSignals};
})();
