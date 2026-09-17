/* ATLAS MARKETS unified portfolio workspace v59.0
   Read-only presentation layer. No strategy, risk, certification or execution changes. */
(()=>{
'use strict';
const e=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n=(v,d=2)=>v==null||v===''?'—':Number(v).toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d});
const usd=v=>v==null||v===''?'—':`${Number(v)<0?'−':''}$${Math.abs(Number(v)).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`;
const pnl=v=>v==null||v===''?'<span class="muted">Not reported</span>':`<strong class="${Number(v)>=0?'pnl-positive':'pnl-negative'}">${usd(v)}</strong>`;
const when=v=>!v?'—':(typeof v==='number'&&v>0?new Date(v).toLocaleString():new Date(v).toLocaleString());
const badge=(v,ok=false)=>`<span class="badge ${ok?'good':'warn'}">${e(v)}</span>`;

// Replace the old Positions navigation label without changing permissions.
if(typeof userPages!=='undefined'){
 const i=userPages.indexOf('Positions');
 if(i>=0) userPages[i]='Portfolio';
}

async function portfolioWorkspace(){
 content.innerHTML='<div class="panel empty-state">Loading portfolio, positions and trade history…</div>';
 try{
  const [p,perf,orders]=await Promise.all([
   api('/portfolio'),
   api('/performance/broker-native?days=30'),
   api('/broker-orders?limit=100')
  ]);
  const t=p.totals||{}, positions=p.positions||[], accounts=p.accounts||[], trades=perf.trades||[], sym=perf.symbols||[];
  const realized=perf.overall?.realized_pnl;
  const pnlTrades=perf.overall?.pnl_trades||0;
  const openOrders=(orders.orders||[]).filter(x=>!['FILLED','Filled','EXECUTED','CANCELLED','Cancelled','REJECTED','Rejected'].includes(String(x.status||''))).length;
  content.innerHTML=`
   <div class="page-intro"><div><p class="eyebrow">BROKER-NATIVE PORTFOLIO</p><h3>Portfolio & trade ledger</h3><p class="muted">Current holdings, entry prices, broker-reported P&amp;L, recent executions and per-symbol results in one read-only workspace.</p></div>${badge(`${positions.length} OPEN`,true)}</div>
   <div class="metric-grid">
    <div class="metric-card"><span>Total equity</span><strong>${usd(t.equity)}</strong></div>
    <div class="metric-card"><span>Available balance</span><strong>${usd(t.available)}</strong></div>
    <div class="metric-card"><span>30d realized P&amp;L</span>${pnl(realized)}</div>
    <div class="metric-card"><span>Open positions / orders</span><strong>${positions.length} / ${openOrders}</strong></div>
   </div>
   <section class="panel"><div class="section-heading"><div><h3>Current positions</h3><p class="muted">What you currently own or are short. P&amp;L is shown only when the provider reports it.</p></div></div>
    <div class="table-wrap"><table class="data-table"><thead><tr><th>Provider</th><th>Account</th><th>Market</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Avg entry</th><th>Current / mark</th><th>Market value</th><th>Unrealized P&amp;L</th></tr></thead><tbody>
     ${positions.map(x=>{const mv=x.mark_price==null?null:Number(x.mark_price)*Number(x.quantity||0);return `<tr><td>${e(x.provider)}</td><td>${e(x.account)}</td><td>${e(x.market)}</td><td><strong>${e(x.symbol)}</strong></td><td>${badge(x.side,Number(x.quantity)>=0)}</td><td>${n(x.quantity,4)}</td><td>${x.entry_price==null?'—':usd(x.entry_price)}</td><td>${x.mark_price==null?'<span class="muted">Not reported</span>':usd(x.mark_price)}</td><td>${mv==null?'<span class="muted">Not reported</span>':usd(mv)}</td><td>${pnl(x.unrealized_pnl)}</td></tr>`}).join('')||'<tr><td colspan="10">No open positions.</td></tr>'}
    </tbody></table></div>
   </section>
   <section class="panel"><div class="section-heading"><div><h3>Results by symbol · 30 days</h3><p class="muted">Closed-trade statistics grouped by instrument. A zero does not imply a loss when the broker has not supplied realized P&amp;L.</p></div></div>
    <div class="table-wrap"><table class="data-table"><thead><tr><th>Market</th><th>Symbol</th><th>Executions</th><th>P&amp;L trades</th><th>Wins</th><th>Losses</th><th>Win rate</th><th>Realized P&amp;L</th></tr></thead><tbody>
     ${sym.map(x=>`<tr><td>${e(x.market)}</td><td><strong>${e(x.symbol)}</strong></td><td>${x.trades||0}</td><td>${x.pnl_trades||0}</td><td>${x.wins||0}</td><td>${x.losses||0}</td><td>${x.pnl_trades?n(x.win_rate,1)+'%':'—'}</td><td>${x.pnl_trades?pnl(x.realized_pnl):'<span class="muted">Not available</span>'}</td></tr>`).join('')||'<tr><td colspan="8">No closed-trade statistics in this window.</td></tr>'}
    </tbody></table></div>
   </section>
   <section class="panel"><div class="section-heading"><div><h3>Recent broker executions</h3><p class="muted">Individual fills/executions. This is the detailed ledger for what was bought or sold and the broker-reported realized result.</p></div>${badge(`${pnlTrades} P&L RECORDS`,true)}</div>
    <div class="table-wrap"><table class="data-table"><thead><tr><th>Time</th><th>Provider</th><th>Account</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Execution price</th><th>Commission</th><th>Realized P&amp;L</th><th>Broker order</th></tr></thead><tbody>
     ${trades.slice(0,100).map(x=>`<tr><td>${x.time?when(x.time):'—'}</td><td>${e(x.provider)}</td><td>${e(x.account)}</td><td><strong>${e(x.symbol)}</strong></td><td>${e(x.side)}</td><td>${x.quantity==null?'—':n(x.quantity,4)}</td><td>${x.execution_price==null?'—':usd(x.execution_price)}</td><td>${x.commission==null?'—':usd(x.commission)}</td><td>${x.pnl_available?pnl(x.pnl):'<span class="muted">Pending / unavailable</span>'}</td><td>${e(x.broker_order_id)}</td></tr>`).join('')||'<tr><td colspan="10">No broker executions in this window.</td></tr>'}
    </tbody></table></div>
   </section>
   <section class="panel"><h3>Account breakdown</h3><div class="analysis-grid">${accounts.map(a=>`<div class="analysis-card"><div class="action-row"><h4 style="margin-right:auto">${e(a.label)}</h4>${badge(a.status||'UNKNOWN',a.status==='CONNECTED')}</div><div class="account-meta"><span>Provider</span><strong>${e(a.provider)}</strong><span>Environment</span><strong>${e(a.environment)}</strong><span>Equity</span><strong>${usd(a.equity)}</strong><span>Available</span><strong>${usd(a.available)}</strong><span>Positions</span><strong>${a.positions||0}</strong><span>Unrealized</span>${pnl(a.unrealized_pnl)}</div></div>`).join('')}</div></section>
   ${(p.errors||[]).length|| (perf.errors||[]).length?`<section class="panel"><h3>Provider notices</h3><p class="muted">${[...(p.errors||[]),...(perf.errors||[])].map(x=>`${e(x.provider)}: ${e(x.error)}`).join('<br>')}</p></section>`:''}`;
 }catch(err){content.innerHTML=`<div class="panel empty-state"><strong>Portfolio unavailable</strong><p class="muted">${e(err?.message||err)}</p></div>`}
}

const previousRender=renderPage;
renderPage=async function(page){
 if(page==='Portfolio'){
  setActive(page);
  return portfolioWorkspace();
 }
 return previousRender(page);
};
window.AtlasPortfolioWorkspace={portfolioWorkspace};
})();
