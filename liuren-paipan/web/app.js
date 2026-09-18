const ZHI = [..."子丑寅卯辰巳午未申酉戌亥"];
const THREE_METHODS_TOPIC = "贼克＋比用＋涉害";
const FOUR_METHODS_TOPIC = "贼克＋比用＋涉害＋遥克";
const FIVE_METHODS_TOPIC = "贼克＋比用＋涉害＋遥克＋昴星";
const SIX_METHODS_TOPIC = "贼克＋比用＋涉害＋遥克＋昴星＋别责";
const SEVEN_METHODS_TOPIC = "贼克＋比用＋涉害＋遥克＋昴星＋别责＋八专";
const EIGHT_METHODS_TOPIC = "贼克＋比用＋涉害＋遥克＋昴星＋别责＋八专＋伏吟";
const NINE_METHODS_TOPIC = "贼克＋比用＋涉害＋遥克＋昴星＋别责＋八专＋伏吟＋返吟";
const MIXED_TOPICS = new Set([
  "贼克＋比用", THREE_METHODS_TOPIC, FOUR_METHODS_TOPIC, FIVE_METHODS_TOPIC,
  SIX_METHODS_TOPIC, SEVEN_METHODS_TOPIC, EIGHT_METHODS_TOPIC, NINE_METHODS_TOPIC,
]);
const TOPICS = ["四课", "贼克", "比用", "贼克＋比用", "涉害",
  THREE_METHODS_TOPIC, "遥克", FOUR_METHODS_TOPIC, "昴星", FIVE_METHODS_TOPIC,
  "别责", SIX_METHODS_TOPIC, "八专", SEVEN_METHODS_TOPIC, "伏吟",
  EIGHT_METHODS_TOPIC, "返吟", NINE_METHODS_TOPIC, "三传", "十二天将与贵人"];
const WUXING_BY_ZHI = {
  子: "water", 丑: "earth", 寅: "wood", 卯: "wood", 辰: "earth", 巳: "fire",
  午: "fire", 未: "earth", 申: "metal", 酉: "metal", 戌: "earth", 亥: "water",
};
const JIANG_DISPLAY = {
  贵人: ["贵", "earth"], 螣蛇: ["蛇", "fire"], 朱雀: ["朱", "fire"],
  六合: ["合", "wood"], 勾陈: ["勾", "earth"], 青龙: ["龙", "wood"],
  天空: ["空", "earth"], 白虎: ["虎", "metal"], 太常: ["常", "earth"],
  玄武: ["玄", "water"], 太阴: ["阴", "metal"], 天后: ["后", "water"],
};
const STAGE_COPY = {
  tianpan: ["第一步", "月将加时，填写天盘", 12],
  sike: ["第二步", "沿两条链，填写四课", 4],
  zeike: ["第三步", "判断取用并说明依据", 3],
  keshi: ["第三步", "根据四课判断九宗门", 1],
  chuan: ["第四步", "依取用路径填写三传", 3],
  tianjiang: ["第五步", "起贵人，填写十二天将", 12],
};
const STAGE_ORDER = ["tianpan", "sike", "zeike", "keshi", "chuan", "tianjiang"];
const SESSION_KEY = "liuren-web-trainer-session-v2";
const state = {
  meta: null,
  currentCase: null,
  remediationTask: null,
  reviewTask: null,
  topic: "贼克",
  stage: "tianpan",
  answers: {
    tianpan: {}, sike: ["", "", "", ""], zeike: ["", "", "", [], []],
    keshi: "", chuan: ["", "", ""], tianjiang: {},
  },
  attempts: 0,
  correct: 0,
  session: {
    id: "", active: false, index: 0, total: 12, score: 0,
    clean: true, complete: false, passed: new Set(), records: [],
    mistakes: [], resultMessage: "",
    mode: "formal", taskId: "", scoringVersion: "",
  },
};

function persistSession() {
  if (!state.session.id) return;
  localStorage.setItem(SESSION_KEY, JSON.stringify({
    id: state.session.id,
    active: state.session.active,
    index: state.session.index,
    total: state.session.total,
    score: state.session.score,
    records: state.session.records,
    topic: state.session.topic,
    mode: state.session.mode,
    taskId: state.session.taskId,
    scoringVersion: state.session.scoringVersion,
  }));
}

function restoreSession() {
  try {
    const saved = JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
    if (!saved || typeof saved.id !== "string" || saved.total !== sessionTotal(saved.topic) ||
        !TOPICS.includes(saved.topic) ||
        !Array.isArray(saved.records) || saved.records.length > saved.total ||
        !Number.isInteger(saved.score) || saved.score < 0 || saved.score > saved.records.length) {
      return false;
    }
    if (state.reviewTask && (
        saved.mode !== "review" ||
        saved.records.some((record, index) =>
          record.review_key !== state.reviewTask.cases[index]?.review_key)
    )) {
      return false;
    }
    state.session = {
      id: saved.id,
      active: true,
      index: Math.min(saved.records.length + 1, saved.total),
      total: saved.total,
      score: saved.score,
      clean: true,
      complete: saved.records.length === saved.total,
      passed: new Set(),
      records: saved.records,
      mistakes: [],
      topic: saved.topic,
      resultMessage: "",
      mode: saved.mode || "formal",
      taskId: saved.taskId || "",
      scoringVersion: saved.scoringVersion || "",
    };
    state.topic = saved.topic;
    return true;
  } catch {
    localStorage.removeItem(SESSION_KEY);
    return false;
  }
}

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const sessionTotal = (topic) => state.remediationTask?.total ||
  state.reviewTask?.total ||
  (topic === "四课" || topic === "三传" || MIXED_TOPICS.has(topic) ? 12 : 6);
const passingScore = (total) => (total === 12 ? 11 : 6);

function options(values, placeholder = "请选择") {
  return `<option value="">${placeholder}</option>` +
    values.map((value) => `<option value="${value}">${value}</option>`).join("");
}

function fillSelect(select, values, selected) {
  select.innerHTML = values.map((value) =>
    `<option value="${value}" ${value === selected ? "selected" : ""}>${value}</option>`).join("");
}

function jiangOptions(selected) {
  return '<option value="">天将</option>' + state.meta.tianjiang.map((value) =>
    `<option value="${value}" ${value === selected ? "selected" : ""}>${JIANG_DISPLAY[value][0]}</option>`
  ).join("");
}

function setJiangColor(select, value) {
  select.classList.remove("wood", "fire", "earth", "metal", "water");
  if (JIANG_DISPLAY[value]) select.classList.add(JIANG_DISPLAY[value][1]);
}

async function request(url, init) {
  const response = await fetch(url, init);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "请求失败");
  return data;
}

function caseQuery(random = false) {
  const params = new URLSearchParams();
  if (random) {
    params.set("random", "1");
  } else {
    params.set("day", $("#day-select").value);
    params.set("shi", $("#shi-select").value);
    params.set("jiang", $("#jiang-select").value);
  }
  params.set("daynight", $('input[name="daynight"]:checked').value);
  params.set("topic", state.topic);
  return params;
}

function clearAnswers() {
  state.answers = {
    tianpan: Object.fromEntries(ZHI.map((z) => [z, ""])),
    sike: ["", "", "", ""],
    zeike: ["", "", "", [], []],
    keshi: "",
    chuan: ["", "", ""],
    tianjiang: Object.fromEntries(ZHI.map((z) => [z, ""])),
  };
}

async function loadCase(random = false) {
  const task = state.reviewTask || state.remediationTask;
  const taskCase = task && state.session.active
    ? task.cases[state.session.index - 1]
    : null;
  if (taskCase?.review_topic) state.topic = taskCase.review_topic;
  state.currentCase = taskCase || await request(`/api/case?${caseQuery(random)}`);
  if (random) {
    $("#day-select").value = state.currentCase.day;
    $("#shi-select").value = state.currentCase.shi;
    $("#jiang-select").value = state.currentCase.jiang;
    const daynight = $(`input[name="daynight"][value="${state.currentCase.daynight}"]`);
    if (daynight) daynight.checked = true;
  }
  clearAnswers();
  if (taskCase?.tianpan_answers && taskCase.review_stage !== "tianpan") {
    state.answers.tianpan = {...taskCase.tianpan_answers};
  }
  if (taskCase?.sike_answers && taskCase.review_stage !== "sike") {
    state.answers.sike = [...taskCase.sike_answers];
  }
  state.session.clean = true;
  state.session.complete = false;
  state.session.passed = new Set();
  state.session.mistakes = [];
  state.stage = taskCase?.review_stage || "tianpan";
  render();
}

function renderQuestion() {
  const c = state.currentCase;
  $("#question-text").textContent = state.reviewTask
    ? `${c.day}日，${c.shi}时，${c.jiang}将：复现原错阶段“${STAGE_COPY[c.review_stage][1]}”。`
    : state.topic === "十二天将与贵人"
      ? `${c.day}日，${c.shi}时，${c.jiang}将，${c.daynight}占：排天地盘，再布十二天将。`
    : state.topic !== "四课"
      ? `${c.day}日，${c.shi}时，${c.jiang}将：排天地盘、立四课，判断取用、初传及依据。`
      : `${c.day}日，${c.shi}时，${c.jiang}将：先排天地盘，再立四课。`;
  if (state.session.active) {
    const prefix = state.session.mode === "review" ? "复现 " :
      (state.session.mode === "remediation" ? "补强 " : "");
    $("#question-index").textContent =
      `${prefix}第 ${state.session.index} / ${state.session.total} 题`;
    $("#question-score").textContent = `${state.session.score} 题正确`;
  } else {
    $("#question-index").textContent = "练习模式";
    $("#question-score").textContent = "0 / 0";
  }
  $("#session-button span:last-child").textContent = state.reviewTask
    ? `开始复现（${state.reviewTask.total}题）`
    : state.remediationTask
      ? `开始补强（${state.remediationTask.total}题）`
      : `开始${sessionTotal(state.topic)}题`;
  $("#session-button").classList.toggle("hidden", state.session.active);
  $("#next-button").classList.add("hidden");
  $("#copy-result-button").classList.toggle("hidden", !state.session.resultMessage);
  $$("#topic-select, #day-select, #shi-select, #jiang-select, input[name='daynight'], #random-button")
    .forEach((control) => {
      control.disabled = state.session.active ||
        Boolean(state.remediationTask) || Boolean(state.reviewTask);
    });
}

function unlockedStages() {
  if (state.reviewTask) return new Set([state.currentCase.review_stage]);
  if (state.topic === "四课") return new Set(["tianpan", "sike"]);
  if (state.topic === "十二天将与贵人") return new Set(["tianpan", "tianjiang"]);
  if (["昴星", "别责", "八专", "伏吟", "返吟", "三传"].includes(state.topic)) {
    return new Set(["tianpan", "sike", "zeike", "chuan"]);
  }
  return new Set(["tianpan", "sike", "zeike"]);
}

function palaceInput(di) {
  const isJiang = state.stage === "tianjiang";
  const stage = isJiang ? "tianjiang" : "tianpan";
  const values = isJiang ? state.meta.tianjiang : state.meta.zhi;
  const disabled = !["tianpan", "tianjiang"].includes(state.stage);
  const tian = state.answers.tianpan[di] || "";
  const selectedJiang = state.answers.tianjiang[di] || "";
  return `${isJiang ? `<span class="jiang-target ${WUXING_BY_ZHI[tian]}">${tian}</span>` : ""}
    <select aria-label="${isJiang ? `天盘${tian}所乘天将，落地盘${di}宫` : `地盘${di}宫的天盘支`}"
    data-stage="${stage}" data-key="${di}" class="${isJiang ? "jiang-input" : ""}" ${disabled ? "disabled" : ""}>
    ${isJiang ? jiangOptions(selectedJiang) : options(values, "天盘")}</select>
    <span class="earth-label ${isJiang ? WUXING_BY_ZHI[di] : ""}">${di}</span>`;
}

function renderPlate() {
  $$(".palace").forEach((cell) => {
    const di = cell.dataset.di;
    cell.className = `palace${state.stage === "tianjiang" ? " tianjiang-palace" : ""}`;
    cell.innerHTML = palaceInput(di);
    const input = cell.querySelector("select");
    const sourceStage = input.dataset.stage;
    input.value = state.answers[sourceStage][di] || "";
    if (sourceStage === "tianjiang") setJiangColor(input, input.value);
  });
}

function renderSike() {
  const names = ["一课", "二课", "三课", "四课"];
  $(".sike-grid").innerHTML = state.currentCase.sike_lows.map((low, index) => {
    const note = index === 0 ? `寄${low.gong}` : (low.gong ? `地盘${low.gong}` : "承上课");
    return `<article class="ke-card" data-key="${index}">
      <header><strong>${names[index]}</strong><span>${note}</span></header>
      <div class="low">下：${low.label}</div>
      <select aria-label="${names[index]}上神" data-stage="sike" data-key="${index}">
        ${options(state.meta.zhi, "上神")}
      </select>
    </article>`;
  }).join("");
  $$(".sike-grid select").forEach((input) => {
    input.value = state.answers.sike[Number(input.dataset.key)] || "";
  });
}

function renderChuan() {
  renderSikeReference("#chuan-sike-grid");
  const names = ["初传", "中传", "末传"];
  $(".chuan-grid").innerHTML = names.map((name, index) =>
    `<article class="chuan-card" data-key="${index}">
      <label>${name}<select aria-label="${name}" data-stage="chuan" data-key="${index}">
        ${options(state.meta.zhi, "地支")}
      </select></label>
    </article>`).join("");
  $$(".chuan-grid select").forEach((input) => {
    input.value = state.answers.chuan[Number(input.dataset.key)] || "";
  });
}

function renderSikeReference(selector) {
  const names = ["一课", "二课", "三课", "四课"];
  const lows = [
    state.currentCase.gan,
    state.answers.sike[0],
    state.currentCase.zhi,
    state.answers.sike[2],
  ];
  $(selector).innerHTML = names.map((name, index) =>
    `<article class="sike-reference-card">
      <strong>${name}</strong>
      <span class="upper"><small>上</small><b>${state.answers.sike[index]}</b></span>
      <span class="lower"><small>下</small><b>${lows[index]}</b></span>
    </article>`).reverse().join("");
}

function renderZeike() {
  renderSikeReference("#zeike-sike-grid");
  const topicMethods = {
    "贼克": ["贼克"],
    "比用": ["比用"],
    "涉害": ["涉害"],
    "遥克": ["遥克"],
    "昴星": ["昴星"],
    "别责": ["别责"],
    "八专": ["八专"],
    "伏吟": ["伏吟"],
    "返吟": ["返吟"],
    "贼克＋比用": ["贼克", "比用"],
    [THREE_METHODS_TOPIC]: ["贼克", "比用", "涉害"],
    [FOUR_METHODS_TOPIC]: ["贼克", "比用", "涉害", "遥克"],
    [FIVE_METHODS_TOPIC]: ["贼克", "比用", "涉害", "遥克", "昴星"],
    [SIX_METHODS_TOPIC]: ["贼克", "比用", "涉害", "遥克", "昴星", "别责"],
    [SEVEN_METHODS_TOPIC]: ["贼克", "比用", "涉害", "遥克", "昴星", "别责", "八专"],
    [EIGHT_METHODS_TOPIC]: [
      "贼克", "比用", "涉害", "遥克", "昴星", "别责", "八专", "伏吟",
    ],
    [NINE_METHODS_TOPIC]: [
      "贼克", "比用", "涉害", "遥克", "昴星", "别责", "八专", "伏吟", "返吟",
    ],
    "三传": [
      "贼克", "比用", "涉害", "遥克", "昴星", "别责", "八专", "伏吟", "返吟",
    ],
  };
  const methodLessons = {
    "贼克": ["元首", "重审"],
    "比用": ["知一"],
    "涉害": ["涉害"],
    "遥克": ["蒿矢", "弹射"],
    "昴星": ["昴星"],
    "别责": ["别责"],
    "八专": [
      "八专", "有克·元首", "有克·重审", "有克·知一",
      "有克·见机", "有克·察微", "有克·涉害", "有克·缀瑕",
    ],
    "伏吟": ["自任", "自信", "有克·元首", "有克·重审"],
    "返吟": ["井栏射", "有克·元首", "有克·重审", "有克·比用", "有克·见机"],
  };
  const methodReasons = {
    "贼克": ["zeike.lower_over_upper", "zeike.upper_over_lower"],
    "比用": ["zeike.lower_over_upper", "zeike.upper_over_lower", "biyong.yang", "biyong.yin"],
    "涉害": [
      "zeike.lower_over_upper", "zeike.upper_over_lower", "shehai.after_biyong",
      "shehai.count_to_home", "shehai.max_depth", "shehai.meng_zhong_ji",
      "shehai.first_seen",
    ],
    "遥克": [
      "no_internal_overcoming", "yaoke.spirit_over_day", "yaoke.day_over_spirit",
      "biyong.yang", "biyong.yin",
    ],
    "昴星": [
      "no_internal_overcoming", "no_yaoke",
      "maoxing.yang_above_you", "maoxing.yin_below_you",
    ],
    "别责": [
      "no_internal_overcoming", "no_yaoke", "bieze.three_distinct",
      "bieze.yang_gan_he", "bieze.yin_zhi_he",
    ],
    "八专": [
      "no_internal_overcoming", "bazhuan.two_distinct", "bazhuan.no_yaoke",
      "zeike.lower_over_upper", "zeike.upper_over_lower", "biyong.yang", "biyong.yin",
      "shehai.after_biyong", "shehai.count_to_home", "shehai.max_depth",
      "shehai.meng_zhong_ji", "shehai.first_seen",
      "bazhuan.yang_forward", "bazhuan.yin_backward",
    ],
    "伏吟": [
      "fuyin.same_plate", "fuyin.overcoming", "fuyin.yang_day", "fuyin.yin_day",
    ],
    "返吟": [
      "fanyin.opposite_plate", "fanyin.overcoming", "fanyin.no_overcoming",
    ],
  };
  const selectedMethod = state.answers.zeike[0] || "";
  const selectedLesson = state.answers.zeike[1] || "";
  const selectedInitial = state.answers.zeike[2] || "";
  const selectedReasons = new Set(state.answers.zeike[3] || []);
  const selectedCandidates = new Set(state.answers.zeike[4] || []);
  const isYaoke = selectedMethod === "遥克";
  $("#selection-title").textContent =
    state.topic === "涉害" ? "涉归本家计重并定初传"
      : (state.topic === "遥克" ? "列全候选并判断遥克取用"
        : (state.topic === "昴星" ? "按刚柔日读取酉位"
          : (state.topic === "别责" ? "按刚柔日别取初传"
            : (state.topic === "八专" ? "按刚柔日顺逆数三位"
              : (state.topic === "伏吟" ? "辨有克无克并确定初传"
                : (state.topic === "返吟" ? "辨有克与井栏并确定初传"
                  : "判断取用并取初传"))))));
  $("#zeike-method").innerHTML = options(topicMethods[state.topic] || [], "宗门");
  $("#zeike-method").value = selectedMethod;
  $("#zeike-keshi").closest(".zeike-card").classList.toggle("hidden", !selectedMethod);
  $("#zeike-keshi").innerHTML = options(methodLessons[selectedMethod] || [], "课名");
  $("#zeike-keshi").value = selectedLesson;
  $("#zeike-chu").innerHTML = options(state.meta.zhi, "初传");
  $("#zeike-chu").value = selectedInitial;
  const candidateCard = $("#yaoke-candidates-card");
  candidateCard.classList.toggle("hidden", !isYaoke || !selectedLesson);
  $("#yaoke-candidates").innerHTML = `<legend>全部同向遥克候选（可多选）</legend>` +
    state.meta.zhi.map((zhi) => `<label><input type="checkbox" data-stage="zeike"
    data-key="4" value="${zhi}" ${selectedCandidates.has(zhi) ? "checked" : ""}>${zhi}</label>`).join("");
  const candidatesReady = !isYaoke || selectedCandidates.size > 0;
  $("#zeike-chu-card").classList.toggle("hidden", !selectedLesson || !candidatesReady);
  $("#zeike-reason-card").classList.toggle("hidden", !selectedInitial);
  const reasonOptions = methodReasons[selectedMethod] || [];
  $("#zeike-reason").innerHTML = `<legend>判断依据（可多选）</legend>` +
    reasonOptions.map((reasonId) => `<label><input type="checkbox" data-stage="zeike"
    data-key="3" value="${reasonId}" ${selectedReasons.has(reasonId) ? "checked" : ""}>${
      state.meta.reason_catalog[reasonId]
    }</label>`).join("");
}

function render() {
  const [kicker, title, total] = STAGE_COPY[state.stage];
  $("#stage-kicker").textContent = kicker;
  $("#stage-title").textContent = title;
  $("#case-day").textContent = `${state.currentCase.day}日`;
  $("#case-time").textContent = `${state.currentCase.shi}时 · ${state.currentCase.jiang}将`;
  renderQuestion();
  $$(".stage-tab").forEach((button) => button.classList.toggle("active", button.dataset.stage === state.stage));
  const unlocked = unlockedStages();
  $$(".stage-tab").forEach((button) => {
    const available = unlocked.has(button.dataset.stage);
    button.disabled = !available;
    button.classList.toggle("locked", !available);
    button.title = available ? "" : "完成前置课程后解锁";
  });
  $$(".editor").forEach((editor) => editor.classList.add("hidden"));
  $(`#${state.stage}-editor`).classList.remove("hidden");
  renderPlate();
  renderSike();
  renderZeike();
  renderChuan();
  $("#keshi-answer").value = state.answers.keshi;
  updateProgress(total);
  syncPrimaryAction();
  setFeedback("idle", "等待填写", "完成当前阶段后检查。");
}

function currentAnswers() {
  return state.answers[state.stage];
}

function updateProgress(total = STAGE_COPY[state.stage][2]) {
  const answers = currentAnswers();
  let values = typeof answers === "string" ? [answers] :
    (Array.isArray(answers) ? answers : Object.values(answers));
  if (state.stage === "zeike") {
    const isYaoke = state.answers.zeike[0] === "遥克";
    values = isYaoke ? state.answers.zeike : state.answers.zeike.slice(0, 4);
    total = isYaoke ? 5 : 4;
  }
  const done = values.filter((value) => Array.isArray(value) ? value.length > 0 : Boolean(value)).length;
  $("#stage-progress").textContent = `${done} / ${total}`;
}

function fillTianpanFromAnchor(di, tian) {
  const shift = (ZHI.indexOf(tian) - ZHI.indexOf(di) + 12) % 12;
  ZHI.forEach((earth, index) => {
    state.answers.tianpan[earth] = ZHI[(index + shift) % 12];
  });
  renderPlate();
  const anchor = $(`.palace[data-di="${di}"]`);
  anchor?.classList.add("anchor");
  updateProgress();
  setFeedback("idle", `已由 ${tian} 加 ${di} 生成全盘`, "核对十二宫后点击检查。");
}

function setFeedback(kind, title, detail) {
  const panel = $("#feedback");
  panel.className = `feedback ${kind}`;
  panel.innerHTML = `<strong>${title}</strong><span>${detail}</span>`;
}

function syncPrimaryAction() {
  const button = $("#check-button");
  const isNext = state.session.active && state.session.complete &&
    state.session.index < state.session.total;
  button.dataset.action = isNext ? "next" : "check";
  button.innerHTML = isNext
    ? '<span>下一题</span><span class="button-symbol" aria-hidden="true">&#8594;</span>'
    : '<span class="button-symbol" aria-hidden="true">&#10003;</span><span>检查当前阶段</span>';
}

function advanceStage(detail) {
  const unlocked = unlockedStages();
  const next = STAGE_ORDER
    .slice(STAGE_ORDER.indexOf(state.stage) + 1)
    .find((stage) => unlocked.has(stage));
  if (!next) return false;
  state.stage = next;
  render();
  setFeedback("success", `已进入${STAGE_COPY[next][0]}`, detail);
  document.querySelector(`#${next}-editor`)?.scrollIntoView({ block: "nearest" });
  return true;
}

function onInput(event) {
  const input = event.target.closest("[data-stage]");
  if (!input) return;
  const stage = input.dataset.stage;
  const key = input.dataset.key;
  if (stage === "tianpan" && input.value) {
    fillTianpanFromAnchor(key, input.value);
    return;
  }
  if (stage === "zeike" && ["3", "4"].includes(key) && input.type === "checkbox") {
    const index = Number(key);
    const selected = new Set(state.answers.zeike[index] || []);
    if (input.checked) selected.add(input.value);
    else selected.delete(input.value);
    state.answers.zeike[index] = [...selected];
    if (key === "4") {
      state.answers.zeike[2] = "";
      state.answers.zeike[3] = [];
    }
  } else if (Array.isArray(state.answers[stage])) state.answers[stage][Number(key)] = input.value;
  else if (typeof state.answers[stage] === "object") state.answers[stage][key] = input.value;
  else state.answers[stage] = input.value;
  if (stage === "tianjiang") setJiangColor(input, input.value);
  if (stage === "zeike" && key === "0") {
    state.answers.zeike = [input.value, "", "", [], []];
  } else if (stage === "zeike" && key === "1") {
    state.answers.zeike = [state.answers.zeike[0], input.value, "", [], []];
  } else if (stage === "zeike" && key === "2") {
    state.answers.zeike[3] = [];
  }
  input.closest(".palace, .ke-card, .zeike-card, .chuan-card")
    ?.classList.remove("correct", "wrong", "missing", "revealed");
  if (stage === "zeike") renderZeike();
  updateProgress();
}

function markCells(result, reveal) {
  for (const cell of result.cells) {
    let element;
    if (result.stage === "tianpan" || result.stage === "tianjiang") {
      element = $(`.palace[data-di="${cell.key}"]`);
    } else if (result.stage === "sike") {
      element = $(`.ke-card[data-key="${cell.key}"]`);
    } else if (result.stage === "zeike") {
      element = $(`.zeike-card[data-key="${cell.key}"]`);
    } else if (result.stage === "chuan") {
      element = $(`.chuan-card[data-key="${cell.key}"]`);
    }
    if (element) {
      element.classList.remove("correct", "wrong", "missing", "revealed");
      if (cell.correct) element.classList.add("correct");
      else if (!cell.filled && !reveal) element.classList.add("missing");
      else element.classList.add("wrong");
      if (reveal && !cell.correct) {
        element.classList.add("revealed");
        const select = element.querySelector("select");
        if (select) {
          select.value = cell.expected;
        } else if (Array.isArray(cell.expected)) {
          element.querySelectorAll('input[type="checkbox"]').forEach((input) => {
            input.checked = cell.expected.includes(input.value);
          });
        }
      }
    }
  }
  if (result.stage === "keshi") {
    $("#keshi-answer").style.borderColor = result.correct ? "#39845f" : "#b94d43";
    if (reveal && !result.correct) $("#keshi-answer").value = result.cells[0].expected;
  }
}

async function check(reveal = false) {
  const payload = {
    ...state.currentCase,
    topic: state.topic,
    stage: state.stage,
    answers: currentAnswers(),
    reveal,
    scoring_version: state.session.scoringVersion || state.meta.scoring_version,
  };
  try {
    const result = await request("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    markCells(result, reveal);
    const hasActualError = result.wrong_count > 0;
    if (state.session.active && (reveal || hasActualError)) {
      state.session.clean = false;
      state.session.mistakes.push({
        stage: state.stage,
        answers: structuredClone(currentAnswers()),
        reveal,
      });
    }
    if (result.correct) state.session.passed.add(state.stage);
    if (!reveal && (result.complete || hasActualError)) {
      state.attempts += 1;
      if (result.correct) state.correct += 1;
      $("#attempt-count").textContent = state.attempts;
      $("#correct-count").textContent = state.correct;
    }
    if (result.correct) {
      if (state.reviewTask && state.stage === state.currentCase.review_stage
          && state.session.active && !state.session.complete) {
        state.session.complete = true;
        if (state.session.clean) state.session.score += 1;
        state.session.records.push({
          review_key: state.currentCase.review_key,
          clean: state.session.clean,
          mistakes: structuredClone(state.session.mistakes),
        });
        persistSession();
        renderQuestion();
        syncPrimaryAction();
        if (state.session.index >= state.session.total) {
          await finishSession();
        } else {
          setFeedback("success", "本题完成",
            state.session.clean ? "原题首次复现正确。" : "已完成订正，本题本次不计正确。");
        }
      } else if (state.stage === "tianpan") {
        advanceStage("天地盘正确，请填写四课上神。");
      } else if (state.stage === "sike" && state.topic !== "四课") {
        advanceStage("四课正确，请判断取用、初传，并选择判断依据。");
      } else if (state.stage === "zeike" && ["昴星", "别责", "八专", "伏吟", "返吟", "三传"].includes(state.topic)) {
        advanceStage("初传取法正确，请填写初、中、末三传。");
      } else if (state.stage === "tianjiang" && state.topic === "十二天将与贵人"
                 && state.session.active && state.session.passed.has("tianpan")
                 && !state.session.complete) {
        state.session.complete = true;
        if (state.session.clean) state.session.score += 1;
        state.session.records.push({
          day: state.currentCase.day,
          shi: state.currentCase.shi,
          jiang: state.currentCase.jiang,
          daynight: state.currentCase.daynight,
          clean: state.session.clean,
          mistakes: state.session.mistakes,
        });
        persistSession();
        renderQuestion();
        syncPrimaryAction();
        if (state.session.index >= state.session.total) {
          await finishSession();
        } else {
          setFeedback("success", "本题完成",
            state.session.clean
              ? "天地盘与十二天将均首次检查正确。"
              : "已完成订正，本题不计首次正确。");
        }
      } else if (((state.stage === "sike" && state.topic === "四课")
                  || (state.stage === "zeike" && state.topic !== "四课"
                      && !["昴星", "别责", "八专", "伏吟", "返吟"].includes(state.topic))
                  || (state.stage === "chuan" && ["昴星", "别责", "八专", "伏吟", "返吟", "三传"].includes(state.topic)))
                 && state.session.active && state.session.passed.has("tianpan")
                 && state.session.passed.has("sike") && !state.session.complete) {
        state.session.complete = true;
        if (state.session.clean) state.session.score += 1;
        state.session.records.push({
          day: state.currentCase.day,
          shi: state.currentCase.shi,
          jiang: state.currentCase.jiang,
          daynight: state.currentCase.daynight,
          clean: state.session.clean,
          mistakes: state.session.mistakes,
        });
        const remediationDone = state.session.mode === "remediation" &&
          state.session.records.length >= 3 &&
          state.session.records.slice(-2).every((record) => record.clean);
        if (remediationDone) state.session.total = state.session.index;
        persistSession();
        renderQuestion();
        syncPrimaryAction();
        if (state.session.index >= state.session.total) {
          await finishSession();
        } else {
          setFeedback("success", "本题完成",
            state.session.clean
              ? `${state.topic}专项各阶段均首次检查正确。`
              : "已完成订正，本题不计首次正确。");
        }
      } else if ((state.stage === "sike" && state.topic === "四课")
                 || (state.stage === "zeike" && state.topic !== "四课"
                     && !["昴星", "别责", "八专", "伏吟", "返吟"].includes(state.topic))
                 || (state.stage === "chuan" && ["昴星", "别责", "八专", "伏吟", "返吟", "三传"].includes(state.topic))) {
        setFeedback("success", "本阶段正确", `${result.total} 项全部吻合。`);
      } else if (state.stage !== "tianjiang") {
        advanceStage(`${STAGE_COPY[state.stage][1]}已通过。`);
      } else {
        setFeedback("success", "本阶段正确", `${result.total} 项全部吻合。可以进入下一阶段。`);
      }
    } else if (!result.complete && !reveal) {
      const detail = result.wrong_count
        ? `还有 ${result.missing_count} 项未填；另有 ${result.wrong_count} 项已填但不正确。`
        : `还有 ${result.missing_count} 项未选择；补齐后再检查，本次不计错。`;
      setFeedback(result.wrong_count ? "error" : "idle", "尚未填完", detail);
    } else if (reveal) {
      setFeedback("error", "已显示标准位置", "红色格为原答案不同处；重新填写后可再次检查。");
    } else {
      setFeedback("error", "存在错误", `${result.correct_count} / ${result.total} 项正确；红色位置需要重查。`);
    }
  } catch (error) {
    setFeedback("error", "无法检查", error.message);
  }
}

async function startSession() {
  const total = sessionTotal(state.topic);
  state.session = {
    id: window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
    active: true, index: 1, total, score: 0,
    clean: true, complete: false, passed: new Set(), records: [],
    mistakes: [], topic: state.topic, resultMessage: "",
    mode: state.reviewTask ? "review" : (state.remediationTask ? "remediation" : "formal"),
    taskId: state.remediationTask?.task_id || "",
    scoringVersion: state.reviewTask?.scoring_version ||
      state.remediationTask?.scoring_version || state.meta.scoring_version,
  };
  await loadCase(true);
  persistSession();
}

async function finishSession() {
  const passed = state.session.score >= passingScore(state.session.total);
  persistSession();
  setFeedback("idle", `本轮 ${state.session.score} / ${state.session.total}`, "正在保存成绩…");
  try {
    const remediation = state.session.mode === "remediation";
    const review = state.session.mode === "review";
    const result = await request(
      review ? "/api/review/result" :
        (remediation ? "/api/remediation/result" : "/api/result"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: state.session.id,
        score: state.session.score,
        total: state.session.total,
        records: state.session.records,
        topic: state.session.topic,
        task_id: state.session.taskId,
        scoring_version: state.session.scoringVersion,
      }),
    });
    state.session.resultMessage = review
      ? result.message
      : remediation
      ? `补强任务 ${result.task_id}：${result.score}/${result.total}，不计正式成绩。`
      : result.message;
    state.session.active = false;
    state.session.complete = false;
    localStorage.removeItem(SESSION_KEY);
    renderQuestion();
    const successful = review ? result.right === result.n :
      (remediation ? result.mastered : passed);
    setFeedback(successful ? "success" : "error",
      `${review ? "复现" : (remediation ? "补强" : "本轮")} ${state.session.score} / ${state.session.total}`,
      remediation && !result.mastered
        ? "已完成任务上限，但尚未形成连续两题正确；结果已单独保存。"
        : result.focused
        ? "成绩已保存，TRAE 已置前；请在当前对话发送任意消息以继续。"
        : "成绩已保存；请返回当前对话发送任意消息以继续。");
  } catch (error) {
    state.session.resultMessage =
      `训练台结果：${state.session.topic}专项 ${state.session.score}/${state.session.total}。请继续当前教学流程。`;
    state.session.active = false;
    state.session.complete = false;
    renderQuestion();
    setFeedback("error", "结果回传失败", `${error.message}；请点击“复制结果”后返回对话粘贴。`);
  }
}

async function nextQuestion() {
  if (!state.session.complete || state.session.index >= state.session.total) return;
  state.session.index += 1;
  await loadCase(true);
  persistSession();
}

async function copyResult() {
  if (!state.session.resultMessage) return;
  await navigator.clipboard.writeText(state.session.resultMessage);
  setFeedback("success", "结果已复制", "返回对话粘贴即可。");
}

function resetCurrent() {
  if (state.stage === "zeike") state.answers.zeike = ["", "", "", [], []];
  else if (Array.isArray(state.answers[state.stage])) state.answers[state.stage].fill("");
  else if (typeof state.answers[state.stage] === "object") {
    Object.keys(state.answers[state.stage]).forEach((key) => state.answers[state.stage][key] = "");
  } else state.answers[state.stage] = "";
  render();
}

async function init() {
  state.meta = await request("/api/meta");
  const pageParams = new URLSearchParams(window.location.search);
  const explicitTopic = pageParams.has("topic") && TOPICS.includes(pageParams.get("topic"));
  if (pageParams.get("review") === "due") {
    state.reviewTask = await request("/api/review/task");
    if (!state.reviewTask.total) throw new Error("当前没有到期错题");
    state.topic = state.reviewTask.cases[0].review_topic;
  }
  if (pageParams.has("task") && !explicitTopic) {
    state.remediationTask = await request(
      `/api/remediation/task?id=${encodeURIComponent(pageParams.get("task"))}`,
    );
    state.topic = state.remediationTask.topic;
  }
  const targeted = pageParams.has("day") && pageParams.has("shi") && pageParams.has("jiang");
  const restored = (targeted || state.remediationTask || explicitTopic)
    ? false : restoreSession();
  if (explicitTopic) localStorage.removeItem(SESSION_KEY);
  if (!restored) state.topic = state.meta.recommended_topic || "四课";
  if (state.remediationTask) state.topic = state.remediationTask.topic;
  if (state.reviewTask) state.topic = state.reviewTask.cases[0].review_topic;
  if (explicitTopic) {
    state.topic = pageParams.get("topic");
  }
  $("#topic-select").value = state.topic;
  fillSelect($("#day-select"), state.meta.days, "戊戌");
  fillSelect($("#shi-select"), state.meta.zhi, "卯");
  fillSelect($("#jiang-select"), state.meta.zhi, "未");
  $("#keshi-answer").innerHTML = options(state.meta.keshi, "选择课式");
  clearAnswers();
  const initialParams = new URLSearchParams({
    daynight: pageParams.get("daynight") || "昼",
    topic: state.topic,
  });
  if (!state.remediationTask && (targeted || state.topic === "四课")) {
    initialParams.set("day", pageParams.get("day") || "戊戌");
    initialParams.set("shi", pageParams.get("shi") || "卯");
    initialParams.set("jiang", pageParams.get("jiang") || "未");
  } else {
    initialParams.set("random", "1");
  }
  state.currentCase = state.reviewTask?.cases[0] || state.remediationTask?.cases[0] ||
    await request(`/api/case?${initialParams}`);
  if (state.reviewTask) {
    if (state.currentCase.review_stage !== "tianpan") {
      state.answers.tianpan = {...state.currentCase.tianpan_answers};
    }
    if (state.currentCase.review_stage !== "sike") {
      state.answers.sike = [...state.currentCase.sike_answers];
    }
    state.stage = state.currentCase.review_stage;
  }
  $("#day-select").value = state.currentCase.day;
  $("#shi-select").value = state.currentCase.shi;
  $("#jiang-select").value = state.currentCase.jiang;
  const currentDaynight = $(`input[name="daynight"][value="${state.currentCase.daynight}"]`);
  if (currentDaynight) currentDaynight.checked = true;
  $("#topic-select").value = state.topic;
  if (restored && state.session.records.length < state.session.total) {
    await loadCase(true);
    setFeedback("idle", "已恢复上次训练", `从第 ${state.session.index} / ${state.session.total} 题继续。`);
  } else if (restored) {
    render();
    await finishSession();
  }

  document.addEventListener("change", onInput);
  $(".case-controls").addEventListener("change", (event) => {
    if (state.remediationTask) return;
    if (event.target.id === "topic-select") {
      state.topic = event.target.value;
      loadCase(state.topic !== "四课");
    } else if (!event.target.matches("[data-stage]")) {
      loadCase(false);
    }
  });
  $$(".stage-tab").forEach((button) => button.addEventListener("click", () => {
    if (!unlockedStages().has(button.dataset.stage)) return;
    state.stage = button.dataset.stage;
    render();
  }));
  $("#random-button").addEventListener("click", () => loadCase(true));
  $("#session-button").addEventListener("click", startSession);
  $("#next-button").addEventListener("click", nextQuestion);
  $("#copy-result-button").addEventListener("click", copyResult);
  $("#reset-button").addEventListener("click", resetCurrent);
  $("#check-button").addEventListener("click", () => {
    if ($("#check-button").dataset.action === "next") nextQuestion();
    else check(false);
  });
  $("#reveal-button").addEventListener("click", () => check(true));
  render();
}

init().catch((error) => setFeedback("error", "启动失败", error.message));
