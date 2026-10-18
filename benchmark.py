"""Benchmark: how accurate is each local model (and the keyword baseline) on the sample set?

Run:  python benchmark.py
Shows the real trade-off that open weights buy you — you can swap model size/cost
against accuracy without changing a line of app code or sending data anywhere.
"""
import tempfile
from deductible import process, keyword_classify, keyword_match, LLM

GROUND_TRUTH = {
    "ADOBE CREATIVE CLOUD MONTHLY": "Software & Subscriptions",
    "STARBUCKS STORE 2145": "Meals",
    "GOOGLE WORKSPACE SUBSCRIPTION": "Software & Subscriptions",
    "UNITED AIRLINES TICKET SFO-JFK": "Travel",
    "MACBOOK PRO 14 M4": "Equipment",
    "MAILCHIMP MONTHLY PLAN": "Marketing",
    "DOCTOR VISIT COPAY": "Other/Personal",
    "UBER TRIP TO CLIENT MEETING": "Travel",
    "ACCOUNTANT QUARTERLY FEE": "Professional Services",
    "COMFY OFFICE CHAIR DEPOT": "Home Office",
    "NETFLIX SUBSCRIPTION": "Other/Personal",
    "VERIZON FIBER INTERNET": "Utilities",
    "UDEMY ADVANCED REACT COURSE": "Education",
    "LUNCH WITH PROSPECTIVE CLIENT": "Meals",
    "WHOLE FOODS GROCERIES": "Other/Personal",
    # messy set
    "SQ *BLUE BOTTLE COFFEE 4471 SF": "Meals",
    "TOAST* THE CORNER BISTRO": "Meals",
    "Claude.ai Subscription": "Software & Subscriptions",
    "OPENAI LLC": "Software & Subscriptions",
    "LH*Lufthansa 220-4471": "Travel",
    "DELTA AIR LINES 0062": "Travel",
    "FACEBK *ADS 88213": "Marketing",
    "MAILCHIMP *MONTHLY": "Marketing",
    "T-MOBILE BUSINESS": "Utilities",
    "WEWORK HOT DESK NYC": "Home Office",
    "COURSERA INC": "Education",
    "INSTACART": "Other/Personal",
    "ADOBE *CREATIVE": "Software & Subscriptions",
    "APPLE STORE R214": "Equipment",
}

def score(csv_path, classify_fn):
    res = process(csv_path, classify_fn, tempfile.mktemp(suffix=".csv"))
    correct = sum(1 for r in res["rows"] if GROUND_TRUTH.get(r["description"]) == r["category"])
    return correct, len(res["rows"])


def main():
    csvs = [("Clean merchant names", "sample_data/transactions.csv"),
            ("Messy bank strings", "sample_data/transactions_messy.csv")]

    # (label, classify_fn). Load the 1.5B once and reuse it for the hybrid too.
    cands = [("keyword", lambda d, a: keyword_classify(d))]
    llm15 = None
    for path, label in [("models/qwen2.5-0.5b-instruct-q4_k_m.gguf", "0.5B"),
                        ("models/qwen2.5-1.5b-instruct-q4_k_m.gguf", "1.5B"),
                        ("models/qwen2.5-3b-instruct-q4_k_m.gguf", "3B")]:
        try:
            m = LLM(path)
            cands.append((label, m.classify))
            if label == "1.5B":
                llm15 = m
        except FileNotFoundError:
            pass
    if llm15:
        cands.append(("hybrid", lambda d, a: keyword_match(d) or llm15.classify(d, a)))

    header = f"  {'dataset':<22}" + "".join(f"{lbl:>9}" for lbl, _ in cands)
    print(header)
    for label, path in csvs:
        line = f"  {label:<22}"
        for _, fn in cands:
            c, n = score(path, fn)
            line += f"{c:>6}/{n:<3}"
        print(line)

    print("\n  -> Rules alone rot on real bank garbage; the model alone is worse on")
    print("     clean names. The hybrid (rules + LLM on the unknown tail) is best of both.")


if __name__ == "__main__":
    main()
