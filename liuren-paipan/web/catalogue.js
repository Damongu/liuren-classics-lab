"use strict";
const $=id=>document.getElementById(id);
// Render a small, safe Markdown subset through DOM nodes; no source HTML executes.
function renderReading(target,raw){
  target.replaceChildren();raw=raw.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/,'');
  const append=(tag,text)=>{const node=document.createElement(tag);for(const [n,part] of text.split(/`([^`]+)`/).entries()){if(n%2){const code=document.createElement('code');code.textContent=part;node.append(code);}else node.append(document.createTextNode(part));}target.append(node);};
  let paragraph=[],quotes=[];
  const flush=()=>{if(paragraph.length){append('p',paragraph.join('\n'));paragraph=[];}if(quotes.length){append('blockquote',quotes.join('\n'));quotes=[];}};
  for(const line of raw.split(/\r?\n/)){const heading=/^(#{1,3})\s+(.+)$/.exec(line);if(heading){flush();append(heading[1].length===1?'h2':'h3',heading[2]);}else if(line.startsWith('> ')){if(paragraph.length)flush();quotes.push(line.slice(2));}else if(!line.trim()){flush();}else{if(quotes.length)flush();paragraph.push(line);}}
  flush();
}
fetch('/api/v3/catalogue').then(async response=>{if(!response.ok)throw new Error('目录读取失败');return response.json();}).then(data=>{
  for(const item of data.books){const option=document.createElement('option');option.value=item.name;option.textContent=item.name;$('book').append(option);}
  for(const item of data.cards){const option=document.createElement('option');option.value=item.name;option.textContent=item.name;$('card').append(option);}
  const showBook=()=>{const item=data.books.find(x=>x.name===$('book').value);renderReading($('profile'),item.text);$('command').textContent=item.command;$('source-count').textContent=`可检索 ${item.source_count} 个条目或片段；引用前查看层次和待核标记。`;};
  const showCard=()=>{renderReading($('card-text'),data.cards.find(x=>x.name===$('card').value).text);};
  $('book').onchange=showBook;$('card').onchange=showCard;showBook();showCard();
  const labels={passed:'已通过',blocked:'受阻',failed:'有失败项',incomplete:'未完成',not_run:'未运行'};
  const v=data.verification;$('verification').textContent=`工程检查：${labels[v.engineering]||v.engineering}；模型检查：${labels[v.model]||v.model}${v.model_reason==='credentials_not_configured'?'（Pi 尚未配置 DeepSeek 凭据）':''}。`;
  $('copy-command').onclick=async()=>{try{await navigator.clipboard.writeText($('command').textContent);$('error').textContent='已复制';}catch{$('error').textContent='复制不可用，请选中命令复制。';}};
}).catch(error=>{$('error').textContent=error.message;});
