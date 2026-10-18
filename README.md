# Deductible

**A local-first expense categorizer for freelancers.**
Your bank exports never leave your laptop. Runs on an open-weight LLM (GGUF via
`llama-cpp-python`). $0 per run. Swap the model to trade speed for accuracy.

> Built for the [Hacktoberfest Open-Source AI Challenge — Week 2: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12).

Freelancers hate two things at tax time: manually tagging every bank line, and
uploading their whole financial life to yet another SaaS. Deductible does the
tagging offline and hands you a Schedule-C-ready CSV — nothing but your laptop
ever sees the data.

## How it works

```
bank.csv  ──►  local open-weight model  ──►  taxes_ready.csv + summary
              (one label per transaction)
```

1. **The model does the fuzzy part.** Each transaction is classified into one of
   10 fixed expense categories. The prompt asks for a single number 1–10 (a
   constrained output tiny models can actually follow), with one few-shot example
   per category.
2. **The boring part is deterministic.** Tax treatment (meals 50%, everything
   else 100%, personal 0%), totals, and review flags are plain, auditable code —
   not model output.
3. **A keyword net is the safety fallback.** If the model emits something
   unparseable, a deterministic matcher catches it. A `--dry-run` mode runs the
   keyword net alone with no model at all.

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# download an open-weight model (pick your size)
#   https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF
curl -L -o models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf

python deductible.py --csv sample_data/transactions.csv --out taxes_ready.csv
python deductible.py --csv sample_data/transactions.csv --dry-run   # no model
python benchmark.py                                                 # accuracy table
python test_deductible.py                                           # tests
```

Input CSV needs `date,description,amount` columns. Output adds `category`,
`deductible_pct`, `deductible_amount`, and a `review` flag for items worth a
human glance (personal or > $1000).

## Talk to your books

`ask.py` reads the categorized CSV, builds a deterministic snapshot (so the
numbers are always right), and lets the local model answer plain-English
questions about your finances — offline:

```bash
python deductible.py --csv sample_data/transactions.csv --out taxes_ready.csv
python ask.py --csv taxes_ready.csv \
  --question "What are my biggest deductible expenses, and what should I double-check before filing?"
```

```
The biggest deductible expenses are for Equipment ($1,999.00) and Professional
Services ($482.00). You should double-check the classification of the MACBOOK PRO
14 M4 and the NETFLIX SUBSCRIPTION to ensure they are correctly categorized as
equipment and personal expenses, respectively.
```

The LLM never does arithmetic — the snapshot is precomputed by auditable Python.
The model only explains and advises, which is exactly where a language model
earns its place.

## Why open weights matter here

- **Privacy:** financial data is the most sensitive data a freelancer has. A
  local model means it never leaves the machine — no ToS, no breach surface, no
  vendor lock-in.
- **Cost:** tax season is bursty. An API that charges per token turns a free tool
  into a bill; a local model is $0 marginal per run.
- **Swappability:** the model is a file. You can drop in a bigger one for better
  accuracy, or a smaller one for a Raspberry Pi — no code change.

## Accuracy (honest numbers)

Run `python benchmark.py` yourself. Results on a commodity laptop, CPU-only:

| dataset | keyword | 0.5B | 1.5B | 3B |
|---|---|---|---|---|
| Clean merchant names | 13/15 | 5/15 | 11/15 | 10/15 |
| Messy bank strings | 10/14 | 6/14 | 7/14 | 7/14 |

Read that honestly — it is the whole story:

- On **clean, well-known merchant names**, a hand-tuned keyword table is hard to
  beat. It was written against exactly those names.
- On **messy real-world strings** ("SQ *BLUE BOTTLE 4471"), everything drops.
  Small local models do **not** magically beat rules at classification.
- So why run a model at all? Three real reasons: (1) zero rule maintenance for
  new merchants, (2) private and offline, and (3) the actual payoff — it powers
  the natural-language layer in `ask.py`. Turning a spreadsheet into a bookkeeper
  you can *talk to* is something no keyword table can do.

That is the honest state of small open models on a laptop today. A bigger model,
or a fine-tune on your own ledger, is one download away — and that is the entire
point of open weights.

## License

MIT.
