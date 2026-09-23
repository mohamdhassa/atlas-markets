/* ATLAS v75 — richer read-only Live Activity Log with broker/account context. */
(()=>{'use strict';
const E=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const D=v=>v?new Date(v).toLocaleString():'—';
const N=(v,d=4)=>v==null||!Number.isFinite(Number(v))?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:d});
const M=v=>v==null||!Number.isFinite(Number(v))?'—':'$'+Number(v).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
const B=(v,k='')=>`<span class="badge ${k}">${E(v)}</span>`;
const css=document.createElement('style');css.textContent=`
.v75-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.v75-tools{display:flex;gap:8px;flex-wrap:wrap}.v75-tools select,.v75-tools input{width:auto;min-width:145px}.v75-log{max-height:560px;overflow:auto}.v75-log thead th{position:sticky;top:0;z-index:2;background:#102033}.v75-sub{display:block;color:var(--muted);font-size:.72rem;margin-top:3px}.v75-reason{min-width:220px;max-width:380px;white-space:normal}.v75-id{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.72rem;max-width:180px;overflow:hidden;text-overflow:ellipsis}.v75-live-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:currentColor;margin-right:5px}
@media(max-width:720px){.v75-head{display:block}.v75-tools{margin-top:10px}.v75-tools>*{flex:1 1 140px}}
`;document.head.appendChild(css);
function brokerName(x){const p=String(x.broker||x.provider||'').toUpperCase();return p==='IBKR'?'Interactive Brokers':p==='BYBIT'?'Bybit':p==='MT5'?'MetaTrader 5':p||'—'}
function statusKind(v){return String(v).toUpperCase()==='EXECUTED'?'good':['BLOCK','BLOCKED','RISK_BLOCKED','PROVIDER_UNAVAILABLE'].includes(String(v).toUpperCase())?'warn':''}
function activityRows(actions,trades){
 const fills=(trades||[]).map(x=>({kind:'FILL',created_at:x.created_at||x.executed_at,provider:x.provider,broker:x.provider,account_label:x.account_label||x.account,environment:x.environment,market:x.market,symbol:x.symbol,side:x.side,status:'EXECUTED',reason:x.exit_reason||'BROKER_FILL',quantity:x.quantity,price:x.execution_price,commission:x.commission,pnl:x.pnl,pnl_available:x.pnl_available,broker_order_id:x.broker_order_id,broker_position_id:x.broker_position_id}));
 const decisions=(actions||[]).map(x=>({...x,kind:'DECISION'}));
 return decisions.concat(fills).sort((a,b)=>new Date(b.created_at||0)-new Date(a.created_at||0)).slice(0,250);
}
function row(x){const price=x.price??x.execution_price,notional=price!=null&&x.quantity!=null?Number(price)*Number(x.quantity):null,filled=x.kind==='FILL'||String(x.status||'').toUpperCase()==='EXECUTED',noFill=!filled&&price==null;const na=noFill?'N/A · no broker fill':'—';return `<tr data-provider="${E(String(x.provider||'').toUpperCase())}" data-status="${E(String(x.status||'').toUpperCase())}" data-symbol="${E(String(x.symbol||'').toUpperCase())}"><td>${D(x.created_at)}<span class="v75-sub">${E(x.kind)}</span></td><td><strong>${E(brokerName(x))}</strong><span class="v75-sub">${E(x.account_label||'Account not labelled')} · ${E(x.environment||'—')}</span></td><td><strong>${E(x.symbol)}</strong><span class="v75-sub">${E(x.market||'—')}</span></td><td>${E(x.side||'HOLD')}</td><td>${B(x.status,statusKind(x.status))}<span class="v75-sub">${E(x.connection_status||'')}</span></td><td class="v75-reason">${E(x.reason||'—')}<span class="v75-sub">${E(x.sizing_policy||'')}</span></td><td>${x.quantity==null?(noFill?'N/A':N(x.quantity)):N(x.quantity)}</td><td>${price==null?E(na):M(price)}<span class="v75-sub">${notional==null?'':('Notional '+M(notional))}</span></td><td>${x.commission==null?E(na):M(x.commission)}</td><td>${x.pnl_available===false?'N/A':(x.pnl==null?E(na):M(x.pnl))}</td><td class="v75-id" title="${E(x.broker_order_id||'')}">${x.broker_order_id?E(x.broker_order_id):E(na)}<span class="v75-sub">${x.broker_position_id?('Pos '+E(x.broker_position_id)):''}</span></td><td class="v75-id" title="${E(x.scan_id||'')}">${E(x.scan_id||'—')}</td></tr>`}
async function liveActivity(){
 const host=document.getElementById('v75Activity');if(!host)return;
 try{
  const [actions,perf]=await Promise.all([api('/automation/actions?limit=250'),api('/performance/broker-native?days=30').catch(()=>({trades:[]}))]);
  if(!document.getElementById('v75Activity'))return;
  const rows=activityRows(actions,perf.trades||[]);
  host.innerHTML=`<div class="v75-head"><div><p class="eyebrow">LIVE ACTIVITY LOG</p><h3>Decisions, executions and broker fills</h3><p class="muted">Broker/account, environment, market, decision, execution result, sizing, fill economics and trace IDs in one read-only operational log.</p></div><div>${B('<span class="v75-live-dot"></span>LIVE','good')}</div></div><div class="v75-tools"><select id="v75Provider"><option value="ALL">All brokers</option>${[...new Set(rows.map(x=>String(x.provider||'').toUpperCase()).filter(Boolean))].map(x=>`<option>${E(x)}</option>`).join('')}</select><select id="v75Status"><option value="ALL">All statuses</option>${[...new Set(rows.map(x=>String(x.status||'').toUpperCase()).filter(Boolean))].map(x=>`<option>${E(x)}</option>`).join('')}</select><input id="v75Search" placeholder="Search symbol"></div><div class="table-wrap v75-log"><table class="data-table"><thead><tr><th>Time</th><th>Broker / Account</th><th>Instrument</th><th>Action</th><th>Status</th><th>Reason / Sizing</th><th>Qty</th><th>Price / Notional</th><th>Fee</th><th>Realized P&L</th><th>Broker IDs</th><th>Scan ID</th></tr></thead><tbody id="v75Rows">${rows.map(row).join('')||'<tr><td colspan="12">No activity records.</td></tr>'}</tbody></table></div>`;
  const p=document.getElementById('v75Provider'),s=document.getElementById('v75Status'),q=document.getElementById('v75Search');
  const filter=()=>document.querySelectorAll('#v75Rows tr[data-provider]').forEach(r=>r.hidden=(p.value!=='ALL'&&r.dataset.provider!==p.value)||(s.value!=='ALL'&&r.dataset.status!==s.value)||(q.value.trim().toUpperCase()&&!r.dataset.symbol.includes(q.value.trim().toUpperCase())));
  [p,s,q].forEach(x=>x&&x.addEventListener('input',filter));
 }catch(e){host.innerHTML=`<div class="empty-state">Live Activity Log unavailable: ${E(e.message)}</div>`}
}
function attach(){
 const title=String(document.getElementById('pageTitle')?.textContent||'');
 if(!['Dashboard','Operations','Portfolio'].includes(title))return;
 if(document.getElementById('v75Activity'))return;
 const section=document.createElement('section');section.className='panel';section.id='v75Activity';section.innerHTML='<div class="empty-state">Loading Live Activity Log…</div>';document.getElementById('content')?.appendChild(section);liveActivity();
}
const previous=renderPage;renderPage=async function(page){const r=await previous(page);if(['Dashboard','Operations','Portfolio'].includes(page))setTimeout(attach,0);return r};
window.AtlasLiveActivityV75={attach,refresh:liveActivity};
})();
