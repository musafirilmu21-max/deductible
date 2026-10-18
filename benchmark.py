"""Benchmark: how accurate is each local model (and the keyword baseline) on the sample set?

Run:  python benchmark.py
Shows the real trade-off that open weights buy you — you can swap model size/cost
against accuracy without changing a line of app code or sending data anywhere.
"""
import tempfile
from deductible import process, keyword_classify, LLM

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

    llm05 = llm15 = None
    for path in ["models/qwen2.5-0.5b-instruct-q4_k_m.gguf",
                 "models/qwen2.5-1.5b-instruct-q4_k_m.gguf",
                 "models/qwen2.5-3b-instruct-q4_k_m.gguf"]:
        try:
            m = LLM(path)
            if "0.5b" in path:
                llm05 = m
            elif "1.5b" in path:
                llm15 = m
        except FileNotFoundError:
            pass

    models = [("0.5B", llm05), ("1.5B", llm15)]
    # include 3B if present
    try:
        models.append(("3B", LLM("models/qwen2.5-3b-instruct-q4_k_m.gguf")))
    except FileNotFoundError:
        pass

    print(f"  {'dataset':<24}{'keyword':>10}" + "".join(f"{lbl:>9}" for lbl, _ in models))
    for label, path in csvs:
        kw = score(path, lambda d, a: keyword_classify(d))
        line = f"  {label:<24}{kw[0]:>4}/{kw[1]:<5}"
        for _, m in models:
            c, n = score(path, m.classify) if m else (0, 0)
            line += f"{c:>6}/{n:<3}"
        print(line)

    print("\n  -> Keyword rules score high on the clean set they were written for,")
    print("     but rot on real bank garbage. The LLM generalises with no rules.")


if __name__ == "__main__":
    main()
