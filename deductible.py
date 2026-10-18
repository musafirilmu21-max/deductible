#!/usr/bin/env python3
"""Deductible — local-first expense categorizer for freelancers.

Every transaction is classified by an open-weight LLM running on THIS machine
(GGUF via llama-cpp-python). No bank data ever leaves the laptop, there is no
per-row API cost, and you can swap the model for a bigger one at any time.

Usage:
    python deductible.py --csv sample_data/transactions.csv --out taxes_ready.csv
    python deductible.py --csv my_bank.csv --model models/qwen2.5-0.5b-instruct-q4_k_m.gguf

Design: the model does ONE thing (pick a category label from a fixed list) —
the semantic, fuzzy part. Everything else (tax treatment, totals, flags) is
deterministic, so the output is auditable.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

CATEGORIES = [
    "Software & Subscriptions",
    "Home Office",
    "Travel",
    "Meals",
    "Equipment",
    "Marketing",
    "Professional Services",
    "Utilities",
    "Education",
    "Other/Personal",
]

# Simplified US Schedule C treatment: fraction of the amount that is deductible.
DEDUCTIBLE_RATE = {
    "Software & Subscriptions": 1.0,
    "Home Office": 1.0,
    "Travel": 1.0,
    "Meals": 0.5,  # meals are 50% deductible
    "Equipment": 1.0,
    "Marketing": 1.0,
    "Professional Services": 1.0,
    "Utilities": 1.0,
    "Education": 1.0,
    "Other/Personal": 0.0,
}

# Deterministic fallback + sanity net when the model returns junk.
KEYWORDS = {
    "Software & Subscriptions": ["adobe", "figma", "github", "notion", "aws", "google workspace",
                                 "subscription", "saas", "dropbox", "slack", "license", "chatgpt", "jetbrains"],
    "Home Office": ["desk", "chair", "monitor", "lamp", "office", "keyboard", "standing desk"],
    "Travel": ["airline", "flight", "hotel", "uber", "lyft", "train", "airbnb", "delta", "united"],
    "Meals": ["coffee", "lunch", "dinner", "restaurant", "cafe", "starbucks", "doordash", "meal", "food"],
    "Equipment": ["laptop", "macbook", "camera", "lens", "ssd", "hard drive", "printer", "iphone"],
    "Marketing": ["facebook ads", "google ads", "ads", "mailchimp", "canva", "promo", "advertis"],
    "Professional Services": ["accountant", "lawyer", "legal", "contractor", "consultant", "bookkeeper"],
    "Utilities": ["internet", "comcast", "verizon", "electric", "phone bill", "mobile", "at&t"],
    "Education": ["course", "udemy", "coursera", "book", "conference", "workshop", "training"],
    "Other/Personal": ["groceries", "netflix", "spotify", "gym", "rent", "personal", "hulu", "grocery"],
}

SYSTEM = (
    "You are a meticulous bookkeeper for a self-employed freelancer. "
    "You classify each bank or card transaction into exactly one expense category."
)

PROMPT_TMPL = """Classify a freelancer's bank transaction for tax purposes.
Choose the single best category by its NUMBER. Reply with ONLY the number (1-10).

{cats}

Examples (one per category):
"ADOBE CREATIVE CLOUD" -> 1
"HERMAN MILLER AERON CHAIR" -> 2
"UNITED AIRLINES TICKET" -> 3
"STARBUCKS COFFEE" -> 4
"APPLE MACBOOK PRO" -> 5
"FACEBOOK ADS CAMPAIGN" -> 6
"ACCOUNTANT QUARTERLY FEE" -> 7
"VERIZON INTERNET BILL" -> 8
"UDEMY ONLINE COURSE" -> 9
"NETFLIX SUBSCRIPTION" -> 10

Note: personal subscriptions and personal expenses (streaming, groceries, medical, gym) are 10.
Transaction: "{desc}" for ${amount}
Number:"""


def build_prompt(desc: str, amount: str) -> str:
    cats = "\n".join(f"{i}. {c}" for i, c in enumerate(CATEGORIES, 1))
    return PROMPT_TMPL.format(cats=cats, desc=desc, amount=amount)


def keyword_classify(desc: str) -> str:
    """Deterministic classifier. Used as --dry-run and as a safety net."""
    d = (desc or "").lower()
    for cat, kws in KEYWORDS.items():
        if any(k in d for k in kws):
            return cat
    return "Other/Personal"


def parse_label(raw: str, desc: str) -> str:
    """Map model output back to a category; fall back to keywords if unparseable."""
    r = (raw or "").strip()
    low = r.lower()
    # 1) the model echoed a category name
    matches = [c for c in CATEGORIES if c.lower() in low]
    if matches:
        return max(matches, key=len)
    # 2) the model replied with a number 1..10 (the constrained format)
    m = re.search(r"\b(10|[1-9])\b", r)
    if m:
        return CATEGORIES[int(m.group(1)) - 1]
    # 3) unparseable -> deterministic keyword net
    return keyword_classify(desc)


class LLM:
    """Thin wrapper so tests can run without a model."""

    def __init__(self, model_path: str, n_ctx: int = 512, n_threads: int | None = None):
        from llama_cpp import Llama  # imported lazily; not needed for --dry-run

        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            verbose=False,
        )

    def classify(self, desc: str, amount: str) -> str:
        resp = self.llm.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": build_prompt(desc, amount)},
            ],
            max_tokens=12,
            temperature=0.0,
        )
        raw = resp["choices"][0]["message"]["content"]
        return parse_label(raw, desc)


def process(csv_path: str, classify_fn, out_path: str) -> dict:
    rows_out = []
    totals = {c: 0.0 for c in CATEGORIES}
    deductible_total = 0.0
    needs_review = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            desc = row.get("description", "").strip()
            amount = row.get("amount", "0").strip()
            try:
                amt = float(str(amount).replace("$", "").replace(",", ""))
            except ValueError:
                amt = 0.0
            category = classify_fn(desc, amount)
            rate = DEDUCTIBLE_RATE.get(category, 0.0)
            deductible = round(abs(amt) * rate, 2)
            flagged = category == "Other/Personal" or abs(amt) > 1000
            if flagged:
                needs_review += 1
            totals[category] += abs(amt)
            deductible_total += deductible
            rows_out.append({
                "date": row.get("date", ""),
                "description": desc,
                "amount": amt,
                "category": category,
                "deductible_pct": int(rate * 100),
                "deductible_amount": deductible,
                "review": "CHECK" if flagged else "",
            })

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date", "description", "amount", "category",
            "deductible_pct", "deductible_amount", "review",
        ])
        writer.writeheader()
        writer.writerows(rows_out)

    return {
        "rows": rows_out,
        "totals": totals,
        "deductible_total": round(deductible_total, 2),
        "needs_review": needs_review,
        "count": len(rows_out),
    }


def print_summary(result: dict) -> None:
    print("\n=== Deductible summary ===")
    for cat, tot in sorted(result["totals"].items(), key=lambda x: -x[1]):
        if tot:
            print(f"  {cat:<26} ${tot:>10,.2f}  ({int(DEDUCTIBLE_RATE[cat]*100)}% deductible)")
    print(f"\n  Transactions:            {result['count']}")
    print(f"  Estimated deductible:    ${result['deductible_total']:,.2f}")
    print(f"  Flagged for review:      {result['needs_review']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Local-first expense categorizer for freelancers.")
    ap.add_argument("--csv", required=True, help="Input CSV with date,description,amount columns.")
    ap.add_argument("--out", default="taxes_ready.csv", help="Output CSV path.")
    ap.add_argument("--model", default="models/qwen2.5-1.5b-instruct-q4_k_m.gguf",
                    help="Path to a GGUF open-weight model.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Skip the model; use the deterministic keyword classifier.")
    args = ap.parse_args(argv)

    if args.dry_run:
        classify_fn = lambda desc, amount: keyword_classify(desc)  # noqa: E731
    else:
        llm = LLM(args.model)
        classify_fn = llm.classify

    result = process(args.csv, classify_fn, args.out)
    print_summary(result)
    print(f"\n  Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
