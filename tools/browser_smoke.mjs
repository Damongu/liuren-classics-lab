import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {resolve} from 'node:path';
import {mkdir} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import assert from 'node:assert/strict';

const playwrightDir = process.argv[2], python = process.argv[3];
if (!playwrightDir || !python) throw new Error('Pass local Playwright and liuren Python paths');
const require = createRequire(resolve(playwrightDir,'package.json'));
const {chromium} = require(playwrightDir);
const root = resolve(import.meta.dirname,'..');
const child = spawn(python,[resolve(root,'tools/serve_test.py')],{cwd:root,windowsHide:true,
  env:{...process.env,PYTHONUTF8:'1'},stdio:['ignore','pipe','pipe']});
let browser;
try {
  const url = await new Promise((accept,reject)=>{
    let output='';const timer=setTimeout(()=>reject(new Error('QA server startup timeout')),20000);
    child.stdout.on('data',chunk=>{output+=chunk;const match=/QA_URL=(http:\/\/127\.0\.0\.1:\d+)/.exec(output);if(match){clearTimeout(timer);accept(match[1]);}});
    child.on('error',reject);child.on('exit',code=>{clearTimeout(timer);reject(new Error('QA server exited '+code));});
  });
  const browserPath = process.env.LIUREN_BROWSER || [
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
  ].find(existsSync);
  browser = await chromium.launch({headless:true,...(browserPath?{executablePath:browserPath}:{})});
  const page = await browser.newPage({viewport:{width:1280,height:900}});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto(url+'/catalogue.html');await page.locator('#book option').last().waitFor({state:'attached'});
  assert.equal(await page.locator('#book option').count(),12);
  assert.equal(await page.locator('#card option').count(),8);
  await page.locator('#book').selectOption('阿甲');
  assert((await page.locator('#profile').innerText()).includes('清人按语'));
  assert((await page.locator('#command').innerText()).includes('-Book 阿甲'));
  await page.locator('#card').selectOption('行年');
  assert((await page.locator('#card-text').innerText()).includes('十一岁壬午'));
  const out=resolve(root,'artifacts/qa');await mkdir(out,{recursive:true});
  await page.screenshot({path:resolve(out,'catalogue-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:resolve(out,'catalogue-mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.setViewportSize({width:1280,height:900});
  await page.goto(url+'/curriculum.html');await page.locator('#levels .level').last().waitFor();
  assert.equal(await page.locator('#levels .level').count(),7);
  await page.locator('#start').click();await page.locator('#exercise').waitFor({state:'visible'});
  assert.equal(await page.locator('#fields [data-key]').count(),5);
  const sid = await page.evaluate(()=>localStorage.getItem('liuren-v3-session'));
  const publicState = await (await page.request.get(url+'/api/v3/session?id='+sid)).json();
  assert(!('answers' in publicState.questions[0]));
  for(const input of await page.locator('#fields [data-key]').all()) await input.selectOption({index:1});
  await page.locator('#submit').click();await page.locator('#feedback h3').waitFor();
  assert(await page.locator('#submit').isDisabled());
  const resultText=await page.locator('#feedback').innerText();assert(resultText.length>20);
  // Simulate refresh: resume authoritative server session, do not recreate scores.
  await page.reload();await page.locator('#levels .level').last().waitFor();
  await page.locator('#recent').selectOption(sid);await page.locator('#resume').click();
  await page.locator('#exercise').waitFor({state:'visible'});
  assert((await page.locator('#progress').innerText()).includes('第2/12题'));
  await page.screenshot({path:resolve(out,'curriculum-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:resolve(out,'curriculum-mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({browser:'passed',views:['desktop','mobile'],profiles:12,cards:8,answerPrivacy:'passed',resume:'passed',pageErrors:errors}));
} finally {
  if(browser) await browser.close();
  child.kill();
}
