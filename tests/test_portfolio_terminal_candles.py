"""Execute the real chart normalization and drawing code without a browser."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_chart_uses_provider_dates_and_actual_canvas_dimensions():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the canvas regression test")
    source = Path("app/static/portfolio-terminal-v63.js").read_text()
    functions = source[source.index("function norm("):source.index("function wireCrosshair(")]
    script = "const assert=require('node:assert/strict'); const devicePixelRatio=2; const num=String;\n" + functions + r'''
const candle={timestamp_ms:1791043200000,open:790,high:792,low:789,close:791,volume:10};
assert.equal(norm([candle])[0].t,candle.timestamp_ms);
assert.equal(norm([{...candle,timestamp_ms:undefined,time:1791043200}])[0].t,candle.timestamp_ms);
assert.equal(norm([{...candle,timestamp_ms:undefined,time:'2026-10-03T16:00:00Z'}])[0].t,candle.timestamp_ms);
assert.ok(Number.isNaN(norm([{...candle,timestamp_ms:undefined}])[0].t));
const labels=[];
const ctx=new Proxy({fillText:t=>labels.push(t)}, {get:(o,k)=>k in o?o[k]:()=>{},set:(o,k,v)=>(o[k]=v,true)});
const canvas={getContext:()=>ctx,getBoundingClientRect:()=>({width:280,height:260})};
draw(canvas,[candle,{...candle,timestamp_ms:candle.timestamp_ms+300000}],{current:791});
assert.equal(canvas.width,560);
assert.equal(canvas.height,520);
assert.ok(labels.some(x=>/Oct/.test(x)));
assert.ok(!labels.some(x=>/Jan/.test(x)));
'''
    subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)
