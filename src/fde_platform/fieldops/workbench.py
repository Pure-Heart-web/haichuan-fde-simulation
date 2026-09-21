"""Unified browser workbench for the synthetic field-pilot rehearsal."""


WORKBENCH_HTML = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stage 13 Pilot Workbench</title><style>
:root{--ink:#14212b;--muted:#65727d;--line:#d9e0e5;--brand:#075e54;--bg:#f3f6f5;--danger:#9b2c2c}
*{box-sizing:border-box}body{margin:0;font:14px system-ui;color:var(--ink);background:var(--bg)}
header{background:var(--ink);color:#fff;padding:18px 24px}header h1{margin:0 0 4px;font-size:22px}header p{margin:0;color:#bfd0d8}
main{max-width:1280px;margin:18px auto;padding:0 18px}.grid{display:grid;grid-template-columns:360px 1fr;gap:16px}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:14px;box-shadow:0 2px 7px #10202a0d}
h2{font-size:16px;margin:0 0 12px}label{display:block;color:var(--muted);margin:8px 0 4px}input,select,textarea,button{width:100%;padding:9px;border:1px solid #bac5cb;border-radius:6px;font:inherit}
textarea{min-height:72px}button{margin-top:8px;background:var(--brand);color:white;border:0;cursor:pointer}.secondary{background:#405563}.danger{background:var(--danger)}
.row{display:grid;grid-template-columns:1fr 1fr;gap:8px}pre{white-space:pre-wrap;word-break:break-word;background:#101820;color:#d7f9ee;padding:14px;border-radius:8px;min-height:500px;max-height:75vh;overflow:auto}
.boundary{border-left:4px solid #d69e2e;padding-left:10px;color:#654b12}@media(max-width:850px){.grid{grid-template-columns:1fr}}
</style></head><body><header><h1>Stage 13 · Design Partner Pilot Workbench</h1>
<p>合成现场演练：审核、升级、发布、指标和回退在同一工作台完成</p></header><main>
<p class="boundary">边界：训练 OIDC 令牌只保存在当前页面内存；客户投递目标仍是本机 Mock Sink。</p>
<div class="grid"><section>
<div class="card"><h2>1. 会话</h2><label>Bearer token</label><textarea id="token" placeholder="粘贴 stage13.py login 返回的训练令牌"></textarea>
<div class="row"><button onclick="get('/v1/cases')">我的队列</button><button class="secondary" onclick="get('/v1/metrics')">运营指标</button></div></div>
<div class="card"><h2>2. 证据与审核</h2><label>Case ID</label><input id="caseId" placeholder="DR-001">
<button class="secondary" onclick="trace()">查看完整 Trace</button><label>动作</label><select id="action"><option>accept</option><option>edit</option><option>escalate</option><option>reject</option></select>
<label>理由 / 人工修改说明</label><textarea id="reason" placeholder="说明核对证据和做出决定的原因"></textarea><button onclick="review()">提交审核</button></div>
<div class="card"><h2>3. 双人发布</h2><label>Message ID</label><input id="messageId" placeholder="MSG-...">
<button onclick="approve()">Release Manager 批准</button></div>
<div class="card"><h2>4. 运行操作</h2><div class="row"><button class="secondary" onclick="post('/v1/worker/tick',{tick:0})">Worker Tick</button>
<button class="secondary" onclick="post('/v1/dispatcher/tick',{tick:0})">Dispatcher Tick</button></div></div>
</section><section class="card"><h2>操作结果</h2><pre id="result">等待操作。先在终端使用 login 获取对应角色的训练 OIDC 令牌。</pre></section></div></main>
<script>
const token=()=>document.querySelector('#token').value.trim();
async function call(path,options={}){options.headers={...(options.headers||{}),Authorization:'Bearer '+token()};
 const r=await fetch(path,options);const v=await r.json();document.querySelector('#result').textContent=JSON.stringify(v,null,2);return v}
function get(path){return call(path)}function post(path,body){return call(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})}
function trace(){return get('/v1/traces/'+encodeURIComponent(document.querySelector('#caseId').value))}
async function review(){const v=await post('/v1/cases/'+encodeURIComponent(document.querySelector('#caseId').value)+'/reviews',{action:document.querySelector('#action').value,reason:document.querySelector('#reason').value});if(v.message_id)document.querySelector('#messageId').value=v.message_id}
function approve(){return post('/v1/outbox/'+encodeURIComponent(document.querySelector('#messageId').value)+'/approve',{})}
</script></body></html>'''


def workbench_contract():
    required = ('/v1/cases', '/v1/metrics', '/v1/traces/', '/reviews', '/approve',
                '/v1/worker/tick', '/v1/dispatcher/tick')
    return {'status': 'SYNTHETIC_OPERATOR_WORKBENCH_READY',
            'required_actions': len(required),
            'actions_present': sum(item in WORKBENCH_HTML for item in required),
            'token_storage': 'browser_memory_only',
            'customer_delivery_target': 'local_mock_only',
            'real_users_observed': 0}
