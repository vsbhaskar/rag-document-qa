import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.retrieve import retrieve
from app.config import MIN_SCORE


def evaluate(k=4, min_score=MIN_SCORE, show_details=True):
    with open(Path(__file__).parent / "eval_questions.json", encoding="utf-8") as f:
        questions = json.load(f)

    ans_total = ans_hit = ans_refused = 0
    oos_total = oos_ok = 0
    failures = []

    for q in questions:
        results = retrieve(q["question"], k=k, min_score=min_score)
        pages = [m["page"] for _, m, _ in results]
        top_score = results[0][2] if results else 0.0

        if q["type"] == "answerable":
            ans_total += 1
            if not results:
                ans_refused += 1
                failures.append((q["id"], q["question"], "WRONGLY REFUSED", q["expected_pages"], pages))
            elif any(p in q["expected_pages"] for p in pages):
                ans_hit += 1
            else:
                failures.append((q["id"], q["question"], "MISSED", q["expected_pages"], pages))
        else:
            oos_total += 1
            if not results:
                oos_ok += 1
            else:
                failures.append((q["id"], q["question"], f"NOT REFUSED (top score {top_score:.2f})", [], pages))

    hit_rate = ans_hit / ans_total * 100
    refusal_rate = oos_ok / oos_total * 100

    print(f"\n=== k={k}, min_score={min_score} ===")
    print(f"Retrieval hit rate : {ans_hit}/{ans_total} ({hit_rate:.0f}%)")
    print(f"Wrongly refused    : {ans_refused}/{ans_total}")
    print(f"Refusal accuracy   : {oos_ok}/{oos_total} ({refusal_rate:.0f}%)")

    if show_details and failures:
        print("\nFailures:")
        for qid, question, reason, expected, got in failures:
            print(f"  #{qid} [{reason}] {question}")
            print(f"       expected pages {expected}, retrieved pages {got}")

    return hit_rate, refusal_rate


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "sweep":
        for k in (3, 4, 6, 8):
            evaluate(k=k, show_details=False)
    else:
        k = int(sys.argv[1]) if len(sys.argv) > 1 else 4
        min_score = float(sys.argv[2]) if len(sys.argv) > 2 else MIN_SCORE
        evaluate(k=k, min_score=min_score)