(()=>{
const KEY='atlas_scope_v42';
const DEFAULT={provider:'ALL',account:'ALL',market:'ALL',symbol:'ALL'};
let scope={...DEFAULT};
try{scope={...DEFAULT,...JSON.parse(sessionStorage.getItem(KEY)||'{}')}}catch{}
let cache={accounts:[],strategies:[]};
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function save(){sessionStorage.setItem(KEY,JSON.stringify(scope));document.dispatchEvent(new CustomEvent('atlas:scope-changed',{detail:{...scope}}))}
function accountForStrategy(s){return cache.accounts.find(a=>String(a.id)===String(s.profile_id))}
function matchesStrategy(s){const a=accountForStrategy(s);return (scope.provider==='ALL'||a?.provider===scope.provider)&&(scope.account==='ALL'||String(s.profile_id)===scope.account)&&(scope.market==='ALL'||s.market===scope.market)&&(scope.symbol==='ALL'||s.symbol===scope.symbol)}
function matchesRow(row){return (scope.provider==='ALL'||row.provider===scope.provider)&&(scope.account==='ALL'||String(row.profile_id||row.broker_profile_id||'')===scope.account)&&(scope.market==='ALL'||String(row.market||'').toUpperCase()===scope.market)&&(scope.symbol==='ALL'||String(row.symbol||'').toUpperCase()===scope.symbol)}
function normalize(){
 const providers=[...new Set(cache.accounts.map(a=>a.provider))];if(scope.provider!=='ALL'&&!providers.includes(scope.provider))scope.provider='ALL';
 const providerAccounts=cache.accounts.filter(a=>scope.provider==='ALL'||a.provider===scope.provider);if(scope.account!=='ALL'&&!providerAccounts.some(a=>String(a.id)===scope.account))scope.account='ALL';
 const rows=cache.strategies.filter(s=>{const a=accountForStrategy(s);return (scope.provider==='ALL'||a?.provider===scope.provider)&&(scope.account==='ALL'||String(s.profile_id)===scope.account)});
 const markets=[...new Set(rows.map(s=>s.market))];if(scope.market!=='ALL'&&!markets.includes(scope.market))scope.market='ALL';
 const syms=[...new Set(rows.filter(s=>scope.market==='ALL'||s.market===scope.market).map(s=>s.symbol))];if(scope.symbol!=='ALL'&&!syms.includes(scope.symbol))scope.symbol='ALL';
}
async function refresh(){try{const [accounts,strategies]=await Promise.all([api('/accounts'),api('/strategies/symbols')]);cache={accounts,strategies};normalize();render()}catch(e){render(String(e.message||e))}}
function options(values,current,label){return `<option value="ALL">All ${label}</option>`+values.map(v=>`<option value="${esc(v.value)}" ${String(current)===String(v.value)?'selected':''}>${esc(v.label)}</option>`).join('')}
function render(error){
 let host=document.getElementById('atlasScopeBar');
 if(!host){const main=document.querySelector('.main-area');const content=document.getElementById('content');if(!main||!content)return;host=document.createElement('div');host.id='atlasScopeBar';host.className='atlas-scope-bar';main.insertBefore(host,content)}
 if(error){host.innerHTML=`<div class="atlas-scope-title"><strong>Scope</strong><span class="muted">${esc(error)}</span></div>`;return}
 normalize();
 const providerVals=[...new Set(cache.accounts.map(a=>a.provider))].sort().map(x=>({value:x,label:x}));
 const accountVals=cache.accounts.filter(a=>scope.provider==='ALL'||a.provider===scope.provider).map(a=>({value:String(a.id),label:`${a.account_label} · ${a.environment}`}));
 const baseRows=cache.strategies.filter(s=>{const a=accountForStrategy(s);return (scope.provider==='ALL'||a?.provider===scope.provider)&&(scope.account==='ALL'||String(s.profile_id)===scope.account)});
 const marketVals=[...new Set(baseRows.map(s=>s.market))].sort().map(x=>({value:x,label:x}));
 const symbolVals=[...new Set(baseRows.filter(s=>scope.market==='ALL'||s.market===scope.market).map(s=>s.symbol))].sort().map(x=>({value:x,label:x}));
 host.innerHTML=`<div class="atlas-scope-title"><strong>Working scope</strong><span class="muted">System → Provider → Account → Market → Symbol</span></div><div class="atlas-scope-fields"><label>Provider<select id="atlasScopeProvider">${options(providerVals,scope.provider,'providers')}</select></label><label>Account<select id="atlasScopeAccount">${options(accountVals,scope.account,'accounts')}</select></label><label>Market<select id="atlasScopeMarket">${options(marketVals,scope.market,'markets')}</select></label><label>Symbol<select id="atlasScopeSymbol">${options(symbolVals,scope.symbol,'symbols')}</select></label><button type="button" class="ghost-button atlas-scope-reset" id="atlasScopeReset">Reset</button></div>`;
 const bind=(id,key,children)=>{const el=document.getElementById(id);if(!el)return;el.onchange=()=>{scope[key]=el.value;children.forEach(k=>scope[k]='ALL');save();render()}};
 bind('atlasScopeProvider','provider',['account','market','symbol']);bind('atlasScopeAccount','account',['market','symbol']);bind('atlasScopeMarket','market',['symbol']);bind('atlasScopeSymbol','symbol',[]);
 document.getElementById('atlasScopeReset').onclick=()=>{scope={...DEFAULT};save();render()};
}
function setScope(next){scope={...scope,...next};normalize();save();render()}
function getScope(){return {...scope}}
const css=document.createElement('style');css.textContent=`.atlas-scope-bar{display:flex;gap:14px;align-items:end;justify-content:space-between;padding:12px 28px;border-bottom:1px solid var(--line);background:rgba(8,17,28,.82);position:sticky;top:86px;z-index:7;backdrop-filter:blur(12px)}.atlas-scope-title{display:grid;gap:2px;min-width:170px}.atlas-scope-title .muted{font-size:.72rem}.atlas-scope-fields{display:flex;gap:8px;align-items:end;flex-wrap:wrap;justify-content:flex-end}.atlas-scope-fields label{display:grid;gap:4px;color:var(--muted);font-size:.68rem}.atlas-scope-fields select{min-width:120px;background:#09131f;border:1px solid var(--line);color:var(--text);border-radius:9px;padding:8px 28px 8px 9px}.atlas-scope-reset{width:auto;padding:8px 12px}@media(max-width:900px){.atlas-scope-bar{position:static;padding:12px 18px;align-items:stretch;flex-direction:column}.atlas-scope-fields{justify-content:stretch;display:grid;grid-template-columns:1fr 1fr}.atlas-scope-fields select{width:100%;min-width:0}.atlas-scope-reset{width:100%}}@media(max-width:520px){.atlas-scope-fields{grid-template-columns:1fr}}`;document.head.appendChild(css);
window.AtlasScope={get:getScope,set:setScope,refresh,matchesStrategy,matchesRow,accounts:()=>cache.accounts.slice(),strategies:()=>cache.strategies.slice()};
const oldShow=window.showApp;if(typeof oldShow==='function')window.showApp=function(){const r=oldShow.apply(this,arguments);setTimeout(refresh,0);return r};
document.addEventListener('atlas:scope-refresh',refresh);if(state?.token)setTimeout(refresh,0);
})();