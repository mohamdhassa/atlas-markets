/* ATLAS MARKETS v59.1 — ensure Portfolio is visible after boot/navigation creation. */
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
buildNav=function(){
 priorBuildNav();
 fixPortfolioNav();
};
// Handles an already-authenticated page where showApp/buildNav ran before this script loaded.
fixPortfolioNav();
window.AtlasPortfolioNavFix={fixPortfolioNav};
})();
