(()=>{
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let busy=false;
async function inject(){
  if(busy)return;
  const root=document.getElementById('content');
  if(!root||!document.querySelector('#nav [data-page="Management"].active'))return;
  if(document.getElementById('p49LiveCertification'))return;
  busy=true;
  try{
    const release=await api('/release/readiness');
    const live=release.live_certification||{};
    const providers=live.providers||{};
    const rows=Object.entries(providers).map(([name,p])=>`<tr><td><strong>${esc(name)}</strong></td><td>${esc(p.simulation_certification)}</td><td><span class="badge ${p.live_certification==='CERTIFIED'?'good':'warn'}">${esc(p.live_certification)}</span></td><td>${p.live_execution_allowed?'YES':'NO'}</td><td>${(p.blockers||[]).map(esc).join(', ')||'—'}</td></tr>`).join('');
    const section=document.createElement('section');
    section.id='p49LiveCertification';
    section.className='panel p44-section';
    section.innerHTML=`<div class="page-intro"><div><h3>Live provider certification</h3><p class="muted">Simulation certification is tracked separately from real-money certification. No Demo, Paper or Testnet result can unlock Live Money.</p></div><span class="badge warn">${esc(live.status||'LOCKED')} · ${Number(live.execution_providers_certified||0)}/${Number(live.execution_providers_required||3)} CERTIFIED</span></div><div class="p44-table-wrap"><table class="data-table"><thead><tr><th>Provider</th><th>Simulation status</th><th>Live certification</th><th>Live execution</th><th>Blockers</th></tr></thead><tbody>${rows}</tbody></table></div><div class="p44-warn">${esc(live.rule||'Live Money remains gated until each execution provider is separately certified.')}</div>`;
    const boundary=[...root.querySelectorAll('section')].find(x=>x.textContent.includes('Live Money boundary'));
    boundary?boundary.insertAdjacentElement('beforebegin',section):root.appendChild(section);
  }catch(e){
    console.warn('Live certification status unavailable',e);
  }finally{busy=false;}
}
const observer=new MutationObserver(()=>{clearTimeout(window.__p49Live);window.__p49Live=setTimeout(inject,100)});
observer.observe(document.getElementById('content')||document.body,{childList:true,subtree:true});
document.addEventListener('click',e=>{if(e.target.closest?.('[data-page="Management"]'))setTimeout(inject,180)});
window.AtlasPhase49={inject};
})();
