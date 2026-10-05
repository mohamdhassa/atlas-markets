/* Live operational timeline. No arbitrary browser messages or stacks are sent. */
(()=>{
'use strict';
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let rows=new Map(),cursor=null,busy=false,paused=false,generation=0,reportCount=0,reportWindow=Date.now();
function report(event,http_status){
 if(!state.token||!state.user)return;
 if(Date.now()-reportWindow>60000){reportWindow=Date.now();reportCount=0}
 if(reportCount++>=30)return;
 const payload={event,page:String(state.page||'Unknown').replace(/[^A-Za-z ]/g,'').slice(0,40)||'Unknown'};
 if(http_status)payload.http_status=http_status;
 fetch('/logs/browser',{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${state.token}`},body:JSON.stringify(payload)}).catch(()=>{});
}
window.addEventListener('error',e=>report(e instanceof ErrorEvent?'JS_ERROR':'RESOURCE_FAILED'),true);
window.addEventListener('unhandledrejection',()=>report('UNHANDLED_REJECTION'));
const originalApi=api;
api=async function(path,options){try{return await originalApi(path,options)}catch(e){if(!String(path).startsWith('/logs'))report('API_FAILED');throw e}};
const previousNav=buildNav;
buildNav=function(){previousNav();if(state.user?.role==='ADMIN'&&!document.querySelector('#nav [data-page="Logs"]')){const b=document.createElement('button');b.className='nav-button';b.dataset.page='Logs';b.textContent='Logs';b.onclick=()=>renderPage('Logs');document.getElementById('nav').appendChild(b)}};
function params(){const p=new URLSearchParams({limit:'200'});for(const key of ['source','level','provider','decision','status','hours','q']){const value=document.getElementById(`log-${key}`)?.value;if(value)p.set(key,value)}return p}
function renderRows(){
 const host=document.getElementById('log-events');if(!host)return;
 const expanded=new Set([...host.querySelectorAll('details[open]')].map(x=>x.dataset.event));const scroll=host.scrollTop;
 const sorted=[...rows.values()].sort((a,b)=>b.time.localeCompare(a.time)||b.id.localeCompare(a.id));
 host.innerHTML=sorted.map(x=>`<article class="log-event"><div class="log-event-head"><time datetime="${esc(x.time)}">${esc(new Date(x.time).toLocaleString())}</time><span class="badge ${x.level==='ERROR'||x.level==='CRITICAL'?'warn':''}">${esc(x.level)}</span><strong>${esc(x.source)}</strong><span>${esc(x.provider||'')}</span></div><div class="log-event-body"><strong>${esc(x.symbol||x.event)}</strong><span>${esc(x.decision||'')}</span><span class="badge">${esc(x.status||x.event)}</span></div><p>${esc(x.reason||x.message)}</p><details><summary>Event details</summary><dl>${Object.entries(x).map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl></details></article>`).join('')||'<div class="empty-state">No events match these filters.</div>';
 [...host.querySelectorAll('details')].forEach((detail,i)=>{detail.dataset.event=sorted[i].id;detail.open=expanded.has(sorted[i].id)});host.scrollTop=scroll;
 document.getElementById('log-count').textContent=`${sorted.length} events loaded`;
}
async function load(older=false){
 if(busy||state.page!=='Logs'||(!older&&(paused||document.hidden)))return;
 busy=true;const epoch=generation;const p=params();if(older&&cursor){p.set('before',cursor.before);p.set('before_id',cursor.before_id)}
 try{
  const data=await api(`/logs?${p}`);if(epoch!==generation||state.page!=='Logs')return;
  for(const x of data.events)rows.set(x.id,x);
  const sorted=[...rows.values()].sort((a,b)=>b.time.localeCompare(a.time)||b.id.localeCompare(a.id));rows=new Map(sorted.slice(0,3000).map(x=>[x.id,x]));
  if(older||rows.size<=200)cursor=data.next;
  document.getElementById('log-more').disabled=!cursor;
  document.getElementById('log-state').textContent=paused?'PAUSED':`LIVE · updated ${new Date().toLocaleTimeString()}`;
  const c=data.coverage;document.getElementById('log-coverage').textContent=`Runtime storage: ${c.persistence}. ${c.runtime_retention}. Persistence drops: ${c.dropped}. ${c.audit_window_capped?'Audit window capped at 2,000 rows per source. ':''}${c.host_logs}. Browser events are reported by signed-in clients. Loaded display is limited to 3,000 events.`;
  renderRows();
 }catch(e){if(epoch===generation&&state.page==='Logs')document.getElementById('log-state').textContent=`Update failed: ${e.message} · showing previous events`}
 finally{busy=false}
}
async function page(){
 setActive('Logs');generation++;rows=new Map();cursor=null;paused=false;
 const opts=values=>'<option value="">All</option>'+values.map(v=>`<option>${v}</option>`).join('');
 content.innerHTML=`<section class="panel system-logs"><div class="page-intro"><div><p class="eyebrow">SYSTEM TIMELINE</p><h3>Live logs</h3><p class="muted">Decisions, approvals, blocks, provider calls, server requests and browser events.</p></div><span class="badge good" id="log-state" role="status">Connecting…</span></div><form id="log-filters" class="log-filters"><label>Source<select id="log-source">${opts(['TRADING','PROVIDER','SERVER','FRONTEND','AUTOMATION','SECURITY','SAFETY','STRATEGY'])}</select></label><label>Severity<select id="log-level">${opts(['INFO','WARNING','ERROR','CRITICAL'])}</select></label><label>Provider<select id="log-provider">${opts(['IBKR','BYBIT','MT5'])}</select></label><label>Decision<select id="log-decision">${opts(['BUY','SELL','HOLD'])}</select></label><label>Outcome<select id="log-status">${opts(['EXECUTED','BLOCK','REJECTED','FAILED','PASS'])}</select></label><label>History<select id="log-hours"><option value="1">1 hour</option><option value="24" selected>24 hours</option><option value="168">7 days</option></select></label><label class="log-search">Search<input id="log-q" maxlength="80" placeholder="Symbol, reason, request or scan ID"></label><button class="primary-button" type="submit">Apply filters</button></form><div class="log-toolbar"><button type="button" id="log-pause" class="ghost-button">Pause live</button><button type="button" id="log-refresh" class="ghost-button">Refresh</button><button type="button" id="log-export" class="ghost-button">Export loaded events</button><span id="log-count">0 events loaded</span></div><p class="muted log-coverage" id="log-coverage"></p><div id="log-events" class="log-events"></div><button type="button" id="log-more" class="ghost-button" disabled>Load older events</button></section>`;
 document.getElementById('log-filters').onsubmit=e=>{e.preventDefault();generation++;rows.clear();cursor=null;paused=false;document.getElementById('log-pause').textContent='Pause live';load()};
 document.getElementById('log-pause').onclick=e=>{paused=!paused;e.currentTarget.textContent=paused?'Resume live':'Pause live';document.getElementById('log-state').textContent=paused?'PAUSED':'LIVE';if(!paused)load()};
 document.getElementById('log-refresh').onclick=()=>{paused=false;document.getElementById('log-pause').textContent='Pause live';load()};
 document.getElementById('log-more').onclick=()=>{paused=true;document.getElementById('log-pause').textContent='Resume live';load(true)};
 document.getElementById('log-export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify([...rows.values()],null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='atlas-loaded-events.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
 await load();if(state.page==='Logs')state.marketTimer=setInterval(()=>load(),3000);
}
const previousRender=renderPage;
renderPage=async function(name){generation++;const result=await previousRender(name);if(state.page!==name)return result;if(name==='Logs'){if(state.user?.role!=='ADMIN'){content.innerHTML='<div class="panel empty-state">Administrator access required.</div>';return}const pending=page();report('PAGE_OPENED');return pending}report('PAGE_OPENED');return result};
window.AtlasSystemLogs={page,report};
})();
