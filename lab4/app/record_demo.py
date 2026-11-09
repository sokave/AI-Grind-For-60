import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pyte
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
DEMO = ROOT.parent / "demo"


def render(screen, title, font_path):
    image = Image.new("RGB", (1280, 960), "#121923")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(font_path, 18)
    title_font = ImageFont.truetype(font_path, 17)
    draw.rectangle((0,0,1280,53),fill="#202a3a")
    draw.text((24,17),title,font=title_font,fill="#d9d4ff")
    for i, line in enumerate(screen.display):
        draw.text((24,72+i*24),line,font=font,fill="#e7eaf1")
    return image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",default="local-cards")
    parser.add_argument("--font",default="/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
    args = parser.parse_args()
    if not Path(args.font).is_file():
        raise FileNotFoundError("Вкажіть --font зі шляхом до моноширинного шрифту з кирилицею.")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("Для MP4 потрібен ffmpeg у PATH.")
    DEMO.mkdir(exist_ok=True)
    tasks = json.loads((ROOT/"data/prompts.json").read_text(encoding="utf-8"))
    (DEMO/"notes.txt").write_text(tasks[0]["source"],encoding="utf-8")
    (DEMO/"empty.txt").write_text("",encoding="utf-8")
    (DEMO/"algorithms.txt").write_text(tasks[4]["source"],encoding="utf-8")
    events, checks = [], []
    screen = pyte.Screen(108,35)
    stream = pyte.Stream(screen)
    started = time.perf_counter()
    title = "LAB 4 | Фактичний запис stdout CLI | локальна Qwen3-1.7B"
    def emit(text):
        events.append([round(time.perf_counter()-started,4),"o",text])
        stream.feed(text)
    scenarios = [
        ("01_cards_cli",["--input","../demo/notes.txt","--count","2","--output","../demo/exported_cards.json"],0),
        ("02_empty_input_cli",["--input","../demo/empty.txt","--count","2"],1),
        ("03_server_unavailable_cli",["--input","../demo/notes.txt","--count","2","--base-url","http://127.0.0.1:18888/v1"],1),
        ("04_validation_error_cli",["--input","../demo/algorithms.txt","--count","2"],1)]
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"]="1"
    env["PYTHONIOENCODING"]="utf-8"
    for name, arguments, expected in scenarios:
        emit("\x1b[2J\x1b[H")
        argv=[sys.executable,"cli.py","--model",args.model,*arguments]
        emit("$ python " + " ".join(argv[1:]) + "\r\n\r\n")
        process = subprocess.Popen(argv,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env)
        chunks=[]
        while True:
            data = os.read(process.stdout.fileno(),4096)
            if not data:break
            decoded=data.decode("utf-8")
            chunks.append(decoded)
            emit(decoded.replace("\n","\r\n"))
        code = process.wait()
        checks.append({"scenario":name,"exit_code":code,"expected_exit_code":expected,"passed":code==expected,
            "stdout":"".join(chunks)})
        render(screen,title,args.font).save(DEMO/(name+".png"))
        print(name,code,flush=True)
        time.sleep(2.5)
        emit("")
    duration = time.perf_counter()-started
    header={"version":2,"width":108,"height":35,"timestamp":int(time.time()),
        "duration":round(duration,3),"title":title,"env":{"TERM":"xterm-256color","SHELL":"subprocess stdout"}}
    with (DEMO/"app_demo.cast").open("w",encoding="utf-8") as handle:
        handle.write(json.dumps(header,ensure_ascii=False)+"\n")
        for event in events:handle.write(json.dumps(event,ensure_ascii=False)+"\n")
    screen=pyte.Screen(108,35)
    stream=pyte.Stream(screen)
    encoder=subprocess.Popen(["ffmpeg","-y","-f","rawvideo","-vcodec","rawvideo","-pix_fmt","rgb24",
        "-s","1280x960","-r","6","-i","-","-an","-c:v","libx264","-crf","24","-pix_fmt","yuv420p",
        "-movflags","+faststart",str(DEMO/"app_demo.mp4")],stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    index=0
    for frame in range(int(duration*6)+1):
        when=frame/6
        while index<len(events) and events[index][0]<=when:
            stream.feed(events[index][2]);index+=1
        encoder.stdin.write(render(screen,title,args.font).tobytes())
    encoder.stdin.close()
    if encoder.wait()!=0:raise RuntimeError("Не вдалося створити MP4.")
    report={"kind":"Фактичний stdout CLI, відтворений із часовими мітками; це не відеозахоплення робочого столу.",
        "model":args.model,"duration_s":round(duration,3),"checks":checks}
    (DEMO/"cli_checks.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    if not all(check["passed"] for check in checks):raise RuntimeError("Не всі CLI-сценарії дали очікуваний результат.")


if __name__=="__main__":
    main()
