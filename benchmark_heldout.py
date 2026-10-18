#!/usr/bin/env python3
"""Held-out benchmark: ~150 labelled transactions with merchants NOT hand-tuned
into the keyword table. This tests generalization, not memorisation.

Writes sample_data/transactions_heldout.csv and reports accuracy for:
  keyword (rules only) | Qwen2.5-1.5B (model only) | hybrid (rules + model on unknowns)

Run:  python benchmark_heldout.py
"""
import csv
import pathlib
import tempfile

from deductible import keyword_classify, keyword_match, LLM, process

DATA = [
    # --- Software & Subscriptions ---
    ("ZOOM VIDEO COMM 888-799-9666", "Software & Subscriptions"),
    ("ATLASSIAN JIRA MONTHLY", "Software & Subscriptions"),
    ("LINEAR APP", "Software & Subscriptions"),
    ("VERCEL INC", "Software & Subscriptions"),
    ("DIGITALOCEAN", "Software & Subscriptions"),
    ("1PASSWORD", "Software & Subscriptions"),
    ("MIRO BOARD", "Software & Subscriptions"),
    ("LOOM SUBSCRIPTION", "Software & Subscriptions"),
    ("CALENDLY LLC", "Software & Subscriptions"),
    ("SUPERHUMAN LABS", "Software & Subscriptions"),
    ("NETLIFY", "Software & Subscriptions"),
    ("HEROKU", "Software & Subscriptions"),
    ("LASTPASS", "Software & Subscriptions"),
    ("WEBFLOW INC", "Software & Subscriptions"),
    ("AIRTABLE INC", "Software & Subscriptions"),
    # --- Travel ---
    ("MARRIOTT HOTELS", "Travel"),
    ("HILTON GARDEN INN", "Travel"),
    ("EXPEDIA INC", "Travel"),
    ("AMERICAN AIRLINES", "Travel"),
    ("ALASKA AIR 027", "Travel"),
    ("BRITISH AIRWAYS", "Travel"),
    ("EMIRATES AIRLINE", "Travel"),
    ("SPIRIT AIRLINES", "Travel"),
    ("HERTZ RENT A CAR", "Travel"),
    ("AVIS RENTAL", "Travel"),
    ("FLIXBUS", "Travel"),
    ("BOOKING.COM", "Travel"),
    ("TRAINLINE", "Travel"),
    ("KAYAK.COM", "Travel"),
    ("AIR CANADA", "Travel"),
    # --- Meals ---
    ("PHILZ COFFEE", "Meals"),
    ("SWEETGREEN", "Meals"),
    ("CHIPOTLE MEXICAN GRILL", "Meals"),
    ("PANERA BREAD", "Meals"),
    ("SHAKE SHACK", "Meals"),
    ("DUNKIN DONUTS", "Meals"),
    ("PEETS COFFEE", "Meals"),
    ("CAVA", "Meals"),
    ("JERSEY MIKES", "Meals"),
    ("WENDYS", "Meals"),
    ("NOBU RESTAURANT", "Meals"),
    ("TACO BELL", "Meals"),
    ("SUBWAY 4471", "Meals"),
    ("LOCAL DINER", "Meals"),
    ("BOSTON MARKET", "Meals"),
    # --- Equipment ---
    ("DELL TECHNOLOGIES", "Equipment"),
    ("LENOVO", "Equipment"),
    ("LOGITECH", "Equipment"),
    ("SAMSUNG ELECTRONICS", "Equipment"),
    ("SONY STORE", "Equipment"),
    ("BOSE CORP", "Equipment"),
    ("ANKER", "Equipment"),
    ("WACOM", "Equipment"),
    ("GOPRO", "Equipment"),
    ("DJI STORE", "Equipment"),
    ("RAZER INC", "Equipment"),
    ("HP INC", "Equipment"),
    ("ASUS", "Equipment"),
    ("BEST BUY", "Equipment"),
    ("MICROSOFT STORE", "Equipment"),
    # --- Home Office ---
    ("IKEA", "Home Office"),
    ("HERMAN MILLER STORE", "Home Office"),
    ("AUTONOMOUS DESK", "Home Office"),
    ("BRANCH FURNITURE", "Home Office"),
    ("WAYFAIR", "Home Office"),
    ("STAPLES", "Home Office"),
    ("OFFICE DEPOT", "Home Office"),
    ("ERGOTRON", "Home Office"),
    ("SECRETLAB", "Home Office"),
    ("CB2 FURNITURE", "Home Office"),
    ("UPLIFT DESK", "Home Office"),
    ("FLEXISPOT", "Home Office"),
    ("HON OFFICE", "Home Office"),
    ("STEELCASE", "Home Office"),
    ("KNOLL", "Home Office"),
    # --- Marketing ---
    ("HUBSPOT INC", "Marketing"),
    ("KLAVIYO", "Marketing"),
    ("CONVERTKIT", "Marketing"),
    ("SEMRUSH", "Marketing"),
    ("AHREFS", "Marketing"),
    ("BUFFER APP", "Marketing"),
    ("HOOTSUITE", "Marketing"),
    ("LINKEDIN ADS", "Marketing"),
    ("TIKTOK ADS", "Marketing"),
    ("PINTEREST ADS", "Marketing"),
    ("GOOGLE ADWORDS", "Marketing"),
    ("BING ADS", "Marketing"),
    ("OUTBRAIN", "Marketing"),
    ("TABOOLA", "Marketing"),
    ("CAPTERRA ADS", "Marketing"),
    # --- Professional Services ---
    ("H&R BLOCK", "Professional Services"),
    ("TURBOTAX", "Professional Services"),
    ("LEGALZOOM", "Professional Services"),
    ("PAYPAL FEE", "Professional Services"),
    ("SQUARE FEE", "Professional Services"),
    ("CPA FIRM LLP", "Professional Services"),
    ("NOTARY PUBLIC", "Professional Services"),
    ("ADP PAYROLL", "Professional Services"),
    ("GUSTO PAYROLL", "Professional Services"),
    ("UPWORK SERVICE FEE", "Professional Services"),
    ("FIVERR FEE", "Professional Services"),
    ("XERO ACCOUNTING", "Professional Services"),
    ("LAW OFFICE OF SMITH", "Professional Services"),
    ("CONSULTING RETAINER", "Professional Services"),
    ("BOOKKEEPING SVC", "Professional Services"),
    # --- Utilities ---
    ("PG&E", "Utilities"),
    ("DUKE ENERGY", "Utilities"),
    ("CONEDISON", "Utilities"),
    ("SPECTRUM", "Utilities"),
    ("FRONTIER COMM", "Utilities"),
    ("GOOGLE FI", "Utilities"),
    ("MINT MOBILE", "Utilities"),
    ("CRICKET WIRELESS", "Utilities"),
    ("VISIBLE WIRELESS", "Utilities"),
    ("CENTURYLINK", "Utilities"),
    ("NATIONAL GRID", "Utilities"),
    ("WATER DEPT CITY", "Utilities"),
    ("XFINITY", "Utilities"),
    ("COX COMM", "Utilities"),
    ("WOW INTERNET", "Utilities"),
    # --- Education ---
    ("MASTERCLASS", "Education"),
    ("SKILLSHARE", "Education"),
    ("PLURALSIGHT", "Education"),
    ("LINKEDIN LEARNING", "Education"),
    ("EDX COURSE", "Education"),
    ("OREILLY MEDIA", "Education"),
    ("PACKT PUBLISHING", "Education"),
    ("CONFERENCE REG FEE", "Education"),
    ("SEMINAR TICKET", "Education"),
    ("BOOTCAMP FEE", "Education"),
    ("CERTIFICATION EXAM", "Education"),
    ("DATACAMP", "Education"),
    ("TREEHOUSE", "Education"),
    ("CODING DOJO", "Education"),
    ("UDEMY ONLINE", "Education"),
    # --- Other/Personal ---
    ("SAFEWAY", "Other/Personal"),
    ("KROGER", "Other/Personal"),
    ("COSTCO WHOLESALE", "Other/Personal"),
    ("TARGET STORE", "Other/Personal"),
    ("WALMART", "Other/Personal"),
    ("CVS PHARMACY", "Other/Personal"),
    ("WALGREENS", "Other/Personal"),
    ("PLANET FITNESS", "Other/Personal"),
    ("EQUINOX GYM", "Other/Personal"),
    ("DISNEY PLUS", "Other/Personal"),
    ("HBO MAX", "Other/Personal"),
    ("APPLE MUSIC", "Other/Personal"),
    ("AMAZON PRIME", "Other/Personal"),
    ("WHOLE FOODS MKT", "Other/Personal"),
    ("LOCAL GROCERY COOP", "Other/Personal"),
]

CSV_PATH = "sample_data/transactions_heldout.csv"


def write_csv():
    pathlib.Path(CSV_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "description", "amount"])
        for i, (desc, _cat) in enumerate(DATA):
            w.writerow([f"2026-{(i % 12) + 1:02d}-{(i % 27) + 1:02d}", desc, f"-{(i % 480) + 5}.00"])


def accuracy(classify_fn):
    truth = dict(DATA)
    out = pathlib.Path(tempfile.mkdtemp()) / "out.csv"
    res = process(CSV_PATH, classify_fn, str(out))
    correct = sum(1 for r in res["rows"] if truth.get(r["description"]) == r["category"])
    return correct, len(res["rows"])


def main():
    write_csv()
    print(f"Held-out set: {len(DATA)} rows, {len(set(c for _, c in DATA))} categories\n")

    kw = accuracy(lambda d, a: (keyword_classify(d), "rule"))
    print(f"  keyword (rules only)      {kw[0]:>3}/{kw[1]}  ({kw[0]/kw[1]:.0%})")

    llm = LLM("models/qwen2.5-1.5b-instruct-q4_k_m.gguf")
    m = accuracy(llm.classify)
    print(f"  Qwen2.5-1.5B (model only) {m[0]:>3}/{m[1]}  ({m[0]/m[1]:.0%})")

    def hybrid(d, a):
        k = keyword_match(d)
        return (k, "rule") if k else llm.classify(d, a)

    h = accuracy(hybrid)
    print(f"  hybrid (rules + model)    {h[0]:>3}/{h[1]}  ({h[0]/h[1]:.0%})")
    print("\n  -> Held-out merchants are not in the keyword table, so rules fall back")
    print("     to Other/Personal; the model generalizes where rules cannot.")


if __name__ == "__main__":
    main()
