from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.skipif(not shutil.which('node'), reason='Node required for chart interaction checks')
def test_profit_chart_filters_reset_render_errors_and_navigation():
    result=subprocess.run(['node','-e',r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const ids={},checks=[];
class El{
 constructor(id){this.id=id;this.value='';this.disabled=false;this.textContent='';this.classList={add(){},remove(){}};}
 set innerHTML(value){this.html=value;for(const match of value.matchAll(/<[^>]*\bid="([^"]+)"[^>]*>/g)){const el=new El(match[1]);const v=match[0].match(/\bvalue="([^"]*)"/);if(v)el.value=v[1];ids[el.id]=el;}
 if(this.id==='content'){checks.length=0;for(const match of value.matchAll(/<input[^>]*name="profitSymbol"[^>]*>/g)){checks.push({value:match[0].match(/value="([^"]*)"/)[1],checked:false});}}}
 get innerHTML(){return this.html||'';}
 getBoundingClientRect(){return {left:0,width:1000};}
}
const content=ids.content=new El('content'),requests=[];
const data={symbols:[{key:'IBKR:PAPER:STOCK:TSLA',symbol:'TSLA',provider:'IBKR',environment:'PAPER',market:'STOCK'},{key:'IBKR:PAPER:STOCK:AAPL',symbol:'AAPL',provider:'IBKR',environment:'PAPER',market:'STOCK'}],series:[{key:'OVERALL',label:'Overall',points:[{time:1790812800000,value:0},{time:1790899199999,value:-12},{time:1790985599999,value:3}]}],recorded_pnl:3,pnl_records:4,selected_symbols:[],start:null,end:null,coverage:'All available recorded history',partial:false};
let fail=false,blockNext=false,release;
const context={content,window:{},document:{createElement:()=>new El('style'),head:{appendChild(){}},getElementById:id=>ids[id]||null,querySelectorAll:selector=>selector.includes('profitSymbol')?checks.filter(x=>!selector.includes(':checked')||x.checked):[]},renderPage:async()=>{},setActive(){},requestAnimationFrame:f=>f(),URLSearchParams,Date,Promise,console,
 api:async url=>{requests.push(url);if(blockNext){blockNext=false;await new Promise(resolve=>release=resolve);}if(fail)throw Error('<unsafe error>');const query=new URL('https://test'+url).searchParams;return {...data,selected_symbols:query.getAll('symbols'),start:query.get('start'),end:query.get('end')};}};
vm.createContext(context);vm.runInContext(fs.readFileSync('app/static/markets-charts-v72.js','utf8'),context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 await context.renderPage('Charts');
 assert.equal(requests[0],'/performance/profit-chart');
 assert(content.innerHTML.includes('Profit performance'));
 assert(ids.profitChart.innerHTML.includes('<svg'));
 assert(!ids.profitChart.innerHTML.includes('NaN'));
 assert(ids.profitPoint.textContent.includes('+3.00'));
 ids.profitSvg.viewBox={baseVal:{width:326}};
 ids.profitSvg.onpointermove({clientX:1000});assert(ids.profitPoint.textContent.includes('+3.00'));
 ids.profitSvg.onpointermove({clientX:0});assert(ids.profitPoint.textContent.includes('0.00'));
 ids.profitDateSlider.value='1';ids.profitDateSlider.oninput();assert(ids.profitPoint.textContent.includes('-12.00'));
 checks[0].checked=checks[1].checked=true;
 ids.profitStart.value='2026-10-01';ids.profitEnd.value='2026-10-02';
 ids.profitFilters.onsubmit({preventDefault(){}});await tick();
 const q=new URL('https://test'+requests.at(-1)).searchParams;
 assert.equal(q.getAll('symbols').length,2);assert.equal(q.get('start'),'2026-10-01');
 assert.equal(ids.profitHeading.textContent,'Selected symbols comparison');
 const count=requests.length;ids.profitStart.value='2026-10-03';
 ids.profitFilters.onsubmit({preventDefault(){}});await tick();
 assert.equal(requests.length,count);assert(ids.profitFilterError.textContent.includes('Filters have not been applied'));
 ids.profitReset.onclick();await tick();
 assert.equal(requests.at(-1),'/performance/profit-chart');
 assert(checks.every(x=>!x.checked));assert.equal(ids.profitStart.value,'');assert.equal(ids.profitEnd.value,'');
 fail=true;ids.profitFilters.onsubmit({preventDefault(){}});await tick();
 assert(ids.profitChart.innerHTML.includes('&lt;unsafe error&gt;'));assert.equal(ids.profitApply.disabled,false);
 fail=false;blockNext=true;ids.profitFilters.onsubmit({preventDefault(){}});await tick();
 await context.renderPage('Dashboard');content.innerHTML='Dashboard retained';release();await tick();
 assert.equal(content.innerHTML,'Dashboard retained');
 fail=true;await context.renderPage('Charts');assert(content.innerHTML.includes('profitRetry'));
 fail=false;await ids.profitRetry.onclick();assert(ids.profitChart.innerHTML.includes('<svg'));
 data.partial=true;data.excluded_unknown_pnl_records=2;data.excluded_undated_records=1;data.provider_errors=[{provider:'IBKR'}];
 ids.profitFilters.onsubmit({preventDefault(){}});await tick();assert(ids.profitCoverage.textContent.includes('Partial history: 1 provider read issue(s)'));

 assert(context.window.AtlasProfitChart.profitGraph({series:[]}).includes('No recorded realized'));
 const zero=context.window.AtlasProfitChart.profitGraph({series:[{label:'Zero',points:[{time:1,value:0},{time:2,value:0}]}]});
 assert(zero.includes('<svg')&&!zero.includes('NaN'));
 for(const width of [260,288,326,366,650,1000]){
  const graph=context.window.AtlasProfitChart.profitGraph(data,width);
  assert(graph.includes('viewBox="0 0 '+width+' '));
  assert(!graph.includes('NaN'));
  const coords=[...graph.matchAll(/points="([^"]+)"/g)].flatMap(m=>m[1].split(' ').map(p=>p.split(',').map(Number)));
  assert(coords.every(([x,y])=>x>=0&&x<=width&&y>=0&&y<=360));
 }

 const escaped=context.window.AtlasProfitChart.profitGraph({series:[{label:'<img onerror=bad>',points:[{time:1,value:0},{time:2,value:1}]}]});
 assert(!escaped.includes('<img'));
})().catch(error=>{console.error(error);process.exitCode=1;});
'''],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_chart_asset_version_and_order_preserve_existing_workspaces():
    html=Path('app/static/index.html').read_text()
    assert 'markets-charts-v72.js?v=72.3' in html
    assert html.index('markets-charts-v72.js')<html.index('frontend-stability-v72-6.js')
