if(!userPages.includes('News'))userPages.splice(3,0,'News');

async function phase12NewsPage(){
  setActive('News');content.innerHTML='<div class="panel empty-state">Loading market news intelligence…</div>';
  try{
    const symbols=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT'];
    const [articles,...contexts]=await Promise.all([api('/news?limit=40'),...symbols.map(s=>api(`/news/context/${s}?hours=24`))]);
    const refresh=state.user?.role==='ADMIN'?'<button id="refreshNews" class="primary-button">Refresh feeds</button>':'';
    content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">NEWS INTELLIGENCE</p><h3>Market context</h3><p class="muted">RSS headlines are scored for symbol relevance and sentiment. News can adjust signal confidence, but risk approval remains mandatory.</p></div>${refresh}</div>
    <div class="metric-grid">${contexts.map(c=>`<div class="metric-card"><span>${c.symbol}</span><strong>${c.bias}</strong><small>${c.article_count} articles · sentiment ${Number(c.sentiment).toFixed(2)}</small></div>`).join('')}</div>
    <div class="panel"><h3>Recent relevant headlines</h3><div class="analysis-grid">${articles.length?articles.map(a=>`<article class="analysis-card"><div class="action-row"><span class="badge">${escapeHtml(a.source)}</span><span class="badge ${a.sentiment_score>0.2?'good':a.sentiment_score<-0.2?'warn':''}">${Number(a.sentiment_score).toFixed(2)}</span></div><h4>${escapeHtml(a.title)}</h4><p class="muted">${(a.symbols||[]).map(escapeHtml).join(' · ')||'General market'}</p><a href="${escapeHtml(a.url)}" target="_blank" rel="noopener">Open source</a></article>`).join(''):'<div class="empty-state">No stored headlines yet. ADMIN can refresh feeds.</div>'}</div></div>`;
    if($('refreshNews'))$('refreshNews').onclick=async()=>{const b=$('refreshNews');b.disabled=true;b.textContent='Refreshing…';try{const r=await api('/news/refresh',{method:'POST'});alert(`News refresh complete: ${r.inserted} new articles${r.errors?.length?`, ${r.errors.length} feed errors`:''}`);phase12NewsPage()}catch(e){alert(e.message)}finally{b.disabled=false}};
  }catch(e){content.innerHTML=`<div class="panel empty-state">News intelligence unavailable: ${escapeHtml(e.message)}</div>`}
}

const phase11RenderPageV12=renderPage;
renderPage=function(page){if(page==='News'){phase12NewsPage();return}phase11RenderPageV12(page)};
