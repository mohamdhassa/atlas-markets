/* ATLAS v72.6 — optimized Markets presentation with safe async render. */
(()=>{'use strict';
const E=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const H=v=>String(v||'—').replaceAll('_',' ').replaceAll('|',' · ');
const B=(v,k='')=>`<span class="badge ${k}">${E(v)}</span>`;
const cache=new Map(),TTL=12000,rawApi=api;
async function cached(path){const n=Date.now(),hit=cache.get(path);if(hit&&n-hit.at<TTL)return hit.value;const value=await rawApi(path);cache.set(path,{at:n,value});return value}
const css=document.createElement('style');css.textContent=`
.v726-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:14px}.v726-summary{display:flex;gap:8px;flex-wrap:wrap}.v726-toolbar{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:12px}.v726-toolbar select,.v726-toolbar input{width:auto;min-width:145px}.v726-table{max-height:610px;overflow:auto}.v726-table thead th{position:sticky;top:0;z-index:2;background:#102033}.v726-symbol{display:grid;gap:2px}.v726-symbol small{color:var(--muted);font-size:.7rem}.v726-reason{max-width:360px;color:var(--muted);font-size:.78rem}.v726-open{color:#72e7b7}.v726-block{color:var(--warn)}
@media(max-width:700px){.v726-head{display:block}.v726-summary{margin-top:10px}.v726-toolbar>*{flex:1 1 140px}}
`;document.head.appendChild(css);
async function markets(){
 content.innerHTML='<div class="panel empty-state">Loading market workspace…</div>';
 try{
  const [m,p]=await Promise.all([cached('/strategies/symbols/universe/market-monitor'),cached('/portfolio')]);
  if(String(document.getElementById('pageTitle')?.textContent)!=='Markets')return;
  const held=new Set((p.positions||[]).map(x=>`${String(x.provider).toUpperCase()}:${String(x.symbol).toUpperCase()}`)),items=m.items||[],configured=items.filter(x=>x.configured).length,research=items.length-configured,open=items.filter(x=>held.has(`${String(x.provider).toUpperCase()}:${String(x.symbol).toUpperCase()}`)).length;
  content.innerHTML=`<div class="v726-head"><div><p class="eyebrow">UNIFIED MARKET</p><h3>Market Monitor</h3><p class="muted">One ATLAS universe across Bybit Testnet and IBKR Paper. Decisions and execution gates are shown separately.</p></div><div class="v726-summary">${B(items.length+' MONITORED',true)}${B(open+' OPEN',open?'good':'')}${B(configured+' CONFIGURED',true)}${B(research+' RESEARCH')}</div></div><div class="panel"><div class="v726-toolbar"><select id="v726Provider"><option value="ALL">All providers</option><option>BYBIT</option><option>IBKR</option></select><select id="v726State"><option value="ALL">All instruments</option><option value="OPEN">Open positions</option><option value="CONFIGURED">Configured</option><option value="RESEARCH">Research</option></select><input id="v726Search" placeholder="Search symbol"></div><div class="table-wrap v726-table"><table class="data-table"><thead><tr><th>Instrument</th><th>Provider</th><th>Mode</th><th>Decision</th><th>Execution</th><th>Reason</th></tr></thead><tbody id="v726Rows">${items.map(x=>{const isOpen=held.has(`${String(x.provider).toUpperCase()}:${String(x.symbol).toUpperCase()}`),gate=isOpen?'OPEN':String(x.execution_gate||'NOT_CONFIGURED'),decision=x.analysis_status==='NOT_SCANNED'?'NOT SCANNED':String(x.decision||'—'),reason=isOpen?'Position held / managed':((x.gate_reasons||[]).join(' · ')||x.signal_reason||'—');return `<tr data-provider="${E(x.provider)}" data-state="${isOpen?'OPEN':x.configured?'CONFIGURED':'RESEARCH'}" data-symbol="${E(x.symbol)}"><td><div class="v726-symbol"><strong>${E(x.symbol)}</strong><small>${E(x.market)}</small></div></td><td>${B(x.provider,'good')}</td><td>${E(x.mode)}</td><td><strong>${E(decision)}</strong></td><td class="${gate==='OPEN'?'v726-open':gate==='BLOCK'?'v726-block':''}"><strong>${E(H(gate))}</strong></td><td class="v726-reason">${E(H(reason))}</td></tr>`}).join('')}</tbody></table></div></div>`;
  const pr=document.getElementById('v726Provider'),st=document.getElementById('v726State'),q=document.getElementById('v726Search');
  const filter=()=>document.querySelectorAll('#v726Rows tr').forEach(r=>r.hidden=(pr.value!=='ALL'&&r.dataset.provider!==pr.value)||(st.value!=='ALL'&&r.dataset.state!==st.value)||(q.value.trim().toUpperCase()&&!r.dataset.symbol.includes(q.value.trim().toUpperCase())));
  [pr,st,q].forEach(x=>x.addEventListener('input',filter));
 }catch(e){if(String(document.getElementById('pageTitle')?.textContent)==='Markets')content.innerHTML=`<div class="panel empty-state">Market monitor unavailable: ${E(e.message)}</div>`}
}
const previous=renderPage;
renderPage=async function(page){if(page==='Markets'){setActive(page);return markets()}return previous(page)};
window.AtlasFrontendV726={markets,clearCache:()=>cache.clear()};
})();