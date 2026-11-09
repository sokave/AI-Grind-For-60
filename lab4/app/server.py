import argparse
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from core import AppError, local_url, make_cards


ROOT = Path(__file__).resolve().parent


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, config, **kwargs):
        self.config = config
        super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

    def send_json(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if urlsplit(self.path).path == "/api/config":
            self.send_json(200, {"model": self.config.model, "base_url": self.config.base_url,
                "max_tokens": self.config.max_tokens, "context": 4096, "temperature": 0})
        else:
            super().do_GET()

    def do_POST(self):
        if self.path != "/api/cards":
            return self.send_json(404, {"error": "Сторінку не знайдено."})
        try:
            size = int(self.headers.get("Content-Length", 0))
            if not 0 < size <= 20000:
                raise AppError("Завеликий або порожній запит.", 400, "invalid_input")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise AppError("Очікується JSON-об’єкт.", 400, "invalid_input")
            result = make_cards(data.get("source"), data.get("count", 3),
                base_url=self.config.base_url, model=self.config.model,
                timeout=self.config.timeout, max_tokens=self.config.max_tokens,
                structured=not self.config.no_schema)
            result.pop("raw", None)
            self.send_json(200, result)
        except AppError as error:
            self.send_json(error.status, {"error": str(error), "code": error.code})
        except (ValueError, TypeError, UnicodeDecodeError):
            self.send_json(400, {"error": "Некоректний JSON-запит.", "code": "invalid_input"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("LOCAL_MODEL_BASE_URL", "http://127.0.0.1:8080/v1"))
    parser.add_argument("--model", default=os.environ.get("LOCAL_MODEL_NAME", "local-cards"))
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--max-tokens", type=int, default=640)
    parser.add_argument("--no-schema", action="store_true")
    args = parser.parse_args()
    local_url(args.base_url)
    handler = partial(Handler, config=args)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Картки з конспекту: http://127.0.0.1:{args.port}", flush=True)
    print(f"Модель: {args.model}; API: {args.base_url}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
