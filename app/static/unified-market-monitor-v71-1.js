/* ATLAS v71.1 — isolated unified Bybit + IBKR Market Monitor UI. Read-only. */
(()=>{'use strict';
const E=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const H=v=>String(v||'—').replaceAll('_',' ').replaceAll('|',' · ').toLowerCase().replace(/\b\w/g,c=>c.toUpperCase());
function heldSet(p){return new Set((p.positions||[]).map(x=>`${String(x.provider).toUpperCase()}:${String(x.symbol).toUpperCase()}`))}
async function rebuild(){
 const old=document.querySelector('.v62-universe');if(!old)return;
 try{
  const [m,p]=await Promise.all([api('/strategies/symbols/universe/market-monitor'),api('/portfolio')]);
  const held=heldSet(p),items=(m.items||[]).filter(x=>['BYBIT','IBKR'].includes(String(x.provider||'').toUpperCase()));
  const cards=items.map(x=>{const k=`${String(x.provider).toUpperCase()}:${String(x.symbol).toUpperCase()}`,isHeld=held.has(k),decision=x.analysis_status==='NOT_SCANNED'?'NOT SCANNED':String(x.decision||'NO DECISION').toUpperCase(),gate=isHeld?'OPEN':String(x.execution_gate||'NOT_CONFIGURED').toUpperCase(),reasons=isHeld?['Held at broker']:(x.gate_reasons||[]),reason=reasons.length?reasons.map(H).join(' · '):H(x.signal_reason||'No execution blocker');
   return `<article class="v641-card ${isHeld?'held':''}"><div class="v641-top"><div><small>${E(x.market)} · ${E(x.provider)}</small><h4>${E(x.symbol)}</h4></div><span class="v641-badge ${isHeld?'open':gate==='BLOCK'?'blocked':''}">${E(gate)}</span></div><div class="v641-reason"><strong>Decision: ${E(decision)}</strong><br><span>${E(reason)}</span></div><div class="v641-foot"><span>${E(x.environment||'')}</span><span>${E(x.mode||'RESEARCH')}</span></div></article>`}).join('');
  old.innerHTML=`<div class="v641-head"><div><p class="eyebrow">UNIFIED MARKET INTELLIGENCE</p><h3>Bybit + IBKR Market Monitor</h3><p class="muted">Decision is analytical. Execution gate is shown separately. Research symbols are not automatically enabled for trading.</p></div><div class="v641-counts"><span><strong>${held.size}</strong> open</span><span><strong>${items.length}</strong> monitored</span></div></div><div class="v641-grid">${cards||'<div class="empty-state">No Bybit or IBKR instruments available.</div>'}</div>`;
  old.className='panel v62-universe v641-universe v711-unified';
 }catch(e){console.warn('v71.1 unified monitor unavailable',e)}
}
function schedule(){setTimeout(rebuild,750)}
const prior=renderPage;renderPage=async page=>{const r=await prior(page);if(page==='Portfolio')schedule();return r};
window.AtlasUnifiedMarketMonitorV711={rebuild};
})();