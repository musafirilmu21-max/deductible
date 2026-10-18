#!/usr/bin/env python3
"""ask.py — talk to your books, privately.

Loads a categorized CSV (from deductible.py), builds a deterministic financial
snapshot, then asks the local open-weight LLM a plain-English question about it.
The numbers come from auditable code; the LLM only explains and advises.

Example:
    python deductible.py --csv sample_data/transactions.csv --out taxes_ready.csv
    python ask.py --csv taxes_ready.csv \
        --question "What are my biggest deductible expenses, and what should I double-check before filing?"
"""
import argparse
import csv
from collections import defaultdict

from deductible import LLM


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def snapshot(rows):
    totals = defaultdict(float)
    ded = defaultdict(float)
    for r in rows:
        try:
            amt = abs(float(r.get("amount", 0) or 0))
        except ValueError:
            amt = 0.0
        totals[r["category"]] += amt
        try:
            ded[r["category"]] += float(r.get("deductible_amount", 0) or 0)
        except ValueError:
            pass
    lines = ["Spending by category (amount | deductible):"]
    for c in sorted(totals, key=lambda x: -totals[x]):
        if totals[c]:
            lines.append(f"- {c}: ${totals[c]:,.2f} | ${ded[c]:,.2f} deductible")
    total = sum(ded.values())
    lines.append("\nHeadline facts (precomputed):")
    lines.append(f"- Total estimated deductible: ${total:,.2f}")
    top = sorted([(c, v) for c, v in ded.items() if v > 0], key=lambda x: -x[1])[:3]
    for i, (c, v) in enumerate(top, 1):
        lines.append(f"- Deductible category #{i}: {c} = ${v:,.2f}")
    flagged = [r for r in rows if r.get("review")]
    if flagged:
        lines.append("\nFlagged for review (possible misclassification or large amount):")
        for r in flagged:
            lines.append(f"- {r['description']}: ${abs(float(r['amount'])):,.2f} -> {r['category']}")
    return "\n".join(lines)


def ask(rows, question, model_path):
    snap = snapshot(rows)
    llm = LLM(model_path)
    system = (
        "You are an accurate, practical bookkeeper for a self-employed freelancer. "
        "Answer ONLY from the financial snapshot provided. Use concrete dollar figures "
        "from it. If the snapshot does not contain the answer, say so plainly. "
        "Be concise (a short paragraph or a few bullets)."
    )
    user = f"FINANCIAL SNAPSHOT:\n{snap}\n\nQUESTION: {question}"
    resp = llm.llm.create_chat_completion(
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        max_tokens=320,
        temperature=0.2,
    )
    return resp["choices"][0]["message"]["content"].strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ask your offline bookkeeping copilot a question.")
    ap.add_argument("--csv", required=True, help="Categorized CSV produced by deductible.py")
    ap.add_argument("--question", required=True)
    ap.add_argument("--model", default="models/qwen2.5-1.5b-instruct-q4_k_m.gguf")
    args = ap.parse_args(argv)
    rows = load_rows(args.csv)
    print("SNAPSHOT\n" + "-" * 40)
    print(snapshot(rows))
    print("\nANSWER\n" + "-" * 40)
    print(ask(rows, args.question, args.model))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
