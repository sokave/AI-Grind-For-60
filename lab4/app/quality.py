import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from core import AppError, make_cards


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--label", choices=["before", "after"], required=True)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--output")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    tasks = json.loads((root / "data/prompts.json").read_text(encoding="utf-8"))
    output = Path(args.output) if args.output else root / "data" / f"quality_{args.label}.json"
    report = {"label": args.label, "model": args.model, "base_url": args.base_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rubric": "Автоматично перевіряються JSON, кількість, непорожні поля, унікальність запитань і дослівна наявність відповіді у джерелі. Зміст запитання й відповіді оцінюється окремо.",
        "results": []}
    for task in tasks:
        row = dict(task)
        try:
            result = make_cards(task["source"], task["count"], args.base_url, args.model, timeout=args.timeout)
            row.update(status="passed", result=result)
        except AppError as error:
            row.update(status="failed", error=str(error), code=error.code,
                raw=getattr(error, "raw", ""), elapsed_s=getattr(error, "elapsed_s", None))
        report["results"].append(row)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(task["id"], row["status"], flush=True)
    print(f"Перевірок пройдено: {sum(r['status'] == 'passed' for r in report['results'])}/{len(tasks)}", flush=True)


if __name__ == "__main__":
    main()
