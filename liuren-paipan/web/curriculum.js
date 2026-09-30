"use strict";
const $ = (id) => document.getElementById(id);
let session = null, current = 0;
const rubricKeys = ["原文义与术语", "判断依据与反例", "证据层次与边界"];

async function api(path, body) {
  const response = await fetch(path, body ? {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)} : {});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "服务请求失败");
  return data;
}
function notice(text, error=false) { $("status").textContent=text; $("status").className=error?"error":""; }
function element(tag, text, className="") { const node=document.createElement(tag); node.textContent=text; node.className=className; return node; }
function saveSession() { try { localStorage.setItem("liuren-v3-session",session.id); } catch (_) {} }
async function refresh() {
  const data=await api("/api/v3/status"); $("levels").replaceChildren();
  const selected=$("level").value; $("level").replaceChildren();
  for (const level of data.levels) {
    const card=element("div","","level");card.append(element("strong",`${level.id===0?"体检":"L"+level.id} · ${level.name}`));
    card.append(element("small",level.passed?"已通过":level.ready?"练习达标 · 待白话复述":"待练习"));$("levels").append(card);
    const option=element("option",`${level.id===0?"体检":"L"+level.id} ${level.name}`);option.value=level.id;$("level").append(option);
  }
  $("level").value=selected||"0";
  $("recent").replaceChildren(element("option","选择会话"));
  for (const item of data.recent_sessions.reverse()) {const option=element("option",`${item.title} · 已答${item.done}题`);option.value=item.id;$("recent").append(option);}
  notice(`到期复现 ${data.due} 条${data.exam_passed?" · 结课测已通过":""}`);
}
function question() { return session.questions[current]; }
function citationRow(value={}) {
  const row=element("div","","citation");
  for(const [key,label] of [["anchor_id","出处锚点"],["quote","原文引句（原样摘录）"],["claim","支持哪一步判断"]]) {
    const wrapper=element("label",label);const input=document.createElement(key==="anchor_id"?"input":"textarea");input.dataset.key=key;input.value=value[key]||"";wrapper.append(input);row.append(wrapper);
  }
  const remove=element("button","移除依据","secondary");remove.type="button";remove.onclick=()=>row.remove();row.append(remove);$("citations").append(row);
}
function render() {
  $("level").value=String(session.level);
  $("question-nav").replaceChildren();
  session.questions.forEach((q,i)=>{const r=session.results[q.id];const option=element("option",`第${i+1}题 · ${r?r.needs_human?"待人工验收":"已核验":"未答"}`);option.value=i;$("question-nav").append(option);});
  $("question-nav").value=String(current);
  const q=question();$("exercise").hidden=false;$("progress").textContent=`${session.title} · 第${current+1}/${session.questions.length}题`;
  $("prompt").textContent=q.prompt;$("fields").replaceChildren();
  const sikeGroup=element("div","","sike-group");
  for(const f of q.fields) {
    const label=element("label",f.label);const input=document.createElement(f.options.length?"select":"input");input.dataset.key=f.key;input.required=true;
    if(f.options.length){const placeholder=element("option","请选择");placeholder.value="";input.append(placeholder);for(const value of f.options){const option=element("option",value);option.value=value;input.append(option);}}
    label.append(input);if(/^ke[1-4]$/.test(f.key))sikeGroup.append(label);else $("fields").append(label);
  }
  if(sikeGroup.childElementCount)$("fields").append(sikeGroup);
  $("open-fields").hidden=!q.open;for(const id of ["prose","reasoning","boundary","human-note"])$(id).value="";
  $("citations").replaceChildren();$("source-results").replaceChildren();if(q.open)for(let i=0;i<3;i++)citationRow();
  $("feedback").replaceChildren();$("human").hidden=true;$("next").hidden=true;$("submit").disabled=false;
  $("answer-form").hidden=false;
  if(session.results[q.id]) showResult(session.results[q.id]);
}
function showResult(result) {
  $("submit").disabled=true;$("feedback").replaceChildren();$("feedback").className="feedback";
  $("feedback").append(element("h3",result.label),element("pre",JSON.stringify(result.expected,null,2)));
  $("feedback").append(element("p","你的首答"),element("pre",JSON.stringify(result.answer,null,2)));
  $("feedback").append(element("p",(result.reason||[]).join("；")));
  const p=result.plate;
  if(p){const sike=p["四课"]||[];if(sike.length){const table=document.createElement("table");const body=document.createElement("tbody");for(const [key,name] of [["课","课序"],["上","上神"],["下","下神"]]){const row=document.createElement("tr");row.append(element("th",name));for(const ke of [...sike].reverse())row.append(element("td",String(ke[key])));body.append(row);}table.append(body);$("feedback").append(table);}}
  if(result.comparison){$("feedback").append(element("p",result.comparison_warning),element("pre",result.comparison.text));}
  $("human").hidden=!result.needs_human;
  if(result.needs_human){$("rubric").replaceChildren();for(const key of rubricKeys){const label=element("label",key);const checkbox=document.createElement("input");checkbox.type="checkbox";checkbox.dataset.key=key;label.prepend(checkbox);$("rubric").append(label);}}
  $("next").hidden=current>=session.questions.length-1;
  $("question-nav").options[current].textContent=`第${current+1}题 · ${result.needs_human?"待人工验收":"已核验"}`;
}
async function begin(mode="practice") {
  session=await api("/api/v3/start",{level:mode==="exam"?6:Number($("level").value),mode});current=0;saveSession();render();await refresh();
}
$("answer-form").onsubmit=async(event)=>{
  event.preventDefault();$("submit").disabled=true;
  try{
    const answer={};for(const input of $("fields").querySelectorAll("[data-key]"))answer[input.dataset.key]=input.value;
    if(question().open){for(const key of ["prose","reasoning","boundary"])answer[key]=$(key).value;answer.citations=[...$("citations").children].map(row=>Object.fromEntries([...row.querySelectorAll("[data-key]")].map(input=>[input.dataset.key,input.value])));}
    const result=await api("/api/v3/submit",{session_id:session.id,question_id:question().id,answer});session.results[question().id]=result;showResult(result);await refresh();
  }catch(error){notice(error.message,true);$("submit").disabled=false;}
};
$("human-submit").onclick=async()=>{
  const rubric=Object.fromEntries([...$("rubric").querySelectorAll("input")].map(input=>[input.dataset.key,input.checked]));
  const result=await api("/api/v3/human-review",{session_id:session.id,question_id:question().id,rubric,note:$("human-note").value});
  session.results[question().id]=result;showResult(result);await refresh();
};
$("source-search").onclick=async()=>{
  const data=await api("/api/v3/sources?q="+encodeURIComponent($("source-query").value));$("source-results").replaceChildren();
  for(const source of data.sources){const box=element("div","","source-hit");box.append(element("code",source.anchor_id),element("p",`${source.book} · ${source.layer} · ${source.evidence} · ${source.pending?"未核原刻":""}`),element("pre",source.text));const add=element("button","使用这个出处","secondary");add.type="button";add.onclick=()=>{const blank=[...$("citations").querySelectorAll('[data-key="anchor_id"]')].find(input=>!input.value.trim());if(blank)blank.value=source.anchor_id;else citationRow({anchor_id:source.anchor_id});};box.append(add);$("source-results").append(box);}
  if(!data.sources.length)$("source-results").append(element("p","没有匹配原文。可尝试繁体或其他原文关键词。"));
};
$("teachback").onclick=async()=>{await api("/api/v3/teachback",{level:Number($("level").value),note:$("teachback-note").value});await refresh();};
$("start").onclick=()=>begin();$("review").onclick=()=>begin("review");$("exam").onclick=()=>begin("exam");
$("next").onclick=()=>{current++;render();};$("add-citation").onclick=()=>citationRow();
$("resume").onclick=async()=>{if(!$("recent").value)throw new Error("请选择要恢复的会话");session=await api("/api/v3/session?id="+encodeURIComponent($("recent").value));current=session.questions.findIndex(q=>!session.results[q.id]||session.results[q.id].needs_human);if(current<0)current=session.questions.length-1;saveSession();render();};
$("question-nav").onchange=()=>{current=Number($("question-nav").value);render();};
// All async actions surface errors on the page, including fetch and validation failures.
for(const button of document.querySelectorAll("button")){if(button.onclick){const original=button.onclick;button.onclick=async(event)=>{try{await original(event);}catch(error){notice(error.message,true);}};}}
refresh().catch(error=>notice(error.message,true));
