// Transfer only. Decoded files must match the frozen original bytes before use.
const manifestAssets = new Set([
  'smart_cabinet.glb', 'components.json',
  'smart_cabinet_drawer.glb', 'drawer_compartment.json',
  'room_environment.glb', 'room_metadata.json'
]);
const pending = new Map();
let loaderModule;

function pageURL(){ return globalThis.document?.baseURI || globalThis.location?.href || import.meta.url; }
function sameOriginURL(value, base = pageURL()){
  const url = new URL(value, base);
  if (url.origin !== new URL(pageURL()).origin || !['http:', 'https:'].includes(url.protocol)) throw new Error('请从同一网站通过 HTTPS 或本机预览打开资源');
  return url;
}
export function assetManifestURL(value){
  const url = sameOriginURL(value);
  if (!manifestAssets.has(url.pathname.split('/').pop())) return null;
  url.pathname += '.manifest.json';
  return url.href;
}
async function fetchResource(url, label){
  let response;
  try { response = await fetch(url, { cache:'no-cache' }); }
  catch { throw new Error(`${label}无法读取，请检查网络后重试`); }
  if (!response.ok) throw new Error(`${label}无法读取（HTTP ${response.status}），请重试`);
  return response;
}
function validDigest(value){ return typeof value === 'string' && /^[a-f\d]{64}$/i.test(value); }
function validSize(value){ return Number.isSafeInteger(value) && value >= 0; }
async function checkBytes(buffer, expected, label){
  if (buffer.byteLength !== expected.bytes) throw new Error(`${label}长度不符，请重新加载`);
  const hash = await crypto.subtle.digest('SHA-256', buffer);
  const hex = Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join('');
  if (hex !== expected.sha256.toLowerCase()) throw new Error(`${label}校验失败，请重新加载`);
}
async function decode(manifestURL){
  if (!globalThis.crypto?.subtle) throw new Error('此环境无法校验文件，请使用支持安全连接的浏览器，通过 HTTPS 或 localhost 打开');
  let manifest;
  try { manifest = await (await fetchResource(manifestURL, '资源清单')).json(); }
  catch (error) { if (error instanceof SyntaxError) throw new Error('资源清单格式不正确'); throw error; }
  if (!manifest || manifest.schema !== 1 || !['gzip','none'].includes(manifest.compression) || !validDigest(manifest.sha256) || !validSize(manifest.bytes) || !Array.isArray(manifest.parts) || !manifest.parts.length) throw new Error('资源清单格式或版本不受支持');
  if (manifest.compression === 'gzip' && typeof globalThis.DecompressionStream !== 'function') throw new Error('当前浏览器不支持此文件的解压，请更新 Chrome、Edge、Safari 或 Firefox 后重试');
  const parts = [];
  for (const [index, part] of manifest.parts.entries()){
    if (!part || typeof part.url !== 'string' || !validSize(part.bytes) || !validDigest(part.sha256)) throw new Error('资源清单包含无效文件信息');
    const url = sameOriginURL(part.url, manifestURL);
    const label = `资源第 ${index + 1} 部分`;
    const bytes = await (await fetchResource(url.href, label)).arrayBuffer();
    await checkBytes(bytes, part, label);
    parts.push(bytes);
  }
  let decoded;
  try {
    const blob = new Blob(parts);
    decoded = manifest.compression === 'none' ? await blob.arrayBuffer() : await new Response(blob.stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
  } catch { throw new Error('文件无法解压，请重新加载；若仍失败，请更新浏览器'); }
  await checkBytes(decoded, manifest, '完整文件');
  return decoded;
}
export function decodeAsset(value){
  const url = sameOriginURL(value).href;
  if (!pending.has(url)){
    const promise = decode(url).finally(() => pending.delete(url));
    pending.set(url, promise);
  }
  return pending.get(url);
}
export async function loadModel(value){
  const url = sameOriginURL(value);
  const manifest = assetManifestURL(url.href);
  loaderModule ??= import('three/addons/loaders/GLTFLoader.js').catch(error => { loaderModule = null; throw error; });
  const { GLTFLoader } = await loaderModule;
  const loader = new GLTFLoader();
  if (!manifest) return loader.loadAsync(url.href);
  const bytes = await decodeAsset(manifest);
  try { return await loader.parseAsync(bytes, new URL('.', url).href); }
  catch { throw new Error('三维模型无法解析，请重新加载'); }
}
export async function loadJSON(value){
  const url = sameOriginURL(value);
  const manifest = assetManifestURL(url.href);
  try {
    if (!manifest) return await (await fetchResource(url.href, '组件参数')).json();
    const bytes = await decodeAsset(manifest);
    return JSON.parse(new TextDecoder('utf-8', { fatal:true }).decode(bytes));
  } catch (error) {
    if (error instanceof SyntaxError || error instanceof TypeError) throw new Error('组件参数格式不正确，请重新加载');
    throw error;
  }
}
