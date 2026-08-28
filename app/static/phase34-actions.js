(()=>{
const dti=v=>v?new Date(v).toLocaleString():'—';
const esc=v=>String(v??'—').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
const badge=s=>s==='EXECUTED'?'good':s==='BLOCK'?'warn':'';
async function renderActions(){
  if(typeof setActive==='function')setActive('Orders');
  const root=document.getElementById('content');
  root.innerHTML='<div class="panel empty-state">Loading ATLAS action history…</div>';
  try{
    const [actions,orders,portfolio,stateData]=await Promise.all([
      api('/automation/actions?limit=200'),
      api('/broker-orders?limit=200'),
      api('/portfolio'),
      api('/automation/state')
    ]);
    const executed=actions.filter(a=>a.status==='EXECUTED').length;
    const blocked=actions.filter(a=>a.status==='BLOCK').length;
    const skipped=actions.filter(a=>a.status==='SKIP').length;
    root.innerHTML=`
      <div class="page-intro"><div><p class="eyebrow">ATLAS EXECUTION LEDGER</p><h3>Orders & ATLAS Actions</h3><p class="muted">Persistent audit history of automatic decisions, broker orders and current positions.</p></div><span class="badge ${stateData.killed?'warn':'good'}">${stateData.killed?'AUTOMATION STOPPED':'AUTOMATION ACTIVE'}</span></div>
      <div class="p21-kpis"><div class="metric"><span>Recorded actions</span><strong>${actions.length}</strong></div><div class="metric"><span>Executed</span><strong>${executed}</strong></div><div class="metric"><span>Blocked</span><strong>${blocked}</strong></div><div class="metric"><span>Skipped</span><strong>${skipped}</strong></div></div>
      <section class="panel"><div class="p21-section-head"><div><h3>ATLAS Actions</h3><div class="muted">Every persisted automatic decision with its reason, sizing policy and broker reference.</div></div><span class="badge">LATEST ${actions.length}</span></div><div class="p21-table-scroll"><table class="data-table"><thead><tr><th>Time</th><th>Provider</th><th>Environment</th><th>Market</th><th>Symbol</th><th>Side</th><th>Status</th><th>Reason</th><th>Qty</th><th>Sizing policy</th><th>Broker order</th></tr></thead><tbody>${actions.length?actions.map(a=>`<tr><td>${dti(a.created_at)}</td><td>${esc(a.provider)}</td><td>${esc(a.environment)}</td><td>${esc(a.market)}</td><td><strong>${esc(a.symbol)}</strong></td><td>${esc(a.side)}</td><td><span class="badge ${badge(a.status)}">${esc(a.status)}</span></td><td>${esc(a.reason)}</td><td>${a.quantity??'—'}</td><td>${esc(a.sizing_policy)}</td><td>${esc(a.broker_order_id)}</td></tr>`).join(''):'<tr><td colspan="11">No ATLAS actions recorded yet. The next automatic cycle will populate this ledger.</td></tr>'}</tbody></table></div></section>
      <section class="panel"><div class="p21-section-head"><div><h3>Provider-reported orders</h3><div class="muted">Current orders reported directly by connected brokers.</div></div><span class="badge">${(orders.orders||[]).length} ORDERS</span></div><div class="p21-table-scroll"><table class="data-table"><thead><tr><th>Provider</th><th>Account</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Filled</th><th>Status</th><th>Order ID</th></tr></thead><tbody>${(orders.orders||[]).length?(orders.orders||[]).map(o=>`<tr><td>${esc(o.provider)}</td><td>${esc(o.account)}</td><td>${esc(o.symbol)}</td><td>${esc(o.side)}</td><td>${o.quantity??'—'}</td><td>${o.filled_quantity??'—'}</td><td>${esc(o.status)}</td><td>${esc(o.order_id)}</td></tr>`).join(''):'<tr><td colspan="8">No provider-reported pending orders.</td></tr>'}</tbody></table></div></section>
      <section class="panel"><div class="p21-section-head"><div><h3>Current positions</h3><div class="muted">Open positions currently reported by connected brokers.</div></div><span class="badge good">${(portfolio.positions||[]).length} OPEN</span></div><div class="p21-table-scroll"><table class="data-table"><thead><tr><th>Provider</th><th>Account</th><th>Market</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>Unrealized P&L</th></tr></thead><tbody>${(portfolio.positions||[]).length?(portfolio.positions||[]).map(p=>`<tr><td>${esc(p.provider)}</td><td>${esc(p.account)}</td><td>${esc(p.market)}</td><td><strong>${esc(p.symbol)}</strong></td><td>${esc(p.side)}</td><td>${p.quantity??'—'}</td><td>${p.entry_price??'—'}</td><td>${p.unrealized_pnl??'—'}</td></tr>`).join(''):'<tr><td colspan="8">No open positions.</td></tr>'}</tbody></table></div></section>`;
  }catch(e){root.innerHTML=`<div class="panel empty-state"><strong>ATLAS Actions unavailable</strong><br>${esc(e.message||e)}</div>`}
}
function capture(e){const b=e.target.closest?.('.nav-button');if(b?.dataset?.page!=='Orders')return;e.preventDefault();e.stopImmediatePropagation();renderActions()}
document.addEventListener('click',capture,true);
window.AtlasPhase34={actions:renderActions};
})();
