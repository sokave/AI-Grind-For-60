import argparse
import json
import os
import socket
import threading
import unittest
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from openai import APITimeoutError

from core import AppError, check_source, make_cards, validate_cards
from server import Handler, ThreadingHTTPServer


ROOT = Path(__file__).resolve().parent
SOURCE = "Стек працює за принципом LIFO. Черга працює за принципом FIFO."
VALID = json.dumps({"cards":[{"question":"Як працює стек?","answer":"Стек працює за принципом LIFO."}]})
CONFIG = None


class Checks(unittest.TestCase):
    def test_01_valid_quote(self):
        self.assertEqual(len(validate_cards(VALID,SOURCE,1)),1)

    def test_02_empty_input(self):
        with self.assertRaises(AppError) as result:check_source("",2)
        self.assertEqual(result.exception.code,"invalid_input")

    def test_03_context_limit(self):
        with self.assertRaises(AppError) as result:check_source("т"*1801,2)
        self.assertEqual(result.exception.code,"context_limit")

    def test_04_invalid_json(self):
        with self.assertRaises(AppError):validate_cards("це не JSON",SOURCE,1)

    def test_05_ungrounded_answer(self):
        data=json.loads(VALID)
        data["cards"][0]["answer"]="Стек працює за принципом FIFO."
        wrong=json.dumps(data)
        with self.assertRaises(AppError) as result:validate_cards(wrong,SOURCE,1)
        self.assertEqual(result.exception.code,"ungrounded_answer")

    def test_06_statement_in_question(self):
        data=json.loads(VALID)
        data["cards"][0]["question"]="Стек працює за принципом LIFO."
        wrong=json.dumps(data)
        with self.assertRaises(AppError) as result:validate_cards(wrong,SOURCE,1)
        self.assertEqual(result.exception.code,"not_a_question")

    def test_07_sdk_timeout_mapping(self):
        with patch("core.OpenAI") as factory:
            factory.return_value.chat.completions.create.side_effect=APITimeoutError(request=httpx.Request("POST","http://127.0.0.1:8080/v1/chat/completions"))
            with self.assertRaises(AppError) as result:make_cards(SOURCE,1)
        self.assertEqual(result.exception.code,"timeout")

    def test_08_real_connection_refused(self):
        with socket.socket() as temporary:
            temporary.bind(("127.0.0.1",0));port=temporary.getsockname()[1]
        with self.assertRaises(AppError) as result:make_cards(SOURCE,1,base_url=f"http://127.0.0.1:{port}/v1",timeout=2)
        self.assertEqual(result.exception.code,"server_unavailable")

    def test_09_http_invalid_request(self):
        config=SimpleNamespace(model="unused",base_url="http://127.0.0.1:18888/v1",timeout=2,max_tokens=640,no_schema=False)
        server=ThreadingHTTPServer(("127.0.0.1",0),partial(Handler,config=config))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with httpx.Client(trust_env=False) as client:
                response=client.post(f"http://127.0.0.1:{server.server_port}/api/cards",json={"source":"","count":2})
            self.assertEqual(response.status_code,400)
            self.assertEqual(response.json()["code"],"invalid_input")
        finally:server.shutdown();server.server_close();thread.join()

    def test_10_real_model_http_success(self):
        if not CONFIG.model:self.skipTest("Передайте --model для інтеграційного тесту з реальною моделлю.")
        task=json.loads((ROOT/"data/prompts.json").read_text(encoding="utf-8"))[0]
        config=SimpleNamespace(model=CONFIG.model,base_url=CONFIG.base_url,timeout=180,max_tokens=640,no_schema=False)
        server=ThreadingHTTPServer(("127.0.0.1",0),partial(Handler,config=config))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with httpx.Client(trust_env=False,timeout=185) as client:
                response=client.post(f"http://127.0.0.1:{server.server_port}/api/cards",json={"source":task["source"],"count":2})
            self.assertEqual(response.status_code,200,response.text)
            data=response.json()
            self.assertEqual(len(data["cards"]),2)
            validate_cards(json.dumps({"cards":data["cards"]}),task["source"],2)
            (ROOT/"data/http_success.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
        finally:server.shutdown();server.server_close();thread.join()


class RecordedResult(unittest.TextTestResult):
    rows=[]
    def addSuccess(self,test):
        super().addSuccess(test);self.rows.append({"test":test._testMethodName,"status":"passed"})
    def addSkip(self,test,reason):
        super().addSkip(test,reason);self.rows.append({"test":test._testMethodName,"status":"skipped","reason":reason})
    def addFailure(self,test,error):
        super().addFailure(test,error);self.rows.append({"test":test._testMethodName,"status":"failed"})
    def addError(self,test,error):
        super().addError(test,error);self.rows.append({"test":test._testMethodName,"status":"error"})


def main():
    global CONFIG
    parser=argparse.ArgumentParser()
    parser.add_argument("--model")
    parser.add_argument("--base-url",default="http://127.0.0.1:8080/v1")
    CONFIG=parser.parse_args()
    for key in ["NO_PROXY","no_proxy"]:os.environ[key]=os.environ.get(key,"")+",localhost,127.0.0.1"
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result=unittest.TextTestRunner(verbosity=2,resultclass=RecordedResult).run(suite)
    report={"tests":result.rows,"model":CONFIG.model,"note":"test_07 моделює виняток таймауту SDK; test_10 звертається до реальної моделі; решта перевіряють валідацію та транспорт."}
    (ROOT/"data/test_results.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=="__main__":
    main()
