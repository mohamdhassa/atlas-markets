from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.mark.skipif(not shutil.which('node'),reason='Node required for frontend runtime')
def test_user_admin_forms_and_late_account_responses():
    result=subprocess.run(['node','-e',r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map();
const element=()=>({innerHTML:'',textContent:'',dataset:{},querySelectorAll:()=>[],setAttribute(){},querySelector:()=>({disabled:false})});
const root=element();let role='USER',resolveAccounts,requests=[];
const context={state:{user:{id:'alice',role}},content:root,window:{},
 document:{getElementById:id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id)}},
 renderPage:async page=>{root.innerHTML=page},setActive(){},buildNav(){},confirm:()=>true,
 api:async path=>{requests.push(path);if(path==='/accounts')return new Promise(resolve=>resolveAccounts=resolve);
 if(path==='/admin/users')return [{id:'alice',username:'Alice',role:'USER',is_active:true}];
 if(path==='/accounts/capabilities')return {providers:{BYBIT:['TESTNET'],IBKR:['PAPER']},credential_fields:{BYBIT:['api_key','api_secret']}};
 return []}};
vm.createContext(context);vm.runInContext(fs.readFileSync('app/static/multi-user.js','utf8'),context);
(async()=>{
 let pending=context.renderPage('Accounts');await Promise.resolve();
 assert(!requests.includes('/admin/users'));
 await context.renderPage('Dashboard');resolveAccounts([]);await pending;
 assert.equal(root.innerHTML,'Dashboard');
 requests=[];pending=context.renderPage('Accounts');await Promise.resolve();resolveAccounts([]);await pending;
 assert(root.innerHTML.includes('administrator-assigned Gateway'));
 assert(!root.innerHTML.includes('muOwnerFilter'));
 context.state.user.role='ADMIN';requests=[];
 pending=context.renderPage('Accounts');await Promise.resolve();resolveAccounts([]);await pending;
 assert(requests.includes('/admin/users'));assert(root.innerHTML.includes('muOwnerFilter'));
 pending=context.renderPage('Users');await Promise.resolve();resolveAccounts([]);await pending;
 assert(root.innerHTML.includes('Suspend user'));assert(root.innerHTML.includes('Reset password'));
 assert(root.innerHTML.includes('Save role'));assert(root.innerHTML.includes('type="password"'));
 context.state.user.role='USER';requests=[];await context.renderPage('Users');
 assert(root.innerHTML.includes('Administrator access required'));assert.equal(requests.length,0);
})().catch(e=>{console.error(e);process.exitCode=1});
'''],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_mobile_layout_assets_and_cache_policy():
    html=Path('app/static/index.html').read_text()
    assert 'multi-user.css?v=1.0' in html and 'multi-user.js?v=1.0' in html
    assert html.index('multi-user.js')>html.index('responsive-v1.js')
    css=Path('app/static/multi-user.css').read_text()
    assert '@media(max-width:600px)' in css and 'minmax(0,1fr)' in css
    assert 'min-height:44px' in css
    assert '"Cache-Control": "no-cache"' in Path('app/main.py').read_text()
