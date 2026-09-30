// Exercise the installed Pi loader and custom tools without making model calls.
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const pkg = process.argv[2];
if (!pkg) throw new Error('Pass the installed pi-coding-agent package directory');
const root = resolve(import.meta.dirname, '..');
const {loadExtensions} = await import(pathToFileURL(resolve(pkg,'dist/core/extensions/loader.js')));
const {parseArgs} = await import(pathToFileURL(resolve(pkg,'dist/cli/args.js')));
const args = parseArgs(['--provider','deepseek','--no-context-files','--extension',resolve(root,'agents/liuren-extension.ts'),
  '--append-system-prompt',resolve(root,'agents/AGENTS.md'),'--append-system-prompt',resolve(root,'agents/凝神子.md')]);
assert.equal(args.diagnostics.filter(d=>d.type==='error').length,0);
assert.equal(args.noContextFiles,true); assert.equal(args.appendSystemPrompt.length,2);
const loaded = await loadExtensions([resolve(root,'agents/liuren-extension.ts')],root);
assert.equal(loaded.errors.length,0,JSON.stringify(loaded.errors));
assert.equal(loaded.extensions.length,1);
const ext = loaded.extensions[0];
const turnHandlers = ext.handlers instanceof Map ? ext.handlers.get('before_agent_start') : ext.handlers?.before_agent_start;
assert(turnHandlers?.length>0,'missing five-turn redline reminder');
const remind = turnHandlers[0];
for(let i=1;i<=5;i++){
  const result = await remind({type:'before_agent_start',prompt:'工程测试'}, {cwd:root});
  if(i===1)assert.equal(result.message.customType,'liuren-classroom-start');
  else if(i<5)assert.equal(result,undefined);else assert.equal(result.message.customType,'liuren-redline-reminder');
}
const tools = ext.tools instanceof Map ? [...ext.tools.values()] : ext.tools;
const names = tools.map(t=>t.definition?.name ?? t.name);
assert(names.includes('liuren_source'));assert(names.includes('liuren_validate_output'));assert(names.includes('liuren_discuss'));
const discussionTool=tools.find(t=>(t.definition?.name??t.name)==='liuren_discuss');
const discussionDef=discussionTool.definition??discussionTool;
process.env.LIUREN_DISCUSSION_CHILD='1';
await assert.rejects(()=>discussionDef.execute('recursive',{topic:'验收',question:'不要调用模型',keywords:[]},undefined,()=>{},{cwd:root}),/递归/);
delete process.env.LIUREN_DISCUSSION_CHILD;
const validationTool=tools.find(t=>(t.definition?.name??t.name)==='liuren_validate_output');
const validationDef=validationTool.definition??validationTool;
await assert.rejects(()=>validationDef.execute('forged-discussion',{explanation:'虚构讨论',evidence_label:'无宋据',
  source_warning:'未核原刻',citations:[],discussion_id:'not-in-this-session'},undefined,()=>{},{cwd:root}),/不属于本会话/);
const sourceTool = tools.find(t=>(t.definition?.name ?? t.name)==='liuren_source');
const def = sourceTool.definition ?? sourceTool;
const result = await def.execute('offline-test',{query:'己身'},undefined,()=>{}, {cwd:root});
const payload = JSON.parse(result.content[0].text);
assert.equal(payload.accepted,true);assert(payload.sources.length>0);
assert(payload.sources.every(s=>s.author==='凝神子'));
const inventory = JSON.parse(await readFile(resolve(root,'docs/content-inventory.json'),'utf8'));
const profiles = Object.keys(inventory.profiles);
for(const name of profiles){
  const parsed = parseArgs(['--provider','deepseek','--no-context-files','--no-extensions','--no-skills','--no-prompt-templates',
    '--extension',resolve(root,'agents/liuren-extension.ts'),'--append-system-prompt',resolve(root,'agents/AGENTS.md'),
    '--append-system-prompt',resolve(root,'agents',name+'.md')]);
  assert.equal(parsed.diagnostics.filter(d=>d.type==='error').length,0);
  process.env.LIUREN_PROFILE = name;
  const pointer = inventory.profiles[name][0];
  const answer = await def.execute('scope-'+name,{anchor:pointer.anchor_id},undefined,()=>{}, {cwd:root});
  const data = JSON.parse(answer.content[0].text);
  assert.equal(data.accepted,true,JSON.stringify(data));
  assert.equal(data.source.author,name);
}
process.env.LIUREN_PROFILE='凝神子';
console.log(JSON.stringify({piArguments:'passed',extensionLoader:'passed',tools:names,sourceBridge:'passed',profilesVerified:profiles.length,fiveTurnReminder:'passed'},null,2));
