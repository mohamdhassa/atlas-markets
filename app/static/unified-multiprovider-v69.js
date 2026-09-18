/* ATLAS v69 — unified multi-provider presentation layer.
   Read-only aggregation: one ATLAS universe across providers. No strategy,
   routing, risk, certification or execution logic is changed here. */
(()=>{'use strict';
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const badge=(v,ok=false)=>`<span class="badge ${ok?'good':'warn'}">${esc(v)}</span>`;
const dt=v=>v?new Date(v).toLocaleString():'—';
const money=v=>v==null?'—':Number(v).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
const byProfile=(strategies,id)=>strategies.filter(s=>String(s.profile_id)===String(id));
const latestFor=(actions,symbol,provider)=>actions.find(a=>String(a.symbol).toUpperCase()===String(symbol).toUpperCase()&&String(a.provider).toUpperCase()===String(provider).toUpperCase());

async function unifiedOperations(){
 setActive('Operations'); content.innerHTML='<div class="panel empty-state">Loading unified ATLAS operations…</div>';
 try{
  const [accounts,auto,actions,strategies,portfolio]=await Promise.all([
   api('/accounts'),api('/automation/state'),api('/automation/actions?limit=100'),
   api('/strategies/symbols'),api('/portfolio')
  ]);
  const connected=accounts.filter(a=>a.last_connection_status==='CONNECTED').length;
  const positions=portfolio.positions||[];
  const providerCards=accounts.map(a=>{
   const routed=byProfile(strategies,a.id), pa=actions.filter(x=>String(x.provider).toUpperCase()===String(a.provider).toUpperCase());
   const pp=positions.filter(x=>String(x.profile_id)===String(a.id));
   return `<article class="analysis-card"><div class="action-row"><div><p class="eyebrow">${esc(a.environment)}</p><h3>${esc(a.provider)} · ${esc(a.account_label)}</h3></div>${badge(a.last_connection_status||'UNKNOWN',a.last_connection_status==='CONNECTED')}</div>
    <div class="account-meta"><span>Equity</span><strong>${money(a.equity_usd)}</strong><span>Enabled</span><strong>${a.is_enabled===false?'NO':'YES'}</strong><span>Routed instruments</span><strong>${routed.length}</strong><span>Open positions</span><strong>${pp.length}</strong><span>Recent actions</span><strong>${pa.length}</strong><span>Execution gate</span><strong>${a.execution_certified?'CERTIFIED':a.provider==='TWELVE_DATA'?'DATA ONLY':'GATED'}</strong></div>
    <p class="muted" style="margin-top:10px">${routed.map(x=>esc(x.symbol)).join(' · ')||'No trading instruments routed to this profile.'}</p></article>`;
  }).join('');
  content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">UNIFIED OPERATIONS</p><h3>ATLAS execution control center</h3><p class="muted">All providers, routed instruments, positions and automation decisions remain visible together. Provider actions do not replace the rest of the ATLAS state.</p></div>${badge(auto.killed?'KILLED':auto.enabled?'RUNNING':'STOPPED',auto.enabled&&!auto.killed)}</div>
   <div class="metric-grid"><div class="metric-card"><span>Providers connected</span><strong>${connected}/${accounts.length}</strong></div><div class="metric-card"><span>ATLAS instruments</span><strong>${strategies.length}</strong></div><div class="metric-card"><span>Open positions</span><strong>${positions.length}</strong></div><div class="metric-card"><span>Automation interval</span><strong>${Number(auto.interval_seconds||0)}s</strong></div></div>
   <section class="panel"><div class="section-heading"><div><h3>Provider control plane</h3><p class="muted">Every provider is part of the same ATLAS system. Use Accounts/Integrations for connection controls; execution-specific certification remains provider-scoped.</p></div></div><div class="analysis-grid">${providerCards}</div></section>
   <section class="panel"><div class="section-heading"><div><h3>Unified routed universe</h3><p class="muted">One strategy universe with the execution provider shown as a route, not as a replacement data source.</p></div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Market</th><th>Symbol</th><th>Provider</th><th>Account</th><th>Mode</th><th>State</th><th>Latest action</th><th>Reason</th></tr></thead><tbody>${strategies.map(s=>{const a=accounts.find(x=>String(x.id)===String(s.profile_id)),last=latestFor(actions,s.symbol,a?.provider);return `<tr><td>${esc(s.market)}</td><td><strong>${esc(s.symbol)}</strong></td><td>${esc(a?.provider)}</td><td>${esc(a?.account_label)}</td><td>${esc(s.mode)}</td><td>${badge(s.enabled?'ENABLED':'DISABLED',s.enabled)}</td><td>${esc(last?.status)}</td><td>${esc(last?.reason)}</td></tr>`}).join('')}</tbody></table></div></section>
   <section class="panel"><div class="section-heading"><div><h3>Recent automation actions · all providers</h3><p class="muted">Chronological ATLAS decisions are aggregated here instead of replacing one provider with another.</p></div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Time</th><th>Provider</th><th>Environment</th><th>Symbol</th><th>Side</th><th>Status</th><th>Reason</th><th>Qty</th></tr></thead><tbody>${actions.map(x=>`<tr><td>${dt(x.created_at)}</td><td><strong>${esc(x.provider)}</strong></td><td>${esc(x.environment)}</td><td>${esc(x.symbol)}</td><td>${esc(x.side)}</td><td>${esc(x.status)}</td><td>${esc(x.reason)}</td><td>${x.quantity??'—'}</td></tr>`).join('')||'<tr><td colspan="8">No recent automation actions.</td></tr>'}</tbody></table></div></section>
   <section class="panel"><h3>Bybit Testnet certification</h3><p class="muted">The existing controlled Bybit certification remains available in the prior Operations implementation. It is intentionally separate from the unified read model and does not change IBKR or other provider data.</p><button id="v69BybitCert" class="ghost-button">Open Bybit certification controls</button></section>`;
  const b=document.getElementById('v69BybitCert'); if(b)b.onclick=()=>window.AtlasCore?.operations?.();
 }catch(e){content.innerHTML=`<div class="panel"><h3>Unified Operations unavailable</h3><p class="error-text">${esc(e.message)}</p></div>`}
}

async function unifiedSignals(){
 setActive('Signals');content.innerHTML='<div class="panel empty-state">Loading unified ATLAS decision activity…</div>';
 try{
  const [strategies,accounts,actions]=await Promise.all([api('/strategies/symbols'),api('/accounts'),api('/automation/actions?limit=100')]);
  content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">ATLAS INTELLIGENCE</p><h3>Unified signal & decision activity</h3><p class="muted">All configured instruments are shown together. Provider identifies the execution route; it does not replace the system-wide dataset.</p></div>${badge(`${strategies.length} INSTRUMENTS`,true)}</div>
   <div class="analysis-grid">${strategies.map(s=>{const a=accounts.find(x=>String(x.id)===String(s.profile_id)),last=latestFor(actions,s.symbol,a?.provider);return `<article class="analysis-card"><div class="action-row"><div><p class="eyebrow">${esc(s.market)} · ${esc(a?.provider)}</p><h3>${esc(s.symbol)}</h3></div>${badge(last?.status||'NO ACTION',last?.status==='EXECUTED')}</div><div class="account-meta"><span>Route</span><strong>${esc(a?.account_label)}</strong><span>Mode</span><strong>${esc(s.mode)}</strong><span>Latest side</span><strong>${esc(last?.side)}</strong><span>Latest result</span><strong>${esc(last?.reason)}</strong><span>Updated</span><strong>${dt(last?.created_at)}</strong></div></article>`}).join('')}</div>
   <p class="muted">This page reports the system's recorded strategy/automation state. It does not create a new recommendation or alter execution.</p>`;
 }catch(e){content.innerHTML=`<div class="panel"><h3>Unified Signals unavailable</h3><p class="error-text">${esc(e.message)}</p></div>`}
}

const prior=renderPage;
renderPage=async function(page){
 if(page==='Operations')return unifiedOperations();
 if(page==='Signals')return unifiedSignals();
 return prior(page);
};
window.AtlasUnifiedV69={operations:unifiedOperations,signals:unifiedSignals};
})();