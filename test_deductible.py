from deductible import (keyword_classify, parse_label, process, DEDUCTIBLE_RATE,
                       keyword_match, Hybrid)
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



def test_keyword_conflicts_fixed():
    # Netflix/groceries must be Other/Personal, not Software/Meals (regression)
    assert keyword_classify("NETFLIX SUBSCRIPTION") == "Other/Personal"
    assert keyword_classify("WHOLE FOODS GROCERIES") == "Other/Personal"


def test_keyword_match_unknown():
    assert keyword_match("SOME BRAND NEW VENDOR") is None


def test_empty_csv():
    import tempfile, os, csv
    d = tempfile.mkdtemp()
    src = os.path.join(d, "empty.csv")
    out = os.path.join(d, "out.csv")
    with open(src, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "description", "amount"])
    res = process(src, lambda desc, amt: keyword_classify(desc), out)
    assert res["count"] == 0


def test_missing_column_raises():
    import tempfile, os, csv
    d = tempfile.mkdtemp()
    src = os.path.join(d, "bad.csv")
    out = os.path.join(d, "out.csv")
    with open(src, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "description"])
    try:
        process(src, lambda desc, amt: keyword_classify(desc), out)
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "amount" in str(e)


def test_malformed_amount_flagged():
    import tempfile, os, csv
    d = tempfile.mkdtemp()
    src = os.path.join(d, "m.csv")
    out = os.path.join(d, "out.csv")
    with open(src, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "description", "amount"])
        w.writerow(["2026-01-01", "FOO", "not-a-number"])
    res = process(src, lambda desc, amt: keyword_classify(desc), out)
    assert res["rows"][0]["amount"] == 0.0
    assert res["rows"][0]["review"] == "CHECK"


def test_hybrid_fallback_uses_llm_on_unknown():
    # Monkey-patch the inner LLM so no model file is needed.
    import types
    fake = types.SimpleNamespace()
    fake.classify = lambda desc, amount: ("Meals", "model")
    h = Hybrid.__new__(Hybrid)
    h.llm = fake
    # known merchant -> rules win, LLM never called
    assert h.classify("STARBUCKS COFFEE", "5") == ("Meals", "rule")
    # unknown merchant -> LLM called
    assert h.classify("MYSTERY VENDOR", "5") == ("Meals", "model")


if __name__ == "__main__":
    test_keyword_classifier()
    test_parse_label()
    test_tax_rates()
    test_process_math()
    test_keyword_conflicts_fixed()
    test_keyword_match_unknown()
    test_empty_csv()
    test_missing_column_raises()
    test_malformed_amount_flagged()
    test_hybrid_fallback_uses_llm_on_unknown()
    print("all tests passed")
