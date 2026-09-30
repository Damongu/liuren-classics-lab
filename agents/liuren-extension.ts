import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { spawn } from "node:child_process";
import { resolve, relative, sep } from "node:path";

async function bridge(mode: string, payload: unknown, cwd: string, signal?: AbortSignal): Promise<any> {
  const python = process.env.LIUREN_PYTHON;
  if (!python) throw new Error("缺 LIUREN_PYTHON，请用启动六壬.ps1 或 launch_book.py 启动");
  return await new Promise((accept, reject) => {
    const child = spawn(python, [resolve(cwd, "tools/pi_tools.py"), mode], {
      cwd, windowsHide: true, signal, env: {...process.env, PYTHONUTF8:"1"}, stdio:["pipe","pipe","pipe"]
    });
    let stdout = "", stderr = "";
    child.stdout.on("data", (chunk) => stdout += chunk);
    child.stderr.on("data", (chunk) => stderr += chunk);
    child.on("error", reject);
    child.on("close", (code) => {
      if (code) reject(new Error(stderr || `Python exit ${code}`));
      else { try { accept(JSON.parse(stdout)); } catch (error) { reject(error); } }
    });
    child.stdin.end(JSON.stringify(payload));
  });
}

export default function(pi: ExtensionAPI) {
  let turns = 0;
  let discussionsThisTurn = 0;
  const discussions = new Map<string,any>();
  pi.on("session_start",async()=>{turns=0;discussionsThisTurn=0;discussions.clear();});
  pi.on("before_agent_start", async() => {
    turns += 1;
    discussionsThisTurn = 0;
    if(turns===1 && process.env.LIUREN_DISCUSSION_CHILD!=="1")return {message:{customType:"liuren-classroom-start",display:false,
      content:"本课堂已启用liuren_discuss。你保持当前底本主讲身份；遇到关键新规则的适用边界、异说或用户困惑，先解释本节原文，再主动邀请相关书魂补证/质疑和复盘官核阅，把短对话带回当前会话并请用户插话。不要让用户手动切书，不由自己伪装多人发言；无据或工具失败如实说明。"}};
    if (turns % 5 === 0) return {message:{customType:"liuren-redline-reminder",display:false,
      content:"本会话已到第"+turns+"轮。先自检六条红线：按版本分层、四拍顺序、程序判机械题、无据不造宋证、流程变更需批准、共名词注明六壬义。讲解先取liuren_source，再通过liuren_validate_output；保留注家与污染边界，不替用户复述或写虚假掌握度。"}};
  });
  pi.registerTool(defineTool({
    name:"liuren_discuss", label:"课堂讨论",
    description:"主讲遇到异说、跨书证据或理解缺口时自动请最多两位独立书魂补证/质疑，再由复盘官核阅，结果回到当前课堂。无需用户换书。所有发言验原句、不写学生成绩。",
    parameters:Type.Object({topic:Type.String(),question:Type.String(),main_claim:Type.Optional(Type.String()),
      keywords:Type.Array(Type.String()),profiles:Type.Optional(Type.Array(Type.String()))}),
    async execute(_id,params,signal,update,ctx){
      if(process.env.LIUREN_DISCUSSION_CHILD==="1") throw new Error("独立书魂不允许递归开讨论");
      if(discussionsThisTurn>=2)throw new Error("本轮已达到两次短讨论上限，先让用户回应，再继续课堂");
      discussionsThisTurn+=1;
      update?.({content:[{type:"text",text:"正在邀请相关书魂补证、质疑，并请复盘官核阅…"}],details:{phase:"discussion"}});
      const result = await bridge("discuss",{...params,_model:ctx.model?{provider:ctx.model.provider,id:ctx.model.id}:undefined},ctx.cwd,signal);
      if(result.accepted){
        discussions.set(result.discussion_id,result);
        if(discussions.size>6)discussions.delete(discussions.keys().next().value!);
      }
      return {content:[{type:"text",text:JSON.stringify(result)}],details:result,isError:!result.accepted};
    }
  }));
  pi.registerTool(defineTool({
    name: "liuren_source", label: "六壬原文检索",
    description: "从当前书魂范围检索原文和锚点；跨书需要复盘官。保留层次、待核、hash。",
    parameters: Type.Object({query: Type.Optional(Type.String()), anchor: Type.Optional(Type.String())}),
    async execute(_id, params, signal, _update, ctx) {
      const result = await bridge("source", params, ctx.cwd, signal);
      return {content:[{type:"text",text:JSON.stringify(result)}],details:result,isError:!result.accepted};
    }
  }));
  pi.registerTool(defineTool({
    name: "liuren_validate_output", label: "核验六壬讲解",
    description: "输出讲解前核验结构化证据、共名词六壬义、单书魂边界与原文 hash。失败必须修正。",
    parameters: Type.Object({explanation:Type.String(), evidence_label:Type.String(), source_warning:Type.String(),
      citations:Type.Array(Type.Object({anchor_id:Type.String(),quote:Type.String(),claim:Type.String(),speaker:Type.Optional(Type.String())})),
      discussion_id:Type.Optional(Type.String()),
      term_senses:Type.Optional(Type.Record(Type.String(),Type.Any())), digressions:Type.Optional(Type.Array(Type.Any()))}),
    async execute(_id, params, signal, _update, ctx) {
      const payload:any = {...params};
      if(params.discussion_id){
        if(!discussions.has(params.discussion_id))throw new Error("讨论id不属于本会话或已失效，请重新调用liuren_discuss");
        payload._discussion_proof = discussions.get(params.discussion_id);
      }
      const result = await bridge("validate", payload, ctx.cwd, signal);
      return {content:[{type:"text",text:JSON.stringify(result)}],details:result,isError:!result.accepted};
    }
  }));
  pi.on("tool_call", async(event,ctx) => {
    if (event.toolName === "write" || event.toolName === "edit") {
      const input = event.input as {path?:string};
      if (input.path) {
        const corpus = resolve(ctx.cwd,"六壬vault","10-底本");
        const target = resolve(ctx.cwd,input.path);
        const rel = relative(corpus,target);
        if (!rel || (rel !== ".." && !rel.startsWith(".." + sep) && !rel.includes(":"))) {
          return {block:true,reason:"带读禁止改底本。注释请写20/40/50目录，并保持原文hash不变。"};
        }
      }
    }
  });
}
