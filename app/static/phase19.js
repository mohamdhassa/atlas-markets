(()=>{
const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
async function loadUniverse(){return api('/analysis/universe')}
async function renderUniverse(){
  setActive('Universe');
  content.innerHTML='<div class="panel empty-state">Loading multi-asset universe…</div>';
  try{
    const data=await loadUniverse();
    const groups=data.groups||{};
    const profiles=data.profiles||[];
    content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">MULTI-ASSET UNIVERSE</p><h3>Configured instruments and strategy families</h3><p class="muted">Universe membership does not imply a live feed is connected. Provider-backed prices and execution remain separately gated.</p></div><span class="badge good">PHASE 19</span></div><div class="analysis-grid">${Object.entries(groups).map(([group,symbols])=>`<div class="analysis-card"><h4>${esc(group.replaceAll('_',' '))}</h4><p>${symbols.map(symbol=>`<span class="badge" style="margin:3px">${esc(symbol)}</span>`).join('')}</p></div>`).join('')}</div><div class="table-wrap" style="margin-top:14px"><table class="data-table"><thead><tr><th>Symbol</th><th>Market</th><th>Asset class</th><th>Strategies</th><th>Timeframes</th></tr></thead><tbody>${profiles.map(profile=>`<tr><td><strong>${esc(profile.symbol)}</strong></td><td>${esc(profile.market)}</td><td>${esc(profile.asset_class)}</td><td>${profile.strategy_families.map(item=>esc(item)).join(', ')}</td><td>${profile.default_timeframes.map(item=>esc(item)).join(', ')}</td></tr>`).join('')}</tbody></table></div>`;
  }catch(error){content.innerHTML=`<div class="panel empty-state">Universe unavailable: ${esc(error.message)}</div>`}
}
function ensureUniverseButton(){
  const navEl=document.getElementById('nav');
  if(!navEl||navEl.querySelector('[data-page="Universe"]'))return;
  const button=document.createElement('button');
  button.className='nav-button';button.textContent='Universe';button.dataset.page='Universe';button.onclick=renderUniverse;
  const marketsButton=navEl.querySelector('[data-page="Markets"]');
  if(marketsButton?.nextSibling)navEl.insertBefore(button,marketsButton.nextSibling);else navEl.appendChild(button);
}
const originalBuildNav=window.buildNav;
if(typeof originalBuildNav==='function')window.buildNav=function(...args){const result=originalBuildNav.apply(this,args);ensureUniverseButton();return result};
const originalRenderPage=window.renderPage;
if(typeof originalRenderPage==='function')window.renderPage=function(page,...args){if(page==='Universe')return renderUniverse();return originalRenderPage.call(this,page,...args)};
new MutationObserver(ensureUniverseButton).observe(document.getElementById('nav'),{childList:true});
ensureUniverseButton();
window.AtlasPhase19={renderUniverse,loadUniverse};
})();
