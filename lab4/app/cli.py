import argparse
import json
import sys
import threading
import time
from pathlib import Path

from core import AppError, make_cards


def main():
    parser = argparse.ArgumentParser(description="Картки для повторення з локальної мовної моделі")
    parser.add_argument("--input", required=True)
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model", default="local-cards")
    parser.add_argument("--output", default="study_cards.json")
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    try:
        source = Path(args.input).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        print(f"Помилка: не вдалося прочитати UTF-8 файл: {error}", file=sys.stderr)
        return 2
    print("КАРТКИ З КОНСПЕКТУ", flush=True)
    print(f"Модель: {args.model}", flush=True)
    print(f"Локальний API: {args.base_url}", flush=True)
    print("temperature=0; seed=1; max_tokens=640; контекст сервера=4096", flush=True)
    print("\nКонспект:\n" + source.strip(), flush=True)
    stop = threading.Event()
    started = time.perf_counter()
    def indicate():
        while not stop.wait(.5):
            print(f"\rОчікування моделі: {time.perf_counter()-started:.0f} с…", end="", flush=True)
    indicator = threading.Thread(target=indicate, daemon=True)
    indicator.start()
    try:
        result = make_cards(source, args.count, args.base_url, args.model, timeout=args.timeout)
    except AppError as error:
        stop.set()
        indicator.join()
        print("\r" + " "*70 + "\r", end="")
        print(f"Помилка [{error.code}]: {error}", flush=True)
        return 1
    finally:
        stop.set()
        indicator.join()
    print("\r" + " "*70 + "\r", end="")
    for i, card in enumerate(result["cards"], 1):
        print(f"\nКартка {i}\nЗапитання: {card['question']}\nВідповідь: {card['answer']}", flush=True)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nГотово: {len(result['cards'])} картки; {result['elapsed_s']:.1f} с; {result['usage'].get('completion_tokens')} токенів.", flush=True)
    print(f"Відповіді дослівно перевірено за конспектом. Збережено: {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
