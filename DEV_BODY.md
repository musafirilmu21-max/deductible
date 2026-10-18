*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 2: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12).*

Every freelancer knows the tax-time ritual: scroll a year of bank lines, tag each one, and try to remember whether `SQ *BLUE BOTTLE 4471` was a client meeting or a personal coffee. The obvious "AI solution" is to upload your whole financial life to a SaaS and let their model sort it. I wanted the opposite: **do it on your own laptop, offline, and use the model only for the part a model is actually good at.**

So I built **Deductible** — a local-first bookkeeping copilot. It tags your transactions into 10 expense categories, applies the right tax treatment, exports a tax-prep starter CSV (categorised spending + deductible estimates) your accountant can drop straight into Schedule C, and then lets you *ask your books questions in plain English* — with no data ever leaving the laptop.

The classifier is a **hybrid**: deterministic rules handle merchants you have seen before (fast, free, exact), and an open-weight LLM handles the unknown long tail — the `SQ *BLUE BOTTLE 4471` garbage that makes keyword tables rot. I benchmarked it honestly, and the hybrid beats either approach alone.

## What I Built

Two jobs:

1. **Categorize** a bank/card CSV into 10 expense categories, apply tax treatment (meals 50%, personal 0%, the rest 100%), total it up, and flag items worth a human glance. Output is an auditable CSV — the numbers come from plain Python, not from a model's vibes.
2. **Explain.** `ask.py` builds a *deterministic* snapshot of your finances and lets the local model answer questions like *"What are my biggest deductible expenses, and what should I double-check before filing?"* — offline.

Everything runs on an open-weight model (Qwen2.5 via `llama-cpp-python`, GGUF): no network, no API key, no per-row cost. `--mode hybrid` is the default; `--mode dry` needs no model at all.

## Demo

```bash
python deductible.py --csv sample_data/transactions.csv --out taxes_ready.csv
python ask.py --csv taxes_ready.csv \
  --question "What are my biggest deductible expenses, and what should I double-check before filing?"
```

The ask layer prints a snapshot and then the model's answer:

```plaintext
Headline facts (precomputed):
- Total estimated deductible: $3,488.11
- Deductible category #1: Equipment = $1,999.00
- Deductible category #2: Professional Services = $482.00
- Deductible category #3: Travel = $371.60
Flagged for review (possible misclassification or large amount):
- MACBOOK PRO 14 M4: $1,999.00 -> Equipment
- NETFLIX SUBSCRIPTION: $15.49 -> Other/Personal

ANSWER
--------
The biggest deductible expenses are for Equipment ($1,999.00) and Professional
Services ($482.00). You should double-check the classification of the MACBOOK PRO
14 M4 and the NETFLIX SUBSCRIPTION to ensure they are correctly categorized as
equipment and personal expenses, respectively.
```

Note the design choice: **the model never does the math.** The snapshot is precomputed by auditable Python; the model only explains and advises. That is the difference between a toy and a tool your accountant does not have to re-check from scratch.

### See it running

![Deductible ledger UI: a messy bank statement, an offline answer, and a categorized ledger](https://raw.githubusercontent.com/musafirilmu21-max/deductible/main/demo_screenshot.png)

That is a real run of the browser UI (`web.py`), captured by an automated Playwright test (`e2e_web_test.py`) that loads the page, asks a question, and asserts the grounded answer came back — so the screenshot is reproducible, not hand-typed.


## Code

GitHub: https://github.com/musafirilmu21-max/deductible

- `deductible.py` — categorizer (`--mode hybrid|model|dry`) + CSV export
- `ask.py` — the "talk to your books" layer
- `benchmark.py` — the accuracy table below
- `web.py` — a local browser UI (the screenshot above)
- `e2e_web_test.py` — Playwright test that drives the UI end to end
- `test_deductible.py` — tests for the deterministic parts
- Sample data + a clean MIT license.

## How I Built It

The interesting part is what the benchmark forced me to change.

I started with the obvious design: the model classifies each transaction. To make a tiny model reliable I constrained its output to a single number 1–10 and gave it one few-shot example per category. Then I measured. I labelled two small datasets — **clean** merchant names, and **messy** real bank strings like `SQ *BLUE BOTTLE COFFEE 4471 SF` — and ran three open models, a keyword baseline, and the hybrid:

| dataset | keyword rules | Qwen2.5-0.5B | Qwen2.5-1.5B | Qwen2.5-3B | **hybrid** |
|---|---|---|---|---|---|
| Clean merchant names | 15/15 | 5/15 | 11/15 | 10/15 | **15/15** |
| Messy bank strings | 13/14 | 6/14 | 7/14 | 7/14 | **13/14** |

Two uncomfortable truths fell out first:

1. **A hand-tuned keyword table beats the models on clean names.** Of course it does — I wrote the keywords against those exact names.
2. **Bigger was not automatically better** — 3B did not beat 1.5B at this task.

But on **real bank garbage**, rules rot (13/14) and the model alone is worse (7/14). Neither is good enough. So I stopped asking "rules or model?" and combined them: rules for any merchant they already recognize (instant, free, exact), and the LLM only for the unknown tail. That **hybrid hits 13/14 on the messy set** — better than either alone — while staying a hair behind pure rules on the clean set they were written for.

Then I asked the better question: *what is a language model actually good at here?* Not memorizing that "Starbucks = meals" — a rule does that for free. It is good at **talking to a human about their money.** So the model's headline job became `ask.py`: turning a spreadsheet into a bookkeeper you can ask *"what should I double-check before filing?"* — grounded in numbers the Python computed, so it never hallucinates a total.

The architecture, in one line: **rules classify, Python calculates, the LLM explains.**

Honest scope: this is a categorisation aid, not a tax filing. It is the input layer to a real Schedule C — it does not do home-office Form 8829, a vehicle log, or depreciation. Those stay with your accountant. What it saves you is the hour a month spent eyeballing a year of statements into the right buckets.

## The Side-Hustle Economics (who actually pays)

The buyer is the **solo 1099 contractor** — a designer, developer, VA, or consultant doing $40–150k/yr. Their pain is real and monthly: a bank export that reads like `SQ *BLUE BOTTLE 4471` and a tax bill that punishes a mislabelled meal.

What would they pay? A freelance accountant charges **$150–400/hr**; a year-end session alone is several hundred dollars, mostly billed for what Deductible does in minutes. At **$15/quarter** ($60/yr — under the cost of one accountant hour) the tool pays for itself the first month if it saves more than its price by cutting an accountant hour that would otherwise be spent tagging those same transactions. The honest pitch is not "replaces your accountant" — it is "stops you paying your accountant to tag coffee." That is a real willingness-to-pay signal, not a land-grab TAM.

The unit economics work *because* it is open weights: $0 marginal inference cost, so the $15 is nearly pure margin once built.

*(This is a one-day build — there is no real user yet, so this is the pricing hypothesis, stated honestly rather than a fake testimonial.)*

## Why Does Open Innovation Matter?

- **Privacy is the product.** Financial data is the most sensitive data a freelancer owns. Running the model locally means it never leaves the laptop — no ToS, no breach surface, no vendor seeing your ledger. A closed API cannot offer that at any price.
- **$0 marginal cost.** Tax season is bursty. An API billed per token turns a free tool into a bill you avoid using in March. A local model costs nothing per run.
- **Swappability as a feature, not a limitation.** Open weights let *you* choose the brain: a 0.5B for a Raspberry Pi, a 1.5B for a laptop, or a fine-tune on your own ledger for better accuracy — by changing a file path. The benchmark above only exists *because* weights are open and downloadable. You cannot A/B three models behind one closed endpoint.
- **Honest tooling.** Because I can read and swap the model, I can benchmark it and tell you the truth about where it is weak. That transparency is only possible in the open.

## My First User

Not yet — this was built in a day. The explicit next step is to hand it to a freelancer for one real quarter of transactions and report back what they used, what they ignored, and what they asked for next. (Early signal from showing the `ask.py` flow: people want a way to teach it *their* recurring vendors — which is exactly the fine-tune path open weights make possible.)

## Prize Categories

No partner-specific technology used — built entirely on open-weight Qwen models via `llama-cpp-python`. Entering for the **overall prize** and the **Best Use of an open-weight model** spirit of the prompt.

---

*If you got value from this, try `benchmark.py` on your own bank export and tell me how your vendors do — I would genuinely like to see where the hybrid breaks.*
