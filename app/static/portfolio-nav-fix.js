/* ATLAS MARKETS v59.1 — canonical visible navigation fix for Portfolio. */
(()=>{
'use strict';
function fixPortfolioNav(){
 document.querySelectorAll('#nav .nav-button').forEach(button=>{
  if(button.dataset.page==='Positions'||button.textContent.trim()==='Positions'){
   button.dataset.page='Portfolio';
   button.textContent='Portfolio';
   button.onclick=()=>renderPage('Portfolio');
  }
 });
}
const priorBuildNav=buildNav;
buildNav=function(){priorBuildNav();fixPortfolioNav();};
fixPortfolioNav();
window.AtlasPortfolioNavFix={fixPortfolioNav};
})();
