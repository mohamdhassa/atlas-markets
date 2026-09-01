(()=>{
const esc=s=>String(s??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const cfg={
 'Stocks & ETFs':{provider:'IBKR',markets:['STOCK','ETF'],label:'Live stocks & ETF quotes & decisions',badge:'LIVE SYMBOLS'},
 'Crypto':{provider:'BYBIT',markets:['CRYPTO'],label:'Live crypto quotes & decisions',badge:'LIVE SYMBOLS'},
 'Metals & Commodities':{provider:'MT5',markets:['METAL','COMMODITY'],label:'Live metals & commodities quotes & decisions',badge:'LIVE SYMBOLS'}
};
let busy=false,lastKey='';
function num(v,d=2){const n=Number(v);return Number.isFinite(n)?n.toFixed(d):'—'}
function decimals(symbol,price){if(String(symbol).includes('JPY'))return 3;if(Number(price)>=1000)return 2;if(Number(price)>=100)return 2;if(Number(price)>=1)return 4;return 5}
function canon(v){return String(v||'').replace('/','').replace(/\s+/g,'').toUpperCase()}
function readableError(e){const raw=e?.message??e;if(typeof raw==='string'&&raw!=='[object Object]')return raw;try{return JSON.stringify(raw)}catch{return String(raw)}}
function warnings(list){return (list||[]).map(x=>{if(typeof x==='string')return esc(x);const sym=x?.symbol?`${esc(x.symbol)}: `:'';return `${sym}${esc(x?.error||x?.detail||JSON.stringify(x))}`}).join(' · ')}
async function inject(){
 const name=document.getElementById('pageTitle')?.textContent?.trim();const c=cfg[name];if(!c||busy)return;
 const root=document.getElementById('content');if(!root||root.querySelector('#p47LiveSection'))return;
 const key=`${name}:${root.childElementCount}`;if(key===lastKey)return;lastKey=key;busy=true;
 try{
  const qs=new URLSearchParams();qs.set('provider',c.provider);c.markets.forEach(m=>qs.append('markets',m));
  const [quotes,signals,strategies]=await Promise.all([api(`/markets/workspace-quotes?${qs.toString()}`),api('/signals?limit=300'),api('/strategies/symbols')]);
  if(document.getElementById('pageTitle')?.textContent?.trim()!==name)return;
  const latest={};(signals||[]).forEach(s=>{const k=canon(s.symbol);if(!latest[k])latest[k]=s});
  const modes={};(strategies||[]).filter(s=>c.markets.includes(String(s.market||'').toUpperCase())).forEach(s=>{modes[canon(s.symbol)]={mode:s.mode,timeframe:s.timeframe}});
  const rows=quotes.symbols||[];const errs=quotes.errors||[];const section=document.createElement('section');section.className='panel';section.id='p47LiveSection';
  const cards=rows.map(q=>{const k=canon(q.symbol),s=latest[k],m=modes[k]||{},d=decimals(q.symbol,q.price),chg=Number(q.change||0),pct=Number(q.change_percent||0),decision=s?.decision||'NO SIGNAL',risk=s?.risk_status||'—',score=s?Number(s.score||0).toFixed(3):'—',mode=m.mode||q.mode||'NOT CONFIGURED',tf=s?.timeframe||m.timeframe||q.timeframe||'—';return `<article class="p25-fx-card"><div class="p25-fx-price"><div><small>${esc(q.display_symbol||q.symbol)}</small><strong>${num(q.price,d)}</strong></div><span class="p25-fx-change ${chg>=0?'p25-positive':'p25-negative'}">${chg>=0?'+':''}${num(chg,d)} · ${pct>=0?'+':''}${num(pct,2)}%</span></div><div class="p25-fx-decision"><span class="badge ${risk==='APPROVED'?'good':risk==='REJECTED'?'warn':''}">${esc(decision)}</span><span class="badge">${esc(mode)}</span><small>${esc(tf)} · score ${score} · ${esc(risk)}</small></div></article>`}).join('');
  const badgeClass=rows.length?'good':'warn';const badgeText=rows.length?`${rows.length} ${c.badge}`:'NO LIVE DATA';
  section.innerHTML=`<div class="p21-section-head"><div><h3>${esc(c.label)}</h3><div class="muted">Price, movement, latest ATLAS decision and configured execution mode.</div></div><span class="badge ${badgeClass}">${badgeText}</span></div>${rows.length?`<div class="p25-fx-grid">${cards}</div>`:`<div class="empty-state"><p>No live quotes returned for the configured symbols.</p></div>`}${errs.length?`<div class="p44-warn" style="margin-top:10px"><strong>Quote diagnostics:</strong> ${warnings(errs)}</div>`:''}`;
  const engine=root.querySelector('section.panel');engine?engine.insertAdjacentElement('afterend',section):root.prepend(section);
 }catch(e){
  if(document.getElementById('pageTitle')?.textContent?.trim()!==name)return;
  const section=document.createElement('section');section.className='panel';section.id='p47LiveSection';section.innerHTML=`<div class="p21-section-head"><div><h3>${esc(c.label)}</h3><div class="muted">Live quote request failed.</div></div><span class="badge warn">DATA ERROR</span></div><p class="p44-warn">${esc(readableError(e))}</p>`;const engine=root.querySelector('section.panel');engine?engine.insertAdjacentElement('afterend',section):root.prepend(section);
 }finally{busy=false}
}
const obs=new MutationObserver(()=>{clearTimeout(window.__p47t);window.__p47t=setTimeout(()=>{lastKey='';inject()},180)});obs.observe(document.getElementById('content')||document.body,{childList:true,subtree:true});document.addEventListener('click',()=>setTimeout(()=>{lastKey='';inject()},250),true);setTimeout(inject,400);window.AtlasPhase47={inject};
})();
