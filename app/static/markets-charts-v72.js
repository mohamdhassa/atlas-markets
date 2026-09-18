/* ATLAS v72 — canonical last-mile Markets/Charts UI + route paint guard. */
(()=>{'use strict';
const H=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const N=(v,d=2)=>v==null||!Number.isFinite(Number(v))?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:d});
const badge=(v,good=false)=>`<span class="badge ${good?'good':'warn'}">${H(v)}</span>`;
const style=document.createElement('style');style.textContent=`
#content.atlas-route-loading{visibility:hidden}
.v72-toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.v72-toolbar select,.v72-toolbar input{min-width:130px}
.v72-market-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}.v72-market-card{cursor:pointer}
.v72-market-card:hover{transform:translateY(-1px)}.v72-chart{min-height:330px}.v72-chart svg{width:100%;height:330px}
`;document.head.appendChild(style);

function line(candles){const a=(candles||[]).map(x=>Number(x.close)).filter(Number.isFinite);if(a.length<2)return '<div class="empty-state">Chart unavailable.</div>';const w=1000,h=330,p=24,lo=Math.min(...a),hi=Math.max(...a),sp=hi-lo||1,pts=a.map((v,i)=>`${p+i/(a.length-1)*(w-p*2)},${h-p-((v-lo)/sp)*(h-p*2)}`).join(' ');return `<svg viewBox="0 0 ${w} ${h}"><polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="2.5" vector-effect="non-scaling-stroke"/></svg>`}
async function markets(){
 content.innerHTML='<div class="panel empty-state">Loading unified market monitor…</div>';
 try{
  const [m,p]=await Promise.all([api('/strategies/symbols/universe/market-monitor'),api('/portfolio')]);
  const held=new Set((p.positions||[]).map(x=>`${x.provider}:${String(x.symbol).toUpperCase()}`));
  const items=m.items||[];
  content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">UNIFIED MARKET</p><h3>Bybit + IBKR market monitor</h3><p class="muted">One ATLAS universe · provider is routing metadata, not a separate intelligence system.</p></div>${badge(items.length+' INSTRUMENTS',true)}</div>
  <div class="panel"><div class="v72-toolbar"><select id="v72Provider"><option value="ALL">All providers</option><option>BYBIT</option><option>IBKR</option></select><select id="v72State"><option value="ALL">All states</option><option value="OPEN">Open positions</option><option value="CONFIGURED">Configured</option><option value="RESEARCH">Research</option></select><input id="v72Search" placeholder="Search symbol"></div></div>
  <div id="v72MarketGrid" class="v72-market-grid">${items.map(x=>{const open=held.has(`${x.provider}:${String(x.symbol).toUpperCase()}`);return `<article class="panel v72-market-card" data-provider="${H(x.provider)}" data-state="${open?'OPEN':x.configured?'CONFIGURED':'RESEARCH'}" data-symbol="${H(x.symbol)}"><div class="action-row"><strong style="margin-right:auto">${H(x.symbol)}</strong>${badge(x.provider,true)}</div><div class="account-meta"><span>Market</span><strong>${H(x.market)}</strong><span>Mode</span><strong>${H(x.mode)}</strong><span>Decision</span><strong>${H(x.decision||'NOT SCANNED')}</strong><span>Analysis</span><strong>${H(x.analysis_status)}</strong><span>Execution gate</span><strong>${H(open?'OPEN':x.execution_gate)}</strong><span>Reason</span><strong>${H((x.gate_reasons||[]).join(' · ')||x.signal_reason)}</strong></div></article>`}).join('')}</div>`;
  const filter=()=>{const pr=document.getElementById('v72Provider').value,st=document.getElementById('v72State').value,q=document.getElementById('v72Search').value.trim().toUpperCase();document.querySelectorAll('.v72-market-card').forEach(c=>c.hidden=(pr!=='ALL'&&c.dataset.provider!==pr)||(st!=='ALL'&&c.dataset.state!==st)||(q&&!c.dataset.symbol.includes(q)))};['v72Provider','v72State','v72Search'].forEach(id=>document.getElementById(id).addEventListener('input',filter));
 }catch(e){content.innerHTML=`<div class="panel empty-state">Market monitor unavailable: ${H(e.message)}</div>`}
}
async function charts(){
 content.innerHTML='<div class="panel empty-state">Loading unified chart workspace…</div>';
 try{
  const [m,p]=await Promise.all([api('/strategies/symbols/universe/market-monitor'),api('/portfolio')]),profiles=new Map((p.accounts||[]).map(a=>[String(a.provider),a.id])),items=(m.items||[]).filter(x=>x.configured&&profiles.has(String(x.provider)));
  content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">UNIFIED CHARTS</p><h3>ATLAS market chart workspace</h3><p class="muted">Configured Bybit + IBKR instruments with one chart workflow.</p></div><div class="v72-toolbar"><select id="v72Symbol">${items.map(x=>`<option value="${H(x.symbol)}" data-provider="${H(x.provider)}">${H(x.symbol)} · ${H(x.provider)}</option>`).join('')}</select><select id="v72Tf"><option>5m</option><option>15m</option><option>1h</option><option>4h</option><option>1d</option></select></div></div><section class="panel"><div id="v72Chart" class="v72-chart">Loading…</div><div id="v72ChartFacts" class="metric-grid"></div></section>`;
  const load=async()=>{const sel=document.getElementById('v72Symbol'),opt=sel.options[sel.selectedIndex],provider=opt.dataset.provider,symbol=sel.value,profile=profiles.get(provider),tf=document.getElementById('v72Tf').value,host=document.getElementById('v72Chart');host.innerHTML='Loading chart…';try{const d=await api(`/portfolio-market/${encodeURIComponent(profile)}/${encodeURIComponent(symbol)}/candles?timeframe=${encodeURIComponent(tf)}&limit=160`),cs=d.candles||d.list||[],last=cs.at(-1)||{},u=(m.items||[]).find(x=>x.symbol===symbol&&x.provider===provider)||{};host.innerHTML=line(cs);document.getElementById('v72ChartFacts').innerHTML=`<div class="metric-card"><span>Provider</span><strong>${H(provider)}</strong></div><div class="metric-card"><span>Last close</span><strong>${N(last.close,4)}</strong></div><div class="metric-card"><span>Decision</span><strong>${H(u.decision||'NOT SCANNED')}</strong></div><div class="metric-card"><span>Gate</span><strong>${H(u.execution_gate)}</strong></div>`}catch(e){host.innerHTML=`<div class="empty-state">Chart unavailable: ${H(e.message)}</div>`}};document.getElementById('v72Symbol').onchange=load;document.getElementById('v72Tf').onchange=load;await load();
 }catch(e){content.innerHTML=`<div class="panel empty-state">Charts unavailable: ${H(e.message)}</div>`}
}
const previous=renderPage;
renderPage=async function(page){
 const root=document.getElementById('content');root.classList.add('atlas-route-loading');
 try{setActive(page);if(page==='Markets')await markets();else if(page==='Charts')await charts();else await previous(page)}
 finally{requestAnimationFrame(()=>root.classList.remove('atlas-route-loading'))}
};
window.AtlasMarketsChartsV72={markets,charts};
})();