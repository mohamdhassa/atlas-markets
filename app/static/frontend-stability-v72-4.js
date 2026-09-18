/* ATLAS v72.4 — frontend-only stale render containment.
   Preserves every existing page and API; prevents delayed legacy callbacks from
   painting into a page after navigation has moved elsewhere. */
(()=>{'use strict';
let epoch=0,active='';
const nativeSetTimeout=window.setTimeout.bind(window);
const nativeSetInterval=window.setInterval.bind(window);
function current(){return String(document.getElementById('pageTitle')?.textContent||'').trim()}
function safeCallback(fn,page,myEpoch){return (...args)=>{if(epoch!==myEpoch||current()!==page)return;return fn(...args)}}
window.setTimeout=function(fn,delay,...args){if(typeof fn!=='function')return nativeSetTimeout(fn,delay,...args);const page=current(),e=epoch;if(!page)return nativeSetTimeout(fn,delay,...args);return nativeSetTimeout(safeCallback(fn,page,e),delay,...args)}
window.setInterval=function(fn,delay,...args){if(typeof fn!=='function')return nativeSetInterval(fn,delay,...args);const page=current(),e=epoch;if(!page)return nativeSetInterval(fn,delay,...args);return nativeSetInterval(safeCallback(fn,page,e),delay,...args)}
const previous=renderPage;
renderPage=async function(page){
 epoch+=1;active=page;
 const root=document.getElementById('content');
 if(root)root.dataset.routeEpoch=String(epoch);
 return previous(page);
};
window.AtlasFrontendStabilityV724={currentPage:()=>active,epoch:()=>epoch};
})();