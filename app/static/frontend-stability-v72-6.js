/* ATLAS v72.6 — frontend-only stale callback containment. */
(()=>{'use strict';
let epoch=0,active='';
const nativeSetTimeout=window.setTimeout.bind(window);
const nativeSetInterval=window.setInterval.bind(window);
function current(){return String(document.getElementById('pageTitle')?.textContent||'').trim()}
function safe(fn,page,myEpoch){return (...args)=>{if(epoch!==myEpoch||current()!==page)return;return fn(...args)}}
window.setTimeout=function(fn,delay,...args){if(typeof fn!=='function')return nativeSetTimeout(fn,delay,...args);const page=current(),e=epoch;return page?nativeSetTimeout(safe(fn,page,e),delay,...args):nativeSetTimeout(fn,delay,...args)}
window.setInterval=function(fn,delay,...args){if(typeof fn!=='function')return nativeSetInterval(fn,delay,...args);const page=current(),e=epoch;return page?nativeSetInterval(safe(fn,page,e),delay,...args):nativeSetInterval(fn,delay,...args)}
const previous=renderPage;
renderPage=async function(page){epoch+=1;active=page;const root=document.getElementById('content');if(root)root.dataset.routeEpoch=String(epoch);return previous(page)};
window.AtlasFrontendStabilityV726={currentPage:()=>active,epoch:()=>epoch};
})();