"""Local browser trainer backed by the liuren calculation engine."""
from __future__ import annotations

import argparse
import ctypes
import json
import random
import sys
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from liuren import GAN, JIGONG, ZHI, from_ganzhi
from liuren.ganzhi import TIANJIANG, gz_name, ke


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from tutor import (MIXED_TOPICS, TOPIC_CORRECT, TOPIC_WINDOW, due_items,  # noqa: E402
                   load_state, practice_ready, record_external_review,
                   record_external_session, topic_score_ready)


WEB_ROOT = ROOT / "web"
STAGES = ("tianpan", "sike", "zeike", "keshi", "chuan", "tianjiang")
KESHI = ("元首", "重审", "知一", "涉害", "遥克", "昴星", "别责", "八专", "伏吟", "返吟")
THREE_METHODS_TOPIC = "贼克＋比用＋涉害"
FOUR_METHODS_TOPIC = "贼克＋比用＋涉害＋遥克"
FIVE_METHODS_TOPIC = "贼克＋比用＋涉害＋遥克＋昴星"
SIX_METHODS_TOPIC = "贼克＋比用＋涉害＋遥克＋昴星＋别责"
SEVEN_METHODS_TOPIC = "贼克＋比用＋涉害＋遥克＋昴星＋别责＋八专"
EIGHT_METHODS_TOPIC = "贼克＋比用＋涉害＋遥克＋昴星＋别责＋八专＋伏吟"
NINE_METHODS_TOPIC = "贼克＋比用＋涉害＋遥克＋昴星＋别责＋八专＋伏吟＋返吟"
TOPICS = (
    "四课", "贼克", "比用", "贼克＋比用", "涉害",
    THREE_METHODS_TOPIC, "遥克", FOUR_METHODS_TOPIC, "昴星",
    FIVE_METHODS_TOPIC, "别责", SIX_METHODS_TOPIC, "八专", SEVEN_METHODS_TOPIC,
    "伏吟", EIGHT_METHODS_TOPIC, "返吟", NINE_METHODS_TOPIC, "三传",
    "十二天将与贵人",
)
TIANJIANG_SHI = {
    "昼": ("巳", "午", "未"),
    "夜": ("亥", "子", "丑"),
}
RESULT_LOG = ROOT / ".training-results.jsonl"
REMEDIATION_TASKS = ROOT / ".remediation-tasks.json"
REMEDIATION_LOG = ROOT / ".remediation-results.jsonl"
REVIEW_LOG = ROOT / ".training-reviews.jsonl"
SCORING_VERSION = "2026-09-14.1"
REASON_LABELS = {
    "zeike.lower_over_upper": "有下贼取下贼",
    "zeike.upper_over_lower": "无下贼取上克",
    "biyong.yang": "阳日取阳神",
    "biyong.yin": "阴日取阴神",
    "shehai.after_biyong": "比用未能唯一，入涉害",
    "shehai.count_to_home": "涉归本家逐位计重",
    "shehai.max_depth": "取涉害重数最多者",
    "shehai.meng_zhong_ji": "同重先比孟仲季",
    "shehai.first_seen": "同级复等依刚柔取先见",
    "no_internal_overcoming": "四课上下无克",
    "yaoke.spirit_over_day": "神克日优先",
    "yaoke.day_over_spirit": "无神克日取日克神",
    "no_yaoke": "无遥克",
    "maoxing.yang_above_you": "阳仰酉上",
    "maoxing.yin_below_you": "阴俯酉下",
    "bieze.three_distinct": "四课不全三课备",
    "bieze.yang_gan_he": "刚日取干合寄宫上神",
    "bieze.yin_zhi_he": "柔日取支前三合宫上神",
    "bazhuan.two_distinct": "四课重成两课",
    "bazhuan.no_yaoke": "八专不论遥克",
    "bazhuan.yang_forward": "刚日日阳顺数三位",
    "bazhuan.yin_backward": "柔日辰阴逆数三位",
    "fuyin.same_plate": "天地盘同位",
    "fuyin.overcoming": "有克取克处发用",
    "fuyin.yang_day": "无克刚取日上神",
    "fuyin.yin_day": "无克柔取辰上神",
    "fanyin.opposite_plate": "天地盘各临冲位",
    "fanyin.overcoming": "有克取克处发用",
    "fanyin.no_overcoming": "无克取马发用",
}
REASON_IDS = {label: reason_id for reason_id, label in REASON_LABELS.items()}
REASON_IDS["取受克重数最多者"] = "shehai.max_depth"


def recommended_topic() -> str:
    """Match the browser trainer to the first unfinished taught unit."""
    state = load_state()
    level = state.get("levels", {}).get("4", {})
    topics = level.get("topics", {})
    if not topic_score_ready(topics.get("贼克", {}), "贼克"):
        return "贼克"
    if not topic_score_ready(topics.get("比用", {}), "比用"):
        return "比用"
    if not topic_score_ready(topics.get("贼克＋比用", {}), "贼克＋比用"):
        return "贼克＋比用"
    shehai = state.get("levels", {}).get("7", {})
    shehai_waived = "7" in state.get("progression_waivers", {})
    if not practice_ready(shehai, 7) and not shehai_waived:
        return "涉害"
    if not topic_score_ready(topics.get(THREE_METHODS_TOPIC, {}), THREE_METHODS_TOPIC):
        return THREE_METHODS_TOPIC
    if not topic_score_ready(topics.get("遥克", {}), "遥克"):
        return "遥克"
    if not topic_score_ready(topics.get(FOUR_METHODS_TOPIC, {}), FOUR_METHODS_TOPIC):
        return FOUR_METHODS_TOPIC
    if not topic_score_ready(topics.get("昴星", {}), "昴星"):
        return "昴星"
    if not topic_score_ready(topics.get(FIVE_METHODS_TOPIC, {}), FIVE_METHODS_TOPIC):
        return FIVE_METHODS_TOPIC
    if not topic_score_ready(topics.get("别责", {}), "别责"):
        return "别责"
    if not topic_score_ready(topics.get(SIX_METHODS_TOPIC, {}), SIX_METHODS_TOPIC):
        return SIX_METHODS_TOPIC
    if not topic_score_ready(topics.get("八专", {}), "八专"):
        return "八专"
    if not topic_score_ready(topics.get(SEVEN_METHODS_TOPIC, {}), SEVEN_METHODS_TOPIC):
        return SEVEN_METHODS_TOPIC
    if not topic_score_ready(topics.get("伏吟", {}), "伏吟"):
        return "伏吟"
    if not topic_score_ready(topics.get(EIGHT_METHODS_TOPIC, {}), EIGHT_METHODS_TOPIC):
        return EIGHT_METHODS_TOPIC
    if not topic_score_ready(topics.get("返吟", {}), "返吟"):
        return "返吟"
    nine_ready = topic_score_ready(topics.get(NINE_METHODS_TOPIC, {}), NINE_METHODS_TOPIC)
    nine_waived = "4" in state.get("progression_waivers", {})
    if not nine_ready and not nine_waived:
        return NINE_METHODS_TOPIC
    return "三传"


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
    if topic == "十二天将与贵人":
        # 抽象题没有日期地点，无法计算真实星出没；只取无歧义核心时段。
        daynight = random.choice(tuple(TIANJIANG_SHI))
    wanted = None
    if topic == "贼克":
        wanted = {"元首", "重审"}
    elif topic == "比用":
        wanted = {"知一"}
    elif topic == "贼克＋比用":
        wanted = {random.choice(("元首", "重审", "知一"))}
    elif topic == "涉害":
        wanted = {"涉害"}
    elif topic == THREE_METHODS_TOPIC:
        wanted = {random.choice(("元首", "重审", "知一", "涉害"))}
    elif topic == "遥克":
        wanted = {"遥克"}
    elif topic == "昴星":
        wanted = {"昴星"}
    elif topic == "别责":
        wanted = {"别责"}
    elif topic == "八专":
        wanted = {"八专"}
    elif topic == "伏吟":
        wanted = {"伏吟"}
    elif topic == "返吟":
        wanted = {"返吟"}
    elif topic == NINE_METHODS_TOPIC:
        method = random.choice(
            ("贼克", "比用", "涉害", "遥克", "昴星", "别责", "八专", "伏吟", "返吟")
        )
        wanted = {
            "贼克": random.choice(({"元首"}, {"重审"})),
            "比用": {"知一"},
            "涉害": {"涉害"},
            "遥克": {"遥克"},
            "昴星": {"昴星"},
            "别责": {"别责"},
            "八专": {"八专"},
            "伏吟": {"伏吟"},
            "返吟": {"返吟"},
        }[method]
    elif topic == EIGHT_METHODS_TOPIC:
        method = random.choice(
            ("贼克", "比用", "涉害", "遥克", "昴星", "别责", "八专", "伏吟")
        )
        wanted = {
            "贼克": random.choice(({"元首"}, {"重审"})),
            "比用": {"知一"},
            "涉害": {"涉害"},
            "遥克": {"遥克"},
            "昴星": {"昴星"},
            "别责": {"别责"},
            "八专": {"八专"},
            "伏吟": {"伏吟"},
        }[method]
    elif topic == FOUR_METHODS_TOPIC:
        method = random.choice(("贼克", "比用", "涉害", "遥克"))
        wanted = {
            "贼克": random.choice(({"元首"}, {"重审"})),
            "比用": {"知一"},
            "涉害": {"涉害"},
            "遥克": {"遥克"},
        }[method]
    elif topic == FIVE_METHODS_TOPIC:
        method = random.choice(("贼克", "比用", "涉害", "遥克", "昴星"))
        wanted = {
            "贼克": random.choice(({"元首"}, {"重审"})),
            "比用": {"知一"},
            "涉害": {"涉害"},
            "遥克": {"遥克"},
            "昴星": {"昴星"},
        }[method]
    elif topic == SIX_METHODS_TOPIC:
        method = random.choice(("贼克", "比用", "涉害", "遥克", "昴星", "别责"))
        wanted = {
            "贼克": random.choice(({"元首"}, {"重审"})),
            "比用": {"知一"},
            "涉害": {"涉害"},
            "遥克": {"遥克"},
            "昴星": {"昴星"},
            "别责": {"别责"},
        }[method]
    elif topic == SEVEN_METHODS_TOPIC:
        method = random.choice(
            ("贼克", "比用", "涉害", "遥克", "昴星", "别责", "八专")
        )
        wanted = {
            "贼克": random.choice(({"元首"}, {"重审"})),
            "比用": {"知一"},
            "涉害": {"涉害"},
            "遥克": {"遥克"},
            "昴星": {"昴星"},
            "别责": {"别责"},
            "八专": {"八专"},
        }[method]
    while True:
        day = gz_name(random.randrange(60))
        shi = random.choice(TIANJIANG_SHI[daynight]) \
            if topic == "十二天将与贵人" else random.choice(ZHI)
        jiang = random.choice(ZHI)
        p = _case(day, shi, jiang, daynight)
        if wanted is None or p.keshi in wanted:
            return case_prompt(day, shi, jiang, daynight)


def _selection_reasons(p) -> list[str]:
    if p.keshi == "昴星":
        return [
            "四课上下无克",
            "无遥克",
            "阳仰酉上" if p.is_gang else "阴俯酉下",
        ]
    if p.keshi == "遥克":
        candidates, sub = _yaoke_candidates(p)
        reasons = ["四课上下无克"]
        reasons.append("神克日优先" if sub == "蒿矢" else "无神克日取日克神")
        if len(candidates) > 1:
            reasons.append("阳日取阳神" if p.is_gang else "阴日取阴神")
        return reasons
    if p.keshi == "别责":
        return [
            "四课上下无克",
            "无遥克",
            "四课不全三课备",
            "刚日取干合寄宫上神" if p.is_gang else "柔日取支前三合宫上神",
        ]
    if p.keshi == "八专":
        if p.keshi_sub.startswith("有克"):
            ze = [k for k in p.kes if k.xia_ze_shang]
            reasons = [
                "四课重成两课",
                "有下贼取下贼" if ze else "无下贼取上克",
            ]
            if p.keshi_sub == "有克·知一":
                reasons.append("阳日取阳神" if p.is_gang else "阴日取阴神")
            elif p.keshi_sub not in ("有克·元首", "有克·重审"):
                reasons.extend([
                    "比用未能唯一，入涉害",
                    "涉归本家逐位计重",
                    "取涉害重数最多者",
                ])
            return reasons
        return [
            "四课上下无克",
            "四课重成两课",
            "八专不论遥克",
            "刚日日阳顺数三位" if p.is_gang else "柔日辰阴逆数三位",
        ]
    if p.keshi == "伏吟":
        return [
            "天地盘同位",
            "有克取克处发用" if p.keshi_sub.startswith("有克")
            else ("无克刚取日上神" if p.is_gang else "无克柔取辰上神"),
        ]
    if p.keshi == "返吟":
        return [
            "天地盘各临冲位",
            "有克取克处发用" if p.keshi_sub.startswith("有克")
            else "无克取马发用",
        ]
    ze = [k for k in p.kes if k.xia_ze_shang]
    direction = "有下贼取下贼" if ze else "无下贼取上克"
    if p.keshi == "知一":
        yin_yang = "阳日取阳神" if p.is_gang else "阴日取阴神"
        return [direction, yin_yang]
    if p.keshi == "重审":
        return [direction]
    if p.keshi == "元首":
        return [direction]
    if p.keshi == "涉害":
        reasons = [
            direction,
            "比用未能唯一，入涉害",
            "涉归本家逐位计重",
            "取涉害重数最多者",
        ]
        if any("深浅相等" in note or "深浅与" in note for note in p.reason):
            reasons.append("同重先比孟仲季")
        if any("复等" in note and "先见神" in note for note in p.reason):
            reasons.append("同级复等依刚柔取先见")
        return reasons
    raise ValueError("本题不属于当前取用训练范围")


def _yaoke_candidates(p) -> tuple[list[str], str]:
    ups = list(dict.fromkeys(k.up for k in p.kes))
    hao = [up for up in ups if ke(up, p.gan)]
    if hao:
        return hao, "蒿矢"
    return [up for up in ups if ke(p.gan, up)], "弹射"


def _method_name(p) -> str:
    if p.keshi in ("元首", "重审"):
        return "贼克"
    if p.keshi == "知一":
        return "比用"
    if p.keshi in ("涉害", "遥克", "昴星", "别责", "八专", "伏吟", "返吟"):
        return p.keshi
    raise ValueError("本题不属于当前取用训练范围")


def _normalize_map(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v).strip() for k, v in value.items()}


def _normalize_list(value, size: int) -> list[str]:
    if not isinstance(value, list):
        return [""] * size
    return [(str(value[i]).strip() if i < len(value) else "") for i in range(size)]


def _normalize_reasons(values) -> list[str]:
    """Normalize stable IDs and labels retained by older browser sessions."""
    if not isinstance(values, list):
        return []
    return sorted({
        REASON_IDS.get(str(value).strip(), str(value).strip())
        for value in values
    })


def _check_scoring_version(payload: dict) -> str:
    version = str(payload.get("scoring_version") or SCORING_VERSION)
    if version != SCORING_VERSION:
        raise ValueError(
            f"判分版本不一致：会话为 {version}，服务器为 {SCORING_VERSION}"
        )
    return version


def _normalize_mistakes(
    item: dict, day: str, shi: str, jiang: str, daynight: str, topic: str
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
            "topic": topic,
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
            for cell in checked["cells"] if cell["filled"] and not cell["correct"]
        ]
        if wrong:
            mistakes.append({
                "stage": raw["stage"],
                "revealed": bool(raw.get("reveal")),
                "wrong": wrong,
            })
    return mistakes


def check_answers(payload: dict) -> dict:
    scoring_version = _check_scoring_version(payload)
    raw = payload.get("answers")
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

    if stage == "tianpan":
        answers = _normalize_map(raw)
        expected = {di: p.tian[di] for di in ZHI}
        order = list(ZHI)
    elif stage == "sike":
        answers = dict(enumerate(_normalize_list(raw, 4)))
        expected = {i: k.up for i, k in enumerate(p.kes)}
        order = list(range(4))
    elif stage == "zeike":
        layered = isinstance(raw, list) and len(raw) >= 5
        base = _normalize_list(raw, 5 if layered else 4)
        if layered:
            method, lesson, initial = base[0], base[1], base[2]
            raw_reasons = raw[3] if isinstance(raw, list) else []
            raw_candidates = raw[4] if isinstance(raw, list) else []
            answers = {
                0: method, 1: lesson, 2: initial,
                3: _normalize_reasons(raw_reasons),
                4: _normalize_reasons(raw_candidates),
            }
        else:
            # 旧版顺序：课名、初传、依据、遥克候选。
            lesson, initial = base[0], base[1]
            raw_reasons = raw[2] if isinstance(raw, list) and len(raw) > 2 else []
            raw_candidates = raw[3] if isinstance(raw, list) and len(raw) > 3 else []
            answers = {
                0: lesson, 1: initial,
                2: _normalize_reasons(raw_reasons),
                3: _normalize_reasons(raw_candidates),
            }
        lesson = p.keshi_sub if p.keshi in ("遥克", "八专", "伏吟", "返吟") else p.keshi
        expected = ({
            0: _method_name(p), 1: lesson, 2: p.chuan[0],
            3: _normalize_reasons(_selection_reasons(p)),
        } if layered else {
            0: lesson, 1: p.chuan[0],
            2: _normalize_reasons(_selection_reasons(p)),
        })
        topic = payload.get("topic")
        if p.keshi == "遥克":
            expected[4 if layered else 3] = \
                sorted(_yaoke_candidates(p)[0])
        if layered:
            order = [0, 1, 4, 2, 3] if p.keshi == "遥克" else [0, 1, 2, 3]
        elif topic == "涉害":
            order = [1, 2]
        elif p.keshi == "遥克":
            order = [0, 3, 1, 2]
        else:
            order = [0, 1, 2]
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
        filled = bool(actual)
        cell = {
            "key": key,
            "actual": actual,
            "filled": filled,
            "correct": filled and actual == want,
        }
        if reveal:
            cell["expected"] = want
        cells.append(cell)
    complete = all(cell["filled"] for cell in cells)
    correct = complete and all(cell["correct"] for cell in cells)
    result = {
        "scoring_version": scoring_version,
        "stage": stage,
        "complete": complete,
        "correct": correct,
        "correct_count": sum(cell["correct"] for cell in cells),
        "missing_count": sum(not cell["filled"] for cell in cells),
        "wrong_count": sum(cell["filled"] and not cell["correct"] for cell in cells),
        "total": len(cells),
        "cells": cells,
    }
    if reveal:
        result["reason"] = list(p.reason)
        result["keshi_sub"] = p.keshi_sub
    return result


def _load_remediation_tasks() -> dict:
    if not REMEDIATION_TASKS.exists():
        return {"tasks": {}}
    try:
        data = json.loads(REMEDIATION_TASKS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"tasks": {}}
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), dict):
        return {"tasks": {}}
    return data


def _save_remediation_tasks(data: dict) -> None:
    REMEDIATION_TASKS.parent.mkdir(parents=True, exist_ok=True)
    temporary = REMEDIATION_TASKS.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    temporary.replace(REMEDIATION_TASKS)


def create_remediation_task(payload: dict) -> dict:
    """Create a 3-5 case task whose result never changes formal scores."""
    topic = str(payload.get("topic", ""))
    reason_code = str(payload.get("reason_code", "")).strip()
    if topic not in TOPICS or topic == "四课" or not reason_code:
        raise ValueError("补强任务信息无效")
    raw_cases = payload.get("cases")
    if raw_cases is None:
        raw_cases = [random_case_prompt(topic) for _ in range(5)]
    if not isinstance(raw_cases, list) or not 3 <= len(raw_cases) <= 5:
        raise ValueError("补强任务须包含3至5题")
    cases = []
    for index, raw in enumerate(raw_cases, 1):
        if not isinstance(raw, dict):
            raise ValueError("补强题目无效")
        prompt = case_prompt(
            str(raw.get("day", "")),
            str(raw.get("shi", "")),
            str(raw.get("jiang", "")),
            str(raw.get("daynight", "昼")),
        )
        prompt["case_id"] = str(raw.get("case_id") or f"q{index}")
        cases.append(prompt)
    task_id = str(payload.get("task_id") or uuid.uuid4())
    data = _load_remediation_tasks()
    if task_id in data["tasks"]:
        raise ValueError("补强任务编号已存在")
    task = {
        "task_id": task_id,
        "mode": "remediation",
        "topic": topic,
        "reason_code": reason_code,
        "scoring_version": SCORING_VERSION,
        "status": "open",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(cases),
        "cases": cases,
        "counts_toward_formal_score": False,
    }
    data["tasks"][task_id] = task
    _save_remediation_tasks(data)
    return task


def get_remediation_task(task_id: str) -> dict:
    task = _load_remediation_tasks()["tasks"].get(task_id)
    if not isinstance(task, dict):
        raise ValueError("补强任务不存在")
    return task


def return_remediation_result(payload: dict) -> dict:
    task_id = str(payload.get("task_id", ""))
    task = get_remediation_task(task_id)
    version = _check_scoring_version(payload)
    session_id = str(payload.get("session_id", ""))
    records = payload.get("records")
    if not 8 <= len(session_id) <= 128 or not isinstance(records, list):
        raise ValueError("补强结果无效")
    if not 3 <= len(records) <= task["total"]:
        raise ValueError("补强至少完成3题，且不得超过任务题数")

    normalized = []
    for index, item in enumerate(records):
        expected_case = task["cases"][index]
        if not isinstance(item, dict) or any(
            item.get(key, expected_case.get(key)) != expected_case.get(key)
            for key in ("day", "shi", "jiang", "daynight")
        ):
            raise ValueError("补强题序与任务不一致")
        clean = item.get("clean")
        if not isinstance(clean, bool):
            raise ValueError("补强明细无效")
        mistakes = _normalize_mistakes(
            item, expected_case["day"], expected_case["shi"],
            expected_case["jiang"], expected_case["daynight"], task["topic"],
        )
        if clean and mistakes:
            raise ValueError("补强明细的首次正确标记与错题记录矛盾")
        normalized.append({
            "case_id": expected_case["case_id"],
            "day": expected_case["day"],
            "shi": expected_case["shi"],
            "jiang": expected_case["jiang"],
            "daynight": expected_case["daynight"],
            "clean": clean,
            "mistakes": mistakes,
        })

    mastered = len(normalized) >= 3 and all(
        row["clean"] for row in normalized[-2:]
    )
    completed = len(normalized) == task["total"] or mastered
    if not completed:
        raise ValueError("补强尚未满足至少3题且连续两题正确")
    result = {
        "task_id": task_id,
        "session_id": session_id,
        "mode": "remediation",
        "topic": task["topic"],
        "reason_code": task["reason_code"],
        "scoring_version": version,
        "score": sum(row["clean"] for row in normalized),
        "total": len(normalized),
        "completed": True,
        "mastered": mastered,
        "records": normalized,
        "counts_toward_formal_score": False,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    }
    data = _load_remediation_tasks()
    stored = data["tasks"][task_id]
    if stored.get("result", {}).get("session_id") == session_id:
        return stored["result"]
    stored["status"] = "completed"
    stored["result"] = result
    _save_remediation_tasks(data)
    with REMEDIATION_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False) + "\n")
    return result


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def record_training_review(payload: dict) -> dict:
    """Append a dispute or revision without rewriting the original judgment."""
    session_id = str(payload.get("session_id", "")).strip()
    question_id = str(payload.get("question_id", "")).strip()
    status = str(payload.get("status", "")).strip()
    note = str(payload.get("note", "")).strip()
    if (not session_id or not question_id or status not in ("pending", "resolved")
            or not note):
        raise ValueError("训练复核记录无效")
    review = {
        "session_id": session_id,
        "question_id": question_id,
        "status": status,
        "note": note,
        "scoring_version": SCORING_VERSION,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    }
    if "revised_clean" in payload:
        if not isinstance(payload["revised_clean"], bool):
            raise ValueError("修订判定无效")
        review["revised_clean"] = payload["revised_clean"]
    with REVIEW_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(review, ensure_ascii=False) + "\n")
    return review


def learning_status() -> dict:
    """Read-only reconciliation of formal, web-error and remediation evidence."""
    state = load_state()
    formal_sessions = []
    web_errors = []
    seen = set()
    for row in state.get("sessions", []):
        session_id = row.get("session_id")
        if not session_id or session_id in seen:
            continue
        seen.add(session_id)
        summary = {
            key: row.get(key)
            for key in ("session_id", "date", "topic", "level", "right", "n", "source")
        }
        formal_sessions.append(summary)
        for question_index, detail in enumerate(row.get("details", []), 1):
            if detail.get("clean"):
                continue
            web_errors.append({
                "session_id": session_id,
                "question_index": question_index,
                "topic": row.get("topic"),
                "mistakes": detail.get("mistakes", []),
            })
    topics = {}
    for topic, value in state.get("levels", {}).get("4", {}).get("topics", {}).items():
        topics[topic] = {
            "history": list(value.get("hist", [])),
            "teachback": bool(value.get("teachback")),
            "passed": topic_score_ready(value, topic) and (
                topic in MIXED_TOPICS or bool(value.get("teachback"))
            ),
        }
    remediation = []
    for task in _load_remediation_tasks()["tasks"].values():
        if task.get("status") == "completed":
            remediation.append({
                "task_id": task.get("task_id"),
                "topic": task.get("topic"),
                "reason_code": task.get("reason_code"),
                "status": task.get("status"),
                "result": task.get("result"),
            })
    reviews = _read_jsonl(REVIEW_LOG)
    latest_reviews = {}
    for review in reviews:
        key = (review.get("session_id"), review.get("question_id"))
        if all(key):
            latest_reviews[key] = review
    return {
        "scoring_version": SCORING_VERSION,
        "topics": topics,
        "formal_sessions": formal_sessions,
        "web_errors": web_errors,
        "active_wrong_count": len(state.get("wrong", [])),
        "remediation": remediation,
        "disputes": [
            review for review in latest_reviews.values()
            if review.get("status") == "pending"
        ],
        "reviews": list(latest_reviews.values()),
    }


def due_review_task(limit: int = 10) -> dict:
    """Expose due mistakes as exact browser-review stages."""
    stage_for_kind = {
        "四课": "sike",
        "三传": "chuan",
        "贼克": "zeike",
        "比用": "zeike",
        "涉害": "zeike",
        "遥克": "zeike",
        "昴星": "zeike",
        "别责": "zeike",
        "八专": "zeike",
        "伏吟": "zeike",
        "返吟": "zeike",
    }
    pool = sorted(
        due_items(load_state()),
        key=lambda item: (item.get("due", ""), -item.get("streak", 0)),
    )[:limit]
    cases = []
    for wrong in pool:
        spec = wrong.get("spec") or str(wrong.get("key", "")).split("|")
        if len(spec) < 4 or spec[0] not in stage_for_kind:
            continue
        prompt = case_prompt(str(spec[1]), str(spec[2]), str(spec[3]))
        plate = _case(str(spec[1]), str(spec[2]), str(spec[3]))
        prompt.update({
            "review_key": wrong["key"],
            "review_stage": stage_for_kind[spec[0]],
            "review_topic": spec[0] if spec[0] != "三传" else "三传",
            "tianpan_answers": {di: plate.tian[di] for di in ZHI},
            "sike_answers": [item.up for item in plate.kes],
        })
        cases.append(prompt)
    return {
        "mode": "review",
        "total": len(cases),
        "cases": cases,
        "scoring_version": SCORING_VERSION,
    }


def return_review_result(payload: dict) -> dict:
    _check_scoring_version(payload)
    session_id = str(payload.get("session_id", ""))
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("复现明细无效")
    results = []
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("clean"), bool):
            raise ValueError("复现明细无效")
        results.append({
            "key": str(record.get("review_key", "")),
            "correct": record["clean"],
            "mistakes": record.get("mistakes", []),
        })
    result = record_external_review(results, "web-trainer", session_id)
    focused = _focus_trae_window()
    return {
        **result,
        "focused": focused,
        "message": f"到期错题复现 {result['right']}/{result['n']}，已更新复现队列。",
    }


def _focus_trae_window() -> bool:
    """Focus the existing TRAE window without launching another process."""
    if sys.platform != "win32":
        return False
    user32 = ctypes.windll.user32
    candidates: list[tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def collect(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        size = user32.GetWindowTextLengthW(hwnd)
        if not size:
            return True
        title = ctypes.create_unicode_buffer(size + 1)
        user32.GetWindowTextW(hwnd, title, size + 1)
        if "TraeCode CN" in title.value:
            candidates.append((hwnd, title.value))
        return True

    user32.EnumWindows(collect, 0)
    if not candidates:
        return False
    project_matches = [item for item in candidates if "六壬agent工作区" in item[1]]
    hwnd = (project_matches or candidates)[0][0]
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    return bool(user32.SetForegroundWindow(hwnd))


def return_training_result(payload: dict) -> dict:
    scoring_version = _check_scoring_version(payload)
    score = payload.get("score")
    total = payload.get("total")
    records = payload.get("records")
    session_id = payload.get("session_id")
    topic = payload.get("topic", "四课")
    expected_total = 12 if topic in ("四课", "三传", *MIXED_TOPICS) else TOPIC_WINDOW
    if (not isinstance(score, int) or not isinstance(total, int)
            or total != expected_total or not 0 <= score <= total):
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
        mistakes = _normalize_mistakes(item, day, shi, jiang, daynight, topic)
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
    if score != sum(item["clean"] for item in normalized):
        raise ValueError("训练成绩与逐题明细不一致")

    result = {
        "scoring_version": scoring_version,
        "topic": topic,
        "score": score,
        "submitted_score": score,
        "total": total,
        "passed": score >= (11 if total == 12 else TOPIC_CORRECT),
        "records": normalized,
        "session_id": session_id,
        "judgment": "original",
        "revisions": [],
    }
    level = 3 if topic == "四课" else (
        5 if topic == "三传" else (
            6 if topic == "十二天将与贵人" else (7 if topic == "涉害" else 4)
        )
    )
    scores = [1 if item["clean"] else 0 for item in normalized]
    if topic in ("三传", "十二天将与贵人"):
        recorded = record_external_session(
            level, scores, "web-trainer", session_id, details=normalized,
        )
    elif topic not in ("四课", "涉害"):
        recorded = record_external_session(
            level, scores, "web-trainer", session_id,
            topic=topic, details=normalized,
        )
    else:
        recorded = record_external_session(
            level, scores, "web-trainer", session_id, details=normalized,
        )
    result["recorded"] = recorded["recorded"]
    result["ready_for_teachback"] = recorded["ready"]
    with RESULT_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False) + "\n")

    stage_names = {"tianpan": "天地盘", "sike": "四课", "zeike": "取用",
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
        f"训练台结果：{topic}"
        f"{'累计混合' if topic in MIXED_TOPICS else '专项'} "
        f"{score}/{total}，"
        f"{'达标' if result['passed'] else '未达标'}。"
        f"{'已写入训练记录。' if result['recorded'] else '该会话已记录，未重复写入。'}"
        f"非首次全对题：{detail}。请据此继续当前教学流程。"
    )
    focused = _focus_trae_window()
    return {**result, "returned": False, "focused": focused, "message": prompt}


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
                "recommended_topic": recommended_topic(),
                "scoring_version": SCORING_VERSION,
                "reason_catalog": REASON_LABELS,
            })
            return
        if parsed.path == "/api/status":
            self._json(learning_status())
            return
        if parsed.path == "/api/review/task":
            self._json(due_review_task())
            return
        if parsed.path == "/api/remediation/task":
            query = parse_qs(parsed.query)
            try:
                self._json(get_remediation_task(query.get("id", [""])[0]))
            except ValueError as exc:
                self._json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
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
        if path not in (
            "/api/check", "/api/result", "/api/remediation/task",
            "/api/remediation/result", "/api/review", "/api/review/result",
        ):
            self._json({"error": "接口不存在"}, HTTPStatus.NOT_FOUND)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 100_000:
                raise ValueError("请求过大")
            payload = json.loads(self.rfile.read(size) or b"{}")
            handlers = {
                "/api/check": check_answers,
                "/api/result": return_training_result,
                "/api/remediation/task": create_remediation_task,
                "/api/remediation/result": return_remediation_result,
                "/api/review": record_training_review,
                "/api/review/result": return_review_result,
            }
            self._json(handlers[path](payload))
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
