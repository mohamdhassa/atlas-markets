/* ATLAS MARKETS consolidated frontend core.
   Owns canonical navigation/routing and critical Operations rendering without
   phase-by-phase wrappers or MutationObservers. app.js remains the compatibility
   layer while its pages are migrated into this core. */
(()=>{
'use strict';
const USER=['Dashboard','Markets','Charts','Signals','Positions','Orders','Performance','Accounts'];
const ADMIN=['Operations','Users','Strategy','Risk','Integrations','System'];
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dt=v=>v?new Date(v).toLocaleString():'—';
const badge=(value,good=false)=>`<span class="badge ${good?'good':'warn'}">${esc(value)}</span>`;
function coreBuildNav(){
 const navEl=document.getElementById('nav'); if(!navEl||!state.user)return;
 navEl.innerHTML='';
 const add=(label,pages)=>{const s=document.createElement('div');s.className='nav-separator';s.textContent=label;navEl.appendChild(s);pages.forEach(page=>{const b=document.createElement('button');b.className='nav-button';b.dataset.page=page;b.textContent=page;b.addEventListener('click',()=>renderPage(page));navEl.appendChild(b)})};
 add(state.user.role==='ADMIN'?'WORKSPACE':'MY WORKSPACE',USER);
 if(state.user.role==='ADMIN')add('CONTROL CENTER',ADMIN);
}
async function operations(){
 const root=document.getElementById('content'); if(!root)return;
 root.innerHTML='<div class="panel empty-state">Loading live operations…</div>';
 try{
  const [accounts,auto,actions]=await Promise.all([api('/accounts'),api('/automation/state'),api('/automation/actions?limit=100')]);
  const bybit=accounts.filter(a=>String(a.provider).toUpperCase()==='BYBIT');
  const ibkr=accounts.filter(a=>String(a.provider).toUpperCase()==='IBKR');
  const cards=[];
  for(const a of bybit){let spot=null;try{spot=await api(`/accounts/${a.id}/bybit-spot-state`)}catch(e){spot={error:e.message}}cards.push(bybitCard(a,spot,actions.filter(x=>String(x.provider).toUpperCase()==='BYBIT')))}
  let portfolio={positions:[],errors:[]};try{portfolio=await api('/portfolio')}catch(_){ }
  for(const a of ibkr){cards.push(ibkrCard(a,actions.filter(x=>String(x.provider).toUpperCase()==='IBKR'),(portfolio.positions||[]).filter(x=>String(x.profile_id)===String(a.id))))}
  root.innerHTML=`<div class="page-intro"><div><p class="eyebrow">OPERATIONS</p><h3>Execution control center</h3><p class="muted">Provider readiness, automation state, certification and recent decisions.</p></div>${badge(auto.killed?'KILLED':auto.enabled?'RUNNING':'STOPPED',auto.enabled&&!auto.killed)}</div>
  <div class="metric-grid"><div class="metric-card"><span>Automation</span><strong>${auto.enabled&&!auto.killed?'RUNNING':'STOPPED'}</strong></div><div class="metric-card"><span>Interval</span><strong>${Number(auto.interval_seconds||0)}s</strong></div><div class="metric-card"><span>Accounts</span><strong>${accounts.length}</strong></div><div class="metric-card"><span>Recent actions</span><strong>${actions.length}</strong></div></div>
  ${cards.join('')||'<section class="panel"><h3>Execution providers</h3><p class="muted">No Bybit or IBKR execution profile configured.</p></section>'}
  <section class="panel atlas-section"><h3>All provider accounts</h3><div class="table-wrap"><table class="data-table"><thead><tr><th>Provider</th><th>Account</th><th>Environment</th><th>Connection</th><th>Equity</th><th>Execution</th></tr></thead><tbody>${accounts.map(a=>`<tr><td><strong>${esc(a.provider)}</strong></td><td>${esc(a.account_label)}</td><td>${esc(a.environment)}</td><td>${badge(a.last_connection_status||'UNKNOWN',a.last_connection_status==='CONNECTED')}</td><td>${a.equity_usd==null?'—':Number(a.equity_usd).toFixed(2)}</td><td>${a.execution_certified?badge('CERTIFIED',true):badge('GATED')}</td></tr>`).join('')}</tbody></table></div></section>`;
  bindOperations();
 }catch(e){root.innerHTML=`<div class="panel"><h3>Operations unavailable</h3><p class="error-text">${esc(e.message)}</p></div>`}
}
function bybitCard(a,s,actions){
 if(s?.error)return `<section class="panel atlas-section"><h3>Bybit Spot · ${esc(a.account_label)}</h3><p class="error-text">${esc(s.error)}</p></section>`;
 const sim=['TESTNET','DEMO'].includes(String(s.environment).toUpperCase());
 const admin=state.user?.role==='ADMIN';
 const certControls=admin&&sim&&!s.execution_certified?`<div class="atlas-cert"><div><label>Certification symbol<input data-cert-symbol value="BTCUSDT"></label><label>Base quantity<input data-cert-qty type="number" min="0.00001" max="0.001" step="0.00001" value="0.0001"></label></div><div class="action-row"><button class="primary-button" data-cert-side="BUY" data-profile="${esc(a.id)}">Certify BUY</button><button class="ghost-button atlas-inline" data-cert-side="SELL" data-profile="${esc(a.id)}">Certify SELL</button><button class="ghost-button atlas-inline" data-reconcile="${esc(a.id)}">Reconcile</button></div><p class="muted">Simulation only. Quantity is base-coin quantity. ATLAS verifies provider fill and wallet balance movement before recording certification.</p></div>`:'';
 return `<section class="panel atlas-section"><div class="page-intro"><div><p class="eyebrow">BYBIT SPOT</p><h3>${esc(a.account_label)}</h3></div>${badge(s.route_ready?'AUTOMATION READY':'GATED',s.route_ready)}</div><div class="metric-grid"><div class="metric-card"><span>Environment</span><strong>${esc(s.environment)}</strong></div><div class="metric-card"><span>BUY</span><strong>${s.buy_certified?'PASSED':'PENDING'}</strong></div><div class="metric-card"><span>SELL</span><strong>${s.sell_certified?'PASSED':'PENDING'}</strong></div><div class="metric-card"><span>Route</span><strong>${s.automatic_execution_enabled?'ENABLED':'BLOCKED'}</strong></div></div>${certControls}<h3>Recent Bybit decisions</h3><div class="table-wrap atlas-table"><table class="data-table"><thead><tr><th>Time</th><th>Symbol</th><th>Side</th><th>Status</th><th>Reason</th><th>Qty</th></tr></thead><tbody>${actions.slice(0,20).map(x=>`<tr><td>${dt(x.created_at)}</td><td>${esc(x.symbol)}</td><td>${esc(x.side)}</td><td>${esc(x.status)}</td><td>${esc(x.reason)}</td><td>${x.quantity??'—'}</td></tr>`).join('')||'<tr><td colspan="6">No actions yet.</td></tr>'}</tbody></table></div></section>`;
}
function ibkrCard(a,actions,positions){
 const connected=String(a.last_connection_status||'').toUpperCase()==='CONNECTED';
 const paper=String(a.environment||'').toUpperCase()==='PAPER';
 const recent=actions.slice(0,20);
 return `<section class="panel atlas-section"><div class="page-intro"><div><p class="eyebrow">IBKR</p><h3>${esc(a.account_label)}</h3><p class="muted">Paper account readiness, broker-held positions and recent ATLAS decisions.</p></div>${badge(connected&&paper?'PAPER READY':connected?'CONNECTED':'GATED',connected)}</div><div class="metric-grid"><div class="metric-card"><span>Environment</span><strong>${esc(a.environment)}</strong></div><div class="metric-card"><span>Connection</span><strong>${esc(a.last_connection_status||'UNKNOWN')}</strong></div><div class="metric-card"><span>Open positions</span><strong>${positions.length}</strong></div><div class="metric-card"><span>Route</span><strong>${connected&&paper?'PAPER':'GATED'}</strong></div></div><h3>Current IBKR positions</h3><div class="table-wrap atlas-table"><table class="data-table"><thead><tr><th>Symbol</th><th>Market</th><th>Side</th><th>Qty</th><th>Avg entry</th></tr></thead><tbody>${positions.map(x=>`<tr><td><strong>${esc(x.symbol)}</strong></td><td>${esc(x.market)}</td><td>${esc(x.side)}</td><td>${x.quantity??'—'}</td><td>${x.entry_price==null?'—':Number(x.entry_price).toFixed(2)}</td></tr>`).join('')||'<tr><td colspan="5">No current IBKR positions.</td></tr>'}</tbody></table></div><h3>Recent IBKR decisions</h3><div class="table-wrap atlas-table"><table class="data-table"><thead><tr><th>Time</th><th>Symbol</th><th>Side</th><th>Status</th><th>Reason</th><th>Qty</th></tr></thead><tbody>${recent.map(x=>`<tr><td>${dt(x.created_at)}</td><td>${esc(x.symbol)}</td><td>${esc(x.side)}</td><td>${esc(x.status)}</td><td>${esc(x.reason)}</td><td>${x.quantity??'—'}</td></tr>`).join('')||'<tr><td colspan="6">No recent IBKR actions.</td></tr>'}</tbody></table></div></section>`;
}
function bindOperations(){
 document.querySelectorAll('[data-cert-side]').forEach(btn=>btn.addEventListener('click',async()=>{const card=btn.closest('.atlas-section'),symbol=card.querySelector('[data-cert-symbol]').value.trim().toUpperCase(),quantity=Number(card.querySelector('[data-cert-qty]').value),side=btn.dataset.certSide;if(!symbol||!Number.isFinite(quantity)||quantity<0.00001||quantity>0.001)return alert('Enter a base quantity from 0.00001 to 0.001.');if(!confirm(`Place controlled ${side} certification order on the configured Bybit TESTNET/DEMO account?`))return;btn.disabled=true;try{const r=await api(`/accounts/${btn.dataset.profile}/certify-bybit-test-order`,{method:'POST',body:JSON.stringify({symbol,side,quantity})});alert(r.certification_pass?`${side} certification passed.`:`${side} certification did not pass. Check provider response.`);await operations()}catch(e){alert(`Certification failed: ${e.message}`)}finally{btn.disabled=false}}));
 document.querySelectorAll('[data-reconcile]').forEach(btn=>btn.addEventListener('click',async()=>{if(!confirm('Reconcile certification from existing filled ATLAS certification orders?'))return;btn.disabled=true;try{await api(`/accounts/${btn.dataset.reconcile}/reconcile-bybit-spot-certification`,{method:'POST'});await operations()}catch(e){alert(`Reconciliation failed: ${e.message}`)}finally{btn.disabled=false}}));
}
/* app.js uses global lexical bindings. Reassign those bindings directly; assigning
   window.buildNav/window.renderPage alone does not reliably replace calls made
   from showApp() and addGroup(). */
const legacyRender=renderPage;
renderPage=async function(page){if(page==='Operations'){setActive(page);return operations()}return legacyRender(page)};
buildNav=coreBuildNav;
window.AtlasCore={operations,buildNav:coreBuildNav};
if(state.user)coreBuildNav();
})();
