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
    SCORING_VERSION, WEB_ROOT, case_prompt, check_answers,
    create_remediation_task, due_review_task, learning_status, random_case_prompt,
    record_training_review, recommended_topic, return_remediation_result,
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
        self.assertIn(".find((stage) => unlocked.has(stage))", script)
        self.assertIn("`已进入${STAGE_COPY[next][0]}`", script)
        self.assertIn("async function finishSession()", script)
        self.assertIn('remediation ? "/api/remediation/result" : "/api/result"', script)
        self.assertIn('pageParams.has("task")', script)
        self.assertIn("state.meta.reason_catalog", script)
        self.assertIn('localStorage.setItem(SESSION_KEY', script)
        self.assertIn("function restoreSession()", script)
        self.assertIn('initialParams.set("random", "1")', script)
        self.assertIn('id="topic-select"', html)
        self.assertIn('id="zeike-editor"', html)
        self.assertIn('id="zeike-sike-grid"', html)
        self.assertIn('id="chuan-sike-grid"', html)
        self.assertIn('id="zeike-method"', html)
        self.assertIn('id="zeike-reason"', html)
        self.assertIn('<option value="比用">比用</option>', html)
        self.assertIn('<option value="贼克＋比用">贼克＋比用</option>', html)
        self.assertIn('<option value="涉害">涉害·涉归本家计重</option>', html)
        self.assertIn('<option value="贼克＋比用＋涉害">贼克＋比用＋涉害</option>', html)
        self.assertIn('<option value="遥克">遥克</option>', html)
        self.assertIn('<option value="贼克＋比用＋涉害＋遥克">', html)
        self.assertIn('<option value="昴星">昴星</option>', html)
        self.assertIn('<option value="贼克＋比用＋涉害＋遥克＋昴星">', html)
        self.assertIn('<option value="别责">别责</option>', html)
        self.assertIn('<option value="贼克＋比用＋涉害＋遥克＋昴星＋别责">', html)
        self.assertIn('<option value="八专">八专</option>', html)
        self.assertIn('<option value="伏吟">伏吟</option>', html)
        self.assertIn('<option value="返吟">返吟</option>', html)
        self.assertIn("const sessionTotal =", script)
        self.assertIn("function renderZeike()", script)
        self.assertIn('renderSikeReference("#chuan-sike-grid")', script)
        self.assertIn('renderSikeReference("#zeike-sike-grid")', script)
        self.assertIn('pageParams.has("day")', script)
        self.assertIn('pageParams.get("topic")', script)
        self.assertIn('TOPICS.includes(pageParams.get("topic"))', script)
        self.assertIn("state.remediationTask || explicitTopic", script)
        self.assertIn('saved.mode !== "review"', script)
        self.assertIn('pageParams.has("task") && !explicitTopic', script)
        self.assertNotIn("state.meta.topics", script)
        self.assertIn('id="yaoke-candidates"', html)
        self.assertIn('state.topic === "遥克"', script)
        self.assertIn('state.topic === "昴星"', script)
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

    def test_due_sike_review_supplies_plate_but_not_sike_answers(self):
        state = {"wrong": [{
            "key": "四课|甲子|丑|申",
            "spec": ["四课", "甲子", "丑", "申"],
            "level": 4,
            "due": "2000-01-01",
            "streak": 0,
        }]}
        with patch("webapp.load_state", return_value=state):
            case = due_review_task()["cases"][0]
        self.assertEqual(case["review_stage"], "sike")
        self.assertEqual(len(case["tianpan_answers"]), 12)
        self.assertEqual(case["tianpan_answers"]["丑"], "申")
        self.assertEqual(case["sike_answers"], ["酉", "辰", "未", "寅"])

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
            ({"levels": {
                "4": {"topics": {
                    "贼克": {"hist": [1] * 11 + [0]},
                    "比用": {"hist": [1] * 12},
                    "贼克＋比用": {"hist": [1] * 11 + [0]},
                }},
                "7": {"hist": [1] * 6},
            }}, "贼克＋比用＋涉害"),
            ({"levels": {
                "4": {"topics": {
                    "贼克": {"hist": [1] * 11 + [0]},
                    "比用": {"hist": [1] * 12},
                    "贼克＋比用": {"hist": [1] * 11 + [0]},
                    "贼克＋比用＋涉害": {"hist": [1] * 12},
                }},
                "7": {"hist": [1] * 6},
            }}, "遥克"),
            ({"levels": {
                "4": {"topics": {
                    "贼克": {"hist": [1] * 6},
                    "比用": {"hist": [1] * 6},
                    "贼克＋比用": {"hist": [1] * 11 + [0]},
                    "贼克＋比用＋涉害": {"hist": [1] * 12},
                    "遥克": {"hist": [1] * 6},
                }},
                "7": {"hist": [1] * 6},
            }}, "贼克＋比用＋涉害＋遥克"),
            ({"levels": {
                "4": {"topics": {
                    "贼克": {"hist": [1] * 6},
                    "比用": {"hist": [1] * 6},
                    "贼克＋比用": {"hist": [1] * 11 + [0]},
                    "贼克＋比用＋涉害": {"hist": [1] * 12},
                    "遥克": {"hist": [1] * 6},
                    "贼克＋比用＋涉害＋遥克": {"hist": [1] * 11 + [0]},
                }},
                "7": {"hist": [1] * 6},
            }}, "昴星"),
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

    def test_missing_answers_are_distinct_from_wrong_answers(self):
        result = check_answers({
            **CASE,
            "stage": "sike",
            "answers": ["酉", "", "子", "午"],
        })
        self.assertFalse(result["complete"])
        self.assertFalse(result["correct"])
        self.assertEqual(result["missing_count"], 1)
        self.assertEqual(result["wrong_count"], 1)
        self.assertTrue(result["cells"][0]["filled"])
        self.assertFalse(result["cells"][1]["filled"])
        self.assertFalse(result["cells"][1]["correct"])

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

    def test_three_method_mixed_cases_are_class_balanced(self):
        seen = set()
        for _ in range(100):
            prompt = random_case_prompt("贼克＋比用＋涉害")
            plate = webapp._case(
                prompt["day"], prompt["shi"], prompt["jiang"], prompt["daynight"],
            )
            self.assertIn(plate.keshi, ("元首", "重审", "知一", "涉害"))
            seen.add(plate.keshi)
            result = check_answers({
                **prompt,
                "topic": "贼克＋比用＋涉害",
                "stage": "zeike",
                "answers": [
                    plate.keshi,
                    plate.chuan[0],
                    webapp._selection_reasons(plate),
                ],
            })
            self.assertTrue(result["correct"])
        self.assertEqual(seen, {"元首", "重审", "知一", "涉害"})

    def test_four_method_mixed_cases_include_yaoke(self):
        seen = set()
        for _ in range(160):
            prompt = random_case_prompt("贼克＋比用＋涉害＋遥克")
            plate = webapp._case(
                prompt["day"], prompt["shi"], prompt["jiang"], prompt["daynight"],
            )
            seen.add(plate.keshi)
            answers = [
                plate.keshi_sub if plate.keshi == "遥克" else plate.keshi,
                plate.chuan[0],
                webapp._selection_reasons(plate),
                webapp._yaoke_candidates(plate)[0] if plate.keshi == "遥克" else [],
            ]
            self.assertTrue(check_answers({
                **prompt,
                "topic": "贼克＋比用＋涉害＋遥克",
                "stage": "zeike",
                "answers": answers,
            })["correct"])
        self.assertTrue({"元首", "重审", "知一", "涉害", "遥克"} <= seen)

    def test_layered_method_selection_is_checked(self):
        method_by_keshi = {
            "元首": "贼克", "重审": "贼克", "知一": "比用",
            "涉害": "涉害", "遥克": "遥克",
        }
        for topic in ("贼克", "比用", "涉害", "遥克"):
            prompt = random_case_prompt(topic)
            plate = webapp._case(
                prompt["day"], prompt["shi"], prompt["jiang"], prompt["daynight"],
            )
            method = method_by_keshi[plate.keshi]
            lesson = plate.keshi_sub if plate.keshi == "遥克" else plate.keshi
            candidates = (
                webapp._yaoke_candidates(plate)[0]
                if plate.keshi == "遥克" else []
            )
            answers = [
                method, lesson, plate.chuan[0],
                webapp._selection_reasons(plate), candidates,
            ]
            self.assertTrue(check_answers({
                **prompt, "topic": topic, "stage": "zeike", "answers": answers,
            })["correct"])
            answers[0] = "遥克" if method != "遥克" else "贼克"
            self.assertFalse(check_answers({
                **prompt, "topic": topic, "stage": "zeike", "answers": answers,
            })["correct"])

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

    def test_yaoke_random_cases_require_subtype_candidates_and_reason(self):
        for _ in range(40):
            prompt = random_case_prompt("遥克")
            plate = webapp._case(
                prompt["day"], prompt["shi"], prompt["jiang"], prompt["daynight"],
            )
            candidates, subtype = webapp._yaoke_candidates(plate)
            self.assertEqual(plate.keshi, "遥克")
            self.assertIn(subtype, ("蒿矢", "弹射"))
            result = check_answers({
                **prompt,
                "topic": "遥克",
                "stage": "zeike",
                "answers": [
                    subtype,
                    plate.chuan[0],
                    webapp._selection_reasons(plate),
                    candidates,
                ],
            })
            self.assertTrue(result["correct"])

            missing_candidate = check_answers({
                **prompt,
                "topic": "遥克",
                "stage": "zeike",
                "answers": [
                    subtype,
                    plate.chuan[0],
                    webapp._selection_reasons(plate),
                    candidates[:-1],
                ],
            })
            self.assertFalse(missing_candidate["correct"])

    def test_maoxing_random_cases_require_direction_and_initial(self):
        for _ in range(40):
            prompt = random_case_prompt("昴星")
            plate = webapp._case(
                prompt["day"], prompt["shi"], prompt["jiang"], prompt["daynight"],
            )
            self.assertEqual(plate.keshi, "昴星")
            reasons = webapp._selection_reasons(plate)
            self.assertIn("四课上下无克", reasons)
            self.assertIn("无遥克", reasons)
            self.assertIn("阳仰酉上" if plate.is_gang else "阴俯酉下", reasons)
            result = check_answers({
                **prompt,
                "topic": "昴星",
                "stage": "zeike",
                "answers": ["昴星", "昴星", plate.chuan[0], reasons, []],
            })
            self.assertTrue(result["correct"])
            self.assertTrue(check_answers({
                **prompt,
                "topic": "昴星",
                "stage": "chuan",
                "answers": list(plate.chuan),
            })["correct"])

    def test_bieze_random_cases_require_entry_direction_and_three_transmissions(self):
        for _ in range(40):
            prompt = random_case_prompt("别责")
            plate = webapp._case(
                prompt["day"], prompt["shi"], prompt["jiang"], prompt["daynight"],
            )
            self.assertEqual(plate.keshi, "别责")
            reasons = webapp._selection_reasons(plate)
            self.assertIn("四课不全三课备", reasons)
            self.assertIn("四课上下无克", reasons)
            self.assertIn("无遥克", reasons)
            self.assertIn(
                "刚日取干合寄宫上神" if plate.is_gang else "柔日取支前三合宫上神",
                reasons,
            )
            self.assertTrue(check_answers({
                **prompt,
                "topic": "别责",
                "stage": "zeike",
                "answers": ["别责", "别责", plate.chuan[0], reasons, []],
            })["correct"])
            self.assertTrue(check_answers({
                **prompt,
                "topic": "别责",
                "stage": "chuan",
                "answers": list(plate.chuan),
            })["correct"])

    def test_bazhuan_random_cases_require_entry_direction_and_three_transmissions(self):
        for _ in range(40):
            prompt = random_case_prompt("八专")
            plate = webapp._case(
                prompt["day"], prompt["shi"], prompt["jiang"], prompt["daynight"],
            )
            self.assertEqual(plate.keshi, "八专")
            reasons = webapp._selection_reasons(plate)
            self.assertIn("四课重成两课", reasons)
            if plate.keshi_sub.startswith("有克"):
                self.assertTrue(
                    {"有下贼取下贼", "无下贼取上克"} & set(reasons)
                )
            else:
                self.assertIn("四课上下无克", reasons)
                self.assertIn("八专不论遥克", reasons)
                self.assertIn(
                    "刚日日阳顺数三位" if plate.is_gang else "柔日辰阴逆数三位",
                    reasons,
                )
            self.assertTrue(check_answers({
                **prompt,
                "topic": "八专",
                "stage": "zeike",
                "answers": ["八专", plate.keshi_sub, plate.chuan[0], reasons, []],
            })["correct"])
            self.assertTrue(check_answers({
                **prompt,
                "topic": "八专",
                "stage": "chuan",
                "answers": list(plate.chuan),
            })["correct"])

    def test_bazhuan_with_overcoming_keeps_structural_classification(self):
        plate = webapp._case("己未", "辰", "酉", "昼")
        self.assertEqual(plate.keshi, "八专")
        self.assertEqual(plate.keshi_sub, "有克·知一")
        self.assertEqual(plate.chuan, ("巳", "戌", "卯"))

    def test_fuyin_random_cases_require_branch_reasons_and_three_transmissions(self):
        seen = set()
        for _ in range(160):
            prompt = random_case_prompt("伏吟")
            plate = webapp._case(
                prompt["day"], prompt["shi"], prompt["jiang"], prompt["daynight"],
            )
            self.assertEqual(plate.keshi, "伏吟")
            seen.add(plate.keshi_sub)
            reasons = webapp._selection_reasons(plate)
            self.assertIn("天地盘同位", reasons)
            self.assertEqual(len(reasons), 2)
            self.assertFalse(any("中传" in reason or "末传" in reason for reason in reasons))
            self.assertTrue(check_answers({
                **prompt,
                "topic": "伏吟",
                "stage": "zeike",
                "answers": ["伏吟", plate.keshi_sub, plate.chuan[0], reasons, []],
            })["correct"])
            self.assertTrue(check_answers({
                **prompt,
                "topic": "伏吟",
                "stage": "chuan",
                "answers": list(plate.chuan),
            })["correct"])
        self.assertEqual(seen, {"自任", "自信", "有克·元首", "有克·重审"})

    def test_fanyin_random_cases_require_branch_reasons_and_three_transmissions(self):
        seen = set()
        for _ in range(160):
            prompt = random_case_prompt("返吟")
            plate = webapp._case(
                prompt["day"], prompt["shi"], prompt["jiang"], prompt["daynight"],
            )
            self.assertEqual(plate.keshi, "返吟")
            seen.add("有克" if plate.keshi_sub.startswith("有克") else plate.keshi_sub)
            reasons = webapp._selection_reasons(plate)
            self.assertIn("天地盘各临冲位", reasons)
            self.assertEqual(len(reasons), 2)
            self.assertTrue(check_answers({
                **prompt,
                "topic": "返吟",
                "stage": "zeike",
                "answers": ["返吟", plate.keshi_sub, plate.chuan[0], reasons, []],
            })["correct"])
            self.assertTrue(check_answers({
                **prompt,
                "topic": "返吟",
                "stage": "chuan",
                "answers": list(plate.chuan),
            })["correct"])
        self.assertEqual(seen, {"有克", "井栏射"})

    def test_five_method_mixed_cases_include_maoxing(self):
        seen = set()
        for _ in range(220):
            prompt = random_case_prompt("贼克＋比用＋涉害＋遥克＋昴星")
            plate = webapp._case(
                prompt["day"], prompt["shi"], prompt["jiang"], prompt["daynight"],
            )
            seen.add(plate.keshi)
        self.assertTrue({"元首", "重审", "知一", "涉害", "遥克", "昴星"} <= seen)

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

    def test_reason_ids_are_stable_and_legacy_labels_remain_compatible(self):
        prompt = random_case_prompt("比用")
        plate = webapp._case(
            prompt["day"], prompt["shi"], prompt["jiang"], prompt["daynight"],
        )
        direction = ("zeike.lower_over_upper"
                     if any(k.xia_ze_shang for k in plate.kes)
                     else "zeike.upper_over_lower")
        polarity = "biyong.yang" if plate.is_gang else "biyong.yin"
        result = check_answers({
            **prompt,
            "topic": "比用",
            "stage": "zeike",
            "scoring_version": SCORING_VERSION,
            "answers": ["比用", "知一", plate.chuan[0], [direction, polarity], []],
        })
        self.assertTrue(result["correct"])
        self.assertEqual(result["scoring_version"], SCORING_VERSION)

    def test_scoring_version_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "判分版本"):
            check_answers({
                **CASE,
                "stage": "sike",
                "scoring_version": "obsolete",
                "answers": list("酉丑寅午"),
            })

    def test_remediation_task_is_persistent_and_never_records_formal_score(self):
        cases = [
            {"day": day, "shi": "子", "jiang": "未", "daynight": "昼"}
            for day in ("甲子", "乙丑", "丙寅")
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(webapp, "REMEDIATION_TASKS", root / "tasks.json"), \
                 patch.object(webapp, "REMEDIATION_LOG", root / "results.jsonl"):
                task = create_remediation_task({
                    "topic": "比用",
                    "reason_code": "漏做比用",
                    "cases": cases,
                })
                result = return_remediation_result({
                    "task_id": task["task_id"],
                    "session_id": "remediation-session-1234",
                    "scoring_version": SCORING_VERSION,
                    "records": [
                        {**case, "clean": True, "mistakes": []}
                        for case in cases
                    ],
                })

        self.assertEqual(task["mode"], "remediation")
        self.assertEqual(task["total"], 3)
        self.assertEqual(result["score"], 3)
        self.assertTrue(result["completed"])
        self.assertTrue(result["mastered"])
        self.assertFalse(result["counts_toward_formal_score"])

    def test_learning_status_reconciles_formal_web_and_remediation_evidence(self):
        state = {
            "levels": {"4": {"topics": {
                "昴星": {"hist": [1] * 6, "teachback": True},
            }}},
            "sessions": [{
                "session_id": "formal-1", "topic": "昴星", "right": 6, "n": 6,
                "details": [{"clean": False, "mistakes": [{"stage": "zeike"}]}],
            }],
            "wrong": [],
        }
        tasks = {"tasks": {"task-1": {
            "task_id": "task-1", "topic": "比用", "status": "completed",
            "result": {"score": 3, "total": 3},
        }}}
        with tempfile.TemporaryDirectory() as directory:
            task_path = Path(directory) / "tasks.json"
            task_path.write_text(
                __import__("json").dumps(tasks, ensure_ascii=False), encoding="utf-8",
            )
            review_path = Path(directory) / "reviews.jsonl"
            review_path.write_text(
                '{"session_id":"formal-1","question_id":"q7",'
                '"status":"pending","note":"文案与额外选择分项复核"}\n',
                encoding="utf-8",
            )
            with patch.object(webapp, "load_state", return_value=state), \
                 patch.object(webapp, "REMEDIATION_TASKS", task_path), \
                 patch.object(webapp, "REVIEW_LOG", review_path):
                status = learning_status()

        self.assertEqual(status["scoring_version"], SCORING_VERSION)
        self.assertEqual(status["formal_sessions"][0]["session_id"], "formal-1")
        self.assertEqual(status["web_errors"][0]["session_id"], "formal-1")
        self.assertEqual(status["remediation"][0]["task_id"], "task-1")
        self.assertEqual(status["disputes"][0]["question_id"], "q7")
        self.assertTrue(status["topics"]["昴星"]["teachback"])

    def test_training_review_is_append_only_and_versioned(self):
        with tempfile.TemporaryDirectory() as directory:
            review_path = Path(directory) / "reviews.jsonl"
            with patch.object(webapp, "REVIEW_LOG", review_path):
                review = record_training_review({
                    "session_id": "formal-session-1234",
                    "question_id": "q7",
                    "status": "pending",
                    "note": "旧文案与额外选择分别复核",
                })
                rows = review_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(rows), 1)
        self.assertEqual(review["scoring_version"], SCORING_VERSION)
        self.assertEqual(review["status"], "pending")

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

    def test_tianjiang_random_cases_use_unambiguous_daynight_hours(self):
        valid = {
            "昼": {"巳", "午", "未"},
            "夜": {"亥", "子", "丑"},
        }
        seen = set()
        for _ in range(100):
            prompt = random_case_prompt("十二天将与贵人")
            seen.add(prompt["daynight"])
            self.assertIn(prompt["shi"], valid[prompt["daynight"]])
        self.assertEqual(seen, {"昼", "夜"})

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
            for _ in range(6)
        ]
        with tempfile.TemporaryDirectory() as directory:
            result_log = Path(directory) / "results.jsonl"
            with patch.object(webapp, "RESULT_LOG", result_log), \
                 patch.object(webapp, "record_external_session", return_value={
                     "recorded": True, "right": 6, "n": 6, "ready": True,
                 }) as record_session, \
                 patch.object(webapp, "_focus_trae_window", return_value=False):
                result = return_training_result({
                    "session_id": "zeike-session-1234",
                    "score": 6,
                    "total": 6,
                    "records": records,
                    "topic": "贼克",
                })

        self.assertIn("贼克专项 6/6", result["message"])
        args, kwargs = record_session.call_args
        self.assertEqual(args, (
            4, [1] * 6, "web-trainer", "zeike-session-1234",
        ))
        self.assertEqual(kwargs["topic"], "贼克")
        self.assertEqual(len(kwargs["details"]), 6)

    def test_biyong_result_is_saved_as_level4_topic(self):
        records = [
            {"day": "壬辰", "shi": "巳", "jiang": "辰", "clean": True}
            for _ in range(6)
        ]
        with tempfile.TemporaryDirectory() as directory:
            result_log = Path(directory) / "results.jsonl"
            with patch.object(webapp, "RESULT_LOG", result_log), \
                 patch.object(webapp, "record_external_session", return_value={
                     "recorded": True, "right": 6, "n": 6, "ready": True,
                 }) as record_session, \
                 patch.object(webapp, "_focus_trae_window", return_value=False):
                result = return_training_result({
                    "session_id": "biyong-session-1234",
                    "score": 6,
                    "total": 6,
                    "records": records,
                    "topic": "比用",
                })

        self.assertIn("比用专项 6/6", result["message"])
        self.assertEqual(record_session.call_args.kwargs["topic"], "比用")

    def test_chuan_result_is_saved_as_level5(self):
        records = [
            {"day": "甲子", "shi": "子", "jiang": "辰", "clean": i != 3}
            for i in range(12)
        ]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(webapp, "RESULT_LOG", Path(directory) / "results.jsonl"), \
                 patch.object(webapp, "record_external_session", return_value={
                     "recorded": True, "right": 11, "n": 12, "ready": True,
                 }) as record_session, \
                 patch.object(webapp, "_focus_trae_window", return_value=False):
                result = return_training_result({
                    "session_id": "chuan-session-1234",
                    "score": 11,
                    "total": 12,
                    "records": records,
                    "topic": "三传",
                })

        self.assertTrue(result["passed"])
        self.assertIn("三传专项 11/12", result["message"])
        self.assertEqual(
            record_session.call_args.args,
            (5, [1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1],
             "web-trainer", "chuan-session-1234"),
        )
        self.assertNotIn("topic", record_session.call_args.kwargs)
        self.assertEqual(len(record_session.call_args.kwargs["details"]), 12)

    def test_tianjiang_result_is_saved_as_level6(self):
        records = [
            {
                "day": "甲子", "shi": "丑", "jiang": "申",
                "daynight": "昼", "clean": True,
            }
            for _ in range(6)
        ]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(webapp, "RESULT_LOG", Path(directory) / "results.jsonl"), \
                 patch.object(webapp, "record_external_session", return_value={
                     "recorded": True, "right": 6, "n": 6, "ready": True,
                 }) as record_session, \
                 patch.object(webapp, "_focus_trae_window", return_value=False):
                result = return_training_result({
                    "session_id": "tianjiang-session-1234",
                    "score": 6,
                    "total": 6,
                    "records": records,
                    "topic": "十二天将与贵人",
                })

        self.assertTrue(result["passed"])
        self.assertIn("十二天将与贵人专项 6/6", result["message"])
        self.assertEqual(
            record_session.call_args.args,
            (6, [1] * 6, "web-trainer", "tianjiang-session-1234"),
        )
        self.assertNotIn("topic", record_session.call_args.kwargs)
        self.assertEqual(len(record_session.call_args.kwargs["details"]), 6)

    def test_shehai_result_is_saved_as_level7(self):
        records = [
            {"day": "丁卯", "shi": "卯", "jiang": "未", "clean": True}
            for _ in range(6)
        ]
        with tempfile.TemporaryDirectory() as directory:
            result_log = Path(directory) / "results.jsonl"
            with patch.object(webapp, "RESULT_LOG", result_log), \
                 patch.object(webapp, "record_external_session", return_value={
                     "recorded": True, "right": 6, "n": 6, "ready": True,
                 }) as record_session, \
                 patch.object(webapp, "_focus_trae_window", return_value=False):
                result = return_training_result({
                    "session_id": "shehai-session-1234",
                    "score": 6,
                    "total": 6,
                    "records": records,
                    "topic": "涉害",
                })

        self.assertIn("涉害专项 6/6", result["message"])
        args, kwargs = record_session.call_args
        self.assertEqual(args, (7, [1] * 6, "web-trainer", "shehai-session-1234"))
        self.assertNotIn("topic", kwargs)

    def test_three_method_result_is_saved_as_level4_topic(self):
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
                    "session_id": "three-method-session-1234",
                    "score": 12,
                    "total": 12,
                    "records": records,
                    "topic": "贼克＋比用＋涉害",
                })

        self.assertIn("贼克＋比用＋涉害累计混合 12/12", result["message"])
        args, kwargs = record_session.call_args
        self.assertEqual(args, (4, [1] * 12, "web-trainer", "three-method-session-1234"))
        self.assertEqual(kwargs["topic"], "贼克＋比用＋涉害")

    def test_four_method_result_remains_twelve_question_mixed(self):
        records = [
            {"day": "甲子", "shi": "子", "jiang": "辰", "clean": i != 3}
            for i in range(12)
        ]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(webapp, "RESULT_LOG", Path(directory) / "results.jsonl"), \
                 patch.object(webapp, "record_external_session", return_value={
                     "recorded": True, "right": 11, "n": 12, "ready": True,
                 }) as record_session, \
                 patch.object(webapp, "_focus_trae_window", return_value=False):
                result = return_training_result({
                    "session_id": "four-method-session-1234",
                    "score": 11,
                    "total": 12,
                    "records": records,
                    "topic": "贼克＋比用＋涉害＋遥克",
                })

        self.assertTrue(result["passed"])
        self.assertIn("贼克＋比用＋涉害＋遥克累计混合 11/12", result["message"])
        self.assertEqual(
            record_session.call_args.args,
            (4, [1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1],
             "web-trainer", "four-method-session-1234"),
        )

    def test_maoxing_result_is_saved_as_level4_topic(self):
        records = [
            {"day": "己丑", "shi": "寅", "jiang": "亥", "clean": True}
            for _ in range(6)
        ]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(webapp, "RESULT_LOG", Path(directory) / "results.jsonl"), \
                 patch.object(webapp, "record_external_session", return_value={
                     "recorded": True, "right": 6, "n": 6, "ready": True,
                 }) as record_session, \
                 patch.object(webapp, "_focus_trae_window", return_value=False):
                result = return_training_result({
                    "session_id": "maoxing-session-1234",
                    "score": 6,
                    "total": 6,
                    "records": records,
                    "topic": "昴星",
                })

        self.assertTrue(result["passed"])
        self.assertIn("昴星专项 6/6", result["message"])
        self.assertEqual(record_session.call_args.kwargs["topic"], "昴星")

    def test_bazhuan_result_is_saved_as_level4_topic(self):
        records = [
            {"day": "甲寅", "shi": "辰", "jiang": "丑", "clean": True}
            for _ in range(6)
        ]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(webapp, "RESULT_LOG", Path(directory) / "results.jsonl"), \
                 patch.object(webapp, "record_external_session", return_value={
                     "recorded": True, "right": 6, "n": 6, "ready": True,
                 }) as record_session, \
                 patch.object(webapp, "_focus_trae_window", return_value=False):
                result = return_training_result({
                    "session_id": "bazhuan-session-1234",
                    "score": 6,
                    "total": 6,
                    "records": records,
                    "topic": "八专",
                })

        self.assertTrue(result["passed"])
        self.assertIn("八专专项 6/6", result["message"])
        self.assertEqual(record_session.call_args.kwargs["topic"], "八专")

    def test_fuyin_result_is_saved_as_level4_topic(self):
        records = [
            {"day": "壬辰", "shi": "卯", "jiang": "卯", "clean": True}
            for _ in range(6)
        ]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(webapp, "RESULT_LOG", Path(directory) / "results.jsonl"), \
                 patch.object(webapp, "record_external_session", return_value={
                     "recorded": True, "right": 6, "n": 6, "ready": True,
                 }) as record_session, \
                 patch.object(webapp, "_focus_trae_window", return_value=False):
                result = return_training_result({
                    "session_id": "fuyin-session-1234",
                    "score": 6,
                    "total": 6,
                    "records": records,
                    "topic": "伏吟",
                })

        self.assertTrue(result["passed"])
        self.assertIn("伏吟专项 6/6", result["message"])
        self.assertEqual(record_session.call_args.kwargs["topic"], "伏吟")

    def test_fanyin_result_is_saved_as_level4_topic(self):
        records = [
            {"day": "辛巳", "shi": "子", "jiang": "午", "clean": True}
            for _ in range(6)
        ]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(webapp, "RESULT_LOG", Path(directory) / "results.jsonl"), \
                 patch.object(webapp, "record_external_session", return_value={
                     "recorded": True, "right": 6, "n": 6, "ready": True,
                 }) as record_session, \
                 patch.object(webapp, "_focus_trae_window", return_value=False):
                result = return_training_result({
                    "session_id": "fanyin-session-1234",
                    "score": 6,
                    "total": 6,
                    "records": records,
                    "topic": "返吟",
                })

        self.assertTrue(result["passed"])
        self.assertIn("返吟专项 6/6", result["message"])
        self.assertEqual(record_session.call_args.kwargs["topic"], "返吟")

    def test_seven_method_result_is_twelve_question_mixed(self):
        topic = "贼克＋比用＋涉害＋遥克＋昴星＋别责＋八专"
        records = [
            {"day": "甲寅", "shi": "辰", "jiang": "丑", "clean": i != 4}
            for i in range(12)
        ]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(webapp, "RESULT_LOG", Path(directory) / "results.jsonl"), \
                 patch.object(webapp, "record_external_session", return_value={
                     "recorded": True, "right": 11, "n": 12, "ready": True,
                 }) as record_session, \
                 patch.object(webapp, "_focus_trae_window", return_value=False):
                result = return_training_result({
                    "session_id": "seven-method-session-1234",
                    "score": 11,
                    "total": 12,
                    "records": records,
                    "topic": topic,
                })

        self.assertTrue(result["passed"])
        self.assertIn(f"{topic}累计混合 11/12", result["message"])
        self.assertEqual(record_session.call_args.kwargs["topic"], topic)

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

    def test_external_session_enqueues_browser_error_once(self):
        details = [
            {
                "day": "甲子", "shi": "丑", "jiang": "申", "daynight": "昼",
                "clean": False,
                "mistakes": [{
                    "stage": "sike", "revealed": False,
                    "wrong": [{"key": "2", "actual": "亥", "expected": "未"}],
                }],
            },
            *[
                {
                    "day": "甲子", "shi": "子", "jiang": "辰",
                    "daynight": "昼", "clean": True, "mistakes": [],
                }
                for _ in range(5)
            ],
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(tutor, "STATE", root / "state.json"), \
                 patch.object(tutor, "RECORD", root / "record.md"), \
                 patch.object(tutor, "WRONGQ", root / "wrong.md"):
                first = tutor.record_external_session(
                    4, [0] + [1] * 5, "web-trainer", "browser-wrong-1234",
                    topic="比用", details=details,
                )
                duplicate = tutor.record_external_session(
                    4, [0] + [1] * 5, "web-trainer", "browser-wrong-1234",
                    topic="比用", details=details,
                )
                state = tutor.load_state()

        self.assertEqual(first["wrong_queued"], 1)
        self.assertFalse(duplicate["recorded"])
        self.assertEqual(len(state["wrong"]), 1)
        self.assertEqual(state["wrong"][0]["spec"], ["四课", "甲子", "丑", "申"])
        self.assertEqual(
            state["wrong"][0]["sources"][0]["session_id"], "browser-wrong-1234",
        )

    def test_external_session_does_not_enqueue_invalidated_error(self):
        details = [{
            "day": "甲申", "shi": "巳", "jiang": "未", "daynight": "昼",
            "clean": True,
            "mistakes": [],
            "invalidated_mistakes": [{
                "stage": "zeike", "revealed": False,
                "wrong": [{"key": "2", "actual": ["旧文案"], "expected": ["新文案"]}],
            }],
        }]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(tutor, "STATE", root / "state.json"), \
                 patch.object(tutor, "RECORD", root / "record.md"), \
                 patch.object(tutor, "WRONGQ", root / "wrong.md"):
                result = tutor.record_external_session(
                    7, [1], "web-trainer", "invalidated-wrong-1234",
                    details=details,
                )
                state = tutor.load_state()

        self.assertEqual(result["wrong_queued"], 0)
        self.assertEqual(state["wrong"], [])

    def test_backfill_skips_pending_review_and_is_idempotent(self):
        details = [
            {
                "day": "甲子", "shi": "丑", "jiang": "申", "daynight": "昼",
                "clean": False,
                "mistakes": [{
                    "stage": "sike", "revealed": False,
                    "wrong": [{"key": "2", "actual": "亥", "expected": "未"}],
                }],
            },
            {
                "day": "丁未", "shi": "戌", "jiang": "丑", "daynight": "昼",
                "clean": False,
                "mistakes": [{
                    "stage": "zeike", "revealed": False,
                    "wrong": [{"key": "2", "actual": "申", "expected": "亥"}],
                }],
            },
        ]
        state = {
            "levels": {}, "wrong": [], "wrong_archive": [], "weak_groups": {},
            "sessions": [], "unscored_sessions": [], "progression_waivers": {},
            "external_sessions": {
                "backfill-session-1234": {
                    "date": "2026-09-15T10:00:00", "level": 4,
                    "topic": "八专", "details": details,
                },
            },
        }
        reviews = [{
            "session_id": "backfill-session-1234", "question_id": "q1",
            "status": "pending",
        }]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(tutor, "STATE", root / "state.json"), \
                 patch.object(tutor, "RECORD", root / "record.md"), \
                 patch.object(tutor, "WRONGQ", root / "wrong.md"):
                tutor.save_state(state)
                first = tutor.backfill_external_wrong_queue(reviews)
                second = tutor.backfill_external_wrong_queue(reviews)
                saved = tutor.load_state()

        self.assertEqual(first["queued"], 1)
        self.assertEqual(first["skipped_review"], 1)
        self.assertEqual(second["queued"], 0)
        self.assertEqual(len(saved["wrong"]), 1)
        self.assertEqual(saved["wrong"][0]["spec"][0], "八专")

    def test_zeike_external_session_stays_out_of_full_level_score(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(tutor, "STATE", root / "state.json"), \
                 patch.object(tutor, "RECORD", root / "record.md"), \
                 patch.object(tutor, "WRONGQ", root / "wrong.md"):
                result = tutor.record_external_session(
                    4, [1] * 6, "web-trainer", "zeike-session-1234",
                    topic="贼克",
                )
                state = tutor.load_state()
                record = (root / "record.md").read_text(encoding="utf-8")

        level = state["levels"]["4"]
        self.assertTrue(result["ready"])
        self.assertEqual(level["hist"], [])
        self.assertEqual(level["topics"]["贼克"]["hist"], [1] * 6)
        self.assertIn("| 贼克 | 关卡 4 前置单项 | 6/6 |", record)
        self.assertIn("累计计分 **6** 题", record)
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
