#!/usr/bin/env python3
"""web.py — a tiny browser UI for Deductible.

Serves a single page: paste your categorized CSV (or pick the sample), then ask
a plain-English question about your books. Fully offline; the LLM runs locally.

Run:  python web.py                 # serves http://127.0.0.1:8000
"""
import json
import os
import pathlib
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from deductible import LLM, Hybrid
from ask import snapshot, load_rows

HERE = pathlib.Path(__file__).parent
MODEL = HERE / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"

INDEX = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Deductible — a ledger that talks back</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root{
    --paper:#efe9da; --paper-2:#f7f2e6; --rule:#cfd8d0; --rule-strong:#b9c6bc;
    --margin:#b5483f; --ink:#22252a; --ink-soft:#4a4e55; --money:#1f5e43;
    --stamp:#9a3b34;
  }
  *{box-sizing:border-box}
  html,body{margin:0}
  body{
    background:
      radial-gradient(120% 90% at 50% -10%, #fbf7ec 0%, var(--paper) 55%, #e7e0cf 100%);
    color:var(--ink);
    font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:15px; line-height:1.5;
    min-height:100vh; padding:2.5rem 1rem 4rem;
  }
  .sheet{
    max-width:760px; margin:0 auto; background:var(--paper-2);
    border:1px solid var(--rule-strong);
    box-shadow:0 1px 0 #fff inset, 0 18px 40px -28px rgba(20,25,30,.55);
    position:relative;
  }
  /* the red margin rule of a bookkeeping ledger */
  .sheet::before{
    content:""; position:absolute; top:0; bottom:0; left:64px; width:1px;
    background:var(--margin); opacity:.55;
  }
  header{
    padding:1.6rem 1.6rem 1rem 88px; border-bottom:2px solid var(--rule-strong);
    position:relative;
  }
  header h1{
    font-family:Georgia,"Iowan Old Style","Palatino Linotype",serif;
    font-weight:600; font-size:1.65rem; letter-spacing:.01em; margin:0 0 .15rem;
  }
  header .sub{ color:var(--ink-soft); font-size:.92rem; margin:0 }
  .stamp{
    position:absolute; right:1.4rem; top:1.3rem; transform:rotate(6deg);
    font-family:Georgia,serif; font-weight:700; font-size:.72rem; letter-spacing:.14em;
    color:var(--stamp); border:2px solid var(--stamp); border-radius:3px;
    padding:.28rem .5rem; opacity:.8; text-transform:uppercase;
  }
  main{ padding:1.4rem 1.6rem 1.8rem 88px }
  .entry{ margin-bottom:1.6rem }
  .entry > label{ display:block; font-size:.82rem; color:var(--ink-soft); margin-bottom:.35rem }
  textarea, input[type=text]{
    width:100%; font:inherit; color:var(--ink);
    background:#fdfaf1; border:1px solid var(--rule-strong); border-radius:2px;
    padding:.6rem .7rem;
  }
  textarea{ min-height:10.5rem; font-family:ui-monospace,"Cascadia Code",Consolas,monospace;
            font-size:.82rem; line-height:1.45; resize:none; min-height:10.5rem }
  .row{ display:flex; gap:.6rem; align-items:stretch; flex-wrap:wrap }
  .row input[type=text]{ flex:1 1 260px }
  button{
    font:inherit; cursor:pointer; border-radius:2px; padding:.6rem .9rem;
    border:1px solid var(--ink); background:var(--ink); color:var(--paper-2);
    transition:transform .06s ease, background .15s ease;
  }
  button:hover{ background:#000 }
  button:active{ transform:translateY(1px) }
  button:disabled{ opacity:.45; cursor:not-allowed }
  button.ghost{ background:transparent; color:var(--ink) }
  button.ghost:hover{ background:#e6dfcd }
  button:focus-visible, input:focus-visible, textarea:focus-visible{
    outline:2px solid var(--margin); outline-offset:2px;
  }
  /* the ledger table */
  #out{
    margin:0; padding:0; border:none; background:transparent; white-space:normal;
    font-family:inherit; font-size:inherit;
  }
  .ledger{ width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums }
  .ledger th{
    text-align:left; font-weight:600; font-size:.78rem; color:var(--ink-soft);
    border-bottom:1px solid var(--rule-strong); padding:.35rem .2rem;
  }
  .ledger th.num, .ledger td.num{ text-align:right }
  .ledger td{
    padding:.42rem .2rem; border-bottom:1px solid var(--rule); vertical-align:top;
  }
  .ledger td.cat{ font-family:Georgia,serif }
  .ledger td.money{ color:var(--money); font-weight:600 }
  .ledger td.pct{ color:var(--ink-soft); font-size:.8rem }
  .total{
    display:flex; justify-content:space-between; align-items:baseline;
    margin-top:.9rem; padding-top:.7rem; border-top:2px solid var(--ink);
    font-family:Georgia,serif;
  }
  .total .lbl{ font-size:.95rem; color:var(--ink-soft) }
  .total .amt{ font-size:1.9rem; font-weight:700; color:var(--money);
               font-variant-numeric:tabular-nums }
  .answer{
    margin-top:1.4rem; padding:1rem 1.1rem; background:#fdfaf1;
    border-left:3px solid var(--money); font-size:.95rem;
  }
  .answer h3{ margin:0 0 .4rem; font-family:Georgia,serif; font-size:.95rem;
              font-weight:600; color:var(--ink-soft) }
  .flag{ color:var(--stamp); font-size:.78rem }
  .flagblock{ margin-top:1rem; padding:.7rem .9rem; border:1px dashed var(--stamp); border-radius:2px }
  .flagblock strong{ font-size:.82rem; color:var(--ink-soft) }
  .flagblock ul{ margin:.4rem 0 0; padding-left:1.1rem }
  .flagblock li{ font-size:.85rem; margin:.15rem 0 }
  .hint{ font-size:.8rem; color:var(--ink-soft); margin-top:.35rem }
  .empty{ color:var(--ink-soft); font-size:.92rem; font-style:italic }
  footer{ padding:.9rem 1.6rem 1.2rem 88px; color:var(--ink-soft); font-size:.78rem;
          border-top:1px solid var(--rule) }
  @media (max-width:560px){
    .sheet::before{ left:28px } header{padding-left:44px} main{padding-left:44px}
    footer{padding-left:44px} .stamp{display:none}
  }
  @media (prefers-reduced-motion:reduce){ *{transition:none!important} }
</style>
</head>
<body>
<div class="sheet">
  <header>
    <h1>Deductible</h1>
    <p class="sub">A bookkeeping ledger for freelancers that never leaves your laptop.</p>
    <span class="stamp">local only</span>
  </header>
  <main>
    <section class="entry">
      <label for="csv">Your transactions</label>
      <div class="hint" id="count"></div>
      <textarea id="csv" placeholder="date,description,amount
2026-09-01,SQ *BLUE BOTTLE COFFEE 4471 SF,-6.50
2026-09-05,LH*Lufthansa 220-4471,-612.30"></textarea>
      <div class="row" style="margin-top:.6rem">
        <button class="ghost" id="load-sample">Use the sample statement</button>
      </div>
    </section>

    <section class="entry">
      <label for="q">Ask about your books</label>
      <div class="row">
        <input id="q" type="text" placeholder="What are my biggest deductible expenses?">
        <button id="ask" disabled>Ask</button>
      </div>
    </section>

    <pre id="out" hidden></pre>
  </main>
  <footer>Runs an open-weight model on this machine. Nothing is uploaded.</footer>
</div>

<script>
const csv = document.getElementById('csv');
const q = document.getElementById('q');
const ask = document.getElementById('ask');
const out = document.getElementById('out');
const loadSample = document.getElementById('load-sample');
const NL = String.fromCharCode(10);

loadSample.onclick = async () => {
  const r = await fetch('/sample');
  csv.value = await r.text();
  ask.disabled = false;
  updateCount();
};
const countEl = document.getElementById('count');
function updateCount(){
  const n = csv.value.split(NL).filter(l => l.trim()).length - 1;
  countEl.textContent = n > 0 ? n + ' transactions ready to categorize · scroll the box to review all' : '';
}
csv.oninput = () => { ask.disabled = !csv.value.trim(); updateCount(); };

function esc(s){ return String(s).replace(/[&<>"']/g, function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
function render(data) {
  const snap = data.snapshot || '';
  const lines = snap.split(NL);
  const rows = []; let total = ''; const flagged = [];
  let section = '';
  for (const ln of lines) {
    if (/^Spending by category/.test(ln)) section = 'rows';
    if (/^Headline facts/.test(ln)) section = 'facts';
    if (/^Flagged for review/.test(ln)) section = 'flags';
    const m = ln.match(/^- (.+?): \$([\d,]+\.\d\d) \| \$([\d,]+\.\d\d) deductible/);
    if (m) { rows.push({cat:m[1], spent:m[2], ded:m[3]}); continue; }
    const t = ln.match(/^- Total estimated deductible: \$([\d,]+\.\d\d)/);
    if (t) total = t[1];
    const f = ln.match(/^- (.+?): \$([\d,.]+) -> (.+)$/);
    if (f && section === 'flags') flagged.push({desc:f[1], amt:f[2], cat:f[3]});
  }
  let html = '<table class="ledger"><thead><tr><th>Category</th><th class="num">Spent</th><th class="num">Deductible</th></tr></thead><tbody>';
  if (rows.length === 0) html += '<tr><td colspan="3" class="empty">No categorized rows yet.</td></tr>';
  else for (const r of rows) html += '<tr><td class="cat">' + esc(r.cat) + '</td><td class="num">$' + esc(r.spent) + '</td><td class="num money">$' + esc(r.ded) + '</td></tr>';
  html += '</tbody></table>';
  if (total) html += '<div class="total"><span class="lbl">Estimated deductible</span><span class="amt">$' + esc(total) + '</span></div>';
  if (flagged.length) html += '<div class="hint" style="margin:.35rem 0 0">Estimate only &mdash; verify the flagged items below before filing.</div>';
  if (flagged.length) {
    html += '<div class="flagblock"><strong>Review these (model-classified or personal — verify before filing)</strong><ul>';
    for (const f of flagged) html += '<li class="flag">' + esc(f.desc) + ': $' + esc(f.amt) + ' &rarr; ' + esc(f.cat) + '</li>';
    html += '</ul></div>';
  }
  const ans = (data.answer || '').split(NL).map(esc).join('<br>');
  html += '<div class="answer"><h3>Your bookkeeper says</h3>' + ans + '</div>';
  out.innerHTML = html;
  out.hidden = false;
}
ask.onclick = async () => {
  ask.disabled = true; const old = ask.textContent; ask.textContent = 'Reading your books…'; out.hidden = true;
  try {
    const r = await fetch('/ask', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({csv: csv.value, question: q.value || 'Summarize my biggest deductible expenses.'})
    });
    const data = await r.json();
    if (data.error) { out.textContent = 'Could not read that: ' + data.error; out.hidden = false; return; }
    render(data);
  } catch (e) {
    out.textContent = 'Could not reach the local model: ' + e.message; out.hidden = false;
  } finally {
    ask.disabled = false; ask.textContent = old;
  }
};
</script>
</body>
</html>"""


def categorize_csv(text):
    """Reuse deductible.process on in-memory CSV -> categorized rows dict."""
    import csv as _csv
    import io
    rows = list(_csv.DictReader(io.StringIO(text)))
    return rows


"""Shared, lazily-loaded model. llama-cpp Llama is not safe for concurrent
completion, so every call goes through _MODEL_LOCK."""
_MODEL_LOCK = threading.Lock()
_HYBRID = None

def get_hybrid():
    global _HYBRID
    if _HYBRID is None:
        with _MODEL_LOCK:
            if _HYBRID is None:
                _HYBRID = Hybrid(str(MODEL), n_ctx=2048)  # the snapshot prompt is ~450 tokens
    return _HYBRID


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self._send(200, INDEX.encode(), "text/html")
        elif self.path == "/sample":
            sample = (HERE / "sample_data" / "transactions_messy.csv").read_text(encoding="utf-8")
            self._send(200, sample.encode(), "text/plain")
        else:
            self._send(404, b"not found")

    def do_POST(self):
        if self.path != "/ask":
            return self._send(404, b"not found")
        try:
            try:
                length = int(self.headers.get("Content-Length", "") or 0)
            except (TypeError, ValueError):
                return self._send(400, json.dumps({"error": "Bad Content-Length"}).encode())
            if length < 0 or length > 1_048_576:
                return self._send(413, json.dumps({"error": "Request too large (max 1 MiB)"}).encode())
            req = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(req, dict):
                return self._send(400, json.dumps({"error": "Expected a JSON object"}).encode())
            text = req.get("csv", "")
            question = req.get("question", "Summarize my biggest deductible expenses.")
            if not isinstance(text, str) or not isinstance(question, str):
                return self._send(400, json.dumps({"error": "csv and question must be strings"}).encode())
            import deductible as D
            rows = categorize_csv(text)
            # If the pasted CSV is raw (no category column), categorize with the shared hybrid.
            if rows and "category" not in rows[0]:
                tmp = None
                try:
                    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="") as f:
                        f.write(text)
                        tmp = f.name
                    outp = tmp + ".out"
                    # resolve the model BEFORE locking: get_hybrid() takes _MODEL_LOCK itself
                    # and threading.Lock is not re-entrant, so nesting it deadlocks.
                    hybrid = get_hybrid()
                    # the classify callback runs create_chat_completion, so it needs the lock too
                    with _MODEL_LOCK:
                        D.process(tmp, hybrid.classify, outp)
                    rows = categorize_csv(pathlib.Path(outp).read_text(encoding="utf-8"))
                finally:
                    if tmp:
                        for p in (tmp, tmp + ".out"):
                            try: os.unlink(p)
                            except OSError: pass
            snap = snapshot(rows)
            if not rows:
                return self._send(200, json.dumps({"snapshot": snap, "answer": "Paste some transactions first."}).encode())
            hybrid = get_hybrid()
            with _MODEL_LOCK:
                resp = hybrid.llm.llm.create_chat_completion(
                    messages=[
                        {"role": "system", "content": "You are an accurate, practical bookkeeper for a self-employed freelancer. Answer ONLY from the financial snapshot. Cite concrete dollar figures that already appear in the snapshot. Do NOT add, subtract, or estimate any numbers yourself. If the snapshot lacks the answer, say so plainly. Be concise; use a short bulleted list, one item per line."},
                        {"role": "user", "content": f"FINANCIAL SNAPSHOT:\n{snap}\n\nQUESTION: {question}"},
                    ], max_tokens=512, temperature=0.2)
            answer = resp["choices"][0]["message"]["content"].strip()
            return self._send(200, json.dumps({"snapshot": snap, "answer": answer}).encode())
        except SystemExit:
            return self._send(503, json.dumps({"error": "Model not available - download a GGUF (see README) or use the CLI with --mode dry."}).encode())
        except Exception:
            return self._send(500, json.dumps({"error": "Internal error (check server log)."}).encode())

    def log_message(self, *a):
        pass


def main():
    port = 8000
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Deductible web UI: http://127.0.0.1:{port}   (Ctrl+C to stop)")
    srv.serve_forever()


if __name__ == "__main__":
    main()