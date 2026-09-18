/* ATLAS v72.5 — frontend-only faster navigation + refined Markets presentation. */
(()=>{'use strict';
const E=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const H=v=>String(v||'—').replaceAll('_',' ').replaceAll('|',' · ');
const B=(v,k='')=>`<span class="badge ${k}">${E(v)}</span>`;
const cache=new Map(),TTL=12000,rawApi=api;
async function cached(path){const n=Date.now(),hit=cache.get(path);if(hit&&n-hit.at<TTL)return hit.value;const value=await rawApi(path);cache.set(path,{at:n,value});return value}
const css=document.createElement('style');css.textContent=`
.v725-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:14px}.v725-summary{display:flex;gap:8px;flex-wrap:wrap}.v725-toolbar{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:12px}.v725-toolbar select,.v725-toolbar input{width:auto;min-width:145px}.v725-table{max-height:610px;overflow:auto}.v725-table thead th{position:sticky;top:0;z-index:2;background:#102033}.v725-symbol{display:grid;gap:2px}.v725-symbol small{color:var(--muted);font-size:.7rem}.v725-reason{max-width:360px;color:var(--muted);font-size:.78rem}.v725-open{color:#72e7b7}.v725-block{color:var(--warn)}
@media(max-width:700px){.v725-head{display:block}.v725-summary{margin-top:10px}.v725-toolbar>*{flex:1 1 140px}}
`;document.head.appendChild(css);
async function markets(){
 content.innerHTML='<div class="panel empty-state">Loading market workspace…</div>';
 try{
  const [m,p]=await Promise.all([cached('/strategies/symbols/universe/market-monitor'),cached('/portfolio')]);
  if(String(document.getElementById('pageTitle')?.textContent)!=='Markets')return;
  const held=new Set((p.positions||[]).map(x=>`${String(x.provider).toUpperCase()}:${String(x.symbol).toUpperCase()}`)),items=m.items||[],configured=items.filter(x=>x.configured).length,research=items.length-configured,open=items.filter(x=>held.has(`${String(x.provider).toUpperCase()}:${String(x.symbol).toUpperCase()}`)).length;
  const rows=items.map(x=>{const isOpen=held.has(`${String(x.provider).toUpperCase()}:${String(x.symbol).toUpperCase()}`),gate=isOpen?'OPEN':String(x.execution_gate||'NOT_CONFIGURED'),decision=x.analysis_status==='NOT_SCANNED'?'NOT SCANNED':String(x.decision||'—'),reason=isOpen?'Position held / managed':((x.gate_reasons||[]).join(' · ')||x.signal_reason||'—');return `<tr data-provider="${E(x.provider)}" data-state="${isOpen?'OPEN':x.configured?'CONFIGURED':'RESEARCH'}" data-symbol="${E(x.symbol)}"><td><div class="v725-symbol"><strong>${E(x.symbol)}</strong><small>${E(x.market)}</small></div></td><td>${B(x.provider,'good')}</td><td>${E(x.mode)}</td><td><strong>${E(decision)}</strong></td><td class="${gate==='OPEN'?'v725-open':gate==='BLOCK'?'v725-block':''}"><strong>${E(H(gate))}</strong></td><td class="v725-reason">${E(H(reason))}</td></tr>`}).join('');
  content.innerHTML=`<div class="v725-head"><div><p class="eyebrow">UNIFIED MARKET</p><h3>Market Monitor</h3><p class="muted">One ATLAS universe across Bybit Testnet and IBKR Paper. Scan decisions and execution gates remain separate.</p></div><div class="v725-summary">${B(items.length+' MONITORED',true)}${B(open+' OPEN',open?'good':'')}${B(configured+' CONFIGURED',true)}${B(research+' RESEARCH')}</div></div><div class="panel"><div class="v725-toolbar"><select id="v725Provider"><option value="ALL">All providers</option><option>BYBIT</option><option>IBKR</option></select><select id="v725State"><option value="ALL">All instruments</option><option value="OPEN">Open positions</option><option value="CONFIGURED">Configured</option><option value="RESEARCH">Research</option></select><input id="v725Search" placeholder="Search symbol"></div><div class="table-wrap v725-table"><table class="data-table"><thead><tr><th>Instrument</th><th>Provider</th><th>Mode</th><th>Decision</th><th>Execution</th><th>Reason</th></tr></thead><tbody id="v725Rows">${rows}</tbody></table></div></div>`;
  const filter=()=>{const pr=v725Provider.value,st=v725State.value,q=v725Search.value.trim().toUpperCase();document.querySelectorAll('#v725Rows tr').forEach(r=>r.hidden=(pr!=='ALL'&&r.dataset.provider!==pr)||(st!=='ALL'&&r.dataset.state!==st)||(q&&!r.dataset.symbol.includes(q)))};[v725Provider,v725State,v725Search].forEach(x=>x.addEventListener('input',filter));
 }catch(e){if(String(document.getElementById('pageTitle')?.textContent)==='Markets')content.innerHTML=`<div class="panel empty-state">Market monitor unavailable: ${E(e.message)}</div>`}
}
const previous=renderPage;
renderPage=async function(page){
 setActive(page);
 if(page==='Markets')return markets();
 return previous(page);
};
window.AtlasFrontendV725={markets,clearCache:()=>cache.clear()};
})();