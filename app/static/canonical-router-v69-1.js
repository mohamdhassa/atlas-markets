/* ATLAS v69.1 — final canonical router.
   Loaded last so legacy presentation wrappers cannot steal navigation.
   No execution, strategy, risk, certification or broker behavior changes. */
(()=>{'use strict';
function canonicalPortfolio(){
 setActive('Portfolio');
 if(window.AtlasPortfolioV61?.render)return window.AtlasPortfolioV61.render();
 content.innerHTML='<div class="panel empty-state">Portfolio Command Center is unavailable.</div>';
}
function canonical(page){
 if(page==='Portfolio')return canonicalPortfolio();
 if(page==='Operations'&&window.AtlasUnifiedV69?.operations)return window.AtlasUnifiedV69.operations();
 if(page==='Signals'&&window.AtlasUnifiedV69?.signals)return window.AtlasUnifiedV69.signals();
 if(page==='News Intelligence'&&window.AtlasNewsDecisionContext?.render)return window.AtlasNewsDecisionContext.render();
 return null;
}
const fallback=renderPage;
renderPage=async function(page){
 const handled=canonical(page);
 if(handled!==null)return handled;
 return fallback(page);
};
function fixNav(){
 document.querySelectorAll('#nav .nav-button').forEach(b=>{
  if(b.dataset.page==='Positions'||b.textContent.trim()==='Positions'){b.dataset.page='Portfolio';b.textContent='Portfolio'}
  b.onclick=()=>renderPage(b.dataset.page);
 });
}
const priorBuild=buildNav;
buildNav=function(){priorBuild();fixNav()};
fixNav();
window.AtlasCanonicalRouterV691={fixNav,portfolio:canonicalPortfolio};
})();