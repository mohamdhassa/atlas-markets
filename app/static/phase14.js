(()=>{
  if(!userPages.includes('FX'))userPages.splice(2,0,'FX');
  const ensureBackdrop=()=>{let b=document.querySelector('.sidebar-backdrop');if(!b){b=document.createElement('div');b.className='sidebar-backdrop';document.body.appendChild(b);b.onclick=closeSidebar}return b};
  const openSidebar=()=>{sidebar.classList.add('open');ensureBackdrop().classList.add('open');document.body.classList.add('sidebar-open')};
  const closeSidebar=()=>{sidebar.classList.remove('open');const b=document.querySelector('.sidebar-backdrop');if(b)b.classList.remove('open');document.body.classList.remove('sidebar-open')};
  const mb=$('menuButton');if(mb){const clone=mb.cloneNode(true);mb.replaceWith(clone);clone.onclick=()=>sidebar.classList.contains('open')?closeSidebar():openSidebar()}
  document.addEventListener('click',e=>{if(e.target.closest('.nav-button')&&window.innerWidth<=760)closeSidebar()});
  window.addEventListener('resize',()=>{if(window.innerWidth>760)closeSidebar()});

  function sparkSvg(points,key='equity'){
    if(!points?.length)return '<div class="empty-state">No history yet.</div>';
    const vals=points.map(x=>Number(x[key]||0)),w=900,h=260,p=24,min=Math.min(...vals),max=Math.max(...vals),span=max-min||1;
    const pts=vals.map((v,i)=>`${p+(i/(vals.length-1||1))*(w-p*2)},${h-p-((v-min)/span)*(h-p*2)}`).join(' ');
    return `<div class="analytics-chart"><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><line x1="${p}" y1="${h-p}" x2="${w-p}" y2="${h-p}" stroke="currentColor" opacity=".18"/><polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="3" vector-effect="non-scaling-stroke"/></svg></div>`;
  }
  function barSvg(items,valueKey='realized_pnl'){
    if(!items?.length)return '<div class="empty-state">No symbol results yet.</div>';
    const data=items.slice(0,8),w=700,h=260,p=32,max=Math.max(...data.map(x=>Math.abs(Number(x[valueKey]||0))),1),bw=(w-p*2)/data.length*.62;
    return `<div class="analytics-chart"><svg viewBox="0 0 ${w} ${h}">${data.map((x,i)=>{const v=Number(x[valueKey]||0),xv=p+i*((w-p*2)/data.length)+8,bh=Math.abs(v)/max*(h-75),y=v>=0?h/2-bh:h/2;return `<rect x="${xv}" y="${y}" width="${bw}" height="${bh}" rx="5" fill="currentColor" opacity="${v>=0?'.8':'.45'}"/><text x="${xv+bw/2}" y="${h-18}" fill="currentColor" opacity=".75" font-size="12" text-anchor="middle">${escapeHtml(x.symbol)}</text>`}).join('')}<line x1="${p}" y1="${h/2}" x2="${w-p}" y2="${h/2}" stroke="currentColor" opacity=".2"/></svg></div>`;
  }

  async function overallDashboard(){
    setActive('Dashboard');content.innerHTML='<div class="panel empty-state">Loading overall performance…</div>';
    try{
      const accounts=(await api('/accounts')).filter(a=>a.provider==='ATLAS_PAPER');
      const perfs=await Promise.all(accounts.map(async a=>({account:a,perf:await api(`/performance/${a.id}`)})));
      const totals=perfs.reduce((o,x)=>{o.pnl+=Number(x.perf.total_realized_pnl||0);o.day+=Number(x.perf.daily_pnl||0);o.week+=Number(x.perf.weekly_pnl||0);o.month+=Number(x.perf.monthly_pnl||0);o.trades+=Number(x.perf.closed_trades||0);o.wins+=Number(x.perf.wins||0);return o},{pnl:0,day:0,week:0,month:0,trades:0,wins:0});
      const win=totals.trades?totals.wins/totals.trades*100:0;
      const newest=perfs.flatMap(x=>x.perf.equity_curve||[]).sort((a,b)=>new Date(a.timestamp)-new Date(b.timestamp));
      content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">OVERALL PERFORMANCE</p><h3>${state.user.role==='ADMIN'?'All accessible ATLAS PAPER accounts':'My trading performance'}</h3><p class="muted">Combined operational view across ${accounts.length} paper account${accounts.length===1?'':'s'}.</p></div><span class="badge good">${state.user.role}</span></div>
      <div class="summary-strip"><div class="metric-card"><span>Total realized</span><strong>${money(totals.pnl)}</strong></div><div class="metric-card"><span>24h P&L</span><strong>${money(totals.day)}</strong></div><div class="metric-card"><span>7d P&L</span><strong>${money(totals.week)}</strong></div><div class="metric-card"><span>30d P&L</span><strong>${money(totals.month)}</strong></div><div class="metric-card"><span>Closed trades</span><strong>${totals.trades}</strong></div><div class="metric-card"><span>Win rate</span><strong>${win.toFixed(1)}%</strong></div></div>
      <div class="chart-grid"><div class="panel"><h3>Combined equity progression</h3><p class="muted">Closed-trade equity observations across accessible accounts.</p>${sparkSvg(newest)}</div><div class="panel"><h3>Account performance</h3><div class="status-list">${perfs.length?perfs.map(x=>`<div class="status-item"><span>${escapeHtml(x.account.account_label)}</span><strong>${money(x.perf.total_realized_pnl)}</strong></div>`).join(''):'<div class="empty-state">No ATLAS PAPER accounts.</div>'}</div></div></div>
      <div class="panel"><h3>Market coverage</h3><div class="market-universe"><div><strong>FX · real currencies</strong><div class="market-symbols"><span>EUR/USD</span><span>GBP/USD</span><span>USD/JPY</span><span>USD/CHF</span><span>AUD/USD</span><span>USD/CAD</span></div></div><div><strong>Crypto</strong><div class="market-symbols"><span>BTC/USDT</span><span>ETH/USDT</span><span>SOL/USDT</span><span>XRP/USDT</span><span>BNB/USDT</span></div></div><div><strong>Stocks / ETFs</strong><div class="market-symbols"><span>SPY</span><span>QQQ</span><span>AAPL</span><span>MSFT</span><span>NVDA</span><span>TSLA</span></div></div></div></div>`;
    }catch(e){content.innerHTML=`<div class="panel empty-state">Dashboard unavailable: ${escapeHtml(e.message)}</div>`}
  }

  async function fxPage(){
    setActive('FX');
    const pairs=[['EUR/USD','Euro / US Dollar'],['GBP/USD','British Pound / US Dollar'],['USD/JPY','US Dollar / Japanese Yen'],['USD/CHF','US Dollar / Swiss Franc'],['AUD/USD','Australian Dollar / US Dollar'],['USD/CAD','US Dollar / Canadian Dollar'],['NZD/USD','New Zealand Dollar / US Dollar'],['EUR/GBP','Euro / British Pound']];
    content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">FOREIGN EXCHANGE</p><h3>Real-currency market foundation</h3><p class="muted">FX is a core ATLAS MARKETS asset class. Live FX pricing and execution will come from the selected FX-capable broker adapter; we do not fake Bybit crypto quotes as currency data.</p></div><span class="badge warn">BROKER ADAPTER NEXT</span></div><div class="analysis-score-grid">${pairs.map(([p,n])=>`<div class="analysis-score-card"><small>${escapeHtml(n)}</small><strong>${p}</strong><small>Major / liquid FX pair</small></div>`).join('')}</div><div class="panel" style="margin-top:18px"><h3>FX analysis model</h3><p class="muted">The same chart engine will support trend, support/resistance, candlestick/price-action structure, momentum, volatility, news/macro context and risk controls. FX-specific context will additionally include session, spread, interest-rate/central-bank and currency-strength inputs.</p></div>`;
  }

  async function richerPerformance(){
    setActive('Performance');content.innerHTML='<div class="panel empty-state">Loading performance analytics…</div>';
    try{
      const accounts=(await api('/accounts')).filter(a=>a.provider==='ATLAS_PAPER');if(!accounts.length){content.innerHTML='<div class="panel empty-state">Create an ATLAS PAPER account first.</div>';return}
      const selected=window.phase11PerformanceAccount||accounts[0].id;window.phase11PerformanceAccount=selected;const p=await api(`/performance/${selected}`);const options=accounts.map(a=>`<option value="${a.id}" ${a.id===selected?'selected':''}>${escapeHtml(a.account_label)}</option>`).join('');const pf=p.profit_factor==null?'—':Number(p.profit_factor).toFixed(2);
      content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">PERFORMANCE ANALYTICS</p><h3>Account performance</h3><p class="muted">Visual trade analytics from actual closed ATLAS PAPER trades.</p></div><label>Account<select id="perfAccount">${options}</select></label></div><div class="summary-strip"><div class="metric-card"><span>Total P&L</span><strong>${money(p.total_realized_pnl)}</strong></div><div class="metric-card"><span>24h</span><strong>${money(p.daily_pnl)}</strong></div><div class="metric-card"><span>7d</span><strong>${money(p.weekly_pnl)}</strong></div><div class="metric-card"><span>30d</span><strong>${money(p.monthly_pnl)}</strong></div><div class="metric-card"><span>Win rate</span><strong>${Number(p.win_rate).toFixed(1)}%</strong></div><div class="metric-card"><span>Drawdown</span><strong>${Number(p.max_drawdown_pct).toFixed(2)}%</strong></div></div><div class="chart-grid"><div class="panel"><h3>Equity curve</h3>${sparkSvg(p.equity_curve)}</div><div class="panel"><h3>P&L by symbol</h3>${barSvg(p.by_symbol)}</div></div><div class="two-col"><div class="panel"><h3>Trade quality</h3><div class="status-list"><div class="status-item"><span>Profit factor</span><strong>${pf}</strong></div><div class="status-item"><span>Wins</span><strong>${p.wins}</strong></div><div class="status-item"><span>Losses</span><strong>${p.losses}</strong></div><div class="status-item"><span>Closed trades</span><strong>${p.closed_trades}</strong></div></div></div><div class="panel"><h3>Symbol breakdown</h3><div class="table-wrap"><table class="data-table"><thead><tr><th>Symbol</th><th>Trades</th><th>Win rate</th><th>P&L</th></tr></thead><tbody>${p.by_symbol.length?p.by_symbol.map(x=>`<tr><td>${escapeHtml(x.symbol)}</td><td>${x.trades}</td><td>${Number(x.win_rate).toFixed(1)}%</td><td>${money(x.realized_pnl)}</td></tr>`).join(''):'<tr><td colspan="4">No closed trades yet.</td></tr>'}</tbody></table></div></div></div>`;
      $('perfAccount').onchange=e=>{window.phase11PerformanceAccount=e.target.value;richerPerformance()};
    }catch(e){content.innerHTML=`<div class="panel empty-state">Performance unavailable: ${escapeHtml(e.message)}</div>`}
  }

  const prevRender=renderPage;renderPage=function(page){if(page==='Dashboard'){overallDashboard();return}if(page==='FX'){fxPage();return}if(page==='Performance'){richerPerformance();return}prevRender(page)};
})();