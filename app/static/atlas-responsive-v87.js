/* ATLAS MARKETS v87 navigation, accessibility, and responsive behavior. */
(()=>{
  'use strict';
  const sidebar=document.getElementById('sidebar');
  const menu=document.getElementById('menuButton');
  const content=document.getElementById('content');
  if(!sidebar||!menu||!content)return;

  const backdrop=document.createElement('button');
  backdrop.type='button';
  backdrop.className='atlas-sidebar-backdrop';
  backdrop.setAttribute('aria-label','Close navigation');
  document.body.appendChild(backdrop);

  menu.setAttribute('aria-controls','sidebar');
  menu.setAttribute('aria-expanded','false');

  const sync=()=>{
    const open=sidebar.classList.contains('open')&&matchMedia('(max-width:760px)').matches;
    backdrop.classList.toggle('open',open);
    document.body.classList.toggle('atlas-nav-open',open);
    menu.setAttribute('aria-expanded',String(open));
  };
  const close=()=>{sidebar.classList.remove('open');sync();};

  menu.addEventListener('click',()=>requestAnimationFrame(sync));
  backdrop.addEventListener('click',close);
  document.addEventListener('keydown',event=>{if(event.key==='Escape')close();});
  document.addEventListener('click',event=>{
    if(event.target.closest?.('.nav-button'))requestAnimationFrame(close);
  });
  matchMedia('(min-width:761px)').addEventListener?.('change',event=>{if(event.matches)close();});

  const enhance=root=>{
    root.querySelectorAll?.('.table-wrap,.responsive-table,.v61-table,.p44-table-wrap').forEach((wrap,index)=>{
      if(wrap.dataset.atlasResponsive)return;
      wrap.dataset.atlasResponsive='1';
      wrap.tabIndex=0;
      wrap.setAttribute('role','region');
      wrap.setAttribute('aria-label',`Scrollable data table ${index+1}`);
    });
  };
  new MutationObserver(records=>records.forEach(record=>record.addedNodes.forEach(node=>{
    if(node.nodeType===1)enhance(node);
  }))).observe(content,{childList:true,subtree:true});
  enhance(document);
  sync();

  /* Compatible page modules can replace the same workspace more than once.
     Hold those intermediate DOM states behind one loading surface. */
  const previousRender=window.renderPage||renderPage;
  const delay=ms=>new Promise(resolve=>window.setTimeout(resolve,ms));
  let routeGeneration=0;
  window.renderPage=renderPage=async function(page){
    const generation=++routeGeneration;
    content.classList.add('atlas-route-rendering');
    try{
      const result=await previousRender(page);
      await delay(page==='Portfolio'?760:140);
      return result;
    }finally{
      if(generation===routeGeneration){
        requestAnimationFrame(()=>requestAnimationFrame(()=>{
          if(generation===routeGeneration)content.classList.remove('atlas-route-rendering');
        }));
      }
    }
  };

  const revealBoot=()=>document.body.classList.remove('atlas-booting');
  if(document.readyState==='complete')revealBoot();
  else window.addEventListener('load',revealBoot,{once:true});
})();
