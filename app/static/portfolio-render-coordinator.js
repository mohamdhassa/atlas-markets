/* One Portfolio assembly path; existing final templates and CSS remain authoritative. */
(()=>{'use strict';
const previous=renderPage;
let epoch=0,active=null;
function release(job){
 if(!job)return;
 if(api===job.read)api=job.originalApi;
 job.loader.remove();
 content.style.visibility=job.visibility;
 content.removeAttribute('aria-busy');
}
renderPage=async function(page){
 const mine=++epoch;
 release(active);active=null;
 window.AtlasLivePositionChartsV66?.stop();
 if(page!=='Portfolio')return previous(page);
 setActive(page);
 const current=()=>epoch===mine;
 const cache=new Map(),originalApi=api;
 const read=async(path,...args)=>{
  // Share read-only snapshots within this assembly only; never cache mutations.
  if(args.length)return originalApi(path,...args);
  if(!current())throw new Error('Portfolio navigation superseded');
  if(!cache.has(path))cache.set(path,Promise.resolve().then(()=>originalApi(path)));
  const value=await cache.get(path);
  if(!current())throw new Error('Portfolio navigation superseded');
  return value;
 };
 const loader=document.createElement('div');loader.className='panel empty-state';
 loader.setAttribute('role','status');loader.textContent='Loading Portfolio…';
 const job={loader,read,originalApi,visibility:content.style.visibility};
 active=job;api=read;
 content.before(loader);content.style.visibility='hidden';content.setAttribute('aria-busy','true');
 try{
  // Bypass the old renderPage/timer chain, using the unchanged final components once.
  await window.AtlasPortfolioV61.baseRender({isCurrent:current});
  if(!current())return;
  if(document.querySelector('.v61-shell')){
   await window.AtlasTradingUniverseV62.inject();
   if(!current())return;
   // The card view is final; the superseded v64 table is never assembled.
   await window.AtlasPortfolioV641.rebuild();
   if(!current())return;
   await Promise.all([window.AtlasPortfolioV63.mount(),window.AtlasOpenPositionChartsV65.run()]);
   if(!current())return;
   window.AtlasPortfolioV631.clean();
  }
 }finally{
  if(current()){
   release(job);active=null;
   if(document.querySelector('.v61-shell'))window.AtlasLivePositionChartsV66?.start();
  }
 }
 if(current())window.AtlasLiveActivityV75?.attach();
};
window.AtlasPortfolioRenderCoordinator={isLoading:()=>active!==null};
})();
