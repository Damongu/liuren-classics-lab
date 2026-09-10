"""Local browser trainer backed by the liuren calculation engine."""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from liuren import GAN, JIGONG, ZHI, from_ganzhi
from liuren.ganzhi import TIANJIANG, gz_name


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from tutor import record_external_session  # noqa: E402


WEB_ROOT = ROOT / "web"
STAGES = ("tianpan", "sike", "zeike", "keshi", "chuan", "tianjiang")
KESHI = ("元首", "重审", "知一", "涉害", "遥克", "昴星", "别责", "八专", "伏吟", "返吟")
TOPICS = ("四课", "贼克")
RESULT_LOG = ROOT / ".training-results.jsonl"


def _case(day: str, shi: str, jiang: str, daynight: str = "昼"):
    if day not in {gz_name(i) for i in range(60)}:
        raise ValueError("日干支无效")
    if shi not in ZHI or jiang not in ZHI:
        raise ValueError("占时或月将无效")
    if daynight not in ("昼", "夜"):
        raise ValueError("昼夜值无效")
    return from_ganzhi(day, shi, jiang, daynight=daynight)


def case_prompt(day: str, shi: str, jiang: str, daynight: str = "昼") -> dict:
    p = _case(day, shi, jiang, daynight)
    return {
        "day": day,
        "shi": shi,
        "jiang": jiang,
        "daynight": daynight,
        "gan": p.gan,
        "zhi": p.zhi,
        "jigong": JIGONG[p.gan],
        "earth": list(ZHI),
        "sike_lows": [
            {"label": p.gan, "gong": p.jigong},
            {"label": "一课上神", "gong": None},
            {"label": p.zhi, "gong": p.zhi},
            {"label": "三课上神", "gong": None},
        ],
    }


def random_case_prompt(topic: str = "四课", daynight: str = "昼") -> dict:
    if topic not in TOPICS:
        raise ValueError("训练类型无效")
    while True:
        day = gz_name(random.randrange(60))
        shi = random.choice(ZHI)
        jiang = random.choice(ZHI)
        p = _case(day, shi, jiang, daynight)
        if topic != "贼克" or p.keshi in ("元首", "重审"):
            return case_prompt(day, shi, jiang, daynight)


def _normalize_map(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v).strip() for k, v in value.items()}


def _normalize_list(value, size: int) -> list[str]:
    if not isinstance(value, list):
        return [""] * size
    return [(str(value[i]).strip() if i < len(value) else "") for i in range(size)]


def _normalize_mistakes(
    item: dict, day: str, shi: str, jiang: str, daynight: str
) -> list[dict]:
    raw_mistakes = item.get("mistakes", [])
    if not isinstance(raw_mistakes, list):
        raise ValueError("训练错题明细无效")
    mistakes = []
    for raw in raw_mistakes:
        if not isinstance(raw, dict) or raw.get("stage") not in STAGES:
            raise ValueError("训练错题明细无效")
        checked = check_answers({
            "day": day,
            "shi": shi,
            "jiang": jiang,
            "daynight": daynight,
            "stage": raw["stage"],
            "answers": raw.get("answers"),
            "reveal": True,
        })
        wrong = [
            {
                "key": str(cell["key"]),
                "actual": cell["actual"],
                "expected": cell["expected"],
            }
            for cell in checked["cells"] if not cell["correct"]
        ]
        if wrong:
            mistakes.append({
                "stage": raw["stage"],
                "revealed": bool(raw.get("reveal")),
                "wrong": wrong,
            })
    return mistakes


def check_answers(payload: dict) -> dict:
    p = _case(
        str(payload.get("day", "")),
        str(payload.get("shi", "")),
        str(payload.get("jiang", "")),
        str(payload.get("daynight", "昼")),
    )
    stage = str(payload.get("stage", ""))
    if stage not in STAGES:
        raise ValueError("训练阶段无效")
    reveal = bool(payload.get("reveal"))
    raw = payload.get("answers")

    if stage == "tianpan":
        answers = _normalize_map(raw)
        expected = {di: p.tian[di] for di in ZHI}
        order = list(ZHI)
    elif stage == "sike":
        answers = dict(enumerate(_normalize_list(raw, 4)))
        expected = {i: k.up for i, k in enumerate(p.kes)}
        order = list(range(4))
    elif stage == "zeike":
        answers = dict(enumerate(_normalize_list(raw, 2)))
        expected = {0: p.keshi, 1: p.chuan[0]}
        order = [0, 1]
    elif stage == "keshi":
        answers = {0: str(raw or "").strip()}
        expected = {0: p.keshi}
        order = [0]
    elif stage == "chuan":
        answers = dict(enumerate(_normalize_list(raw, 3)))
        expected = {i: p.chuan[i] for i in range(3)}
        order = list(range(3))
    else:
        answers = _normalize_map(raw)
        expected = {di: p.jiang_on(p.tian[di]) for di in ZHI}
        order = list(ZHI)

    cells = []
    for key in order:
        actual = answers.get(key, "")
        want = expected[key]
        cell = {"key": key, "actual": actual, "correct": actual == want}
        if reveal:
            cell["expected"] = want
        cells.append(cell)
    complete = all(cell["actual"] for cell in cells)
    correct = complete and all(cell["correct"] for cell in cells)
    result = {
        "stage": stage,
        "complete": complete,
        "correct": correct,
        "correct_count": sum(cell["correct"] for cell in cells),
        "total": len(cells),
        "cells": cells,
    }
    if reveal:
        result["reason"] = list(p.reason)
        result["keshi_sub"] = p.keshi_sub
    return result


def _trae_cli() -> Path | None:
    found = shutil.which("trae-cn.cmd") or shutil.which("trae-cn")
    if found:
        return Path(found)
    install_root = os.environ.get("VSCODE_CWD", "")
    candidate = Path(install_root) / "bin" / "trae-cn.cmd"
    return candidate if candidate.is_file() else None


def _schedule_trae_return(cli: Path, prompt: str, delay: float = 1.0) -> None:
    """Focus TRAE after the browser has finished handling the result response."""
    def launch() -> None:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        command = [
            str(cli), "chat", "--mode", "agent",
            "--reuse-window", "--maximize", prompt,
        ]
        shell = False
        if cli.suffix.lower() == ".cmd":
            command = subprocess.list2cmdline(command)
            shell = True
        subprocess.Popen(
            command,
            cwd=str(ROOT.parent),
            creationflags=creation_flags,
            shell=shell,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    timer = threading.Timer(delay, launch)
    timer.daemon = True
    timer.start()


def return_training_result(payload: dict) -> dict:
    score = payload.get("score")
    total = payload.get("total")
    records = payload.get("records")
    session_id = payload.get("session_id")
    topic = payload.get("topic", "四课")
    if not isinstance(score, int) or not isinstance(total, int) or total != 12 or not 0 <= score <= total:
        raise ValueError("训练成绩无效")
    if not isinstance(records, list) or len(records) != total:
        raise ValueError("训练明细不完整")
    if not isinstance(session_id, str) or not 8 <= len(session_id) <= 128:
        raise ValueError("训练会话编号无效")
    if topic not in TOPICS:
        raise ValueError("训练类型无效")

    normalized = []
    valid_days = {gz_name(i) for i in range(60)}
    for item in records:
        if not isinstance(item, dict):
            raise ValueError("训练明细无效")
        day, shi, jiang = item.get("day"), item.get("shi"), item.get("jiang")
        daynight = item.get("daynight", "昼")
        clean = item.get("clean")
        if (day not in valid_days or shi not in ZHI or jiang not in ZHI
                or daynight not in ("昼", "夜") or not isinstance(clean, bool)):
            raise ValueError("训练明细无效")
        mistakes = _normalize_mistakes(item, day, shi, jiang, daynight)
        if clean and mistakes:
            raise ValueError("训练明细的首次正确标记与错题记录矛盾")
        normalized.append({
            "day": day,
            "shi": shi,
            "jiang": jiang,
            "daynight": daynight,
            "clean": clean,
            "mistakes": mistakes,
        })

    result = {
        "topic": topic,
        "score": score,
        "total": total,
        "passed": score >= 11,
        "records": normalized,
        "session_id": session_id,
    }
    level = 4 if topic == "贼克" else 3
    scores = [1 if item["clean"] else 0 for item in normalized]
    if topic == "贼克":
        recorded = record_external_session(
            level, scores, "web-trainer", session_id,
            topic="贼克", details=normalized,
        )
    else:
        recorded = record_external_session(
            level, scores, "web-trainer", session_id, details=normalized,
        )
    result["recorded"] = recorded["recorded"]
    result["ready_for_teachback"] = recorded["ready"]
    with RESULT_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False) + "\n")

    stage_names = {"tianpan": "天地盘", "sike": "四课", "zeike": "贼克",
                   "keshi": "课体", "chuan": "三传", "tianjiang": "天将"}
    wrong = []
    for index, item in enumerate(normalized):
        if item["clean"]:
            continue
        stages = "、".join(dict.fromkeys(
            stage_names[mistake["stage"]] for mistake in item["mistakes"]
        )) or "阶段不详"
        wrong.append(
            f"{index + 1}.{item['day']}日 {item['shi']}时 {item['jiang']}将（{stages}）"
        )
    detail = "；".join(wrong) if wrong else "无"
    prompt = (
        f"训练台自动返回结果：{topic}专项 {score}/{total}，"
        f"{'达标' if result['passed'] else '未达标'}。"
        f"{'已写入训练记录。' if result['recorded'] else '该会话已记录，未重复写入。'}"
        f"非首次全对题：{detail}。请据此继续当前教学流程。"
    )
    cli = _trae_cli()
    if cli is None:
        return {**result, "returned": False, "message": prompt, "error": "未找到 trae-cn CLI"}

    _schedule_trae_return(cli, prompt)
    return {**result, "returned": True, "message": prompt}


class TrainerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[web] {self.address_string()} {fmt % args}")

    def _json(self, data: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/meta":
            self._json({
                "days": [gz_name(i) for i in range(60)],
                "zhi": list(ZHI),
                "gan": list(GAN),
                "tianjiang": list(TIANJIANG),
                "keshi": list(KESHI),
                "stages": list(STAGES),
            })
            return
        if parsed.path == "/api/case":
            query = parse_qs(parsed.query)
            try:
                if query.get("random") == ["1"]:
                    self._json(random_case_prompt(
                        query.get("topic", ["四课"])[0],
                        query.get("daynight", ["昼"])[0],
                    ))
                    return
                else:
                    day = query.get("day", ["甲子"])[0]
                    shi = query.get("shi", ["卯"])[0]
                    jiang = query.get("jiang", ["子"])[0]
                self._json(case_prompt(day, shi, jiang, query.get("daynight", ["昼"])[0]))
            except ValueError as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in ("/api/check", "/api/result"):
            self._json({"error": "接口不存在"}, HTTPStatus.NOT_FOUND)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 100_000:
                raise ValueError("请求过大")
            payload = json.loads(self.rfile.read(size) or b"{}")
            self._json(check_answers(payload) if path == "/api/check" else return_training_result(payload))
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)


def main() -> None:
    parser = argparse.ArgumentParser(description="六壬交互式排盘训练台")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), TrainerHandler)
    print(f"六壬交互式排盘训练台：http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
