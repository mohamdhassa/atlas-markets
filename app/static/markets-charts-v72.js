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
.profit-filters{display:flex;gap:14px;align-items:flex-end;flex-wrap:wrap}.profit-filters>label{display:grid;gap:6px;min-width:150px}.profit-picker{position:relative;min-width:230px}.profit-picker summary{cursor:pointer;padding:12px;border:1px solid var(--border,#263445);border-radius:8px}.profit-symbols{position:absolute;z-index:10;top:100%;left:0;min-width:290px;max-width:min(400px,85vw);max-height:320px;overflow:auto;background:var(--panel,#14202e);border:1px solid var(--border,#263445);padding:12px;border-radius:8px;box-shadow:0 10px 30px #0007}.profit-symbols label{display:flex;align-items:center;gap:10px;padding:8px}.profit-symbols input{width:18px;height:18px;min-width:18px}.profit-symbols small{display:block;opacity:.65;margin-top:3px}.profit-plot-scroll{overflow-x:auto}.profit-plot-scroll svg{width:100%;min-width:560px;display:block}.profit-legend{display:flex;gap:18px;flex-wrap:wrap;margin:14px 0}.profit-legend span{display:flex;align-items:center;gap:7px;font-size:13px}.profit-legend i{width:10px;height:10px;border-radius:50%;flex-shrink:0}.profit-inspect{display:grid;gap:8px;margin-top:18px}.profit-inspect input{width:100%}.profit-point{font-size:13px;line-height:1.8;min-height:30px;margin-top:10px}#profitFilterError{color:#fda4af} @media(max-width:650px){.profit-filters>*{flex:1 1 100%}.profit-symbols{position:static;min-width:0;max-width:100%;margin-top:6px}.profit-filters button{min-height:44px}.profit-legend{gap:12px}.profit-legend span{flex-wrap:wrap}}

#profitPage{display:grid;gap:18px;min-width:0}
#profitPage>.page-intro{margin-bottom:0}
#profitPage .page-intro h3{margin:0 0 8px}
#profitPage .page-intro .muted{margin:0;font-size:.9rem}
#profitPage .eyebrow{margin:0 0 10px}
#profitPage .profit-filters{display:grid;grid-template-columns:minmax(210px,1.5fr) repeat(2,minmax(145px,1fr)) auto auto;gap:12px;align-items:end}
#profitPage .profit-filters>*{min-width:0}
#profitPage .profit-filters>label{font-size:.78rem;color:var(--muted);gap:8px}
#profitPage .profit-filters input[type=date]{box-sizing:border-box;width:100%;min-width:0;height:46px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:#09131f;color:var(--text);color-scheme:dark;font:inherit}
#profitPage .profit-picker{min-width:0}
#profitPage .profit-picker summary{box-sizing:border-box;min-height:46px;display:flex;align-items:center;padding:10px 14px;background:#09131f;border-color:var(--line);font-size:.85rem}
#profitPage .profit-picker summary::before{content:'▾';margin-right:10px;color:var(--accent)}
#profitPage .profit-picker summary:focus-visible,#profitPage input:focus-visible,#profitPage button:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
#profitPage .profit-filters button{width:auto;min-height:46px;white-space:nowrap;padding:10px 16px;font-size:.85rem}
#profitPage #profitReset{color:var(--muted)}
#profitPage #profitFilterError{margin:12px 0 0;font-size:.85rem}
#profitPage #profitFilterError:empty{display:none}
#profitPage #profitFacts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:0}
#profitPage .metric-card{display:flex;flex-direction:column;align-items:flex-start;gap:10px;min-width:0;padding:20px}
#profitPage .metric-card>span{display:block;font-size:.78rem;color:var(--muted);line-height:1.4}
#profitPage .metric-card>strong{display:block;font-size:clamp(1.35rem,2vw,1.9rem);line-height:1.2;letter-spacing:-.025em;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
#profitPage .metric-card>small{display:block;font-size:.75rem;color:var(--muted);line-height:1.5}
#profitPage .profit-loss{color:#fb7185}
#profitPage .profit-gain{color:#34d399}
#profitPage #profitCoverage{font-size:.76rem;line-height:1.7;border-top:1px solid var(--line);padding-top:16px;margin-top:18px}
@media(max-width:1100px){#profitPage .profit-filters{grid-template-columns:repeat(2,minmax(0,1fr))}#profitPage .profit-picker{grid-column:1/-1}#profitPage .profit-filters button{width:100%}}
@media(max-width:650px){#profitPage{gap:14px}#profitPage #profitFacts{grid-template-columns:1fr}#profitPage .metric-card{gap:8px;padding:18px}#profitPage .profit-filters{gap:12px}#profitPage .profit-symbols{box-sizing:border-box;width:100%}#profitPage .profit-filters button{padding:10px 8px}}

#profitPage .profit-plot-scroll{min-width:0;overflow:hidden}
#profitPage .profit-plot-scroll svg{min-width:0;width:100%;height:auto}
#profitPage .profit-symbols label{min-height:44px}
#profitPage .profit-symbols input[type=checkbox]{min-height:18px;height:18px;width:18px;flex:0 0 18px}
#profitPage .profit-symbols label>span{min-width:0;overflow-wrap:anywhere}
#profitPage .profit-inspect input[type=range]{box-sizing:border-box;min-width:0;min-height:44px;margin:0}
#profitPage .profit-point{overflow-wrap:anywhere}
@media(max-width:650px){
 #profitPage .panel{padding:14px}
 #profitPage #profitFacts{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
 #profitPage .metric-card{padding:14px;gap:6px}
 #profitPage .metric-card:first-child{grid-column:1/-1}
 #profitPage .metric-card>strong{font-size:1.2rem}
 #profitPage .metric-card:first-child>strong{font-size:1.7rem}
 #profitPage .metric-card>small{font-size:.7rem}
 #profitPage .profit-filters>label{grid-column:1/-1;display:flex;flex-direction:column;min-width:0;width:100%}
 #profitPage .profit-filters input[type=date]{-webkit-appearance:none;appearance:none;display:block;box-sizing:border-box;width:100%;max-width:100%;min-width:0;inline-size:100%;min-inline-size:0;max-inline-size:100%;height:46px;min-height:46px;max-height:46px;font-size:16px;line-height:24px;padding:10px 12px;overflow:hidden}
 #profitPage .profit-filters input[type=date]::-webkit-date-and-time-value{text-align:left;min-width:0;margin:0}
 #profitPage .profit-filters input[type=date]::-webkit-datetime-edit{display:block;min-width:0;padding:0}
 #profitPage .profit-legend{gap:10px;margin:10px 0}
 #profitPage .profit-legend span{font-size:12px;max-width:100%;overflow-wrap:anywhere}
 #profitPage .profit-inspect{margin-top:12px;font-size:.8rem}
 #profitPage .page-intro h3{font-size:1.1rem}
 #profitPage .page-intro .muted{font-size:.8rem}
}
@media(max-width:400px){#profitPage .profit-filters>label{grid-column:1/-1}}

#profitPage .profit-insight-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
#profitPage .profit-insight-head h3{margin:0}
#profitPage .profit-insight-head>span{font-size:.75rem}
#profitPage .profit-insight-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}
#profitPage .profit-insight-metrics>div{display:grid;align-content:start;gap:8px;padding:14px;border:1px solid var(--line);border-radius:12px;min-width:0}
#profitPage .profit-insight-metrics span,#profitPage .profit-insight-metrics small{font-size:.75rem;color:var(--muted);line-height:1.5}
#profitPage .profit-insight-metrics strong{font-size:1.2rem;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}
#profitPage .profit-insight-lists{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px}
#profitPage .profit-insight-lists h4{font-size:.9rem;margin:10px 0}
#profitPage .profit-insight-lists ul{list-style:none;padding:0;margin:0}
#profitPage .profit-insight-lists li{display:flex;justify-content:space-between;align-items:start;gap:12px;border-bottom:1px solid var(--line);padding:12px 0;font-size:.85rem}
#profitPage .profit-insight-lists li>div{min-width:0;overflow-wrap:anywhere}
#profitPage .profit-insight-lists li>strong{white-space:nowrap}
#profitPage .profit-insight-lists small{display:block;color:var(--muted);font-size:.7rem;margin-top:5px}
#profitPage .profit-insight-note{font-size:.75rem;line-height:1.7}
@media(max-width:900px){#profitPage .profit-insight-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:650px){#profitPage .profit-insight-lists{grid-template-columns:1fr;gap:12px}#profitPage .profit-insight-metrics{gap:10px}#profitPage .profit-insight-metrics>div{padding:12px}}
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
let chartsEpoch=0,profitResizeObserver;
const profitColors=['#60a5fa','#34d399','#fbbf24','#f472b6','#a78bfa','#22d3ee','#fb923c','#e879f9'];
const profitNumber=v=>v==null||!Number.isFinite(Number(v))?'—':(Number(v)>0?'+':'')+Number(v).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
const profitDate=ms=>new Date(ms).toLocaleDateString(undefined,{timeZone:'UTC',year:'numeric',month:'short',day:'numeric'});
function profitInsights(data){
 const a=data.insights;
 if(!a)return '<p class="muted">No priced records available for performance insights.</p>';
 const drivers=a.loss_drivers_since_peak||[];
 const detail=rows=>rows.map(row=>`<li><div><strong>${H(row.symbol)}</strong><small>${H(row.provider)} · ${H(row.environment)}${row.day?' · '+H(row.day)+' UTC':''}</small></div><strong class="profit-loss">${H(profitNumber(row.pnl))}</strong></li>`).join('');
 return `<div class="profit-insight-head"><h3>What changed</h3><span class="muted">Current filters · USD / USDT</span></div>
 <p class="muted">${a.current_drawdown>0?`Recorded P&amp;L is ${H(N(a.current_drawdown))} below its ${a.peak_day?'highest daily closing level on '+H(a.peak_day)+' UTC':'zero starting baseline'}.`:'Recorded P&amp;L is at its highest daily closing level for this selection.'}</p>
 <div class="profit-insight-metrics">
 <div><span>Profit peak</span><strong>${H(profitNumber(a.peak_pnl))}</strong><small>${H(a.peak_day||'Starting baseline')}</small></div>
 <div><span>Below peak now</span><strong>${H(N(a.current_drawdown))}</strong><small>P&amp;L decrease, not account equity</small></div>
 <div><span>Largest daily drawdown</span><strong>${H(N(a.max_daily_drawdown))}</strong><small>Peak to later daily closing level</small></div>
 <div><span>Worst recorded day</span><strong>${a.worst_day?H(profitNumber(a.worst_day.pnl)):'—'}</strong><small>${a.worst_day?H(a.worst_day.date)+' UTC':'No losing day recorded'}</small></div></div>
 <div class="profit-insight-lists"><div><h4>Loss contributors after peak</h4><ul>${detail(drivers)||'<li>No negative symbol contribution after the peak day.</li>'}</ul></div>
 <div><h4>Largest loss records · selected period</h4><ul>${detail(a.largest_loss_records||[])||'<li>No losing records in this selection.</li>'}</ul></div></div>
 <p class="muted profit-insight-note">${data.partial?'Partial history: these figures use available priced records only. ':''}${H(a.basis)} Symbol contributions show where losses were recorded; they do not prove a strategy or protection failure. Open P&amp;L is excluded.</p>`;
}
function profitGraph(data, availableWidth=1000){
 const series=data.series||[];
 if(!series.length)return '<div class="empty-state">No recorded realized P&amp;L in this selection. Open positions and records without P&amp;L do not create a profit curve.</div>';
 const points=series[0].points,w=Math.max(260,Math.min(1000,availableWidth)),h=w<650?300:360,l=w<650?64:88,r=w<650?12:28,t=22,b=48;
 let lo=0,hi=0;for(const s of series)for(const p of s.points){lo=Math.min(lo,p.value);hi=Math.max(hi,p.value)}
 const margin=(hi-lo||1)*.12;lo-=margin;hi+=margin;
 const first=points[0].time,last=points.at(-1).time,span=last-first||1;
 const x=p=>l+(p.time-first)/span*(w-l-r),y=v=>t+(hi-v)/(hi-lo)*(h-t-b);
 const grid=Array.from({length:5},(_,i)=>{const v=lo+(hi-lo)*i/4,yy=y(v);return `<line x1="${l}" y1="${yy}" x2="${w-r}" y2="${yy}" stroke="currentColor" opacity=".12"/><text x="${l-10}" y="${yy+4}" text-anchor="end" fill="currentColor" font-size="12">${H(N(v))}</text>`}).join('');
 const ticks=(w<500?[0,points.length-1]:[0,Math.floor((points.length-1)/2),points.length-1]).filter((v,i,a)=>a.indexOf(v)===i).map((index,i,a)=>{const p=points[index];return `<text x="${x(p)}" y="${h-16}" text-anchor="${i===0?'start':i===a.length-1?'end':'middle'}" fill="currentColor" font-size="12">${H(profitDate(p.time))}</text>`}).join('');
 return `<div class="profit-plot-scroll"><svg id="profitSvg" viewBox="0 0 ${w} ${h}" role="img" aria-label="Cumulative recorded realized profit and loss over time. Use the date slider below for exact values.">${grid}<line x1="${l}" y1="${y(0)}" x2="${w-r}" y2="${y(0)}" stroke="currentColor" opacity=".4" stroke-dasharray="5 5"/>${series.map((s,i)=>`<polyline points="${s.points.map(p=>`${x(p)},${y(p.value)}`).join(' ')}" fill="none" stroke="${profitColors[i%profitColors.length]}" stroke-width="${i?2:3}" vector-effect="non-scaling-stroke"/>`).join('')}${ticks}</svg></div><div class="profit-legend">${series.map((s,i)=>`<span><i style="background:${profitColors[i%profitColors.length]}"></i>${H(s.label)} <strong>${H(profitNumber(s.points.at(-1).value))}</strong></span>`).join('')}</div><label class="profit-inspect">Inspect date<input id="profitDateSlider" type="range" min="0" max="${points.length-1}" value="${points.length-1}" aria-label="Inspect profit performance date"></label><div id="profitPoint" class="profit-point" role="status" aria-live="polite"></div>`;
}
async function charts(){
 const epoch=chartsEpoch;
 if(profitResizeObserver)profitResizeObserver.disconnect();
 content.innerHTML='<div class="panel empty-state">Loading profit performance…</div>';
 content.classList.remove('atlas-route-loading');
 try{
  let data=await api('/performance/profit-chart');
  if(epoch!==chartsEpoch)return;
  content.innerHTML=`<div id="profitPage"><div class="page-intro"><div><p class="eyebrow">YOUR PERFORMANCE</p><h3>Profit performance</h3><p class="muted">Cumulative recorded realized P&amp;L. Overall · all available history by default.</p></div></div><section class="panel"><form id="profitFilters" class="profit-filters"><details class="profit-picker"><summary id="profitSelectionLabel">Compare symbols · all</summary><div class="profit-symbols">${(data.symbols||[]).map(s=>`<label><input type="checkbox" name="profitSymbol" value="${H(s.key)}"><span>${H(s.symbol)}<small>${H(s.provider)} · ${H(s.environment)} · ${H(s.market)}</small></span></label>`).join('')||'<span class="muted">No recorded symbols yet.</span>'}</div></details><label>From · UTC<input id="profitStart" type="date" aria-label="Performance start date"></label><label>To · UTC<input id="profitEnd" type="date" aria-label="Performance end date"></label><button id="profitApply" class="primary-button" type="submit">Apply filters</button><button id="profitReset" class="ghost-button" type="button">Reset</button></form><p id="profitFilterError" role="alert"></p></section><div id="profitFacts" class="metric-grid"></div><section class="panel"><div class="page-intro"><div><h3 id="profitHeading">Overall performance</h3><p class="muted">Recorded realized P&amp;L · USD / USDT · UTC dates</p></div></div><div id="profitChart"></div><p id="profitCoverage" class="muted"></p></section><section id="profitInsights" class="panel" aria-label="Performance insights"></section></div>`;
  let request=0,loading=false;
  const selected=()=>Array.from(document.querySelectorAll('input[name="profitSymbol"]:checked')).map(x=>x.value);
  const paint=d=>{
   document.getElementById('profitInsights').innerHTML=profitInsights(d);
   document.getElementById('profitFacts').innerHTML=`<div class="metric-card"><span>Recorded realized P&amp;L</span><strong class="${d.recorded_pnl<0?'profit-loss':d.recorded_pnl>0?'profit-gain':''}">${H(profitNumber(d.recorded_pnl))}</strong><small>USD / USDT · selected period</small></div><div class="metric-card"><span>P&amp;L records</span><strong>${N(d.pnl_records,0)}</strong><small>Available recorded outcomes</small></div><div class="metric-card"><span>History window</span><strong>${d.start||d.end?'Custom dates':'All available'}</strong><small>${H(d.start||'Beginning')} → ${H(d.end||'Latest record')}</small></div>`;
   const count=(d.selected_symbols||[]).length;
   document.getElementById('profitHeading').textContent=count?'Selected symbols comparison':'Overall performance';
   document.getElementById('profitSelectionLabel').textContent=count?`Compare symbols · ${count} selected`:'Compare symbols · all';
   document.getElementById('profitChart').innerHTML=profitGraph(d,document.getElementById('profitChart').clientWidth||1000);
   document.getElementById('profitCoverage').textContent=(d.partial?'Partial history: '+(d.provider_errors||[]).length+' provider read issue(s); '+d.excluded_unknown_pnl_records+' records without P&L and '+d.excluded_undated_records+' undated records excluded. ':'')+((d.symbols_without_priced_records||[]).length?'No priced records for: '+d.symbols_without_priced_records.join(', ')+'. ':'')+d.coverage+' Open P&L is excluded; fee treatment follows the Performance ledger. USD/USDT are reported in existing ledger units without conversion.';
   const series=d.series||[],slider=document.getElementById('profitDateSlider');
   if(slider&&series.length){const inspect=index=>{index=Math.max(0,Math.min(series[0].points.length-1,Number(index)));slider.value=String(index);document.getElementById('profitPoint').textContent=profitDate(series[0].points[index].time)+' · '+series.map(s=>s.label+': '+profitNumber(s.points[index].value)).join(' | ')};slider.oninput=()=>inspect(slider.value);inspect(slider.value);
    const svg=document.getElementById('profitSvg');svg.onpointermove=e=>{const bounds=svg.getBoundingClientRect(),vw=svg.viewBox.baseVal.width,leftPad=vw<650?64:88,rightPad=vw<650?12:28,px=(e.clientX-bounds.left)/bounds.width*vw,ratio=Math.max(0,Math.min(1,(px-leftPad)/(vw-leftPad-rightPad))),ps=series[0].points,target=ps[0].time+ratio*(ps.at(-1).time-ps[0].time);let left=0,right=ps.length-1;while(left<right){const mid=Math.floor((left+right)/2);if(ps[mid].time<target)left=mid+1;else right=mid}const index=left>0&&target-ps[left-1].time<ps[left].time-target?left-1:left;inspect(index)};
   }
  };
  const load=async()=>{
   const start=document.getElementById('profitStart').value,end=document.getElementById('profitEnd').value,error=document.getElementById('profitFilterError');
   if(start&&end&&start>end){error.textContent='Start date must be on or before end date. Filters have not been applied.';return}
   error.textContent='';const id=++request,query=new URLSearchParams();for(const symbol of selected())query.append('symbols',symbol);if(start)query.set('start',start);if(end)query.set('end',end);
   loading=true;document.getElementById('profitInsights').innerHTML='<p class="muted">Updating insights…</p>';document.getElementById('profitApply').disabled=true;document.getElementById('profitFacts').innerHTML='';document.getElementById('profitChart').innerHTML='<div class="empty-state">Loading performance…</div>';
   try{const next=await api('/performance/profit-chart'+(query.toString()?'?'+query:''));if(epoch!==chartsEpoch||id!==request)return;data=next;paint(data)}catch(e){if(epoch!==chartsEpoch||id!==request)return;document.getElementById('profitChart').innerHTML=`<div class="empty-state">Performance unavailable: ${H(e.message)}</div>`;document.getElementById('profitInsights').innerHTML='<p class="muted">Insights unavailable. Apply filters to retry.</p>';document.getElementById('profitCoverage').textContent='Try Apply filters again to refresh.'}finally{if(epoch===chartsEpoch&&id===request){loading=false;document.getElementById('profitApply').disabled=false}}
  };
  document.getElementById('profitFilters').onsubmit=e=>{e.preventDefault();load()};
  document.getElementById('profitReset').onclick=()=>{document.querySelectorAll('input[name="profitSymbol"]').forEach(x=>x.checked=false);document.getElementById('profitStart').value='';document.getElementById('profitEnd').value='';load()};
  paint(data);
  if(typeof ResizeObserver!=='undefined'){
   let lastWidth=document.getElementById('profitChart').clientWidth;
   const observer=new ResizeObserver(entries=>{
    if(epoch!==chartsEpoch){observer.disconnect();return}
    const width=entries[0].contentRect.width;
    if(Math.abs(width-lastWidth)>1&&!loading){lastWidth=width;paint(data)}
   });
   profitResizeObserver=observer;observer.observe(document.getElementById('profitChart'));
  }
 }catch(e){if(epoch===chartsEpoch){content.innerHTML=`<div class="panel empty-state">Profit performance unavailable: ${H(e.message)}<br><button id="profitRetry" class="ghost-button">Retry</button></div>`;document.getElementById('profitRetry').onclick=()=>charts()}}
}
const previous=renderPage;
renderPage=async function(page){
 chartsEpoch++;
 const root=document.getElementById('content');root.classList.add('atlas-route-loading');
 try{setActive(page);if(page==='Markets')await markets();else if(page==='Charts')await charts();else await previous(page)}
 finally{requestAnimationFrame(()=>root.classList.remove('atlas-route-loading'))}
};
window.AtlasMarketsChartsV72={markets,charts};
window.AtlasProfitChart={profitGraph,profitInsights};
})();