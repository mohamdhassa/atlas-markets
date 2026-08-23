(()=>{
const catalog={
 ATLAS_PAPER:{label:'ATLAS PAPER',envs:['PAPER'],hint:'Internal paper portfolio. No external credentials.'},
 BYBIT:{label:'BYBIT',envs:['TESTNET','DEMO','LIVE'],hint:'Crypto. Use TESTNET for Bybit Testnet API keys; LIVE for production keys.'},
 TWELVE_DATA:{label:'TWELVE DATA',envs:['LIVE'],hint:'Market-data provider. API keys use the production API environment; this does not enable trading.'},
 MT5:{label:'METATRADER 5 / FUSION MARKETS',envs:['DEMO','LIVE'],hint:'FX, metals and commodities. DEMO uses FusionMarkets-Demo; LIVE uses the live server.'},
 IBKR:{label:'INTERACTIVE BROKERS',envs:['PAPER','LIVE'],hint:'Stocks/ETFs and supported exchange products. Configure later.'}
};
async function renderAccounts(){
 setActive('Accounts');
 const [accounts,users]=await Promise.all([api('/accounts'),state.user.role==='ADMIN'?api('/admin/users'):Promise.resolve([])]);
 const owner=state.user.role==='ADMIN'?`<label>Owner<select id="p20Owner">${users.map(u=>`<option value="${u.id}">${escapeHtml(u.username)} · ${u.role}</option>`).join('')}</select></label>`:'';
 const providerOptions=Object.entries(catalog).map(([v,c])=>`<option value="${v}">${c.label}</option>`).join('');
 content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">PROVIDER INTEGRATION</p><h3>Unified provider accounts</h3><p class="muted">Provider-specific environments are enforced by ATLAS. Demo/Testnet and LIVE profiles can coexist; selecting LIVE never authorizes real orders.</p></div><span class="badge">PHASE 20</span></div><div class="panel form-panel"><h3>Add provider</h3><form id="p20Form" class="form-grid"><label>Connection label<input id="p20Label" required placeholder="Bybit Testnet"></label><label>Provider<select id="p20Provider">${providerOptions}</select></label><label>Environment<select id="p20Env"></select></label><label>Account reference (optional)<input id="p20Ref" placeholder="Account number / reference"></label>${owner}<div class="form-actions"><button class="primary-button" type="submit">Add provider</button><span id="p20Msg" class="muted"></span></div></form><p id="p20Hint" class="muted"></p></div><div class="analysis-grid">${accounts.map(a=>typeof phase17AccountCard==='function'?phase17AccountCard(a,{allow_live_trading:false}):`<div class="analysis-card"><h4>${escapeHtml(a.account_label)}</h4><span>${escapeHtml(a.provider)} · ${escapeHtml(a.environment)}</span></div>`).join('')}</div>`;
 const p=$('p20Provider'),e=$('p20Env'),hint=$('p20Hint');
 const refresh=()=>{const c=catalog[p.value];e.innerHTML=c.envs.map(v=>`<option value="${v}">${v}</option>`).join('');hint.textContent=c.hint;const label=$('p20Label');if(!label.value)label.placeholder=c.label+(c.envs[0]?` ${c.envs[0]}`:'')};p.onchange=refresh;refresh();
 $('p20Form').onsubmit=async ev=>{ev.preventDefault();const allowed=catalog[p.value]?.envs||[];if(!allowed.includes(e.value)){ $('p20Msg').textContent=`${p.value} does not support ${e.value}. Choose: ${allowed.join(', ')}`;return;}const body={account_label:$('p20Label').value.trim(),provider:p.value,environment:e.value,external_account_ref:$('p20Ref').value.trim()||null};if($('p20Owner'))body.owner_user_id=$('p20Owner').value;try{await api('/accounts',{method:'POST',body:JSON.stringify(body)});await renderAccounts()}catch(err){$('p20Msg').textContent=err.message}};
 document.querySelectorAll('[data-activate-account]').forEach(b=>b.onclick=()=>phase17Action(b.dataset.activateAccount,'activate'));document.querySelectorAll('[data-save-provider-creds]').forEach(b=>b.onclick=()=>phase17SaveCreds(b.dataset.saveProviderCreds,b.dataset.provider));document.querySelectorAll('[data-test-account]').forEach(b=>b.onclick=()=>phase17Action(b.dataset.testAccount,'test'));document.querySelectorAll('[data-sync-account]').forEach(b=>b.onclick=()=>phase17Action(b.dataset.syncAccount,'sync'));document.querySelectorAll('[data-live-account]').forEach(b=>b.onclick=()=>phase17Live(b.dataset.liveAccount,b.dataset.liveEnabled==='true'));
}
const previous=renderPage;renderPage=function(page){if(page==='Accounts'){renderAccounts().catch(err=>content.innerHTML=`<div class="panel empty-state">Accounts unavailable: ${escapeHtml(err.message)}</div>`);return}return previous(page)};
window.AtlasPhase20={renderAccounts,catalog};
})();
