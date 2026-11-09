import { decodeAsset } from './asset-loader.js?v=20261109-front-variants-v2';

const status = document.getElementById('downloadStatus');
const groups = document.getElementById('downloadGroups');
const retry = document.getElementById('retryCatalog');
const buttons = [];
let busy = false;
function report(message, error = false){ status.textContent = message; status.classList.toggle('error', error); }
function safeFilename(value){
  return typeof value === 'string' && value.length > 0 && !/[\/\\\x00-\x1f]/.test(value) && value !== '.' && value !== '..';
}
async function download(item){
  if (busy) return;
  busy = true;
  for (const button of buttons) button.disabled = true;
  report(`正在准备「${item.label}」，请稍候…`);
  try {
    const bytes = await decodeAsset(new URL(item.manifest, document.baseURI).href);
    const type = item.filename.endsWith('.png') ? 'image/png' : item.filename.endsWith('.json') ? 'application/json' : 'application/octet-stream';
    const url = URL.createObjectURL(new Blob([bytes], { type }));
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = item.filename;
    document.body.append(anchor); anchor.click(); anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    report(`「${item.label}」已准备好，已请求浏览器保存。`);
  } catch (error) { report(`「${item.label}」未能下载：${error.message}。可再次点击下载。`, true); }
  finally { busy = false; for (const button of buttons) button.disabled = false; }
}
async function loadCatalog(){
  retry.hidden = true;
  report('正在读取资料目录…');
  try {
    const response = await fetch('./download-assets.json?v=20261109-front-variants-v2', { cache:'no-cache' });
    if (!response.ok) throw new Error(`资料目录无法读取（HTTP ${response.status}）`);
    const catalog = await response.json();
    if (!Array.isArray(catalog.groups) || !catalog.groups.length) throw new Error('资料目录为空');
    const fragment = document.createDocumentFragment();
    buttons.length = 0;
    for (const group of catalog.groups){
      if (typeof group.title !== 'string' || !Array.isArray(group.items)) throw new Error('资料目录格式不正确');
      const section = document.createElement('section'), title = document.createElement('h2'), list = document.createElement('ul');
      title.textContent = group.title; list.className = 'download-list'; section.append(title, list);
      for (const item of group.items){
        if (typeof item.label !== 'string' || !safeFilename(item.filename) || typeof item.manifest !== 'string') throw new Error('资料目录包含无效文件信息');
        const manifestURL = new URL(item.manifest, document.baseURI);
        if (manifestURL.origin !== new URL(document.baseURI).origin) throw new Error('资料必须来自当前网站');
        const row = document.createElement('li'), info = document.createElement('div'), label = document.createElement('div'), type = document.createElement('div'), button = document.createElement('button');
        row.className = 'download-item'; info.className = 'file-info'; label.className = 'file-label'; type.className = 'file-type';
        label.textContent = item.label; type.textContent = item.filename.split('.').pop().toUpperCase();
        button.textContent = '下载'; button.setAttribute('aria-label', `下载${item.label}`); button.addEventListener('click', () => download(item));
        info.append(label, type); row.append(info, button); list.append(row); buttons.push(button);
      }
      fragment.append(section);
    }
    groups.replaceChildren(fragment); report('');
  } catch (error) { report(`资料目录未能载入：${error.message}`, true); retry.hidden = false; }
}
retry.addEventListener('click', loadCatalog);
loadCatalog();
