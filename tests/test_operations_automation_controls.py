from pathlib import Path
import shutil
import subprocess
import pytest


def test_operations_controls_asset_is_current_and_single():
    html = Path('app/static/index.html').read_text()
    assert html.count('/static/operations-v72-1.js?v=72.2') == 1
    assert 'phase38-operations.js' not in html
    assert html.index('operations-v72-1.js') < html.index('responsive-v1.js')


@pytest.mark.skipif(not shutil.which('node'), reason='Node is optional in the Python container')
def test_operations_admin_controls_requests_and_pending_states():
    subprocess.run(['node', '-e', r'''
const assert=require('assert'),fs=require('fs'),vm=require('vm');
let calls=[],confirmation=true,answer={},failure=null,pending=null;
const auto={enabled:true,killed:false,simulation_execution:true,interval_seconds:300,symbols:['XRPUSDT'],next_scan_at:null};
const context={document:{head:{appendChild(){}},createElement:()=>({}),getElementById:()=>null},window:{},content:{innerHTML:''},state:{user:{role:'USER'}},renderPage:async()=>{},setActive(){},confirm:()=>confirmation,
 api:async(path,options)=>{calls.push({path,options});if(failure)throw failure;if(pending)return await pending;if(path==='/automation/state')return auto;if(path==='/portfolio')return{positions:[]};if(path==='/accounts'||path.includes('/automation/actions'))return[];return answer}};
vm.createContext(context);vm.runInContext(fs.readFileSync('app/static/operations-v72-1.js','utf8'),context);
function panel(allowed=true){const status={textContent:''},buttons=['scan','pause','restart','kill'].map(action=>({dataset:{action},disabled:false}));return{dataset:{scanAllowed:String(allowed)},querySelector:()=>status,querySelectorAll:()=>buttons,status,buttons}}
(async()=>{
 await context.renderPage('Operations');assert(!context.content.innerHTML.includes('id="v721-controls"'));
 context.state.user.role='ADMIN';await context.renderPage('Operations');assert(context.content.innerHTML.includes('Run monitored scan'));assert(context.content.innerHTML.includes('aria-live="polite"'));
 const p=panel();context.window.AtlasOperationsV721.bindControls(p);calls=[];
 confirmation=false;await p.buttons[0].onclick();assert.equal(calls.length,0);
 confirmation=true;await p.buttons[1].onclick();assert.equal(calls[0].path,'/automation/state');assert.equal(calls[1].options.method,'PUT');assert.deepEqual(JSON.parse(calls[1].options.body),{enabled:false,simulation_execution:true,interval_seconds:300,symbols:['XRPUSDT']});
 calls=[];await p.buttons[2].onclick();assert.equal(calls[0].path,'/automation/restart');assert.equal(calls[0].options.method,'POST');
 calls=[];await p.buttons[3].onclick();assert.equal(calls[0].path,'/automation/kill');
 let resolve;pending=new Promise(r=>resolve=r);calls=[];const scan=p.buttons[0].onclick();assert(p.buttons[0].disabled);assert(p.buttons[1].disabled);assert(!p.buttons[3].disabled);await p.buttons[0].onclick();assert.equal(calls.length,1);assert.equal(calls[0].path,'/automation/scan-now');
 const replacement=panel();context.window.AtlasOperationsV721.bindControls(replacement);assert(replacement.buttons[0].disabled);
 resolve({status:'COMPLETED',signals:0,approved:0,executed:0});await scan;pending=null;assert(!p.buttons[0].disabled);
 failure=new Error('503 unavailable');await p.buttons[0].onclick();assert(p.status.textContent.includes('Refresh Operations'));assert(!p.buttons[0].disabled);failure=null;
 const off=panel(false);context.window.AtlasOperationsV721.bindControls(off);calls=[];await off.buttons[0].onclick();assert.equal(calls.length,0);
})().catch(error=>{console.error(error);process.exitCode=1});
'''], check=True, capture_output=True, text=True)
