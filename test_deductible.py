from deductible import keyword_classify, parse_label, process, DEDUCTIBLE_RATE
import tempfile, os, csv


def test_keyword_classifier():
    assert keyword_classify("ADOBE CREATIVE CLOUD MONTHLY") == "Software & Subscriptions"
    assert keyword_classify("STARBUCKS STORE 2145") == "Meals"
    assert keyword_classify("UNITED AIRLINES TICKET") == "Travel"
    assert keyword_classify("TOTALLY UNKNOWN VENDOR XYZ") == "Other/Personal"


def test_parse_label():
    assert parse_label("Software & Subscriptions", "x") == "Software & Subscriptions"
    assert parse_label("  meals\n", "x") == "Meals"
    # unparseable model output falls back to keywords on the description
    assert parse_label("I am not sure", "STARBUCKS COFFEE") == "Meals"


def test_tax_rates():
    assert DEDUCTIBLE_RATE["Meals"] == 0.5
    assert DEDUCTIBLE_RATE["Other/Personal"] == 0.0
    assert DEDUCTIBLE_RATE["Travel"] == 1.0


def test_process_math():
    d = tempfile.mkdtemp()
    src = os.path.join(d, "in.csv")
    out = os.path.join(d, "out.csv")
    with open(src, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "description", "amount"])
        w.writerow(["2026-09-01", "STARBUCKS COFFEE", "-10.00"])   # Meals -> 50%
        w.writerow(["2026-09-02", "ADOBE CREATIVE CLOUD", "-60.00"])  # Software -> 100%
    res = process(src, lambda desc, amt: keyword_classify(desc), out)
    assert res["count"] == 2
    assert res["deductible_total"] == 5.0 + 60.0  # 10*0.5 + 60*1.0
    assert os.path.exists(out)


if __name__ == "__main__":
    test_keyword_classifier()
    test_parse_label()
    test_tax_rates()
    test_process_math()
    print("all tests passed")
