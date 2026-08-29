(()=>{
function ensureAutomationNav(){
 const nav=document.getElementById('nav');
 if(!nav)return;
 let b=nav.querySelector('[data-page="Automation"]');
 if(!b){
  b=document.createElement('button');
  b.className='nav-button';
  b.dataset.page='Automation';
  b.textContent='Automation';
  const dash=nav.querySelector('[data-page="Dashboard"]');
  dash?dash.insertAdjacentElement('afterend',b):nav.prepend(b);
 }
 b.onclick=e=>{e?.preventDefault?.();if(window.AtlasPhase38?.render){window.AtlasPhase38.render();return}const root=document.getElementById('content');if(root)root.innerHTML='<div class="panel empty-state">Automation Operations Center is loading. Refresh once if this persists.</div>'};
}
const originalBuildNav=window.buildNav;
if(typeof originalBuildNav==='function'){
 window.buildNav=function(){const r=originalBuildNav.apply(this,arguments);ensureAutomationNav();return r};
}
const originalRenderPage=window.renderPage;
if(typeof originalRenderPage==='function'){
 window.renderPage=function(page){if(page==='Automation'&&window.AtlasPhase38?.render){window.AtlasPhase38.render();return}return originalRenderPage.apply(this,arguments)};
}
const observer=new MutationObserver(()=>ensureAutomationNav());
observer.observe(document.getElementById('nav')||document.body,{childList:true,subtree:true});
ensureAutomationNav();
setTimeout(ensureAutomationNav,0);
setTimeout(ensureAutomationNav,250);
window.AtlasPhase39={ensureAutomationNav};
})();
