(()=>{
const productionPages=new Set(['Dashboard','Engines','FX','Stocks & ETFs','Crypto','Metals & Commodities','Charts','Strategies','Positions','Orders & History','Performance','Automation','Accounts & Integrations','Users','Management']);
function route(name){
  if(name==='Performance'&&window.AtlasProductionFixes?.performance)return window.AtlasProductionFixes.performance();
  if(name==='Orders & History'&&window.AtlasProductionFixes?.orders)return window.AtlasProductionFixes.orders();
  if(window.AtlasProduction?.render)return window.AtlasProduction.render(name);
}
document.addEventListener('click',e=>{
  const b=e.target.closest?.('#nav .nav-button');
  if(!b||!productionPages.has(b.dataset.page))return;
  e.preventDefault();
  e.stopImmediatePropagation();
  route(b.dataset.page);
},true);
window.AtlasRouter={route};
})();