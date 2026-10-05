from pathlib import Path
import shutil
import subprocess

import pytest


def test_log_assets_load_before_final_responsive_boot():
    html = Path('app/static/index.html').read_text()
    assert html.index('/static/system-logs.css?v=1.0') < html.index('/static/responsive-v1.css')
    assert html.index('/static/system-logs.js?v=1.0') < html.index('/static/responsive-v1.js')


@pytest.mark.skipif(not shutil.which('node'), reason='Node is optional in the Python container')
def test_logs_navigation_escape_poll_and_browser_payload():
    # Execute the shipped script against a small DOM fixture, rather than only
    # checking source strings. No browser credentials or live providers are used.
    subprocess.run(['node', '-e', r'''
const assert=require('assert');const fs=require('fs');const vm=require('vm');
const elements=new Map();const reports=[];const timers=[];let nav=[];
function element(id){if(!elements.has(id))elements.set(id,{value:'',textContent:'',innerHTML:'',dataset:{},scrollTop:0,querySelectorAll:()=>[],appendChild:x=>nav.push(x)});return elements.get(id)}
const document={hidden:false,getElementById:element,querySelector:()=>nav.find(x=>x.dataset.page==='Logs'),createElement:()=>({dataset:{},click(){}})};
const state={token:'fixture-token',user:{role:'ADMIN'},page:'Dashboard'};
let data={events:[{id:'one',time:new Date().toISOString(),source:'TRADING',level:'WARNING',event:'BLOCK',decision:'BUY',status:'BLOCK',reason:'<img onerror=attack()>',scan_id:'scan-1'}],next:null,coverage:{persistence:'MEMORY_ONLY',dropped:0,runtime_retention:'Bounded',host_logs:'Host logs not collected'}};
const context={document,state,content:element('content'),window:{addEventListener(){}},ErrorEvent:class {},URLSearchParams,URL,Blob,Map,Set,Date,console,setInterval:f=>{timers.push(f);return 1},setTimeout:()=>1,
 fetch:async(path,opts)=>{reports.push(JSON.parse(opts.body));return{}},api:async()=>data,buildNav:()=>{nav=[]},setActive:page=>{state.page=page;state.marketTimer=null},renderPage:async page=>{state.page=page}};
vm.createContext(context);vm.runInContext(fs.readFileSync('app/static/system-logs.js','utf8'),context);
(async()=>{
 context.buildNav();context.buildNav();assert.equal(nav.length,1);
 await context.renderPage('Logs');assert(element('log-events').innerHTML.includes('&lt;img'));assert(!element('log-events').innerHTML.includes('<img'));
 assert.equal(timers.length,1);assert.equal(reports[0].page,'Logs');assert.deepEqual(Object.keys(reports[0]).sort(),['event','page']);
 element('log-events').scrollTop=77;await timers[0]();assert.equal(element('log-events').scrollTop,77);
 element('log-pause').onclick({currentTarget:element('log-pause')});const before=element('log-events').innerHTML;data.events=[];await timers[0]();assert.equal(element('log-events').innerHTML,before);
 state.user.role='USER';context.buildNav();assert.equal(nav.length,0);await context.renderPage('Logs');assert(context.content.innerHTML.includes('Administrator access required'));
})().catch(e=>{console.error(e);process.exitCode=1});
'''], check=True, capture_output=True, text=True)
