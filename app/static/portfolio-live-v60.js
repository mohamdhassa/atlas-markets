/* ATLAS MARKETS Portfolio v60 — read-only live position charts and activity totals. */
(()=>{
'use strict';
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=(v,d=2)=>v==null||v===''?'—':Number(v).toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d});
const usd=v=>v==null||v===''||!Number.isFinite(Number(v))?'—':`${Number(v)<0?'−':''}$${Math.abs(Number(v)).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`;
const pct=v=>v==null||!Number.isFinite(Number(v))?'—':`${Number(v)>=0?'+':''}${Number(v).toFixed(2)}%`;
const good=v=>Number(v)>=0?'pnl-positive':'pnl-negative';
const badge=(v,ok=false)=>`<span class="badge ${ok?'good':'warn'}">${esc(v)}</span>`;

function lineSvg(candles,entry,target,stop){
 const vals=(candles||[]).map(x=>Number(x.close)).filter(Number.isFinite);
 if(vals.length<2)return '<div class="empty-state muted">Live chart unavailable</div>';
 const refs=[entry,target,stop].map(Number).filter(Number.isFinite), all=vals.concat(refs), min=Math.min(...all), max=Math.max(...all), span=max-min||1;
 const w=720,h=220,p=18,y=v=>h-p-((v-min)/span)*(h-p*2);
 const points=vals.map((v,i)=>`${p+(i/(vals.length-1))*(w-p*2)},${y(v)}`).join(' ');
 const ref=(v,label,cls)=>Number.isFinite(Number(v))?`<line x1="${p}" x2="${w-p}" y1="${y(Number(v))}" y2="${y(Number(v))}" class="${cls}"/><text x="${p+4}" y="${Math.max(12,y(Number(v))-4)}" class="portfolio-chart-label">${label} ${usd(v)}</text>`:'';
 return `<svg viewBox="0 0 ${w} ${h}" class="portfolio-live-chart" role="img" aria-label="Live price chart"><polyline points="${points}" fill="none" stroke="currentColor" stroke-width="2.5" vector-effect="non-scaling-stroke"/>${ref(entry,'ENTRY','portfolio-entry-line')}${ref(target,'TARGET','portfolio-target-line')}${ref(stop,'STOP','portfolio-stop-line')}</svg>`;
}
function targetFor(orders,p,field){
 const rows=(orders||[]).filter(o=>String(o.profile_id)===String(p.profile_id)&&String(o.symbol).toUpperCase()===String(p.symbol).toUpperCase()&&o[field]!=null);
 return rows.length?Number(rows[0][field]):null;
}
function calcPnl(p,current){
 if(p.unrealized_pnl!=null)return {value:Number(p.unrealized_pnl),derived:false};
 const entry=Number(p.entry_price),qty=Number(p.quantity),cur=Number(current);
 if(!Number.isFinite(entry)||!Number.isFinite(qty)||!Number.isFinite(cur))return {value:null,derived:false};
 const short=['SHORT','SELL'].includes(String(p.side).toUpperCase());
 return {value:(short?entry-cur:cur-entry)*qty,derived:true};
}
async function loadChart(p,orders){
 const host=document.getElementById(`portfolio-chart-${String(p.profile_id).replace(/[^a-zA-Z0-9]/g,'')}-${String(p.symbol).replace(/[^a-zA-Z0-9]/g,'')}`);
 if(!host)return;
 try{
  const d=await api(`/portfolio-market/${encodeURIComponent(p.profile_id)}/${encodeURIComponent(p.symbol)}/candles?timeframe=5m&limit=120`);
  const candles=d.candles||d.list||[], last=candles.length?Number(candles[candles.length-1].close):null;
  const target=targetFor(orders,p,'take_profit'),stop=targetFor(orders,p,'stop_loss'),cp=Number.isFinite(last)?last:(p.mark_price==null?null:Number(p.mark_price));
  const pl=calcPnl(p,cp),plPct=pl.value!=null&&Number(p.entry_price)&&Number(p.quantity)?pl.value/(Math.abs(Number(p.entry_price)*Number(p.quantity)))*100:null;
  host.innerHTML=`${lineSvg(candles,p.entry_price,target,stop)}<div class="account-meta portfolio-chart-meta"><span>Entry</span><strong>${usd(p.entry_price)}</strong><span>Live</span><strong>${usd(cp)}</strong><span>Target</span><strong>${target==null?'No target configured':usd(target)}</strong><span>Stop</span><strong>${stop==null?'No stop configured':usd(stop)}</strong><span>Open P&amp;L${pl.derived?' (derived)':''}</span><strong class="${good(pl.value)}">${usd(pl.value)} ${plPct==null?'':`(${pct(plPct)})`}</strong></div>`;
 }catch(err){host.innerHTML=`<div class="empty-state"><strong>Chart unavailable</strong><div class="muted">${esc(err?.message||err)}</div></div>`}
}

async function portfolioV60(){
 content.innerHTML='<div class="panel empty-state">Loading live portfolio monitor…</div>';
 try{
  const [p,perf,ob]=await Promise.all([api('/portfolio'),api('/performance/broker-native?days=30'),api('/broker-orders?limit=200')]);
  const positions=p.positions||[],trades=perf.trades||[],orders=ob.orders||[],t=p.totals||{};
  const buys=trades.filter(x=>['BUY','BOT'].includes(String(x.side||'').toUpperCase()));
  const sells=trades.filter(x=>['SELL','SLD'].includes(String(x.side||'').toUpperCase()));
  const buyQty=buys.reduce((a,x)=>a+Number(x.quantity||0),0),sellQty=sells.reduce((a,x)=>a+Number(x.quantity||0),0);
  const buyValue=buys.reduce((a,x)=>a+(Number(x.quantity||0)*Number(x.execution_price||0)),0),sellValue=sells.reduce((a,x)=>a+(Number(x.quantity||0)*Number(x.execution_price||0)),0);
  const realized=perf.overall?.realized_pnl;
  content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">LIVE PORTFOLIO MONITOR</p><h3>Holdings, buys, sells, targets & performance</h3><p class="muted">Broker-native positions and executions. Charts refresh from provider market data when Portfolio is opened.</p></div>${badge(`${positions.length} HOLDINGS`,true)}</div>
  <div class="metric-grid portfolio-summary-grid">
   <div class="metric-card"><span>Total equity</span><strong>${usd(t.equity)}</strong></div><div class="metric-card"><span>Available</span><strong>${usd(t.available)}</strong></div><div class="metric-card"><span>Total holdings</span><strong>${positions.length}</strong></div><div class="metric-card"><span>Open P&amp;L</span><strong class="${good(t.unrealized_pnl)}">${usd(t.unrealized_pnl)}</strong></div>
   <div class="metric-card"><span>30d BUY executions</span><strong>${buys.length}</strong><small>${num(buyQty,4)} units · ${usd(buyValue)}</small></div><div class="metric-card"><span>30d SELL executions</span><strong>${sells.length}</strong><small>${num(sellQty,4)} units · ${usd(sellValue)}</small></div><div class="metric-card"><span>30d realized P&amp;L</span><strong class="${good(realized)}">${usd(realized)}</strong></div><div class="metric-card"><span>Total executions</span><strong>${trades.length}</strong></div>
  </div>
  <section class="panel"><div class="section-heading"><div><h3>Live holdings</h3><p class="muted">Each open position has its own 5-minute live chart with entry, target and stop when those values exist.</p></div></div><div class="portfolio-chart-grid">${positions.map(x=>{const id=`portfolio-chart-${String(x.profile_id).replace(/[^a-zA-Z0-9]/g,'')}-${String(x.symbol).replace(/[^a-zA-Z0-9]/g,'')}`;return `<article class="analysis-card portfolio-position-card"><div class="action-row"><div><p class="eyebrow">${esc(x.provider)} · ${esc(x.account)}</p><h3>${esc(x.symbol)}</h3></div><div>${badge(x.side,!['SHORT','SELL'].includes(String(x.side).toUpperCase()))}</div></div><div class="account-meta"><span>Quantity</span><strong>${num(x.quantity,4)}</strong><span>Entry</span><strong>${usd(x.entry_price)}</strong><span>Broker mark</span><strong>${x.mark_price==null?'—':usd(x.mark_price)}</strong><span>Market</span><strong>${esc(x.market)}</strong></div><div id="${id}" class="portfolio-chart-host"><div class="empty-state muted">Loading chart…</div></div></article>`}).join('')||'<div class="empty-state">No open holdings.</div>'}</div></section>
  <section class="panel"><div class="section-heading"><div><h3>Buy / sell ledger · 30 days</h3><p class="muted">What was bought and sold, execution price, quantity, commission and broker-reported realized result.</p></div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Provider</th><th>Symbol</th><th>Action</th><th>Qty</th><th>Price</th><th>Value</th><th>Commission</th><th>Realized P&amp;L</th><th>Order</th></tr></thead><tbody>${trades.map(x=>`<tr><td>${esc(x.provider)}</td><td><strong>${esc(x.symbol)}</strong></td><td>${badge(x.side,['BUY','BOT'].includes(String(x.side||'').toUpperCase()))}</td><td>${num(x.quantity,4)}</td><td>${usd(x.execution_price)}</td><td>${x.execution_price&&x.quantity?usd(Number(x.execution_price)*Number(x.quantity)):'—'}</td><td>${usd(x.commission)}</td><td>${x.pnl_available?`<strong class="${good(x.pnl)}">${usd(x.pnl)}</strong>`:'—'}</td><td>${esc(x.broker_order_id)}</td></tr>`).join('')||'<tr><td colspan="9">No executions in this window.</td></tr>'}</tbody></table></div></section>
  <section class="panel"><h3>Provider notices</h3><p class="muted">${[...(p.errors||[]),...(perf.errors||[]),...(ob.errors||[])].map(x=>`${esc(x.provider)}: ${esc(x.error)}`).join('<br>')||'No provider errors reported.'}</p></section>`;
  await Promise.allSettled(positions.map(x=>loadChart(x,orders)));
 }catch(err){content.innerHTML=`<div class="panel empty-state"><strong>Portfolio monitor unavailable</strong><p class="muted">${esc(err?.message||err)}</p></div>`}
}
const priorRender=renderPage;
renderPage=async function(page){if(page==='Portfolio'){setActive(page);return portfolioV60()}return priorRender(page)};
window.AtlasPortfolioV60={portfolioV60};
})();
