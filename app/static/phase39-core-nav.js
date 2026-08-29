(()=>{
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=v=>Number(v||0).toLocaleString(undefined,{style:'currency',currency:'USD'});
const dt=v=>v?new Date(v).toLocaleString():'—';
function setAutomationActive(){if(typeof setActive==='function')setActive('Automation');const t=document.getElementById('pageTitle');if(t)t.textContent='Automation'}
function reasonGroup(r){r=String(r||'');if(r.includes('NO_DIRECTION')||r.includes('NO_SIGNAL'))return 'NO TRADE SIGNAL';if(r.includes('AUTO_TRADE_NOT_ENABLED'))return 'STRATEGY SIGNALS ONLY';if(r.includes('POSITION_LIMIT')||r.includes('SYMBOL_ALREADY_HAS_POSITION'))return 'RISK PREVENTED';if(r.includes('PROVIDER_EXECUTION_NOT_CERTIFIED'))return 'PROVIDER BLOCKED';if(r.includes('BROKER_ORDER')||r.includes('IBKR_QUANTITY'))return 'BROKER / SIZING';return r||'OTHER'}
async function renderAutomation(){
 setAutomationActive();
 const root=document.getElementById('content');if(!root)return;
 root.innerHTML='<div class="panel empty-state">Loading Automation Operations Center…</div>';
 try{
  const [s,scans,actions,portfolio,strategies,perf]=await Promise.all([
   api('/automation/state'),api('/automation/scans?limit=20'),api('/automation/actions?limit=200'),api('/portfolio'),api('/strategies/symbols'),api('/performance/unified?days=30')
  ]);
  const latest=scans?.[0]||null;
  const counts={EXECUTED:0,BLOCK:0,SKIP:0,SKIPPED:0,CANCELLED:0,SUBMITTED:0};
  (actions||[]).forEach(a=>counts[a.status]=(counts[a.status]||0)+1);
  const reasonCounts={};(actions||[]).forEach(a=>{const k=reasonGroup(a.reason);reasonCounts[k]=(reasonCounts[k]||0)+1});
  const topReasons=Object.entries(reasonCounts).sort((a,b)=>b[1]-a[1]).slice(0,8);
  const modes={AUTO_TRADE:0,SIGNALS:0,WATCH:0};(strategies||[]).filter(x=>x.enabled).forEach(x=>modes[x.mode]=(modes[x.mode]||0)+1);
  const ps=perf?.summary||{};
  root.innerHTML=`<div class="page-intro"><div><p class="eyebrow">AUTOMATION OPERATIONS CENTER</p><h3>ATLAS automatic trading control</h3><p class="muted">Engine state, certified routes, scan outcomes, broker positions and performance in one place.</p></div><span class="badge ${s.enabled&&!s.killed?'good':'warn'}">${s.killed?'KILLED':s.enabled?'RUNNING':'OFF'}</span></div>
  <div class="metric-grid"><div class="metric-card"><span>Simulation auto-execution</span><strong>${s.simulation_execution?'ON':'OFF'}</strong></div><div class="metric-card"><span>Interval</span><strong>${Math.round(Number(s.interval_seconds||0)/60)} min</strong></div><div class="metric-card"><span>Last scan</span><strong>${dt(s.last_scan_at)}</strong></div><div class="metric-card"><span>Next scan</span><strong>${dt(s.next_scan_at)}</strong></div><div class="metric-card"><span>Open positions</span><strong>${portfolio.positions?.length||0}</strong></div><div class="metric-card"><span>30d realized P&L</span><strong>${money(ps.realized_pnl)}</strong></div></div>
  <div class="p25-two"><section class="panel"><h3>Execution routes</h3><div class="status-list">${(s.certified_routes||[]).map(r=>`<div class="status-item"><span>${esc(r.provider)} · ${esc(r.environment)}</span><strong class="badge good">CERTIFIED${r.max_shares_per_order?` · MAX ${r.max_shares_per_order} SHARE`:''}</strong></div>`).join('')}${Object.entries(s.blocked_routes||{}).map(([p,r])=>`<div class="status-item"><span>${esc(p)}</span><strong class="badge warn">${esc(r)}</strong></div>`).join('')}</div></section>
  <section class="panel"><h3>Strategy modes</h3><div class="status-list"><div class="status-item"><span>AUTO TRADE</span><strong>${modes.AUTO_TRADE||0}</strong></div><div class="status-item"><span>SIGNALS</span><strong>${modes.SIGNALS||0}</strong></div><div class="status-item"><span>WATCH</span><strong>${modes.WATCH||0}</strong></div><div class="status-item"><span>Total configured</span><strong>${strategies?.length||0}</strong></div></div></section></div>
  <section class="panel"><div class="p21-section-head"><div><h3>Recent action outcomes</h3><div class="muted">Healthy safety blocks are separated from executions and broker cancellations.</div></div></div><div class="metric-grid"><div class="metric-card"><span>Executed</span><strong>${counts.EXECUTED||0}</strong></div><div class="metric-card"><span>Blocked</span><strong>${counts.BLOCK||0}</strong></div><div class="metric-card"><span>Skipped</span><strong>${(counts.SKIP||0)+(counts.SKIPPED||0)}</strong></div><div class="metric-card"><span>Cancelled</span><strong>${counts.CANCELLED||0}</strong></div><div class="metric-card"><span>Submitted</span><strong>${counts.SUBMITTED||0}</strong></div></div><div class="p21-table-scroll"><table class="data-table"><thead><tr><th>Reason category</th><th>Count</th></tr></thead><tbody>${topReasons.length?topReasons.map(([r,n])=>`<tr><td>${esc(r)}</td><td>${n}</td></tr>`).join(''):'<tr><td colspan="2">No action history yet.</td></tr>'}</tbody></table></div></section>
  <section class="panel"><h3>Latest automatic scan</h3>${latest?`<div class="p21-table-scroll"><table class="data-table"><thead><tr><th>Started</th><th>Status</th><th>Symbols</th><th>Accounts</th><th>Signals</th><th>Approved</th><th>Executed</th><th>Finished</th></tr></thead><tbody><tr><td>${dt(latest.started_at)}</td><td>${esc(latest.status)}</td><td>${latest.symbols_count??'—'}</td><td>${latest.accounts_count??'—'}</td><td>${latest.signals_count??0}</td><td>${latest.approved_count??0}</td><td><strong>${latest.executed_count??0}</strong></td><td>${dt(latest.finished_at)}</td></tr></tbody></table></div>`:'<div class="empty-state">No scan history.</div>'}</section>
  <section class="panel"><div class="p21-section-head"><div><h3>Open broker positions</h3><div class="muted">Current broker-reported positions.</div></div><span class="badge good">${portfolio.positions?.length||0} OPEN</span></div><div class="p21-table-scroll"><table class="data-table"><thead><tr><th>Provider</th><th>Account</th><th>Market</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>Unrealized P&L</th></tr></thead><tbody>${portfolio.positions?.length?portfolio.positions.map(p=>`<tr><td>${esc(p.provider)}</td><td>${esc(p.account)}</td><td>${esc(p.market)}</td><td><strong>${esc(p.symbol)}</strong></td><td>${esc(p.side)}</td><td>${p.quantity}</td><td>${p.entry_price??'—'}</td><td>${money(p.unrealized_pnl)}</td></tr>`).join(''):'<tr><td colspan="8">No open broker positions.</td></tr>'}</tbody></table></div></section>
  ${state.user?.role==='ADMIN'?`<section class="panel"><h3>Engine controls</h3><p class="muted">Simulation routes only. Live Money remains separately gated.</p><div class="p21-actions"><button class="primary-button" id="p39Scan">Run monitored scan</button><button class="ghost-button" id="p39Restart">Restart engine</button><button class="danger-button" id="p39Kill">KILL SWITCH</button></div><div id="p39Status" class="p21-inline-status"></div></section>`:''}`;
  if(state.user?.role==='ADMIN'){
   document.getElementById('p39Scan').onclick=async()=>{const o=document.getElementById('p39Status');o.textContent='Running scan…';try{const r=await api('/automation/scan-now',{method:'POST'});o.textContent=`Scan ${r.status}: ${r.signals||0} signals, ${r.approved||0} approved, ${r.executed||0} executed.`;setTimeout(renderAutomation,700)}catch(e){o.textContent=e.message;o.className='p21-inline-status bad'}};
   document.getElementById('p39Restart').onclick=async()=>{await api('/automation/restart',{method:'POST'});setTimeout(renderAutomation,300)};
   document.getElementById('p39Kill').onclick=async()=>{if(!confirm('Activate the automation kill switch?'))return;await api('/automation/kill',{method:'POST'});setTimeout(renderAutomation,300)};
  }
 }catch(e){root.innerHTML=`<div class="panel empty-state"><strong>Automation Operations unavailable</strong><br>${esc(e.message)}</div>`}
}
function ensureAutomationNav(){
 const nav=document.getElementById('nav');if(!nav)return;
 let b=nav.querySelector('[data-page="Automation"]');
 if(!b){b=document.createElement('button');b.className='nav-button';b.dataset.page='Automation';b.textContent='Automation';const dash=nav.querySelector('[data-page="Dashboard"]');dash?dash.insertAdjacentElement('afterend',b):nav.prepend(b)}
 b.onclick=e=>{e?.preventDefault?.();renderAutomation()};
}
const originalBuildNav=window.buildNav;if(typeof originalBuildNav==='function')window.buildNav=function(){const r=originalBuildNav.apply(this,arguments);ensureAutomationNav();return r};
const originalRenderPage=window.renderPage;if(typeof originalRenderPage==='function')window.renderPage=function(page){if(page==='Automation')return renderAutomation();return originalRenderPage.apply(this,arguments)};
document.addEventListener('click',e=>{const b=e.target.closest?.('.nav-button');if(b?.dataset?.page!=='Automation')return;e.preventDefault();e.stopImmediatePropagation();renderAutomation()},true);
const observer=new MutationObserver(()=>ensureAutomationNav());observer.observe(document.getElementById('nav')||document.body,{childList:true,subtree:true});ensureAutomationNav();setTimeout(ensureAutomationNav,0);setTimeout(ensureAutomationNav,250);
window.AtlasPhase39={ensureAutomationNav,render:renderAutomation};
})();