const state={token:localStorage.getItem('atlas_token'),user:null,page:'Dashboard',marketTimer:null};
const loginView=document.getElementById('loginView');
const appView=document.getElementById('appView');
const loginForm=document.getElementById('loginForm');
const loginError=document.getElementById('loginError');
const nav=document.getElementById('nav');
const content=document.getElementById('content');
const pageTitle=document.getElementById('pageTitle');
const profileName=document.getElementById('profileName');
const profileRole=document.getElementById('profileRole');
const avatar=document.getElementById('avatar');
const systemDot=document.getElementById('systemDot');
const systemText=document.getElementById('systemText');
const sidebar=document.getElementById('sidebar');

const commonPages=['Dashboard','Markets','Charts','Signals','Positions','Orders','Performance','Accounts'];
const adminPages=['Users','Strategy','Risk','Integrations','System'];

async function api(path,options={}){
  const headers={...(options.headers||{})};
  if(options.body && !headers['Content-Type']) headers['Content-Type']='application/json';
  if(state.token) headers.Authorization=`Bearer ${state.token}`;
  const res=await fetch(path,{...options,headers});
  if(res.status===204) return null;
  let data=null;
  try{data=await res.json();}catch{}
  if(!res.ok){throw new Error(data?.detail||`Request failed (${res.status})`)}
  return data;
}

async function boot(){await checkSystem();if(!state.token){showLogin();return}try{state.user=await api('/auth/me');showApp()}catch{clearSession();showLogin()}}
function showLogin(){stopMarketTimer();loginView.hidden=false;appView.hidden=true}
function showApp(){loginView.hidden=true;appView.hidden=false;profileName.textContent=state.user.username;profileRole.textContent=state.user.role;avatar.textContent=state.user.username.slice(0,1).toUpperCase();buildNav();renderPage('Dashboard')}
function clearSession(){state.token=null;state.user=null;localStorage.removeItem('atlas_token')}
function stopMarketTimer(){if(state.marketTimer){clearInterval(state.marketTimer);state.marketTimer=null}}

loginForm.addEventListener('submit',async e=>{e.preventDefault();loginError.hidden=true;const button=document.getElementById('loginButton');button.disabled=true;button.textContent='Signing in…';try{const data=await api('/auth/login',{method:'POST',body:JSON.stringify({username:document.getElementById('username').value,password:document.getElementById('password').value})});state.token=data.access_token;state.user=data.user;localStorage.setItem('atlas_token',state.token);showApp()}catch(err){loginError.textContent=err.message;loginError.hidden=false}finally{button.disabled=false;button.textContent='Sign in'}});
document.getElementById('logoutButton').addEventListener('click',async()=>{try{await api('/auth/logout',{method:'POST'})}catch{}clearSession();showLogin()});
document.getElementById('menuButton').addEventListener('click',()=>sidebar.classList.toggle('open'));

async function checkSystem(){try{const h=await api('/health');systemDot.className='status-dot good';systemText.textContent=`${h.service||'ATLAS MARKETS'} online`}catch{systemDot.className='status-dot bad';systemText.textContent='System unavailable'}}
function buildNav(){nav.innerHTML='';addGroup('WORKSPACE',commonPages);if(state.user?.role==='ADMIN') addGroup('ADMIN',adminPages)}
function addGroup(label,pages){const sep=document.createElement('div');sep.className='nav-separator';sep.textContent=label;nav.appendChild(sep);pages.forEach(page=>{const b=document.createElement('button');b.className='nav-button';b.textContent=page;b.onclick=()=>renderPage(page);b.dataset.page=page;nav.appendChild(b)})}
function setActive(page){stopMarketTimer();document.querySelectorAll('.nav-button').forEach(b=>b.classList.toggle('active',b.dataset.page===page));pageTitle.textContent=page;state.page=page;sidebar.classList.remove('open')}

function dashboard(){return `<div class="hero"><div class="panel"><p class="eyebrow">CONTROL CENTER</p><h3>Welcome back, ${escapeHtml(state.user.username)}</h3><p>ATLAS MARKETS is online. Phase 5 now connects the workspace to normalized Bybit public market data while trading execution remains disabled.</p></div><div class="panel"><span class="badge good">${state.user.role}</span><h3 style="margin-top:14px">Market data active</h3><p>Open Markets for live quotes or Charts for current Bybit candle history.</p></div></div><div class="metric-grid"><div class="metric-card"><span>Account equity</span><strong>—</strong></div><div class="metric-card"><span>Open positions</span><strong>0</strong></div><div class="metric-card"><span>Today's P&amp;L</span><strong>—</strong></div><div class="metric-card"><span>Active signals</span><strong>0</strong></div></div><div class="two-col"><div class="panel"><h3>Trading performance</h3><p>Equity history will appear after broker account integration.</p><div class="placeholder-chart">Performance module reserved</div></div><div class="panel"><h3>System status</h3><div class="status-list"><div class="status-item"><span>FastAPI</span><span class="badge good">ONLINE</span></div><div class="status-item"><span>PostgreSQL</span><span class="badge good">CONNECTED</span></div><div class="status-item"><span>Redis</span><span class="badge good">CONNECTED</span></div><div class="status-item"><span>Bybit market data</span><span class="badge good">AVAILABLE</span></div><div class="status-item"><span>Trading engine</span><span class="badge warn">NOT CONNECTED</span></div></div></div></div>`}
function placeholder(page){return `<div class="page-intro"><div><p class="eyebrow">${page.toUpperCase()}</p><h3>${page}</h3><p class="muted">This workspace is ready for the upcoming ${page.toLowerCase()} implementation phase.</p></div><span class="badge">FRONTEND SHELL</span></div><div class="panel empty-state">No ${page.toLowerCase()} data yet. The page shell is active and waiting for backend integration.</div>`}

async function marketsPage(){
  content.innerHTML='<div class="panel empty-state">Loading live Bybit market data…</div>';
  const load=async()=>{try{const snap=await api('/markets/tickers?category=linear');if(state.page!=='Markets')return;content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">LIVE MARKET DATA</p><h3>Crypto perpetual markets</h3><p class="muted">Normalized public Bybit quotes. Auto-refreshes every 10 seconds.</p></div><span class="badge good">${escapeHtml(snap.provider)} · ${snap.count} SYMBOLS</span></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Symbol</th><th>Last</th><th>24h</th><th>Bid</th><th>Ask</th><th>24h High</th><th>24h Low</th><th>Volume</th></tr></thead><tbody>${snap.tickers.map(t=>`<tr><td><strong>${escapeHtml(t.symbol)}</strong></td><td>${money(t.last_price)}</td><td><span class="badge ${Number(t.change_24h_pct)>=0?'good':'warn'}">${pct(t.change_24h_pct)}</span></td><td>${money(t.bid_price)}</td><td>${money(t.ask_price)}</td><td>${money(t.high_24h)}</td><td>${money(t.low_24h)}</td><td>${compact(t.volume_24h)}</td></tr>`).join('')}</tbody></table></div><p class="muted" style="margin-top:12px">Fetched ${new Date(snap.fetched_at).toLocaleTimeString()}</p>`}catch(err){if(state.page==='Markets')content.innerHTML=`<div class="panel empty-state">Market data unavailable: ${escapeHtml(err.message)}</div>`}};
  await load();state.marketTimer=setInterval(load,10000);
}

async function chartsPage(){
  content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">MARKET CHART</p><h3>Bybit candles</h3><p class="muted">Select a symbol and timeframe to inspect normalized OHLCV history.</p></div><div><select id="chartSymbol"><option>BTCUSDT</option><option>ETHUSDT</option><option>SOLUSDT</option><option>XRPUSDT</option><option>BNBUSDT</option></select> <select id="chartInterval"><option value="1m">1m</option><option value="5m" selected>5m</option><option value="15m">15m</option><option value="1h">1h</option><option value="4h">4h</option><option value="1d">1d</option></select></div></div><div class="panel"><div id="chartHost" class="placeholder-chart">Loading candles…</div></div><div id="candleStats" class="metric-grid" style="margin-top:18px"></div>`;
  const symbolEl=document.getElementById('chartSymbol');const intervalEl=document.getElementById('chartInterval');const load=async()=>{const host=document.getElementById('chartHost');if(!host)return;host.textContent='Loading candles…';try{const candles=await api(`/markets/candles/${symbolEl.value}?interval=${intervalEl.value}&category=linear&limit=120`);if(!candles.length){host.textContent='No candle data returned';return}renderLineChart(host,candles);const last=candles[candles.length-1];const first=candles[0];document.getElementById('candleStats').innerHTML=`<div class="metric-card"><span>Last close</span><strong>${money(last.close)}</strong></div><div class="metric-card"><span>Period high</span><strong>${money(Math.max(...candles.map(c=>c.high)))}</strong></div><div class="metric-card"><span>Period low</span><strong>${money(Math.min(...candles.map(c=>c.low)))}</strong></div><div class="metric-card"><span>Window change</span><strong>${pct(((last.close-first.open)/first.open)*100)}</strong></div>`}catch(err){host.textContent=`Chart unavailable: ${err.message}`}};symbolEl.onchange=load;intervalEl.onchange=load;await load();
}

function renderLineChart(host,candles){const w=900,h=260,p=18;const values=candles.map(c=>c.close);const min=Math.min(...values),max=Math.max(...values);const span=max-min||1;const points=values.map((v,i)=>`${p+(i/(values.length-1||1))*(w-p*2)},${h-p-((v-min)/span)*(h-p*2)}`).join(' ');host.innerHTML=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Close price chart" style="width:100%;height:100%"><polyline points="${points}" fill="none" stroke="currentColor" stroke-width="3" vector-effect="non-scaling-stroke"/><line x1="${p}" y1="${h-p}" x2="${w-p}" y2="${h-p}" stroke="currentColor" opacity=".2"/></svg>`}

async function usersPage(){content.innerHTML='<div class="panel empty-state">Loading users…</div>';try{const users=await api('/admin/users');content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">ADMIN</p><h3>User management</h3><p class="muted">Application users and assigned access levels.</p></div><span class="badge good">${users.length} USERS</span></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Username</th><th>Email</th><th>Role</th><th>Status</th></tr></thead><tbody>${users.map(u=>`<tr><td>${escapeHtml(u.username)}</td><td>${escapeHtml(u.email||'—')}</td><td><span class="badge">${escapeHtml(u.role)}</span></td><td><span class="badge ${u.is_active?'good':'warn'}">${u.is_active?'ACTIVE':'DISABLED'}</span></td></tr>`).join('')}</tbody></table></div>`}catch(err){content.innerHTML=`<div class="panel empty-state">${escapeHtml(err.message)}</div>`}}

function renderPage(page){setActive(page);if(page==='Dashboard'){content.innerHTML=dashboard();return}if(page==='Markets'){marketsPage();return}if(page==='Charts'){chartsPage();return}if(page==='Users'&&state.user?.role==='ADMIN'){usersPage();return}content.innerHTML=placeholder(page)}
function money(v){if(v===null||v===undefined||Number.isNaN(Number(v)))return '—';const n=Number(v);return n>=1000?n.toLocaleString(undefined,{maximumFractionDigits:2}):n.toLocaleString(undefined,{maximumFractionDigits:6})}
function pct(v){if(v===null||v===undefined||Number.isNaN(Number(v)))return '—';const n=Number(v);return `${n>=0?'+':''}${n.toFixed(2)}%`}
function compact(v){if(v===null||v===undefined||Number.isNaN(Number(v)))return '—';return Intl.NumberFormat(undefined,{notation:'compact',maximumFractionDigits:2}).format(Number(v))}
function escapeHtml(v){return String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}

boot();
