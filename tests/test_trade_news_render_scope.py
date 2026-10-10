from pathlib import Path
import shutil
import subprocess

import pytest


def test_news_helper_is_inside_workspace_closure():
    script = Path('app/static/live-pages.js').read_text()
    assert script.index('function tradeNewsLive') < script.rindex('})();')


def test_full_performance_renderer_without_global_formatting_helpers():
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is required for the JavaScript runtime check')
    result = subprocess.run([node, '-'], input=r'''
const vm = require('vm'), fs = require('fs'), assert = require('assert');
let data;
const context = {
  window: {}, content: {innerHTML: ''}, renderPage: async () => {}, setActive: () => {},
  api: async () => { if (data instanceof Error) throw data; return data; },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('app/static/live-pages.js', 'utf8'), context);
(async () => {
  data = {trades: [{closed_trade: true, provider: 'IBKR', symbol: 'MSFT',
    opened_at: 1, time: 2, entry_news: [{title: '<unsafe>', url: '#', source: 'Test', sentiment_score: 1}],
    exit_news: []}]};
  await context.renderPage('Performance');
  assert(context.content.innerHTML.includes('&lt;unsafe&gt;'));
  assert(context.content.innerHTML.includes('<strong>Entry</strong>'));
  assert(context.content.innerHTML.includes('<strong>Exit</strong>'));
  assert(!context.content.innerHTML.includes('Data unavailable'));
  data = {trades: [{closed_trade: true}]};
  await context.renderPage('Performance');
  assert(context.content.innerHTML.includes('Time unavailable'));
  data = {trades: []};
  await context.renderPage('Performance');
  assert(context.content.innerHTML.includes('No verified closed trades'));
  data = new Error('API unavailable');
  await context.renderPage('Performance');
  assert(context.content.innerHTML.includes('API unavailable'));
  assert.equal(context.escLive, undefined);
})().catch(error => { console.error(error); process.exitCode = 1; });
''', text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
