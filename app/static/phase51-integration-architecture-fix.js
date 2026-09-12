(()=>{
const old=window.AtlasPhase24;
function fix(){document.querySelectorAll('.p24-requirements,.p24-detail-grid,.p21-note').forEach(el=>{if(!/IBKR|TWS|Gateway|Windows bridge|7497/.test(el.textContent))return;el.innerHTML=el.innerHTML.replaceAll('TWS or IB Gateway authenticated on Windows','IB Gateway authenticated on the Oracle Linux execution host').replaceAll('Windows bridge<strong>localhost:8766</strong>','ATLAS bridge<strong>localhost:8766</strong>').replaceAll('Paper TWS port<strong>7497</strong>','Paper Gateway API<strong>4002</strong>').replaceAll('ATLAS → Windows bridge :8766 → TWS/IB Gateway','ATLAS → local bridge :8766 → IB Gateway :4002').replaceAll('TWS/IB Gateway','IB Gateway')})}
const observer=new MutationObserver(()=>fix());document.addEventListener('DOMContentLoaded',()=>{fix();observer.observe(document.getElementById('content')||document.body,{childList:true,subtree:true})});
})();
