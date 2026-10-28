from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.mark.skipif(not shutil.which('node'),reason='Node required for frontend check')
def test_onboarding_roles_secret_form_and_stale_response():
    result=subprocess.run(['node','-e',r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map(),element=()=>({id:'',innerHTML:'',textContent:'',append(el){elements.set(el.id,el)},querySelectorAll:()=>[]});
const content={prepend(el){elements.set(el.id,el)}};
let release,pending=false;
const context={state:{page:'',user:{id:'owner',role:'USER'}},window:{},
 document:{createElement:element,getElementById:id=>id==='content'?content:(elements.has(id)?elements.get(id):(elements.set(id,element()),elements.get(id)))},
 renderPage:async page=>{context.state.page=page},api:async()=>pending?new Promise(resolve=>release=resolve):({enabled:true,jobs:[{id:'job',user_id:'owner',account_id:'DU12345',account_label:'Paper',status:'APPROVED',attempts:0}]})};
vm.createContext(context);vm.runInContext(fs.readFileSync('app/static/ibkr-onboarding.js','utf8'),context);
(async()=>{
 await context.renderPage('Accounts');let html=elements.get('ibkrSetupPanel').innerHTML;
 assert(html.includes('Submit Paper login'));assert(!html.includes('Approve Paper setup'));
 context.state.user.role='ADMIN';context.api=async()=>({enabled:true,jobs:[{id:'job',user_id:'another-owner',account_id:'DU12345',account_label:'Paper',status:'REQUESTED',attempts:0}]});
 await context.renderPage('Accounts');html=elements.get('ibkrSetupPanel').innerHTML;
 assert(html.includes('Approve Paper setup'));assert(!html.includes('Submit Paper login'));
 assert(html.includes('Connection progress'));
 assert(html.includes('Connect IBKR Paper'));
 context.api=async()=>({enabled:true,jobs:[{id:'job',user_id:'owner',account_id:'DU12345',account_label:'Paper',status:'CONNECTED',attempts:1}]});
 await context.renderPage('Accounts');html=elements.get('ibkrSetupPanel').innerHTML;
 assert(!html.includes('id="ibkrSetupRequest"'));assert(!html.includes('Submit Paper login'));
 assert(html.includes('Verified')); 
 context.api=async()=>new Promise(resolve=>release=resolve);
 let rendering=context.renderPage('Accounts');await new Promise(setImmediate);
 await context.renderPage('Dashboard');release({enabled:true,jobs:[]});await rendering;
 assert.equal(context.state.page,'Dashboard');
})().catch(e=>{console.error(e);process.exitCode=1});
'''],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_frontend_has_no_docker_or_local_secret_storage():
    source=Path('app/static/ibkr-onboarding.js').read_text()
    assert 'localStorage' not in source and 'sessionStorage' not in source
    assert 'values.password=\'\'' in source and 'f.reset()' in source
    assert 'Docker' not in source
    html=Path('app/static/index.html').read_text()
    assert html.index('ibkr-onboarding.js')>html.index('multi-user.js')


def test_web_process_never_executes_docker_or_accepts_node_specs():
    source=Path('app/api/routes_ibkr_onboarding.py').read_text()
    assert 'subprocess' not in source and '/var/run/docker.sock' not in source
    assert "ibkr_provisioning_enabled: bool = False" in Path('app/core/config.py').read_text()
