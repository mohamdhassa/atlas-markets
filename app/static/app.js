const state={token:localStorage.getItem('atlas_token'),user:null,page:'Dashboard'};
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

async function boot(){
  await checkSystem();
  if(!state.token){showLogin();return}
  try{state.user=await api('/auth/me');showApp()}catch{clearSession();showLogin()}
}

function showLogin(){loginView.hidden=false;appView.hidden=true}
function showApp(){
  loginView.hidden=true;appView.hidden=false;
  profileName.textContent=state.user.username;
  profileRole.textContent=state.user.role;
  avatar.textContent=state.user.username.slice(0,1).toUpperCase();
  buildNav();renderPage('Dashboard');
}
function clearSession(){state.token=null;state.user=null;localStorage.removeItem('atlas_token')}

loginForm.addEventListener('submit',async e=>{
  e.preventDefault();loginError.hidden=true;
  const button=document.getElementById('loginButton');button.disabled=true;button.textContent='Signing in…';
  try{
    const data=await api('/auth/login',{method:'POST',body:JSON.stringify({username:document.getElementById('username').value,password:document.getElementById('password').value})});
    state.token=data.access_token;state.user=data.user;localStorage.setItem('atlas_token',state.token);showApp();
  }catch(err){loginError.textContent=err.message;loginError.hidden=false}
  finally{button.disabled=false;button.textContent='Sign in'}
});

document.getElementById('logoutButton').addEventListener('click',async()=>{try{await api('/auth/logout',{method:'POST'})}catch{}clearSession();showLogin()});
document.getElementById('menuButton').addEventListener('click',()=>sidebar.classList.toggle('open'));

async function checkSystem(){
  try{const h=await api('/health');systemDot.className='status-dot good';systemText.textContent=`${h.service||'ATLAS MARKETS'} online`}
  catch{systemDot.className='status-dot bad';systemText.textContent='System unavailable'}
}

function buildNav(){
  nav.innerHTML='';
  addGroup('WORKSPACE',commonPages);
  if(state.user?.role==='ADMIN') addGroup('ADMIN',adminPages);
}
function addGroup(label,pages){
  const sep=document.createElement('div');sep.className='nav-separator';sep.textContent=label;nav.appendChild(sep);
  pages.forEach(page=>{const b=document.createElement('button');b.className='nav-button';b.textContent=page;b.onclick=()=>renderPage(page);b.dataset.page=page;nav.appendChild(b)});
}

function setActive(page){document.querySelectorAll('.nav-button').forEach(b=>b.classList.toggle('active',b.dataset.page===page));pageTitle.textContent=page;state.page=page;sidebar.classList.remove('open')}

function dashboard(){return `<div class="hero"><div class="panel"><p class="eyebrow">CONTROL CENTER</p><h3>Welcome back, ${escapeHtml(state.user.username)}</h3><p>ATLAS MARKETS is online. Trading modules will populate these panels as provider, market-data and execution phases are connected.</p></div><div class="panel"><span class="badge good">${state.user.role}</span><h3 style="margin-top:14px">Engine foundation</h3><p>Backend, database, Redis and authentication are active. Live trading remains disabled.</p></div></div><div class="metric-grid"><div class="metric-card"><span>Account equity</span><strong>—</strong></div><div class="metric-card"><span>Open positions</span><strong>0</strong></div><div class="metric-card"><span>Today's P&amp;L</span><strong>—</strong></div><div class="metric-card"><span>Active signals</span><strong>0</strong></div></div><div class="two-col"><div class="panel"><h3>Equity curve</h3><p>Performance history will appear here after account integration.</p><div class="placeholder-chart">Chart module reserved</div></div><div class="panel"><h3>System status</h3><div class="status-list"><div class="status-item"><span>FastAPI</span><span class="badge good">ONLINE</span></div><div class="status-item"><span>PostgreSQL</span><span class="badge good">CONNECTED</span></div><div class="status-item"><span>Redis</span><span class="badge good">CONNECTED</span></div><div class="status-item"><span>Trading engine</span><span class="badge warn">NOT CONNECTED</span></div></div></div></div>`}
function placeholder(page){return `<div class="page-intro"><div><p class="eyebrow">${page.toUpperCase()}</p><h3>${page}</h3><p class="muted">This workspace is ready for the upcoming ${page.toLowerCase()} implementation phase.</p></div><span class="badge">FRONTEND SHELL</span></div><div class="panel empty-state">No ${page.toLowerCase()} data yet. The page shell is active and waiting for backend integration.</div>`}

async function usersPage(){
  content.innerHTML='<div class="panel empty-state">Loading users…</div>';
  try{
    const users=await api('/admin/users');
    content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">ADMIN</p><h3>User management</h3><p class="muted">Application users and assigned access levels.</p></div><span class="badge good">${users.length} USERS</span></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Username</th><th>Email</th><th>Role</th><th>Status</th></tr></thead><tbody>${users.map(u=>`<tr><td>${escapeHtml(u.username)}</td><td>${escapeHtml(u.email||'—')}</td><td><span class="badge">${escapeHtml(u.role)}</span></td><td><span class="badge ${u.is_active?'good':'warn'}">${u.is_active?'ACTIVE':'DISABLED'}</span></td></tr>`).join('')}</tbody></table></div>`;
  }catch(err){content.innerHTML=`<div class="panel empty-state">${escapeHtml(err.message)}</div>`}
}

function renderPage(page){
  setActive(page);
  if(page==='Dashboard'){content.innerHTML=dashboard();return}
  if(page==='Users'&&state.user?.role==='ADMIN'){usersPage();return}
  content.innerHTML=placeholder(page);
}
function escapeHtml(v){return String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}

boot();
