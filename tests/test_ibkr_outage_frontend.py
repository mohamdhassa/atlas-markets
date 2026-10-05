from pathlib import Path
import shutil
import subprocess
import pytest


def test_outage_assets_have_new_cache_versions():
    html = Path('app/static/index.html').read_text()
    assert 'portfolio-v61.js?v=84.1' in html
    assert 'dashboard-v72-2.js?v=72.3' in html


@pytest.mark.skipif(not shutil.which('node'), reason='Node optional in Python container')
def test_dashboard_and_portfolio_label_stale_data_and_recover():
    subprocess.run(['node', '-e', r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const stale={id:'ib',provider:'IBKR',label:'Paper',environment:'PAPER',market:'STOCK',equity:999,data_status:'STALE',available:null,positions:null,observed_at:'2026-10-05T17:00:00Z'};
let portfolio={accounts:[stale,{id:'by',provider:'BYBIT',label:'Testnet',data_status:'FRESH',equity:100}],positions:[],errors:[{provider:'IBKR',error:'IBKR_SERVER_UNAVAILABLE'}],totals:{equity:100,available:80,partial:true}};
const saved=[{id:'ib',provider:'IBKR',account_label:'Paper',last_connection_status:'CONNECTED',equity_usd:999},{id:'by',provider:'BYBIT',account_label:'Testnet'}];
function sandbox(){return {content:{innerHTML:''},document:{createElement:()=>({}),head:{appendChild(){}},getElementById:()=>null},window:{},renderPage:async()=>{},setActive:()=>{},api:async p=>p==='/portfolio'?portfolio:p==='/accounts'?saved:p.startsWith('/automation/actions')?[]:p.startsWith('/automation/state')?{enabled:true}:p.startsWith('/broker-orders')?{orders:[]}:p.startsWith('/performance')?{overall:{}}:{items:[]},console,Date,Promise,setTimeout};}
(async()=>{
const dashboard=sandbox();vm.createContext(dashboard);vm.runInContext(fs.readFileSync('app/static/dashboard-v72-2.js','utf8'),dashboard);
await dashboard.window.AtlasDashboardV722.dashboard();assert(dashboard.content.innerHTML.includes('Last saved equity · STALE'));assert(dashboard.content.innerHTML.includes('1/2 EXECUTION ROUTES'));assert(dashboard.content.innerHTML.includes('Partial total'));
const page=sandbox();vm.createContext(page);vm.runInContext(fs.readFileSync('app/static/portfolio-v61.js','utf8'),page);await page.window.AtlasPortfolioV61.render();assert(page.content.innerHTML.includes('POSITION DATA UNAVAILABLE'));assert(page.content.innerHTML.includes('Last saved equity · STALE'));assert(page.content.innerHTML.includes('Partial totals'));
portfolio={accounts:[{...stale,data_status:'FRESH',available:999,positions:1}],positions:[{profile_id:'ib',symbol:'TSLA',provider:'IBKR',account:'Paper',quantity:1,entry_price:100,side:'LONG'}],totals:{equity:999}};
await page.window.AtlasPortfolioV61.render();assert(page.content.innerHTML.includes('POSITION OPEN'));assert(!page.content.innerHTML.includes('STALE'));assert(!page.content.innerHTML.includes('Portfolio unavailable'));
await dashboard.window.AtlasDashboardV722.dashboard();assert(!dashboard.content.innerHTML.includes('Last saved equity · STALE $999'));
})().catch(e=>{console.error(e);process.exitCode=1});
'''], check=True, capture_output=True, text=True)
