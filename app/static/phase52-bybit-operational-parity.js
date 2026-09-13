(()=>{
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dt=v=>v?new Date(v).toLocaleString():'—';
let busy=false;
async function reconcile(profileId,button){
  if(state.user?.role!=='ADMIN')return;
  if(!confirm('Reconcile Bybit Spot certification from filled ATLAS certification orders? No new order will be placed.'))return;
  button.disabled=true;button.textContent='Reconciling…';
  try{await api(`/accounts/${profileId}/reconcile-bybit-spot-certification`,{method:'POST'});await decorate(true)}
  catch(e){alert(`Bybit certification reconciliation failed: ${e.message}`)}
  finally{button.disabled=false;button.textContent='Reconcile certification'}
}
function inventoryRows(rows){
  if(!rows?.length)return '<tr><td colspan="5">No ATLAS-managed Spot inventory yet. Manual/pre-existing holdings are protected and not counted as managed inventory.</td></tr>';
  return rows.map(r=>`<tr><td><strong>${esc(r.symbol)}</strong></td><td>${Number(r.managed_quantity||0).toFixed(8)}</td><td>${r.average_entry_price?Number(r.average_entry_price).toFixed(4):'—'}</td><td>${Number(r.cumulative_bought_quantity||0).toFixed(8)}</td><td>${Number(r.cumulative_sold_quantity||0).toFixed(8)}</td></tr>`).join('');
}
function actionRows(rows){
  if(!rows?.length)return '<tr><td colspan="7">No Bybit automation actions recorded yet.</td></tr>';
  return rows.slice(0,20).map(a=>`<tr><td>${dt(a.created_at)}</td><td><strong>${esc(a.symbol)}</strong></td><td>${esc(a.side)}</td><td><span class="badge ${a.status==='EXECUTED'?'good':a.status==='BLOCK'?'warn':''}">${esc(a.status)}</span></td><td>${esc(a.reason||'—')}</td><td>${a.quantity??'—'}</td><td>${esc(a.broker_order_id||'—')}</td></tr>`).join('');
}
async function renderCard(account){
  let spot;
  try{spot=await api(`/accounts/${account.id}/bybit-spot-state`)}catch(e){return `<section class="panel p44-section"><h3>Bybit Spot operational state</h3><p class="error-text">${esc(e.message)}</p></section>`}
  let actions=[];try{actions=await api('/automation/actions?provider=BYBIT&limit=50')}catch(_){ }
  const env=String(spot.environment||'').toUpperCase();
  const simulation=env==='TESTNET'||env==='DEMO';
  const cert=spot.execution_certified===true;
  const ready=spot.route_ready===true;
  const reconcileButton=state.user?.role==='ADMIN'?`<button class="ghost-button" data-bybit-reconcile="${esc(account.id)}">Reconcile certification</button>`:'';
  return `<section class="panel p44-section" data-bybit-parity-card>
    <div class="page-intro"><div><p class="eyebrow">BYBIT SPOT</p><h3>${esc(account.account_label||'Bybit')}</h3><p class="muted">Live broker state, certification, ATLAS-owned inventory and automatic execution visibility.</p></div><span class="badge ${ready?'good':'warn'}">${ready?'AUTOMATION READY':'NOT READY'}</span></div>
    <div class="p44-grid">
      <div class="metric-card"><span>Environment</span><strong>${esc(env)}</strong></div>
      <div class="metric-card"><span>Product</span><strong>SPOT</strong></div>
      <div class="metric-card"><span>Connection</span><strong>${esc(account.last_connection_status||'UNKNOWN')}</strong></div>
      <div class="metric-card"><span>Certification</span><strong>${cert?'CERTIFIED':'PENDING'}</strong></div>
      <div class="metric-card"><span>BUY certification</span><strong>${spot.buy_certified?'PASSED':'PENDING'}</strong></div>
      <div class="metric-card"><span>SELL certification</span><strong>${spot.sell_certified?'PASSED':'PENDING'}</strong></div>
      <div class="metric-card"><span>Automatic route</span><strong>${spot.automatic_execution_enabled?'ENABLED':'BLOCKED'}</strong></div>
      <div class="metric-card"><span>Live money</span><strong>${spot.live_money_armed?'ARMED':'NOT ARMED'}</strong></div>
      <div class="metric-card"><span>Managed positions</span><strong>${spot.managed_inventory_count??0}</strong></div>
      <div class="metric-card"><span>Spot open orders</span><strong>${spot.spot_open_orders_count??0}</strong></div>
    </div>
    <div class="p21-actions">${reconcileButton}</div>
    <p class="muted">${simulation?'TESTNET/DEMO automation may execute only after certification and readiness checks pass.':'LIVE automatic execution is not certified by this route.'} Manual/pre-existing holdings are not treated as ATLAS-owned inventory.</p>
    <h3>ATLAS-managed Spot inventory</h3>
    <div class="p44-table-wrap"><table class="data-table"><thead><tr><th>Symbol</th><th>Managed qty</th><th>Avg entry</th><th>Total bought</th><th>Total sold</th></tr></thead><tbody>${inventoryRows(spot.managed_inventory)}</tbody></table></div>
    <h3>Recent Bybit automatic decisions & actions</h3>
    <div class="p44-table-wrap"><table class="data-table"><thead><tr><th>Time</th><th>Symbol</th><th>Side</th><th>Status</th><th>Reason</th><th>Qty</th><th>Broker order</th></tr></thead><tbody>${actionRows(actions)}</tbody></table></div>
  </section>`;
}
async function decorate(force=false){
  if(busy)return;
  const title=document.getElementById('pageTitle');const root=document.getElementById('content');
  if(!root||title?.textContent!=='Operations')return;
  if(root.querySelector('[data-bybit-parity-root]')&&!force)return;
  busy=true;
  try{
    root.querySelector('[data-bybit-parity-root]')?.remove();
    const accounts=await api('/accounts');const bybit=accounts.filter(a=>String(a.provider).toUpperCase()==='BYBIT');
    const wrap=document.createElement('div');wrap.dataset.bybitParityRoot='1';
    if(!bybit.length)wrap.innerHTML='<section class="panel p44-section"><h3>Bybit Spot operational parity</h3><p class="muted">No Bybit account is configured.</p></section>';
    else wrap.innerHTML=(await Promise.all(bybit.map(renderCard))).join('');
    root.appendChild(wrap);
    wrap.querySelectorAll('[data-bybit-reconcile]').forEach(btn=>btn.addEventListener('click',()=>reconcile(btn.dataset.bybitReconcile,btn)));
  }catch(e){
    const wrap=document.createElement('section');wrap.className='panel p44-section';wrap.dataset.bybitParityRoot='1';wrap.innerHTML=`<h3>Bybit Spot operational parity</h3><p class="error-text">${esc(e.message)}</p>`;root.appendChild(wrap);
  }finally{busy=false}
}
let timer;
const obs=new MutationObserver(()=>{clearTimeout(timer);timer=setTimeout(()=>decorate(false),80)});
document.addEventListener('DOMContentLoaded',()=>{const root=document.getElementById('content');if(root)obs.observe(root,{childList:true,subtree:false});setTimeout(()=>decorate(false),300)});
window.AtlasBybitOperationalParity={refresh:()=>decorate(true)};
})();
