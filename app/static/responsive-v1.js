/* ATLAS v1.1 responsive navigation and final boot coordinator. */
(()=>{'use strict';
const sidebar=document.getElementById('sidebar');
const backdrop=document.getElementById('sidebarBackdrop');
const menu=document.getElementById('menuButton');
const mobile=()=>window.matchMedia('(max-width:760px)').matches;
function setMenu(open){
  const active=Boolean(open&&mobile());
  sidebar?.classList.toggle('open',active);
  backdrop?.classList.toggle('open',active);
  document.body.classList.toggle('sidebar-open',active);
  menu?.setAttribute('aria-expanded',String(active));
  menu?.setAttribute('aria-label',active?'Close menu':'Open menu');
}
menu?.addEventListener('click',event=>{event.stopImmediatePropagation();setMenu(!sidebar?.classList.contains('open'))});
backdrop?.addEventListener('click',()=>setMenu(false));
document.addEventListener('keydown',event=>{if(event.key==='Escape')setMenu(false)});
document.getElementById('nav')?.addEventListener('click',event=>{if(event.target.closest('.nav-button'))setMenu(false)});
window.addEventListener('resize',()=>{if(!mobile())setMenu(false)},{passive:true});
window.addEventListener('orientationchange',()=>setMenu(false),{passive:true});
if(typeof window.AtlasBoot==='function')window.AtlasBoot();
})();
