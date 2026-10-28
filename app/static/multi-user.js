/* User/account onboarding with explicit owner and administrator boundaries. */
(()=>{'use strict';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let epoch=0;
const admin=()=>state.user?.role==='ADMIN';
const button=(label,action,id)=>`<button type="button" class="mu-button ${['add','role','activate'].includes(action)?'mu-primary':action==='toggle'?'mu-caution':''}" data-action="${action}" data-id="${esc(id)}">${esc(label)}</button>`;
const field=(label,name,type='text',extra='')=>`<label>${label}<input name="${name}" type="${type}" autocomplete="${type==='password'?'new-password':'off'}" ${extra}></label>`;
const message=(text,bad=false)=>{const el=document.getElementById('muMessage');if(el){el.textContent=text;el.setAttribute('role',bad?'alert':'status')}};
function bind(root,action){root.querySelectorAll('[data-action]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await action(b.dataset.action,b.dataset.id)}catch(e){message(e.message,true)}finally{b.disabled=false}})}
const badge=(text,tone='neutral')=>`<span class="mu-badge mu-${tone}">${esc(text)}</span>`;
const stats=items=>`<div class="mu-stats">${items.map(([label,value])=>`<div><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join('')}</div>`;
const heading=(eyebrow,title,description)=>`<header class="mu-heading"><p class="eyebrow">${eyebrow}</p><h3>${title}</h3><p>${description}</p></header>`;
async function users(){
 const ticket=++epoch;setActive('Users');content.innerHTML='<div class="panel">Loading users…</div>';
 if(!admin()){content.innerHTML='<div class="panel">Administrator access required.</div>';return}
 try{
 const [rows,accounts]=await Promise.all([api('/admin/users'),api('/accounts')]);if(ticket!==epoch)return;
 content.innerHTML=`<div class="mu-workspace">${heading('ADMINISTRATION','Users & access','Manage the people who can access ATLAS and their connected accounts.')}${stats([['Total users',rows.length],['Enabled',rows.filter(u=>u.is_active).length],['Administrators',rows.filter(u=>u.is_active&&u.role==='ADMIN').length]])}<div id="muMessage" role="status" aria-live="polite"></div><details class="panel mu-disclosure"><summary><span><strong>Create user</strong><small>Add a login and assign access</small></span><span class="mu-disclosure-icon" aria-hidden="true">+</span></summary><form id="muCreate" class="mu-form">${field('Username','username','text','required minlength="3" maxlength="64" pattern="[A-Za-z0-9_.-]+"')}${field('Email (optional)','email','email')}${field('Initial password','password','password','required minlength="12" maxlength="256"')}<label>Role<select name="role"><option>USER</option><option>ADMIN</option></select></label><p class="mu-help">Use at least 12 characters. Share the initial password privately.</p><button class="mu-primary">Create user</button></form></details><div id="muEditor"></div><div class="mu-section-title"><h3>People</h3><span>${rows.length} users</span></div><div class="mu-grid">${rows.map(u=>`<section class="panel mu-card"><div class="mu-card-heading"><span class="mu-avatar" aria-hidden="true">${esc(u.username.slice(0,2).toUpperCase())}</span><div><h3>${esc(u.username)}${u.id===state.user.id?' <small>(you)</small>':''}</h3><p>${esc(u.email||'No email added')}</p></div>${badge(u.is_active?'Enabled':'Suspended',u.is_active?'good':'warn')}</div><div class="mu-card-meta"><span>${esc(u.role==='ADMIN'?'Administrator':'User')}</span><span>${accounts.filter(a=>a.user_id===u.id).length} broker profiles</span></div><div class="mu-role-control"><label>Account role<select data-role="${esc(u.id)}"><option ${u.role==='USER'?'selected':''}>USER</option><option ${u.role==='ADMIN'?'selected':''}>ADMIN</option></select></label>${button('Save role','role',u.id)}</div><div class="mu-card-footer">${button(u.is_active?'Suspend user':'Enable user','toggle',u.id)}${button('Reset password','password',u.id)}</div></section>`).join('')||'<section class="panel mu-empty">No users to display.</section>'}</div><p class="mu-footnote">Suspending a user blocks new automated entries. Existing broker positions remain open.</p></div>`;
 document.getElementById('muCreate').onsubmit=async e=>{e.preventDefault();const f=e.currentTarget,b=f.querySelector('button'),v=Object.fromEntries(new FormData(f));v.email=v.email||null;b.disabled=true;try{await api('/admin/users',{method:'POST',body:JSON.stringify(v)});f.reset();await users();message('User created. Share their initial password privately.')}catch(ex){message(ex.message,true)}finally{b.disabled=false}};
 bind(content,async(action,id)=>{
  const u=rows.find(u=>u.id===id);if(!u)return;
  if(action==='password'){
   document.getElementById('muEditor').innerHTML=`<section class="panel"><h3>Reset password for ${esc(u.username)}</h3><form id="muReset" class="mu-form">${field('New password','password','password','required minlength="12" maxlength="256"')}<button class="mu-primary">Reset and revoke sessions</button></form></section>`;
   document.getElementById('muReset').onsubmit=async e=>{e.preventDefault();const f=e.currentTarget,b=f.querySelector('button');b.disabled=true;try{await api(`/admin/users/${id}/reset-password`,{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(f)))});f.reset();document.getElementById('muEditor').innerHTML='';message('Password reset; existing sessions revoked.')}catch(ex){message(ex.message,true)}finally{b.disabled=false}};return;
  }
  const patch=action==='toggle'?{is_active:!u.is_active}:{role:content.querySelector(`[data-role="${id}"]`).value};
  if(!confirm(`${action==='toggle'?(u.is_active?'Suspend':'Enable'):'Change role for'} ${u.username}?`))return;
  await api(`/admin/users/${id}`,{method:'PATCH',body:JSON.stringify(patch)});
  if(id===state.user.id&&patch.role){state.user.role=patch.role;buildNav();if(!admin()){await renderPage('Accounts');return}}
  await users();message('User access updated. Existing broker positions were not closed.');
 });
 }catch(e){if(ticket===epoch)content.innerHTML=`<section class="panel" role="alert">${esc(e.message)}</section>`}
}
async function accounts(){
 const ticket=++epoch;setActive('Accounts');content.innerHTML='<div class="panel">Loading broker accounts…</div>';
 try{
 const [rows,caps,users]=await Promise.all([api('/accounts'),api('/accounts/capabilities'),admin()?api('/admin/users'):Promise.resolve([])]);if(ticket!==epoch)return;
 const names=new Map(users.map(u=>[u.id,u.username]));
 content.innerHTML=`<div class="mu-workspace">${heading(admin()?'ACCOUNT ADMINISTRATION':'MY ACCOUNTS','Broker connections','Manage your broker accounts, connection checks and account access.')}${stats([['Connections',rows.length],['Active',rows.filter(a=>a.is_enabled&&a.is_active).length],['Disabled',rows.filter(a=>!a.is_enabled).length]])}<div id="muMessage" role="status" aria-live="polite"></div><section class="mu-toolbar"><div><h3>Connected accounts</h3><p>Test or sync a connection before activating it.</p></div><div class="mu-toolbar-controls">${admin()?'<label>Account owner<select id="muOwnerFilter"><option value="">All users</option>'+users.map(u=>`<option value="${esc(u.id)}">${esc(u.username)}</option>`).join('')+'</select></label>':''}${button('Add broker account','add','')}</div></section><div id="muEditor"></div><div id="muCards" class="mu-grid">${rows.map(a=>`<section class="panel mu-card" data-owner="${esc(a.user_id)}"><div class="mu-card-heading"><span class="mu-avatar mu-broker" aria-hidden="true">${esc(a.provider==='TWELVE_DATA'?'TD':a.provider.slice(0,2))}</span><div><p class="eyebrow">${esc(a.provider)} · ${esc(a.environment)}</p><h3>${esc(a.account_label)}</h3></div>${badge(!a.is_enabled?'Disabled':a.is_active?'Active':'Standby',!a.is_enabled?'warn':a.is_active?'good':'neutral')}</div><dl class="mu-facts">${admin()?`<div><dt>Owner</dt><dd>${esc(names.get(a.user_id)||'Unknown user')}</dd></div>`:''}<div><dt>Account</dt><dd>${esc(a.external_account_ref||'Pending verification')}</dd></div><div><dt>Connection</dt><dd>${esc((a.last_connection_status||'Not checked').replaceAll('_',' '))}</dd></div></dl><div class="mu-card-footer">${button('Test connection','test',a.id)}${button('Sync balance','sync',a.id)}${a.is_enabled&&!a.is_active?button('Activate','activate',a.id):''}</div>${admin()||a.is_enabled||a.provider==='BYBIT'?`<details class="mu-advanced"><summary>Manage account</summary><div class="mu-actions">${admin()||a.is_enabled?button(a.is_enabled?'Disable':'Enable','toggle',a.id):''}${admin()||a.provider==='BYBIT'?button('Replace credentials','credentials',a.id):''}</div></details>`:''}${!a.is_enabled&&!admin()?'<p class="mu-help">Ask your administrator to re-enable this account.</p>':''}</section>`).join('')||'<section class="panel mu-empty"><h3>No broker accounts yet</h3><p>Add a Bybit connection or request an isolated IBKR Paper connection below.</p></section>'}</div><div id="muFilterEmpty" class="mu-empty" hidden>No accounts for this owner.</div><div id="muSetupSlot"></div><p class="mu-footnote">Connecting or activating an account does not bypass trading certification or risk controls.</p></div>`;
 const filter=document.getElementById('muOwnerFilter');if(filter)filter.onchange=()=>{const cards=[...content.querySelectorAll('[data-owner]')];cards.forEach(el=>el.hidden=!!filter.value&&el.dataset.owner!==filter.value);document.getElementById('muFilterEmpty').hidden=!cards.length||cards.some(el=>!el.hidden)};
 const form=(profile=null)=>{
  const allowed=admin()?['BYBIT','IBKR','MT5','TWELVE_DATA']:['BYBIT'];
  const editor=document.getElementById('muEditor');
  editor.innerHTML=`<section class="panel mu-editor"><div class="mu-editor-heading"><h3>${profile?'Replace credentials':'Connect account'}</h3><button type="button" id="muCancel">Cancel</button></div><p class="mu-help">Secrets are encrypted and never shown again. Use Bybit keys without withdrawal permissions. Replacing credentials requires a new broker validation.</p><form id="muConnect" class="mu-form">${profile?`<p>${esc(profile.provider)} · ${esc(profile.account_label)}</p>`:`<label>Provider<select name="provider" id="muProvider">${allowed.map(p=>`<option>${p}</option>`).join('')}</select></label><label>Environment<select name="environment" id="muEnvironment"></select></label>${field('Account label','account_label','text','required minlength="2" maxlength="96"')}${admin()?'<label>Owner<select name="owner_user_id">'+users.filter(u=>u.is_active).map(u=>`<option value="${esc(u.id)}" ${u.id===state.user.id?'selected':''}>${esc(u.username)}</option>`).join('')+'</select></label>':''}`}<div id="muCredentialFields" class="mu-form-fields"></div>${profile?'':'<label class="mu-check"><input type="checkbox" name="activate"> Activate after validation</label>'}<button class="mu-primary">Validate & save</button></form><p>Live execution remains separately gated. Connecting an account does not enable trading.</p></section>`;
  document.getElementById('muCancel').onclick=()=>{editor.innerHTML=''};
  editor.scrollIntoView?.({behavior:'smooth',block:'start'});
  const refresh=()=>{const provider=profile?.provider||document.getElementById('muProvider').value,env=document.getElementById('muEnvironment');if(env)env.innerHTML=(caps.providers[provider]||[]).slice().sort((a,b)=>(a==='LIVE')-(b==='LIVE')).map(v=>`<option>${esc(v)}</option>`).join('');const fields=provider==='IBKR'?['account_id','bridge_url','bridge_token']:caps.credential_fields[provider]||[];document.getElementById('muCredentialFields').innerHTML=fields.map(k=>field(k.replaceAll('_',' '),k,k.includes('secret')||k.includes('token')||k.includes('password')||k==='api_key'?'password':'text',k==='bridge_token'?'':'required')).join('')+(provider==='IBKR'?'<p>Admin: use this owner’s isolated bridge address and token. Never reuse another user’s Gateway session.</p>':'')};
  if(!profile)document.getElementById('muProvider').onchange=refresh;refresh();
  document.getElementById('muConnect').onsubmit=async e=>{
   e.preventDefault();const f=e.currentTarget,b=f.querySelector('button'),v=Object.fromEntries(new FormData(f)),provider=profile?.provider||v.provider;
   const body=profile?{}:{provider,environment:v.environment,account_label:v.account_label,activate:v.activate==='on'};
   if(v.owner_user_id)body.owner_user_id=v.owner_user_id;
   if(provider==='BYBIT'){body.api_key=v.api_key;body.api_secret=v.api_secret}
   else if(provider==='TWELVE_DATA')body.api_key=v.api_key;
   else{body.credentials={};(provider==='IBKR'?['account_id','bridge_url','bridge_token']:caps.credential_fields[provider]||[]).forEach(k=>{if(v[k])body.credentials[k]=v[k]})}
   const url=profile?(provider==='IBKR'?`/ibkr/${profile.id}/credentials`:`/accounts/${profile.id}/credentials`):(provider==='IBKR'?'/ibkr/connect':'/accounts/connect');
   b.disabled=true;try{await api(url,{method:profile?'PUT':'POST',body:JSON.stringify(body)});f.reset();await renderPage('Accounts');message('Connection validated and saved. Configure strategies separately.')}catch(ex){message(ex.message,true)}finally{b.disabled=false}
  };
 };
 bind(content,async(action,id)=>{
  if(action==='add'){form();return}const a=rows.find(a=>a.id===id);if(!a)return;
  if(action==='credentials'){form(a);return}
  if(action==='toggle'&&!confirm(`${a.is_enabled?'Disable':'Enable'} ${a.account_label}? This does not close broker positions.`))return;
  const url=a.provider==='IBKR'&&['test','sync'].includes(action)?`/ibkr/${id}/${action}`:`/accounts/${id}/${action}`;
  await api(url,{method:action==='toggle'?'PATCH':'POST'});await renderPage('Accounts');message('Account action completed.');
 });
 }catch(e){if(ticket===epoch)content.innerHTML=`<section class="panel" role="alert">${esc(e.message)}</section>`}
}
const previous=renderPage;
renderPage=async function(page){if(page==='Users')return users();if(page==='Accounts')return accounts();++epoch;return previous(page)};
window.AtlasMultiUser={users,accounts};
})();
