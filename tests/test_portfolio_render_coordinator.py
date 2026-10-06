from pathlib import Path
import shutil
import subprocess
import pytest


def test_coordinator_loads_after_components_before_boot():
    html = Path('app/static/index.html').read_text()
    coordinator = html.index('/static/portfolio-render-coordinator.js?v=1.0')
    for component in ('portfolio-v61.js', 'portfolio-terminal-v63.js', 'portfolio-universe-cards-v64-1.js', 'live-position-charts-v66.js', 'live-activity-v75.js', 'frontend-stability-v72-6.js'):
        assert html.index('/static/' + component) < coordinator
    assert coordinator < html.index('/static/responsive-v1.js')


def test_single_assembly_reuses_reads_and_preserves_navigation_and_error_states():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the frontend lifecycle test')
    script = r'''
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync('app/static/portfolio-render-coordinator.js','utf8');
function setup(){
 const calls=[],reads=[],loaders=[],content={style:{visibility:''},before:x=>loaders.push(x),setAttribute(){},removeAttribute(){}};
 const x={window:{},content,console,Promise,Error,renderPage:async p=>calls.push('legacy:'+p),setActive:p=>calls.push('active:'+p),api:async p=>{reads.push(p);return {positions:[]}},document:{createElement:()=>({setAttribute(){},remove(){this.removed=true}}),querySelector:()=>x.shell?{}:null},shell:true};
 x.window.AtlasPortfolioV61={baseRender:async({isCurrent})=>{calls.push('base');await x.api('/portfolio');assert(isCurrent());assert.equal(content.style.visibility,'hidden')}};
 const stage=name=>async()=>{calls.push(name);await x.api('/portfolio');assert.equal(content.style.visibility,'hidden')};
 x.window.AtlasTradingUniverseV62={inject:stage('universe')};x.window.AtlasPortfolioV641={rebuild:stage('cards')};
 x.window.AtlasPortfolioV63={mount:stage('terminal')};x.window.AtlasOpenPositionChartsV65={run:stage('charts')};
 x.window.AtlasPortfolioV631={clean:()=>calls.push('clean')};
 x.window.AtlasLivePositionChartsV66={stop:()=>calls.push('stop'),start:()=>{assert.equal(content.style.visibility,'');calls.push('live')}};
 x.window.AtlasLiveActivityV75={attach:()=>calls.push('activity')};
 vm.createContext(x);vm.runInContext(source,x);return {x,calls,reads,loaders,content};
}
(async()=>{
 const a=setup(),original=a.x.api;
 await a.x.renderPage('Portfolio');
 assert.deepEqual(a.calls,['stop','active:Portfolio','base','universe','cards','terminal','charts','clean','live','activity']);
 assert.deepEqual(a.reads,['/portfolio']);assert.equal(a.x.api,original);assert(a.loaders[0].removed);assert(!a.x.window.AtlasPortfolioRenderCoordinator.isLoading());
 await a.x.renderPage('Portfolio');assert.equal(a.reads.length,2); // no cross-open stale cache
 await a.x.renderPage('Performance');assert.equal(a.calls.at(-1),'legacy:Performance');
 const b=setup();let resolve;
 b.x.api=()=>new Promise(r=>resolve=r);
 b.x.window.AtlasPortfolioV61.baseRender=async({isCurrent})=>{try{await b.x.api('/portfolio');if(isCurrent())b.calls.push('write')}catch(e){if(isCurrent())b.calls.push('error')}};
 const pending=b.x.renderPage('Portfolio');await Promise.resolve();await Promise.resolve();
 await b.x.renderPage('Dashboard');resolve({positions:[]});await pending;
 assert(!b.calls.includes('write'));assert(!b.calls.includes('error'));assert(!b.calls.includes('terminal'));assert.equal(b.content.style.visibility,'');assert(b.loaders[0].removed);
 const c=setup();c.x.shell=false;c.x.window.AtlasPortfolioV61.baseRender=async()=>c.calls.push('error-page');await c.x.renderPage('Portfolio');
 assert(c.calls.includes('error-page'));assert(!c.calls.includes('terminal'));assert(!c.calls.includes('live'));assert.equal(c.content.style.visibility,'');
 const d=setup();d.x.shell=false;d.x.window.AtlasPortfolioV61.baseRender=async()=>{await d.x.api('/example',{method:'POST'});await d.x.api('/example',{method:'POST'})};await d.x.renderPage('Portfolio');assert.equal(d.reads.length,2);
})().catch(e=>{console.error(e);process.exit(1)});
'''
    subprocess.run([node, '-e', script], check=True, capture_output=True, text=True)
