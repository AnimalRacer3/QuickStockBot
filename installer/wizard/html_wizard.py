"""Embedded single-page HTML wizard served by the local Flask server."""

WIZARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>QuickStockBot Setup</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  background:#0f1117;color:#e2e8f0;min-height:100vh;display:flex;
  align-items:flex-start;justify-content:center;padding:24px 16px}
.card{background:#1a1f2e;border:1px solid #2d3748;border-radius:12px;
  width:100%;max-width:640px;padding:32px;box-shadow:0 8px 32px rgba(0,0,0,.4)}
h1{font-size:1.5rem;font-weight:700;color:#f7fafc;margin-bottom:4px}
.subtitle{color:#718096;font-size:.9rem;margin-bottom:24px}
.progress{height:4px;background:#2d3748;border-radius:2px;margin-bottom:28px}
.progress-fill{height:100%;background:#3b82f6;border-radius:2px;
  transition:width .3s ease}
.step-label{font-size:.75rem;color:#718096;margin-bottom:20px;font-weight:500;
  text-transform:uppercase;letter-spacing:.05em}
.step{display:none}.step.active{display:block}
.field{margin-bottom:18px}
label{display:block;font-size:.85rem;color:#a0aec0;margin-bottom:6px;
  font-weight:500}
input[type=text],input[type=password],input[type=number],select{
  width:100%;background:#0f1117;border:1px solid #2d3748;border-radius:6px;
  color:#e2e8f0;font-size:.9rem;padding:10px 12px;outline:none;
  transition:border-color .15s}
input:focus,select:focus{border-color:#3b82f6}
.hint{font-size:.78rem;color:#4a5568;margin-top:4px}
.error-msg{font-size:.78rem;color:#fc8181;margin-top:4px;display:none}
.error-msg.visible{display:block}
input.err,select.err{border-color:#fc8181}
.check-group{display:flex;flex-direction:column;gap:8px}
.check-item{display:flex;align-items:center;gap:8px;cursor:pointer;
  font-size:.88rem;color:#a0aec0}
.check-item input{width:auto}
.radio-group{display:flex;gap:12px;flex-wrap:wrap}
.radio-item{display:flex;align-items:center;gap:6px;cursor:pointer;
  font-size:.88rem;color:#a0aec0}
.radio-item input{width:auto}
.section-title{font-size:.8rem;font-weight:600;color:#718096;
  text-transform:uppercase;letter-spacing:.06em;margin:20px 0 12px;
  border-bottom:1px solid #2d3748;padding-bottom:6px}
.optional-badge{font-size:.7rem;color:#4a5568;background:#1e2535;
  border:1px solid #2d3748;border-radius:3px;padding:1px 5px;margin-left:6px}
.actions{display:flex;justify-content:space-between;align-items:center;
  margin-top:28px;gap:12px}
.btn{padding:10px 22px;border-radius:6px;font-size:.9rem;font-weight:600;
  cursor:pointer;border:none;transition:background .15s,opacity .15s}
.btn:disabled{opacity:.45;cursor:not-allowed}
.btn-primary{background:#3b82f6;color:#fff}
.btn-primary:hover:not(:disabled){background:#2563eb}
.btn-secondary{background:#2d3748;color:#a0aec0}
.btn-secondary:hover:not(:disabled){background:#374151}
.btn-danger{background:#7f1d1d;color:#fca5a5;border:1px solid #991b1b}
.btn-danger:hover:not(:disabled){background:#991b1b}
.test-btn{padding:8px 14px;border-radius:5px;font-size:.82rem;font-weight:600;
  cursor:pointer;border:1px solid #3b82f6;background:transparent;color:#3b82f6;
  transition:all .15s;margin-top:8px}
.test-btn:hover{background:#3b82f6;color:#fff}
.test-result{margin-top:8px;font-size:.82rem;padding:8px 10px;border-radius:5px;
  display:none}
.test-result.ok{background:#064e3b;color:#6ee7b7;border:1px solid #065f46;
  display:block}
.test-result.fail{background:#7f1d1d;color:#fca5a5;border:1px solid #991b1b;
  display:block}
.spinner{display:inline-block;width:14px;height:14px;border:2px solid transparent;
  border-top-color:currentColor;border-radius:50%;animation:spin .7s linear infinite;
  margin-right:6px;vertical-align:middle}
@keyframes spin{to{transform:rotate(360deg)}}
.notice{background:#1e2d40;border:1px solid #1e3a5f;border-radius:6px;
  padding:12px 14px;font-size:.83rem;color:#90cdf4;margin-bottom:16px}
.notice strong{color:#63b3ed}
.progress-log{margin-top:16px;background:#0f1117;border-radius:6px;
  padding:12px;font-size:.82rem;font-family:monospace;color:#68d391;
  min-height:80px;white-space:pre-wrap}
.done-box{text-align:center;padding:12px 0}
.done-icon{font-size:3rem;margin-bottom:12px}
.bot-url-box{background:#0f1117;border:1px solid #2d3748;border-radius:8px;
  padding:14px;margin:16px 0;word-break:break-all;font-family:monospace;
  font-size:.88rem;color:#63b3ed;position:relative}
.copy-btn{position:absolute;top:8px;right:8px;padding:4px 10px;
  border-radius:4px;font-size:.75rem;background:#2d3748;color:#a0aec0;
  border:none;cursor:pointer}
.copy-btn:hover{background:#374151}
</style>
</head>
<body>
<div class="card">
  <h1>QuickStockBot Setup</h1>
  <p class="subtitle">One-time wizard to configure your trading bot.</p>

  <div class="progress"><div class="progress-fill" id="prog" style="width:11%"></div></div>
  <div class="step-label" id="step-label">Step 1 of 9 &mdash; Connection</div>

  <!-- ─── Step 1: Relay URL + License ─────────────────────────────────── -->
  <div class="step active" id="s1">
    <div class="field">
      <label>Relay URL</label>
      <input id="relay_url" type="text" value="wss://quickstockbot-relay-production.up.railway.app/bot"
             placeholder="wss://quickstockbot-relay-production.up.railway.app/bot">
      <div class="hint">WebSocket address of the QuickStockBot relay server.</div>
      <div class="error-msg" id="e_relay_url"></div>
    </div>
    <div class="field">
      <label>License Key</label>
      <input id="license_key" type="text" placeholder="QSB-XXXX-XXXX-XXXX">
      <div class="hint">Issued at purchase. Check your confirmation email.</div>
      <div class="error-msg" id="e_license_key"></div>
    </div>
  </div>

  <!-- ─── Step 2: Connection Password ─────────────────────────────────── -->
  <div class="step" id="s2">
    <div class="notice">
      <strong>Connection password</strong> is a private secret that links
      <em>your</em> bot to your license. Choose any strong password
      (≥&nbsp;8&nbsp;chars) — it will be registered with your account on the
      QuickStockBot server so only your bot can connect. You will not need to
      type it again after setup.
    </div>
    <div class="field">
      <label>Connection Password</label>
      <input id="connection_password" type="password" autocomplete="new-password">
      <div class="error-msg" id="e_connection_password"></div>
    </div>
    <div class="field">
      <label>Confirm Password</label>
      <input id="connection_password_confirm" type="password" autocomplete="new-password">
    </div>
  </div>

  <!-- ─── Step 3: Alpaca Paper Keys ────────────────────────────────────── -->
  <div class="step" id="s3">
    <div class="notice">
      Paper trading uses Alpaca's simulated account — safe to test with real market
      data and no real money at risk.
    </div>
    <div class="field">
      <label>Paper API Key</label>
      <input id="paper_api_key" type="text" placeholder="PKT…">
      <div class="error-msg" id="e_paper_api_key"></div>
    </div>
    <div class="field">
      <label>Paper API Secret</label>
      <input id="paper_api_secret" type="password">
    </div>
    <button class="test-btn" onclick="testAlpaca('paper')">
      Test Paper Connection
    </button>
    <div class="test-result" id="alpaca_paper_result"></div>

    <div class="section-title">Trading Mode</div>
    <div class="field">
      <div class="radio-group">
        <label class="radio-item">
          <input type="radio" name="paper_trading" value="true" checked> Paper (recommended)
        </label>
        <label class="radio-item">
          <input type="radio" name="paper_trading" value="false"> Live
        </label>
      </div>
      <div class="hint">You can switch modes from the dashboard at any time.</div>
    </div>
  </div>

  <!-- ─── Step 4: Alpaca Live Keys ─────────────────────────────────────── -->
  <div class="step" id="s4">
    <div class="notice">
      Live keys are <strong>optional</strong> and only required for real-money trading.
      Leave blank to skip — you can add them later from the dashboard.
    </div>
    <div class="field">
      <label>Live API Key <span class="optional-badge">optional</span></label>
      <input id="live_api_key" type="text" placeholder="AK…">
    </div>
    <div class="field">
      <label>Live API Secret <span class="optional-badge">optional</span></label>
      <input id="live_api_secret" type="password">
    </div>
    <button class="test-btn" onclick="testAlpaca('live')">
      Test Live Connection
    </button>
    <div class="test-result" id="alpaca_live_result"></div>
  </div>

  <!-- ─── Step 5: News API Keys ─────────────────────────────────────────── -->
  <div class="step" id="s5">
    <div class="notice">
      <strong>Alpaca news is enabled by default</strong> and requires no extra key.
      The providers below are optional paid add-ons for broader coverage.
    </div>
    <div class="field">
      <label>Finnhub API Key <span class="optional-badge">optional · paid</span></label>
      <input id="finnhub_api_key" type="text" placeholder="Leave blank to skip">
    </div>
    <div class="field">
      <label>NewsAPI Key <span class="optional-badge">optional · paid</span></label>
      <input id="newsapi_api_key" type="text" placeholder="Leave blank to skip">
    </div>
    <div class="field">
      <label>Benzinga API Key <span class="optional-badge">optional · paid</span></label>
      <input id="benzinga_api_key" type="text" placeholder="Leave blank to skip">
    </div>
  </div>

  <!-- ─── Step 6: Scanner Settings ─────────────────────────────────────── -->
  <div class="step" id="s6">
    <div class="field">
      <label>Pre-open Lead Hours</label>
      <input id="pre_open_lead_hours" type="number" step="0.5" min="0" max="8" value="1">
      <div class="hint">How many hours before market open the scanner starts.</div>
      <div class="error-msg" id="e_pre_open_lead_hours"></div>
    </div>
    <div class="field">
      <label>Scan Duration Hours</label>
      <input id="scan_duration_hours" type="number" step="0.5" min="0.5" max="24" value="3">
      <div class="hint">How long the active scanner runs each session.</div>
      <div class="error-msg" id="e_scan_duration_hours"></div>
    </div>
    <div class="field">
      <label>RVOL Minimum</label>
      <input id="relative_volume_min" type="number" step="0.1" min="1" value="2">
      <div class="hint">Minimum relative volume multiplier to qualify a ticker.</div>
      <div class="error-msg" id="e_relative_volume_min"></div>
    </div>
    <div class="field">
      <label>Gap-up Minimum %</label>
      <input id="gap_up_min_pct" type="number" step="0.5" min="0" value="5">
      <div class="hint">Minimum overnight gap-up percentage.</div>
      <div class="error-msg" id="e_gap_up_min_pct"></div>
    </div>
    <div class="field">
      <label>Max Float Shares</label>
      <input id="max_float_shares" type="number" step="1000000" min="100000" value="20000000">
      <div class="hint">Upper float cap (shares). 20M is a common small-float threshold.</div>
      <div class="error-msg" id="e_max_float_shares"></div>
    </div>
    <div class="field">
      <div class="check-group">
        <label class="check-item">
          <input type="checkbox" id="include_unknown_float" checked>
          Include tickers with unknown float
        </label>
      </div>
    </div>
    <div class="field">
      <label>Top Gainers (N)</label>
      <input id="active_tickers_n" type="number" step="1" min="1" max="50" value="3">
      <div class="hint">Maximum active tickers held in the scan window at once.</div>
      <div class="error-msg" id="e_active_tickers_n"></div>
    </div>
  </div>

  <!-- ─── Step 7: Patterns + MACD ──────────────────────────────────────── -->
  <div class="step" id="s7">
    <div class="section-title">Enabled Patterns</div>
    <div class="field">
      <div class="check-group">
        <label class="check-item">
          <input type="checkbox" class="pattern-cb" value="bullish_engulfing" checked>
          Bullish Engulfing
        </label>
        <label class="check-item">
          <input type="checkbox" class="pattern-cb" value="hammer" checked>
          Hammer
        </label>
        <label class="check-item">
          <input type="checkbox" class="pattern-cb" value="morning_star" checked>
          Morning Star
        </label>
        <label class="check-item">
          <input type="checkbox" class="pattern-cb" value="bullish_continuation" checked>
          Bullish Continuation
        </label>
      </div>
    </div>
    <div class="field">
      <label>Candle Lookback</label>
      <input id="pattern_candle_lookback" type="number" step="1" min="2" max="20" value="5">
      <div class="hint">How many candles back the pattern detector looks.</div>
    </div>
    <div class="section-title">MACD</div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">
      <div class="field">
        <label>Fast Period</label>
        <input id="macd_fast" type="number" step="1" min="1" value="12">
      </div>
      <div class="field">
        <label>Slow Period</label>
        <input id="macd_slow" type="number" step="1" min="1" value="26">
      </div>
      <div class="field">
        <label>Signal Period</label>
        <input id="macd_signal" type="number" step="1" min="1" value="9">
      </div>
    </div>
    <div class="field">
      <div class="check-group">
        <label class="check-item">
          <input type="checkbox" id="macd_enforce_above_zero" checked>
          Enforce MACD histogram above zero
        </label>
      </div>
      <div class="hint" style="margin-top:4px">
        Only enter when MACD histogram is positive (trend confirmation).
      </div>
    </div>
  </div>

  <!-- ─── Step 8: Risk + Exits ─────────────────────────────────────────── -->
  <div class="step" id="s8">
    <div class="field">
      <label>Daily Max-Loss %</label>
      <input id="daily_max_loss_pct" type="number" step="0.1" value="-2">
      <div class="hint">Negative value. Circuit breaker trips when daily P&L hits this.</div>
      <div class="error-msg" id="e_daily_max_loss_pct"></div>
    </div>
    <div class="field">
      <label>Daily Profit Target %</label>
      <input id="daily_profit_target_pct" type="number" step="0.1" min="0.1" value="3">
      <div class="hint">Optional upper limit — bot stops taking new trades after hitting this.</div>
      <div class="error-msg" id="e_daily_profit_target_pct"></div>
    </div>
    <div class="field">
      <div class="check-group">
        <label class="check-item">
          <input type="checkbox" id="override_risk_per_trade"
                 onchange="toggleRiskOverride(this)">
          Override risk-per-trade %
        </label>
      </div>
      <div class="hint">When unchecked: risk per trade = |daily max-loss| ÷ max positions.</div>
    </div>
    <div class="field" id="risk_per_trade_field" style="display:none">
      <label>Risk Per Trade %</label>
      <input id="risk_per_trade_pct" type="number" step="0.1" min="0.01" value="1">
      <div class="hint">Must be less than |daily max-loss %|.</div>
      <div class="error-msg" id="e_risk_per_trade_pct"></div>
    </div>
    <div class="section-title">Exit Mode</div>
    <div class="field">
      <div class="radio-group">
        <label class="radio-item">
          <input type="radio" name="exit_mode" value="dump" checked
                 onchange="toggleTrailOff(false)"> Dump (close all at once)
        </label>
        <label class="radio-item">
          <input type="radio" name="exit_mode" value="trail_off"
                 onchange="toggleTrailOff(true)"> Trail off (scale out gradually)
        </label>
      </div>
    </div>
    <div id="trail_off_options" style="display:none">
      <div class="field">
        <label>Trail-off Trigger</label>
        <div class="radio-group">
          <label class="radio-item">
            <input type="radio" name="trail_off_trigger" value="per_candle" checked>
            Per candle
          </label>
          <label class="radio-item">
            <input type="radio" name="trail_off_trigger" value="candle_pattern">
            Candle pattern
          </label>
        </div>
      </div>
      <div class="field">
        <label>Fraction to Exit Per Candle</label>
        <input id="trail_off_fraction_per_candle" type="number" step="0.05"
               min="0.05" max="1" value="0.25">
        <div class="hint">0.25 = exit 25% of position per trigger candle.</div>
        <div class="error-msg" id="e_trail_off_fraction_per_candle"></div>
      </div>
    </div>
  </div>

  <!-- ─── Step 9: Reachability Check ───────────────────────────────────── -->
  <div class="step" id="s9">
    <div class="notice">
      The bot will now connect to the relay server to confirm it is reachable
      from the web dashboard. This requires an active internet connection.
    </div>
    <div id="reach_idle">
      <p style="color:#a0aec0;font-size:.9rem;margin-bottom:12px">
        Click <strong>Connect</strong> when ready.
      </p>
    </div>
    <div id="reach_running" style="display:none">
      <p style="color:#a0aec0;font-size:.9rem">
        <span class="spinner"></span>Connecting to relay&hellip;
      </p>
    </div>
    <div id="reach_ok" style="display:none">
      <p style="color:#6ee7b7;font-weight:600;margin-bottom:8px">
        &#10003; Bot is reachable!
      </p>
      <p style="color:#a0aec0;font-size:.85rem;margin-bottom:6px">
        Your stable bot URL (paste this into the web <em>view</em> page):
      </p>
      <div class="bot-url-box" id="bot_url_display">
        <button class="copy-btn" onclick="copyUrl()">Copy</button>
        <span id="bot_url_text"></span>
      </div>
    </div>
    <div id="reach_fail" style="display:none">
      <p style="color:#fc8181;font-weight:600">&#x2717; Connection failed</p>
      <p id="reach_fail_msg" style="color:#a0aec0;font-size:.85rem;margin-top:4px"></p>
    </div>
  </div>

  <!-- ─── Step 10: Install ──────────────────────────────────────────────── -->
  <div class="step" id="s10">
    <div id="install_idle">
      <p style="color:#a0aec0;font-size:.9rem;margin-bottom:12px">
        Click <strong>Install</strong> to write configuration and enable autostart.
      </p>
    </div>
    <div id="install_running" style="display:none">
      <p style="color:#a0aec0;font-size:.9rem">
        <span class="spinner"></span>Installing&hellip;
      </p>
      <div class="progress-log" id="install_log"></div>
    </div>
    <div id="install_ok" style="display:none" class="done-box">
      <div class="done-icon">&#10003;</div>
      <h2 style="color:#6ee7b7;margin-bottom:8px">Setup Complete!</h2>
      <p style="color:#a0aec0;font-size:.9rem;margin-bottom:14px">
        QuickStockBot is installed and will start automatically on login.
      </p>
      <p style="color:#a0aec0;font-size:.85rem;margin-bottom:6px">
        Your bot URL (paste into the web view page):
      </p>
      <div class="bot-url-box" id="final_url_display">
        <button class="copy-btn" onclick="copyFinalUrl()">Copy</button>
        <span id="final_url_text"></span>
      </div>
      <p style="color:#4a5568;font-size:.8rem;margin-top:16px">
        Config saved to: <span id="config_dir_display" style="font-family:monospace"></span>
      </p>
    </div>
    <div id="install_fail" style="display:none">
      <p style="color:#fc8181;font-weight:600">&#x2717; Installation failed</p>
      <p id="install_fail_msg" style="color:#a0aec0;font-size:.85rem;margin-top:4px"></p>
    </div>
  </div>

  <!-- ─── Navigation ────────────────────────────────────────────────────── -->
  <div class="actions" id="nav-actions">
    <button class="btn btn-secondary" id="btn-back" onclick="prevStep()">
      &larr; Back
    </button>
    <button class="btn btn-primary" id="btn-next" onclick="nextStep()">
      Next &rarr;
    </button>
  </div>
</div>

<script>
const TOTAL = 9;
let currentStep = 1;
const state = {};

const STEP_LABELS = [
  '', // 0 unused
  'Step 1 of 9 — Connection',
  'Step 2 of 9 — Security',
  'Step 3 of 9 — Alpaca Paper Keys',
  'Step 4 of 9 — Alpaca Live Keys',
  'Step 5 of 9 — News APIs',
  'Step 6 of 9 — Scanner',
  'Step 7 of 9 — Patterns & MACD',
  'Step 8 of 9 — Risk & Exits',
  'Step 9 of 9 — Connect & Install',
];

function showStep(n) {
  document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
  document.getElementById('s' + n).classList.add('active');
  document.getElementById('prog').style.width = (n / TOTAL * 100) + '%';
  document.getElementById('step-label').textContent = STEP_LABELS[n];
  document.getElementById('btn-back').style.visibility = n <= 1 ? 'hidden' : 'visible';
  currentStep = n;
  updateNavButtons();
}

function updateNavButtons() {
  const btnNext = document.getElementById('btn-next');
  if (currentStep === 9) {
    // handled by reach/install buttons
    document.getElementById('nav-actions').style.display = 'none';
  } else {
    document.getElementById('nav-actions').style.display = 'flex';
    btnNext.textContent = currentStep === 8 ? 'Connect →' : 'Next →';
  }
}

function val(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : '';
}

function clearErrors() {
  document.querySelectorAll('.error-msg').forEach(e => {
    e.classList.remove('visible');
    e.textContent = '';
  });
  document.querySelectorAll('input.err, select.err').forEach(e =>
    e.classList.remove('err'));
}

function showError(id, msg) {
  const el = document.getElementById('e_' + id);
  if (el) { el.textContent = msg; el.classList.add('visible'); }
  const inp = document.getElementById(id);
  if (inp) inp.classList.add('err');
}

async function validateStep(n) {
  clearErrors();
  if (n === 1) {
    const res = await postJSON('/api/validate/inputs', {
      step: 'credentials',
      relay_url: val('relay_url'),
      license_key: val('license_key'),
      // skip password here — step 2 handles it
      connection_password: 'placeholder',
      connection_password_confirm: 'placeholder',
    });
    const errors = res.errors || {};
    // Only surface relay/license errors on step 1
    let ok = true;
    if (errors.relay_url) { showError('relay_url', errors.relay_url); ok = false; }
    if (errors.license_key) { showError('license_key', errors.license_key); ok = false; }
    return ok;
  }
  if (n === 2) {
    const res = await postJSON('/api/validate/inputs', {
      step: 'credentials',
      relay_url: val('relay_url') || 'wss://placeholder',
      license_key: val('license_key') || 'placeholder',
      connection_password: val('connection_password'),
      connection_password_confirm: val('connection_password_confirm'),
    });
    const errors = res.errors || {};
    if (errors.connection_password) {
      showError('connection_password', errors.connection_password);
      return false;
    }
    return true;
  }
  if (n === 3) {
    if (!val('paper_api_key')) { showError('paper_api_key', 'Paper API key is required.'); return false; }
    return true;
  }
  if (n === 6) {
    const res = await postJSON('/api/validate/inputs', {
      step: 'scanner',
      pre_open_lead_hours: val('pre_open_lead_hours'),
      scan_duration_hours: val('scan_duration_hours'),
      relative_volume_min: val('relative_volume_min'),
      gap_up_min_pct: val('gap_up_min_pct'),
      max_float_shares: val('max_float_shares'),
      active_tickers_n: val('active_tickers_n'),
    });
    const errors = res.errors || {};
    let ok = true;
    for (const [k, v2] of Object.entries(errors)) { showError(k, v2); ok = false; }
    return ok;
  }
  if (n === 8) {
    const override = document.getElementById('override_risk_per_trade').checked;
    const exitMode = document.querySelector('input[name=exit_mode]:checked').value;
    const res = await postJSON('/api/validate/inputs', {
      step: 'risk',
      daily_max_loss_pct: val('daily_max_loss_pct'),
      daily_profit_target_pct: val('daily_profit_target_pct'),
      override_risk_per_trade: override,
      risk_per_trade_pct: override ? val('risk_per_trade_pct') : null,
      exit_mode: exitMode,
      trail_off_trigger: document.querySelector('input[name=trail_off_trigger]:checked')?.value,
      trail_off_fraction_per_candle: exitMode === 'trail_off' ? val('trail_off_fraction_per_candle') : null,
    });
    const errors = res.errors || {};
    let ok = true;
    for (const [k, v2] of Object.entries(errors)) { showError(k, v2); ok = false; }
    return ok;
  }
  return true;
}

async function nextStep() {
  const ok = await validateStep(currentStep);
  if (!ok) return;

  if (currentStep === 8) {
    collectState();
    showStep(9);
    startConnect();
    return;
  }
  showStep(currentStep + 1);
}

function prevStep() {
  if (currentStep <= 1) return;
  if (currentStep === 9) {
    document.getElementById('nav-actions').style.display = 'flex';
  }
  showStep(currentStep - 1);
}

function collectState() {
  state.relay_url = val('relay_url');
  state.license_key = val('license_key');
  state.connection_password = val('connection_password');
  state.paper_api_key = val('paper_api_key');
  state.paper_api_secret = val('paper_api_secret');
  state.paper_trading = document.querySelector('input[name=paper_trading]:checked').value === 'true';
  state.live_api_key = val('live_api_key');
  state.live_api_secret = val('live_api_secret');
  state.finnhub_api_key = val('finnhub_api_key');
  state.newsapi_api_key = val('newsapi_api_key');
  state.benzinga_api_key = val('benzinga_api_key');

  state.pre_open_lead_hours = parseFloat(val('pre_open_lead_hours'));
  state.scan_duration_hours = parseFloat(val('scan_duration_hours'));
  state.relative_volume_min = parseFloat(val('relative_volume_min'));
  state.gap_up_min_pct = parseFloat(val('gap_up_min_pct'));
  state.max_float_shares = parseInt(val('max_float_shares'), 10);
  state.include_unknown_float = document.getElementById('include_unknown_float').checked;
  state.active_tickers_n = parseInt(val('active_tickers_n'), 10);

  state.enabled_patterns = [...document.querySelectorAll('.pattern-cb:checked')]
    .map(cb => cb.value);
  state.pattern_candle_lookback = parseInt(val('pattern_candle_lookback'), 10);
  state.macd_fast = parseInt(val('macd_fast'), 10);
  state.macd_slow = parseInt(val('macd_slow'), 10);
  state.macd_signal = parseInt(val('macd_signal'), 10);
  state.macd_enforce_above_zero = document.getElementById('macd_enforce_above_zero').checked;

  state.daily_max_loss_pct = parseFloat(val('daily_max_loss_pct'));
  state.daily_profit_target_pct = parseFloat(val('daily_profit_target_pct'));
  state.override_risk_per_trade = document.getElementById('override_risk_per_trade').checked;
  state.risk_per_trade_pct = parseFloat(val('risk_per_trade_pct') || '1');
  state.exit_mode = document.querySelector('input[name=exit_mode]:checked').value;
  state.trail_off_trigger = document.querySelector('input[name=trail_off_trigger]:checked')?.value || 'per_candle';
  state.trail_off_fraction_per_candle = parseFloat(val('trail_off_fraction_per_candle') || '0.25');
}

// ── step 9: connect then install ─────────────────────────────────────────────

async function startConnect() {
  // show connect button
  const s9 = document.getElementById('s9');
  s9.innerHTML = `
    <div class="notice">
      Confirming your bot is reachable from the relay server&hellip;
    </div>
    <div id="reach_running" style="color:#a0aec0;font-size:.9rem">
      <span class="spinner"></span>Connecting to relay&hellip;
    </div>
    <div id="reach_result" style="margin-top:14px"></div>
    <div id="step9_actions" style="margin-top:20px"></div>
  `;

  const res = await postJSON('/api/check-relay', {
    relay_url: state.relay_url,
    license_key: state.license_key,
    connection_password: state.connection_password,
  });

  document.getElementById('reach_running').style.display = 'none';
  state.bot_id = res.bot_id;
  state.bot_url = res.bot_url;

  const resultEl = document.getElementById('reach_result');
  const actionsEl = document.getElementById('step9_actions');

  if (res.success) {
    resultEl.innerHTML = `
      <p style="color:#6ee7b7;font-weight:600;margin-bottom:8px">&#10003; Bot is reachable!</p>
      <p style="color:#a0aec0;font-size:.85rem;margin-bottom:6px">
        Your stable bot URL (paste into the web <em>view</em> page):
      </p>
      <div class="bot-url-box">
        <button class="copy-btn" onclick="navigator.clipboard.writeText('${res.bot_url}')">Copy</button>
        <span style="font-family:monospace">${res.bot_url}</span>
      </div>
    `;
    actionsEl.innerHTML = `
      <button class="btn btn-primary" onclick="startInstall()" style="width:100%">
        Install &amp; Enable Autostart
      </button>
    `;
  } else {
    resultEl.innerHTML = `
      <p style="color:#fc8181;font-weight:600">&#x2717; Connection failed</p>
      <p style="color:#a0aec0;font-size:.85rem;margin-top:4px">${res.message}</p>
    `;
    actionsEl.innerHTML = `
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <button class="btn btn-secondary" onclick="prevStep()">
          &larr; Back
        </button>
        <button class="btn btn-primary" onclick="startConnect()">
          Retry
        </button>
        <button class="btn btn-primary" onclick="startInstall()" style="background:#2d7a4f">
          Skip check &amp; install anyway
        </button>
      </div>
    `;
  }
}

async function startInstall() {
  const s9 = document.getElementById('s9');
  const log = [];

  s9.innerHTML = `
    <div style="color:#a0aec0;font-size:.9rem;margin-bottom:8px">
      <span class="spinner"></span>Installing&hellip;
    </div>
    <div class="progress-log" id="install_log"></div>
  `;

  function appendLog(msg) {
    const el = document.getElementById('install_log');
    if (el) { log.push(msg); el.textContent = log.join('\n'); }
  }

  appendLog('[1/5] Writing configuration to disk...');

  const payload = Object.assign({}, state);
  const res = await postJSON('/api/install', payload);

  if (!res.success) {
    s9.innerHTML = `
      <p style="color:#fc8181;font-weight:600">&#x2717; Installation failed</p>
      <p style="color:#a0aec0;font-size:.85rem;margin-top:4px">${res.message || 'Unknown error'}</p>
      <div style="margin-top:16px">
        <button class="btn btn-secondary" onclick="prevStep()">&larr; Back</button>
      </div>
    `;
    return;
  }

  appendLog('[2/5] Configuration written.');
  appendLog('[3/5] ' + (res.autostart_ok
    ? 'Autostart enabled — bot will launch automatically on login.'
    : 'Note: ' + (res.autostart_message || 'autostart requires manual setup.')));
  appendLog('[4/5] ' + (res.shortcut_ok
    ? 'Desktop shortcut created — double-click QuickStockBot on your Desktop to restart.'
    : 'Note: ' + (res.shortcut_message || 'desktop shortcut could not be created.')));
  appendLog('[5/5] ' + (res.bot_launched
    ? 'Bot is now running in the background.'
    : 'Note: ' + (res.launch_message || 'start the bot manually using the desktop shortcut.')));
  appendLog('');
  appendLog('Done!');

  await new Promise(r => setTimeout(r, 600));

  const botUrl = state.bot_url || '';
  s9.innerHTML = `
    <div class="done-box">
      <div class="done-icon">&#10003;</div>
      <h2 style="color:#6ee7b7;margin-bottom:8px">Setup Complete!</h2>
      <p style="color:#a0aec0;font-size:.9rem;margin-bottom:6px">
        QuickStockBot is now running in the background.
      </p>
      <p style="color:#a0aec0;font-size:.85rem;margin-bottom:14px">
        ${res.autostart_ok ? 'It will start automatically each time you log in.' : ''}
        ${res.shortcut_ok ? 'Use the <strong>QuickStockBot</strong> shortcut on your Desktop to restart it any time.' : ''}
      </p>
      ${botUrl ? `
      <p style="color:#a0aec0;font-size:.85rem;margin-bottom:6px">
        Paste this URL into the web <em>view</em> page:
      </p>
      <div class="bot-url-box">
        <button class="copy-btn" onclick="navigator.clipboard.writeText('${botUrl}')">Copy</button>
        <span style="font-family:monospace">${botUrl}</span>
      </div>` : ''}
      <p style="color:#4a5568;font-size:.8rem;margin-top:16px">
        Config saved to: <span style="font-family:monospace">${res.config_dir || ''}</span>
      </p>
      <p style="color:#4a5568;font-size:.78rem;margin-top:8px">
        You may close this window.
      </p>
    </div>
  `;
}

// ── helpers ───────────────────────────────────────────────────────────────────

async function postJSON(url, data) {
  const r = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data),
  });
  return r.json();
}

async function testAlpaca(mode) {
  const paper = mode === 'paper';
  const key = paper ? val('paper_api_key') : val('live_api_key');
  const secret = paper ? val('paper_api_secret') : val('live_api_secret');
  const resultId = paper ? 'alpaca_paper_result' : 'alpaca_live_result';
  const el = document.getElementById(resultId);
  el.className = 'test-result';
  el.textContent = 'Testing…';
  el.style.display = 'block';
  const res = await postJSON('/api/validate/alpaca', {api_key: key, api_secret: secret, paper});
  el.className = 'test-result ' + (res.success ? 'ok' : 'fail');
  el.textContent = res.message;
}

function toggleRiskOverride(cb) {
  document.getElementById('risk_per_trade_field').style.display =
    cb.checked ? 'block' : 'none';
}

function toggleTrailOff(on) {
  document.getElementById('trail_off_options').style.display = on ? 'block' : 'none';
}

function copyUrl() {
  navigator.clipboard.writeText(document.getElementById('bot_url_text').textContent);
}
function copyFinalUrl() {
  navigator.clipboard.writeText(document.getElementById('final_url_text').textContent);
}

// init
showStep(1);
</script>
</body>
</html>
"""
