async function phase7SignalsPage(){
  content.innerHTML='<div class="panel empty-state">Loading persisted signals…</div>';
  try{
    const [accounts,signals]=await Promise.all([api('/accounts'),api('/signals?limit=50')]);
    const options=accounts.map(a=>`<option value="${a.id}">${escapeHtml(a.account_label)} · ${escapeHtml(a.environment)}</option>`).join('');
    content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">SIGNAL ENGINE</p><h3>Analysis → decision → risk</h3><p class="muted">Generate a persisted signal for one of your broker profiles. Approval means simulation-ready only; no order is placed.</p></div><span class="badge good">PHASE 7</span></div>
    <div class="panel form-panel"><h3>Generate signal</h3>${accounts.length?`<form id="signalForm" class="form-grid"><label>Account<select id="signalAccount">${options}</select></label><label>Symbol<select id="signalSymbol"><option>BTCUSDT</option><option>ETHUSDT</option><option>SOLUSDT</option><option>XRPUSDT</option><option>BNBUSDT</option></select></label><label>Timeframe<select id="signalInterval"><option value="5m">5m</option><option value="15m">15m</option><option value="1h">1h</option><option value="4h">4h</option></select></label><div class="form-actions"><button class="primary-button" type="submit">Generate & evaluate</button><span id="signalMessage" class="muted"></span></div></form>`:'<p class="muted">Add a broker profile in Accounts before generating signals.</p>'}</div>
    <div id="signalHistory">${phase7SignalCards(signals)}</div>`;
    const form=$('signalForm');
    if(form)form.onsubmit=async e=>{e.preventDefault();const msg=$('signalMessage');msg.textContent='Analyzing market…';try{const r=await api(`/signals/generate?profile_id=${encodeURIComponent($('signalAccount').value)}&symbol=${encodeURIComponent($('signalSymbol').value)}&interval=${encodeURIComponent($('signalInterval').value)}`,{method:'POST'});msg.textContent=`${r.decision} · ${r.risk.reason_code}`;setTimeout(phase7SignalsPage,500)}catch(err){msg.textContent=err.message}};
  }catch(err){content.innerHTML=`<div class="panel empty-state">Signals unavailable: ${escapeHtml(err.message)}</div>`}
}

function phase7SignalCards(rows){
  if(!rows.length)return '<div class="panel empty-state">No persisted signals yet.</div>';
  return `<div class="analysis-grid">${rows.map(s=>`<div class="analysis-card"><div class="action-row"><h4 style="margin-right:auto">${escapeHtml(s.symbol)}</h4><span class="badge ${s.risk_status==='APPROVED'?'good':'warn'}">${s.risk_status}</span></div><strong>${escapeHtml(s.decision)} · ${Number(s.score).toFixed(0)}/100</strong><p class="muted">${escapeHtml(s.classification)} · ${escapeHtml(s.timeframe)}</p><div class="reason-list">${(s.reasons||[]).map(r=>`<span class="badge">${escapeHtml(r)}</span>`).join(' ')}</div><p class="muted small-text">${new Date(s.created_at).toLocaleString()}</p></div>`).join('')}</div>`;
}

async function phase7RiskPage(){
  content.innerHTML='<div class="panel empty-state">Loading risk policy…</div>';
  try{
    const r=await api('/risk/profile');
    const editable=state.user?.role==='ADMIN';
    content.innerHTML=`<div class="page-intro"><div><p class="eyebrow">RISK POLICY</p><h3>${escapeHtml(r.name)} profile</h3><p class="muted">Risk gates run after signal generation and before any future execution layer.</p></div><span class="badge ${r.is_active?'good':'warn'}">${r.is_active?'ACTIVE':'INACTIVE'}</span></div><div class="metric-grid"><div class="metric-card"><span>Minimum signal strength</span><strong>${r.minimum_signal_score}</strong></div><div class="metric-card"><span>Risk / trade</span><strong>${r.risk_per_trade_pct}%</strong></div><div class="metric-card"><span>Max daily loss</span><strong>${r.max_daily_loss_pct}%</strong></div><div class="metric-card"><span>Max open positions</span><strong>${r.max_open_positions}</strong></div></div>${editable?`<div class="panel form-panel"><h3>Edit risk policy</h3><form id="riskForm" class="form-grid"><label>Minimum signal strength<input id="riskMinScore" type="number" min="50" max="100" step="1" value="${r.minimum_signal_score}" /></label><label>Risk per trade %<input id="riskTrade" type="number" min="0.1" max="5" step="0.1" value="${r.risk_per_trade_pct}" /></label><label>Max daily loss %<input id="riskDaily" type="number" min="0.1" max="20" step="0.1" value="${r.max_daily_loss_pct}" /></label><label>Max open positions<input id="riskPositions" type="number" min="1" max="20" value="${r.max_open_positions}" /></label><div class="form-actions"><button class="primary-button" type="submit">Save risk policy</button><span id="riskMessage" class="muted"></span></div></form></div>`:'<div class="panel"><p class="muted">Risk policy is read-only for USER accounts.</p></div>'}`;
    const form=$('riskForm');if(form)form.onsubmit=async e=>{e.preventDefault();const msg=$('riskMessage');msg.textContent='Saving…';try{await api('/risk/profile',{method:'PUT',body:JSON.stringify({minimum_signal_score:Number($('riskMinScore').value),risk_per_trade_pct:Number($('riskTrade').value),max_daily_loss_pct:Number($('riskDaily').value),max_open_positions:Number($('riskPositions').value)})});msg.textContent='Saved';setTimeout(phase7RiskPage,400)}catch(err){msg.textContent=err.message}};
  }catch(err){content.innerHTML=`<div class="panel empty-state">Risk policy unavailable: ${escapeHtml(err.message)}</div>`}
}

const phase6RenderPage=renderPage;
renderPage=function(page){
  if(page==='Signals'){setActive(page);phase7SignalsPage();return}
  if(page==='Risk'){setActive(page);phase7RiskPage();return}
  phase6RenderPage(page);
};
