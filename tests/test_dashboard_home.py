from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.mark.skipif(not shutil.which('node'), reason='Node required for navigation checks')
def test_dashboard_overview_navigation_for_both_roles_and_late_response():
    result = subprocess.run(['node', '-e', r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const nav={children:[],set innerHTML(v){this.children=[]},appendChild(el){this.children.push(el)}};
const element=()=>({dataset:{},addEventListener(event,fn){this[event]=fn}});
const state={user:null};
const context={state,window:{},document:{getElementById:()=>nav,createElement:element},
 renderPage:p=>context.clicked=p,buildNav(){},setActive(){}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('app/static/atlas-core.js','utf8'),context);
for(const role of ['USER','ADMIN']){
 state.user={role};context.buildNav();
 const buttons=nav.children.filter(el=>el.dataset.page);
 assert.deepEqual(buttons.slice(0,3).map(el=>el.dataset.page),['Dashboard','Overview','Markets']);
 assert(!buttons.some(el=>el.dataset.page==='Charts'));
 buttons.find(el=>el.dataset.page==='Dashboard').click();assert.equal(context.clicked,'Dashboard');
 assert.equal(buttons.some(el=>el.dataset.page==='Users'),role==='ADMIN');
}
let release,active='',invalidations=0;
const root={innerHTML:''},pending=new Promise(resolve=>release=resolve);
const page={content:root,window:{AtlasMarketsChartsV72:{invalidate(){invalidations++}}},
 document:{createElement:()=>({}),head:{appendChild(){}}},
 renderPage:async p=>{active=p;root.innerHTML=p},setActive:p=>active=p,
 api:async p=>p==='/portfolio'?pending:p==='/accounts'||p.startsWith('/automation/actions')?[]:
 p.startsWith('/performance')?{overall:{}}:p.startsWith('/broker-orders')?{orders:[]}:
 p.startsWith('/automation/state')?{}:{items:[]}};
vm.createContext(page);
vm.runInContext(fs.readFileSync('app/static/dashboard-v72-2.js','utf8'),page);
(async()=>{
 const overview=page.renderPage('Overview');
 assert.equal(invalidations,1);assert.equal(active,'Overview');
 await page.renderPage('Dashboard');assert.equal(root.innerHTML,'Dashboard');
 release({totals:{},accounts:[]});await overview;
 assert.equal(root.innerHTML,'Dashboard');
})().catch(e=>{console.error(e);process.exitCode=1});
'''], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_login_still_opens_dashboard_after_decorators_register():
    source = Path('app/static/app.js').read_text()
    assert "buildNav();renderPage('Dashboard')" in source
    html = Path('app/static/index.html').read_text()
    assert 'app.js?v=84.1' in html
    assert 'atlas-core.js?v=53.1' in html
    assert html.index('markets-charts-v72.js') < html.index('dashboard-v72-2.js')
    assert html.index('dashboard-v72-2.js') < html.index('frontend-stability-v72-6.js')
