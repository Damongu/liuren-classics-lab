const ZHI = [..."子丑寅卯辰巳午未申酉戌亥"];
const THREE_METHODS_TOPIC = "贼克＋比用＋涉害";
const TOPICS = ["四课", "贼克", "比用", "贼克＋比用", "涉害", THREE_METHODS_TOPIC];
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
  topic: "贼克",
  stage: "tianpan",
  answers: {
    tianpan: {}, sike: ["", "", "", ""], zeike: ["", "", []],
    keshi: "", chuan: ["", "", ""], tianjiang: {},
  },
  attempts: 0,
  correct: 0,
  session: {
    id: "", active: false, index: 0, total: 12, score: 0,
    clean: true, complete: false, passed: new Set(), records: [],
    mistakes: [], resultMessage: "",
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
  }));
}

function restoreSession() {
  try {
    const saved = JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
    if (!saved || typeof saved.id !== "string" || saved.total !== 12 ||
        !TOPICS.includes(saved.topic) ||
        !Array.isArray(saved.records) || saved.records.length > saved.total ||
        !Number.isInteger(saved.score) || saved.score < 0 || saved.score > saved.records.length) {
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

function options(values, placeholder = "请选择") {
  return `<option value="">${placeholder}</option>` +
    values.map((value) => `<option value="${value}">${value}</option>`).join("");
}

function fillSelect(select, values, selected) {
  select.innerHTML = values.map((value) =>
    `<option value="${value}" ${value === selected ? "selected" : ""}>${value}</option>`).join("");
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
    zeike: ["", "", []],
    keshi: "",
    chuan: ["", "", ""],
    tianjiang: Object.fromEntries(ZHI.map((z) => [z, ""])),
  };
}

async function loadCase(random = false) {
  state.currentCase = await request(`/api/case?${caseQuery(random)}`);
  if (random) {
    $("#day-select").value = state.currentCase.day;
    $("#shi-select").value = state.currentCase.shi;
    $("#jiang-select").value = state.currentCase.jiang;
  }
  clearAnswers();
  state.session.clean = true;
  state.session.complete = false;
  state.session.passed = new Set();
  state.session.mistakes = [];
  state.stage = "tianpan";
  render();
}

function renderQuestion() {
  const c = state.currentCase;
  $("#question-text").textContent =
    state.topic !== "四课"
      ? `${c.day}日，${c.shi}时，${c.jiang}将：排天地盘、立四课，判断取用、初传及依据。`
      : `${c.day}日，${c.shi}时，${c.jiang}将：先排天地盘，再立四课。`;
  if (state.session.active) {
    $("#question-index").textContent = `第 ${state.session.index} / ${state.session.total} 题`;
    $("#question-score").textContent = `${state.session.score} 题正确`;
  } else {
    $("#question-index").textContent = "练习模式";
    $("#question-score").textContent = "0 / 0";
  }
  $("#session-button").classList.toggle("hidden", state.session.active);
  $("#next-button").classList.add("hidden");
  $("#copy-result-button").classList.toggle("hidden", !state.session.resultMessage);
  $$("#topic-select, #day-select, #shi-select, #jiang-select, input[name='daynight'], #random-button")
    .forEach((control) => { control.disabled = state.session.active; });
}

function unlockedStages() {
  return new Set(state.topic !== "四课"
    ? ["tianpan", "sike", "zeike"]
    : ["tianpan", "sike"]);
}

function palaceInput(di) {
  const isJiang = state.stage === "tianjiang";
  const stage = isJiang ? "tianjiang" : "tianpan";
  const values = isJiang ? state.meta.tianjiang : state.meta.zhi;
  const value = state.answers[stage][di] || "";
  const disabled = !["tianpan", "tianjiang"].includes(state.stage);
  return `<select aria-label="地盘${di}宫的${isJiang ? "天将" : "天盘支"}"
    data-stage="${stage}" data-key="${di}" class="${isJiang ? "jiang-input" : ""}" ${disabled ? "disabled" : ""}>
    ${options(values, isJiang ? "天将" : "天盘")}</select>
    <span class="earth-label">${di}</span>`;
}

function renderPlate() {
  $$(".palace").forEach((cell) => {
    const di = cell.dataset.di;
    cell.className = "palace";
    cell.innerHTML = palaceInput(di);
    const input = cell.querySelector("select");
    const sourceStage = input.dataset.stage;
    input.value = state.answers[sourceStage][di] || "";
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

function renderZeike() {
  const names = ["一课", "二课", "三课", "四课"];
  const lows = [
    state.currentCase.gan,
    state.answers.sike[0],
    state.currentCase.zhi,
    state.answers.sike[2],
  ];
  $("#zeike-sike-grid").innerHTML = names.map((name, index) =>
    `<article class="sike-reference-card">
      <strong>${name}</strong>
      <span class="upper"><small>上</small><b>${state.answers.sike[index]}</b></span>
      <span class="lower"><small>下</small><b>${lows[index]}</b></span>
    </article>`).reverse().join("");
  const keshiNames = state.topic === "贼克" ? ["元首", "重审"]
    : (state.topic === "比用" ? ["知一"]
      : (state.topic === "涉害" ? ["涉害"] : ["元首", "重审", "知一"]));
  if (state.topic === THREE_METHODS_TOPIC) keshiNames.push("涉害");
  $("#selection-title").textContent = state.topic === "涉害"
    ? "涉归本家计重并定初传"
    : "判断取用并取初传";
  $("#zeike-keshi").closest(".zeike-card").classList.toggle("hidden", state.topic === "涉害");
  $("#zeike-keshi").innerHTML = options(keshiNames, "课名");
  $("#zeike-chu").innerHTML = options(state.meta.zhi, "初传");
  const selectedReasons = new Set(state.answers.zeike[2] || []);
  const reasonOptions = [
    "有下贼取下贼", "无下贼取上克", "阳日取阳神", "阴日取阴神",
  ];
  if (state.topic === "涉害" || state.topic === THREE_METHODS_TOPIC) reasonOptions.push(
    "俱比或俱不比入涉害",
    "涉归本家逐位计重",
    "取涉害重数最多者",
    "同重先比孟仲季",
    "同级复等依刚柔取先见",
  );
  $("#zeike-reason").innerHTML = `<legend>判断依据（可多选）</legend>` +
    reasonOptions.map((reason) => `<label><input type="checkbox" data-stage="zeike"
    data-key="2" value="${reason}" ${selectedReasons.has(reason) ? "checked" : ""}>${reason}</label>`).join("");
  $("#zeike-keshi").value = state.answers.zeike[0] || "";
  $("#zeike-chu").value = state.answers.zeike[1] || "";
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
  if (state.stage === "zeike" && state.topic === "涉害") {
    values = [state.answers.zeike[1], state.answers.zeike[2]];
    total = 2;
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
  const next = STAGE_ORDER[STAGE_ORDER.indexOf(state.stage) + 1];
  if (!next || !unlockedStages().has(next)) return false;
  state.stage = next;
  render();
  setFeedback("success", "已进入下一阶段", detail);
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
  if (stage === "zeike" && key === "2" && input.type === "checkbox") {
    const selected = new Set(state.answers.zeike[2] || []);
    if (input.checked) selected.add(input.value);
    else selected.delete(input.value);
    state.answers.zeike[2] = [...selected];
  } else if (Array.isArray(state.answers[stage])) state.answers[stage][Number(key)] = input.value;
  else if (typeof state.answers[stage] === "object") state.answers[stage][key] = input.value;
  else state.answers[stage] = input.value;
  input.closest(".palace, .ke-card, .zeike-card, .chuan-card")
    ?.classList.remove("correct", "wrong", "missing", "revealed");
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
      if (state.stage === "tianpan") {
        advanceStage("天地盘正确，请填写四课上神。");
      } else if (state.stage === "sike" && state.topic !== "四课") {
        advanceStage("四课正确，请判断取用、初传，并选择判断依据。");
      } else if (((state.stage === "sike" && state.topic === "四课")
                  || (state.stage === "zeike" && state.topic !== "四课"))
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
                 || (state.stage === "zeike" && state.topic !== "四课")) {
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
  state.session = {
    id: window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
    active: true, index: 1, total: 12, score: 0,
    clean: true, complete: false, passed: new Set(), records: [],
    mistakes: [], topic: state.topic, resultMessage: "",
  };
  await loadCase(true);
  persistSession();
}

async function finishSession() {
  const passed = state.session.score >= 11;
  persistSession();
  setFeedback("idle", `本轮 ${state.session.score} / ${state.session.total}`, "正在保存成绩…");
  try {
    const result = await request("/api/result", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: state.session.id,
        score: state.session.score,
        total: state.session.total,
        records: state.session.records,
        topic: state.session.topic,
      }),
    });
    state.session.resultMessage = result.message;
    state.session.active = false;
    state.session.complete = false;
    localStorage.removeItem(SESSION_KEY);
    renderQuestion();
    setFeedback(passed ? "success" : "error", `本轮 ${state.session.score} / ${state.session.total}`,
      result.focused
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
  if (state.stage === "zeike") state.answers.zeike = ["", "", []];
  else if (Array.isArray(state.answers[state.stage])) state.answers[state.stage].fill("");
  else if (typeof state.answers[state.stage] === "object") {
    Object.keys(state.answers[state.stage]).forEach((key) => state.answers[state.stage][key] = "");
  } else state.answers[state.stage] = "";
  render();
}

async function init() {
  state.meta = await request("/api/meta");
  const restored = restoreSession();
  if (!restored) state.topic = state.meta.recommended_topic || "四课";
  $("#topic-select").value = state.topic;
  fillSelect($("#day-select"), state.meta.days, "戊戌");
  fillSelect($("#shi-select"), state.meta.zhi, "卯");
  fillSelect($("#jiang-select"), state.meta.zhi, "未");
  $("#keshi-answer").innerHTML = options(state.meta.keshi, "选择课式");
  clearAnswers();
  const initialParams = new URLSearchParams({
    daynight: "昼",
    topic: state.topic,
  });
  if (state.topic === "四课") {
    initialParams.set("day", "戊戌");
    initialParams.set("shi", "卯");
    initialParams.set("jiang", "未");
  } else {
    initialParams.set("random", "1");
  }
  state.currentCase = await request(`/api/case?${initialParams}`);
  $("#day-select").value = state.currentCase.day;
  $("#shi-select").value = state.currentCase.shi;
  $("#jiang-select").value = state.currentCase.jiang;
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
