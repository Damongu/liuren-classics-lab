"""Regression tests for the local interactive trainer API."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import webapp  # noqa: E402
import tutor  # noqa: E402
from webapp import (  # noqa: E402
    WEB_ROOT, case_prompt, check_answers, random_case_prompt, recommended_topic,
    return_training_result,
)


CASE = {"day": "戊戌", "shi": "卯", "jiang": "未", "daynight": "昼"}


class WebTrainerTests(unittest.TestCase):
    def test_static_assets_exist(self):
        for name in ("index.html", "styles.css", "app.js"):
            self.assertTrue((WEB_ROOT / name).is_file())
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        script = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="question-text"', html)
        self.assertIn('id="session-button"', html)
        self.assertIn('id="next-button"', html)
        self.assertIn("async function nextQuestion()", script)
        self.assertIn("function fillTianpanFromAnchor(", script)
        self.assertIn("function advanceStage(", script)
        self.assertIn("async function finishSession()", script)
        self.assertIn('request("/api/result"', script)
        self.assertIn('localStorage.setItem(SESSION_KEY', script)
        self.assertIn("function restoreSession()", script)
        self.assertIn('initialParams.set("random", "1")', script)
        self.assertIn('id="topic-select"', html)
        self.assertIn('id="zeike-editor"', html)
        self.assertIn('id="zeike-sike-grid"', html)
        self.assertIn('id="zeike-reason"', html)
        self.assertIn('<option value="比用">比用</option>', html)
        self.assertIn('<option value="贼克＋比用">贼克＋比用</option>', html)
        self.assertIn('<option value="涉害">涉害·涉归本家计重</option>', html)
        self.assertIn("function renderZeike()", script)
        self.assertIn("state.answers.sike[2]", script)
        self.assertIn("</article>`).reverse().join", script)
        self.assertIn("function syncPrimaryAction()", script)
        self.assertIn('button.dataset.action = isNext ? "next" : "check"', script)
        self.assertNotIn("unpkg.com", html)
        self.assertNotIn("window.lucide", script)
        self.assertIn('["tianpan", "sike", "zeike"]', script)
        self.assertEqual(html.count("class=\"stage-tab locked\""), 2)

    def test_case_prompt_does_not_leak_answers(self):
        prompt = case_prompt(**CASE)
        self.assertEqual(prompt["jigong"], "巳")
        self.assertNotIn("tian", prompt)
        self.assertNotIn("chuan", prompt)
        self.assertNotIn("keshi", prompt)

    def test_recommended_topic_follows_training_progress(self):
        states = [
            ({}, "贼克"),
            ({"levels": {"4": {"topics": {
                "贼克": {"hist": [1] * 11 + [0]},
            }}}}, "比用"),
            ({"levels": {"4": {"topics": {
                "贼克": {"hist": [1] * 11 + [0]},
                "比用": {"hist": [1] * 12},
            }}}}, "贼克＋比用"),
            ({"levels": {"4": {"topics": {
                "贼克": {"hist": [1] * 11 + [0]},
                "比用": {"hist": [1] * 12},
                "贼克＋比用": {"hist": [1] * 11 + [0]},
            }}}}, "涉害"),
        ]
        for state, expected in states:
            with self.subTest(expected=expected), patch.object(
                webapp, "load_state", return_value=state,
            ):
                self.assertEqual(recommended_topic(), expected)

    def test_tianpan_check(self):
        answers = {
            "子": "辰", "丑": "巳", "寅": "午", "卯": "未",
            "辰": "申", "巳": "酉", "午": "戌", "未": "亥",
            "申": "子", "酉": "丑", "戌": "寅", "亥": "卯",
        }
        result = check_answers({**CASE, "stage": "tianpan", "answers": answers})
        self.assertTrue(result["correct"])
        self.assertNotIn("expected", result["cells"][0])

    def test_sike_check_and_reveal(self):
        correct = check_answers({**CASE, "stage": "sike", "answers": list("酉丑寅午")})
        self.assertTrue(correct["correct"])

        wrong = check_answers({
            **CASE, "stage": "sike", "answers": list("子丑寅午"), "reveal": True,
        })
        self.assertFalse(wrong["correct"])
        self.assertEqual(wrong["cells"][0]["expected"], "酉")

    def test_zeike_random_cases_and_check(self):
        for _ in range(40):
            prompt = random_case_prompt("贼克")
            plate = webapp._case(
                prompt["day"], prompt["shi"], prompt["jiang"], prompt["daynight"],
            )
            self.assertIn(plate.keshi, ("元首", "重审"))
            result = check_answers({
                **prompt,
                "stage": "zeike",
                "answers": [
                    plate.keshi,
                    plate.chuan[0],
                    ["有下贼取下贼" if plate.keshi == "重审" else "无下贼取上克"],
                ],
            })
            self.assertTrue(result["correct"])

    def test_biyong_random_cases_require_reason(self):
        for _ in range(40):
            prompt = random_case_prompt("比用")
            plate = webapp._case(
                prompt["day"], prompt["shi"], prompt["jiang"], prompt["daynight"],
            )
            self.assertEqual(plate.keshi, "知一")
            direction = ("有下贼取下贼"
                         if any(k.xia_ze_shang for k in plate.kes)
                         else "无下贼取上克")
            reason = "阳日取阳神" if plate.is_gang else "阴日取阴神"
            result = check_answers({
                **prompt,
                "stage": "zeike",
                "answers": [plate.keshi, plate.chuan[0], [direction, reason]],
            })
            self.assertTrue(result["correct"])
            one_reason_only = check_answers({
                **prompt,
                "stage": "zeike",
                "answers": [plate.keshi, plate.chuan[0], [reason]],
            })
            self.assertFalse(one_reason_only["correct"])
            missing_reason = check_answers({
                **prompt,
                "stage": "zeike",
                "answers": [plate.keshi, plate.chuan[0], []],
            })
            self.assertFalse(missing_reason["correct"])

    def test_zeike_biyong_mixed_cases_stay_within_taught_scope(self):
        seen = set()
        for _ in range(60):
            prompt = random_case_prompt("贼克＋比用")
            plate = webapp._case(
                prompt["day"], prompt["shi"], prompt["jiang"], prompt["daynight"],
            )
            self.assertIn(plate.keshi, ("元首", "重审", "知一"))
            seen.add(plate.keshi)
        self.assertEqual(seen, {"元首", "重审", "知一"})

    def test_shehai_random_cases_use_counted_depth(self):
        for _ in range(40):
            prompt = random_case_prompt("涉害")
            plate = webapp._case(
                prompt["day"], prompt["shi"], prompt["jiang"], prompt["daynight"],
            )
            self.assertEqual(plate.keshi, "涉害")
            self.assertIn(plate.keshi_sub, ("见机", "察微", "涉害", "缀瑕"))
            self.assertTrue(any("涉害深浅：" in reason for reason in plate.reason))
            result = check_answers({
                **prompt,
                "topic": "涉害",
                "stage": "zeike",
                "answers": [
                    "",
                    plate.chuan[0],
                    webapp._selection_reasons(plate),
                ],
            })
            self.assertTrue(result["correct"])

    def test_shehai_topic_does_not_score_fixed_keshi_name(self):
        prompt = random_case_prompt("涉害")
        plate = webapp._case(
            prompt["day"], prompt["shi"], prompt["jiang"], prompt["daynight"],
        )
        result = check_answers({
            **prompt,
            "topic": "涉害",
            "stage": "zeike",
            "answers": [
                "",
                plate.chuan[0],
                webapp._selection_reasons(plate),
            ],
        })
        self.assertTrue(result["correct"])
        self.assertEqual([cell["key"] for cell in result["cells"]], [1, 2])

    def test_shehai_tie_requires_tie_break_reasons(self):
        prompt = case_prompt("辛未", "子", "未")
        plate = webapp._case("辛未", "子", "未")
        reasons = webapp._selection_reasons(plate)
        self.assertIn("同重先比孟仲季", reasons)
        self.assertIn("同级复等依刚柔取先见", reasons)

        full = check_answers({
            **prompt,
            "topic": "涉害",
            "stage": "zeike",
            "answers": ["", plate.chuan[0], reasons],
        })
        missing_tie_break = check_answers({
            **prompt,
            "topic": "涉害",
            "stage": "zeike",
            "answers": [
                "",
                plate.chuan[0],
                [reason for reason in reasons if reason != "同级复等依刚柔取先见"],
            ],
        })
        self.assertTrue(full["correct"])
        self.assertFalse(missing_tie_break["correct"])

    def test_shehai_first_ke_stem_element_can_win_without_tie_break(self):
        prompt = case_prompt("戊申", "子", "未")
        plate = webapp._case("戊申", "子", "未")
        reasons = webapp._selection_reasons(plate)
        self.assertEqual(plate.chuan[0], "子")
        self.assertNotIn("同重先比孟仲季", reasons)
        self.assertNotIn("同级复等依刚柔取先见", reasons)
        result = check_answers({
            **prompt,
            "topic": "涉害",
            "stage": "zeike",
            "answers": ["", "子", reasons],
        })
        self.assertTrue(result["correct"])

    def test_shehai_accepts_pre_rename_equivalent_reason_label(self):
        prompt = case_prompt("甲申", "巳", "未")
        plate = webapp._case("甲申", "巳", "未")
        reasons = [
            "取受克重数最多者" if reason == "取涉害重数最多者" else reason
            for reason in webapp._selection_reasons(plate)
        ]
        result = check_answers({
            **prompt,
            "topic": "涉害",
            "stage": "zeike",
            "answers": ["", plate.chuan[0], reasons],
        })
        self.assertTrue(result["correct"])

    def test_later_stage_checks_share_same_plate(self):
        self.assertTrue(check_answers({**CASE, "stage": "keshi", "answers": "元首"})["correct"])
        self.assertTrue(check_answers({**CASE, "stage": "chuan", "answers": list("寅午戌")})["correct"])

        generals = {
            "子": "玄武", "丑": "太常", "寅": "白虎", "卯": "天空",
            "辰": "青龙", "巳": "勾陈", "午": "六合", "未": "朱雀",
            "申": "螣蛇", "酉": "贵人", "戌": "天后", "亥": "太阴",
        }
        self.assertTrue(check_answers({
            **CASE, "stage": "tianjiang", "answers": generals,
        })["correct"])

    def test_training_result_is_saved_and_trae_is_only_focused(self):
        records = [
            {"day": "戊戌", "shi": "卯", "jiang": "未", "clean": i != 4}
            for i in range(12)
        ]
        with tempfile.TemporaryDirectory() as directory:
            result_log = Path(directory) / "results.jsonl"
            with patch.object(webapp, "RESULT_LOG", result_log), \
                 patch.object(webapp, "record_external_session", return_value={
                     "recorded": True, "right": 11, "n": 12, "ready": True,
                 }) as record_session, \
                 patch.object(webapp, "_focus_trae_window", return_value=True) as focus:
                result = return_training_result({
                    "session_id": "session-1234",
                    "score": 11,
                    "total": 12,
                    "records": records,
                })

        self.assertFalse(result["returned"])
        self.assertTrue(result["focused"])
        self.assertTrue(result["passed"])
        self.assertTrue(result["recorded"])
        self.assertIn("四课专项 11/12", result["message"])
        self.assertIn("已写入训练记录", result["message"])
        self.assertIn("5.戊戌日 卯时 未将", result["message"])
        args, kwargs = record_session.call_args
        self.assertEqual(args, (
            3, [1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1],
            "web-trainer", "session-1234",
        ))
        self.assertEqual(len(kwargs["details"]), 12)
        focus.assert_called_once_with()

    def test_result_does_not_launch_trae_cli(self):
        source = Path(webapp.__file__).read_text(encoding="utf-8")
        self.assertNotIn("trae-cn.cmd", source)
        self.assertNotIn("subprocess.Popen", source)

    def test_zeike_result_is_saved_as_level4_topic(self):
        records = [
            {"day": "甲子", "shi": "子", "jiang": "辰", "clean": True}
            for _ in range(12)
        ]
        with tempfile.TemporaryDirectory() as directory:
            result_log = Path(directory) / "results.jsonl"
            with patch.object(webapp, "RESULT_LOG", result_log), \
                 patch.object(webapp, "record_external_session", return_value={
                     "recorded": True, "right": 12, "n": 12, "ready": True,
                 }) as record_session, \
                 patch.object(webapp, "_focus_trae_window", return_value=False):
                result = return_training_result({
                    "session_id": "zeike-session-1234",
                    "score": 12,
                    "total": 12,
                    "records": records,
                    "topic": "贼克",
                })

        self.assertIn("贼克专项 12/12", result["message"])
        args, kwargs = record_session.call_args
        self.assertEqual(args, (
            4, [1] * 12, "web-trainer", "zeike-session-1234",
        ))
        self.assertEqual(kwargs["topic"], "贼克")
        self.assertEqual(len(kwargs["details"]), 12)

    def test_biyong_result_is_saved_as_level4_topic(self):
        records = [
            {"day": "壬辰", "shi": "巳", "jiang": "辰", "clean": True}
            for _ in range(12)
        ]
        with tempfile.TemporaryDirectory() as directory:
            result_log = Path(directory) / "results.jsonl"
            with patch.object(webapp, "RESULT_LOG", result_log), \
                 patch.object(webapp, "record_external_session", return_value={
                     "recorded": True, "right": 12, "n": 12, "ready": True,
                 }) as record_session, \
                 patch.object(webapp, "_focus_trae_window", return_value=False):
                result = return_training_result({
                    "session_id": "biyong-session-1234",
                    "score": 12,
                    "total": 12,
                    "records": records,
                    "topic": "比用",
                })

        self.assertIn("比用专项 12/12", result["message"])
        self.assertEqual(record_session.call_args.kwargs["topic"], "比用")

    def test_shehai_result_is_saved_as_level7(self):
        records = [
            {"day": "丁卯", "shi": "卯", "jiang": "未", "clean": True}
            for _ in range(12)
        ]
        with tempfile.TemporaryDirectory() as directory:
            result_log = Path(directory) / "results.jsonl"
            with patch.object(webapp, "RESULT_LOG", result_log), \
                 patch.object(webapp, "record_external_session", return_value={
                     "recorded": True, "right": 12, "n": 12, "ready": True,
                 }) as record_session, \
                 patch.object(webapp, "_focus_trae_window", return_value=False):
                result = return_training_result({
                    "session_id": "shehai-session-1234",
                    "score": 12,
                    "total": 12,
                    "records": records,
                    "topic": "涉害",
                })

        self.assertIn("涉害专项 12/12", result["message"])
        args, kwargs = record_session.call_args
        self.assertEqual(args, (7, [1] * 12, "web-trainer", "shehai-session-1234"))
        self.assertNotIn("topic", kwargs)

    def test_training_result_preserves_error_stage_and_answers(self):
        records = [
            {"day": "戊戌", "shi": "卯", "jiang": "未", "clean": True}
            for _ in range(12)
        ]
        records[0] = {
            "day": "戊戌", "shi": "卯", "jiang": "未", "clean": False,
            "mistakes": [{
                "stage": "sike",
                "answers": ["子", "子", "子", "子"],
                "reveal": False,
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            result_log = Path(directory) / "results.jsonl"
            with patch.object(webapp, "RESULT_LOG", result_log), \
                 patch.object(webapp, "record_external_session", return_value={
                     "recorded": True, "right": 11, "n": 12, "ready": True,
                 }) as record_session, \
                 patch.object(webapp, "_focus_trae_window", return_value=False):
                result = return_training_result({
                    "session_id": "detail-session-1234",
                    "score": 11,
                    "total": 12,
                    "records": records,
                })

        detail = record_session.call_args.kwargs["details"][0]
        self.assertEqual(detail["mistakes"][0]["stage"], "sike")
        self.assertTrue(detail["mistakes"][0]["wrong"])
        self.assertIn("（四课）", result["message"])

    def test_external_session_updates_tutor_state_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(tutor, "STATE", root / "state.json"), \
                 patch.object(tutor, "RECORD", root / "record.md"), \
                 patch.object(tutor, "WRONGQ", root / "wrong.md"):
                first = tutor.record_external_session(
                    3, [1] * 11 + [0], "web-trainer", "session-1234",
                )
                duplicate = tutor.record_external_session(
                    3, [1] * 11 + [0], "web-trainer", "session-1234",
                )
                state = tutor.load_state()

        self.assertTrue(first["recorded"])
        self.assertTrue(first["ready"])
        self.assertFalse(duplicate["recorded"])
        self.assertEqual(state["levels"]["3"]["hist"], [1] * 11 + [0])
        self.assertEqual(len(state["sessions"]), 1)

    def test_zeike_external_session_stays_out_of_full_level_score(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(tutor, "STATE", root / "state.json"), \
                 patch.object(tutor, "RECORD", root / "record.md"), \
                 patch.object(tutor, "WRONGQ", root / "wrong.md"):
                result = tutor.record_external_session(
                    4, [1] * 12, "web-trainer", "zeike-session-1234",
                    topic="贼克",
                )
                state = tutor.load_state()
                record = (root / "record.md").read_text(encoding="utf-8")

        level = state["levels"]["4"]
        self.assertTrue(result["ready"])
        self.assertEqual(level["hist"], [])
        self.assertEqual(level["topics"]["贼克"]["hist"], [1] * 12)
        self.assertIn("| 贼克 | 12/12 |", record)
        self.assertIn("累计计分 **12** 题", record)
        self.assertIn("## 已学与当前", record)
        self.assertIn("## 后续完整关卡", record)
        self.assertIn("未教学内容不提前开放", record)

    def test_unscored_session_preserves_completion_without_inventing_score(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(tutor, "STATE", root / "state.json"), \
                 patch.object(tutor, "RECORD", root / "record.md"), \
                 patch.object(tutor, "WRONGQ", root / "wrong.md"):
                recorded = tutor.record_unscored_session(
                    3, 12, "web-trainer", "lost-session-20260909",
                    "旧版训练台故障；用户确认完成，分数不可恢复",
                )
                duplicate = tutor.record_unscored_session(
                    3, 12, "web-trainer", "lost-session-20260909",
                    "旧版训练台故障；用户确认完成，分数不可恢复",
                )
                state = tutor.load_state()
                record = (root / "record.md").read_text(encoding="utf-8")

        self.assertTrue(recorded)
        self.assertFalse(duplicate)
        self.assertNotIn("3", state["levels"])
        self.assertEqual(state["unscored_sessions"][0]["n"], 12)
        self.assertIn("未计分完成 **12** 题", record)
        self.assertIn("分数不可恢复", record)

    def test_progression_waiver_does_not_fabricate_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(tutor, "STATE", root / "state.json"), \
                 patch.object(tutor, "RECORD", root / "record.md"), \
                 patch.object(tutor, "WRONGQ", root / "wrong.md"):
                state = tutor.load_state()
                state["progression_waivers"] = {
                    "1": {"date": "2026-09-09", "reason": "test"},
                    "2": {"date": "2026-09-09", "reason": "test"},
                }
                tutor.save_state(state)
                tutor.waive_level_progression(3, "旧版训练台丢失成绩")
                state = tutor.load_state()
                record = (root / "record.md").read_text(encoding="utf-8")

        self.assertFalse(tutor.final_passed(tutor.lv_state(state, 3), 3))
        self.assertEqual(tutor.pick_level(state), 4)
        self.assertIn("已完成·成绩遗失·不阻断", record)


if __name__ == "__main__":
    unittest.main()
