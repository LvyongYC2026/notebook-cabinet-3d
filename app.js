import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { CabinetDimensions } from './dimensions.js?v=20261108-room-v1';
import { formatLengthCm, lengthTextToCm } from './length-format.js?v=20261108-room-v1';
import { WiringPanel } from './wiring.js?v=20261108-room-v1';
import { CabinetRoom } from './room-scene.js?v=20261108-room-v1';

const $ = id => document.getElementById(id);
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
const bayIds = ['A','B'].flatMap(side=>Array.from({length:9},(_,index)=>`${side}${index+1}`));
const singleDefaultAngle=THREE.MathUtils.degToRad(4.5);
const state = { loaded:false, autoRotate:false, structure:false, glass:true, selection:null, demo:false, mode:'cabinet', sceneMode:'cabinet', roomView:'overview', switching:false, dimensions:false, wiring:false, wiringInspection:false };
function makeRefs(){return {doors:new Map(),trays:new Map(),laptops:new Map(),adapters:new Map(),modules:new Map(),housings:[],statuses:new Map(),components:new Map(),cables:[],usb:new Map(),interiorLights:[]};}
let refs = makeRefs();
const modelContexts=new Map();
let singleAssetPromise=null,stageLights,groundPool,roomEnvironment=null;
let loadErrorAction=()=>location.reload();
const originals = new Map();
const tweens = [];
const emptyBays = new Set(['A3','B2','B6']);
const meshDescriptors = new WeakMap();
const fallbackMetadata = {};
let metadata = {}, metadataDocument = {};
let scene, renderer, camera, controls, model, screenMesh, screenMaterial, demoScreenMaterial,perspectiveCamera=null,topCamera=null;
let selectionMeshes = [], screenTexture, demoTimer = 0, demoIndex = -1;
let viewport = { width:1, height:1 };
let fitBox = new THREE.Box3(new THREE.Vector3(-1.65,0,-.325),new THREE.Vector3(1.65,1.85,.325));
let lastFrame = 0, resized = false, orbitMotion = null;
let renderDiagnosticsLogged=false;
let dimensionLayer=null, wiringPanel=null,lastSceneModeLayout=null;

const icon = {
  doorOpen:'<path d="M4 21V3h12v18M4 3l10 3v15L4 18zM18 7l3 3-3 3m-2-3h5M11 11v2"/>',
  doorClose:'<path d="M5 3h14v18H5zM15 11v2M2 12h8m-3-3 3 3-3 3"/>',
  trayOut:'<path d="M4 5h16v8H4zM4 13l-2 6h20l-2-6M12 5V1m-3 3 3-3 3 3"/>',
  trayIn:'<path d="M4 5h16v8H4zM4 13l-2 6h20l-2-6M12 1v7m-3-3 3 3 3-3"/>'
};

function announce(text){ $('announcement').textContent=lengthTextToCm(text); }
function isVisible(object){for(let node=object;node;node=node.parent)if(!node.visible)return false;return true;}
function setPressed(id,pressed){const button=$(id);button.setAttribute('aria-pressed',String(pressed));button.classList.toggle('active',pressed);}
function saveOrigin(node){if(node&&!originals.has(node))originals.set(node,{position:node.position.clone(),rotation:node.rotation.clone(),visible:node.visible});}
function cancelTween(object){for(let i=tweens.length-1;i>=0;i--)if(tweens[i].object===object)tweens.splice(i,1);}
function tween(object,property,to,duration=.75,delay=0,gate=null){
  for(let i=tweens.length-1;i>=0;i--)if(tweens[i].object===object&&tweens[i].property===property)tweens.splice(i,1);
  if(reducedMotion){object[property]=to;return;}
  tweens.push({object,property,from:object[property],to,start:performance.now()+delay*1000,duration:duration*1000,gate});
}
function updateTweens(time){
  let moving=false;
  for(let i=tweens.length-1;i>=0;i--){
    const motion=tweens[i];if(time<motion.start)continue;
    if(motion.gate){if(!motion.gate())continue;motion.gate=null;motion.start=time;motion.from=motion.object[motion.property];}
    const p=Math.min((time-motion.start)/motion.duration,1),ease=p<.5?4*p*p*p:1-Math.pow(-2*p+2,3)/2;
    motion.object[motion.property]=motion.from+(motion.to-motion.from)*ease;if(p===1)tweens.splice(i,1);
    if(motion.object!==camera.position&&motion.object!==controls.target)moving=true;
  }
  return moving;
}
function tweenVector(object,to,duration=.9){for(const k of ['x','y','z'])tween(object,k,to[k],duration);}
function pauseRotation(){state.autoRotate=false;if(controls)controls.autoRotate=false;setPressed('autoRotate',false);}
function moveCamera(position,target,duration=.9){orbitMotion=null;pauseRotation();tweenVector(camera.position,position,duration);tweenVector(controls.target,target,duration);}
function viewingDirection(){return camera.position.clone().sub(controls.target).normalize();}
function intendedViewingDirection(){
  if(orbitMotion)return new THREE.Vector3(Math.sin(orbitMotion.toAngle)*Math.cos(orbitMotion.elevation),Math.sin(orbitMotion.elevation),Math.cos(orbitMotion.toAngle)*Math.cos(orbitMotion.elevation));
  const position=camera.position.clone(),target=controls.target.clone();for(const motion of tweens){if(motion.object===camera.position)position[motion.property]=motion.to;else if(motion.object===controls.target)target[motion.property]=motion.to;}return position.sub(target).normalize();
}
function fitDistanceForBox(box,angle,elevation,aspect,fov){
  const center=box.getCenter(new THREE.Vector3());
  const direction=new THREE.Vector3(Math.sin(angle)*Math.cos(elevation),Math.sin(elevation),Math.cos(angle)*Math.cos(elevation));
  const right=new THREE.Vector3().crossVectors(new THREE.Vector3(0,1,0),direction).normalize();
  const up=new THREE.Vector3().crossVectors(direction,right).normalize();
  const tangent=Math.tan(THREE.MathUtils.degToRad(fov/2));let distance=0;
  for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z]){
    const point=new THREE.Vector3(x,y,z).sub(center),depth=point.dot(direction);
    distance=Math.max(distance,depth+Math.abs(point.dot(right))/(tangent*aspect*.84),depth+Math.abs(point.dot(up))/(tangent*.82));
  }
  return {center,direction,distance:distance+.04};
}
function currentBounds(){
  if(state.sceneMode==='room'&&roomEnvironment?.active)return roomEnvironment.bounds().expandByScalar(.12);
  if(!model)return fitBox.clone();model.updateMatrixWorld(true);const bounds=new THREE.Box3();
  model.traverse(mesh=>{if(mesh.isMesh&&isVisible(mesh))bounds.expandByObject(mesh,Boolean(mesh.morphTargetInfluences?.length));});
  return bounds.isEmpty()?fitBox.clone():bounds;
}
function mechanismTargetBounds(measure=currentBounds){
  const saved=[];for(const motion of tweens){if(motion.object===camera.position||motion.object===controls.target)continue;saved.push([motion.object,motion.property,motion.object[motion.property]]);motion.object[motion.property]=motion.to;}
  updateDynamicCables();model.updateMatrixWorld(true);const bounds=measure();for(let i=saved.length-1;i>=0;i--){const [object,key,value]=saved[i];object[key]=value;}updateDynamicCables();model.updateMatrixWorld(true);return bounds;
}
function fitView(angle=Math.PI/8,elevation=.12,immediate=false,bounds=currentBounds()){
  // Keep the immersive camera inside complete walls; explicit component focus
  // has its own fitted pose and opens the cutaway only if that pose is outside.
  if(state.sceneMode==='room'&&state.roomView==='interior'&&!camera.isOrthographicCamera)return;
  if(camera.isOrthographicCamera){if(state.dimensions){syncDimensions();bounds=bounds.clone().union(dimensionLayer.getBounds());}fitRoomTop(bounds);return;}
  if(state.dimensions){const annotationBounds=mechanismTargetBounds(()=>{syncDimensions();return dimensionLayer.getBounds();});bounds=bounds.clone().union(annotationBounds);if(state.selection){const direction=new THREE.Vector3(Math.sin(angle)*Math.cos(elevation),Math.sin(elevation),Math.cos(angle)*Math.cos(elevation));const pose=focusPoseForBox(bounds,direction,camera.aspect,camera.fov,dimensionViewRegion());controls.maxDistance=Math.max(16,pose.distance*1.25);moveCamera(pose.position,pose.target,immediate?0:.9);return;}}
  const {center,distance}=fitDistanceForBox(bounds,angle,elevation,camera.aspect,camera.fov);
  controls.maxDistance=Math.max(16,distance*1.25);
  orbitTo(angle,elevation,distance,center,immediate?0:.9);
}
function setWiring(open){
  state.wiring=Boolean(open);setPressed('wiringView',state.wiring);const label=state.wiring?'关闭布线方案':'查看布线方案';$('wiringView').title=label;$('wiringView').setAttribute('aria-label',label);$('stage').classList.toggle('wiring-open',state.wiring);
  if(state.wiring){stopDemo();pauseRotation();closePanel();wiringPanel??=new WiringPanel($('wiringPanel'),()=>setWiring(false),inspectWiringInModel);const cabinet=modelContexts.get('cabinet')?.refs||refs;wiringPanel.setModelStatus?.({usb:cabinet.usb.size===18,fixed:cabinet.components.has('wiring:fixed')});wiringPanel.setOpen(true);announce(cabinet.usb.size===18?'布线方案已打开。可进入柜内查看USB接线与后侧固定主干。':'布线方案已打开。USB数据接入为待选型设计，当前三维模型采用原生RJ45接入。');}
  else {wiringPanel?.setOpen(false);$('wiringView').focus?.({preventScroll:true});}
}
function dimensionViewRegion(){
  const panel=$('componentPanel').getBoundingClientRect(),view=$('viewer').getBoundingClientRect();
  let left=24,right=viewport.width-24,top=viewport.height*.07,bottom=viewport.height*.93;
  if(state.selection){if(viewport.width>620)right=Math.max(viewport.width*.25,panel.left-view.left-24);else{left=viewport.width*.05;right=viewport.width*.95;bottom=Math.max(viewport.height*.22,panel.top-view.top-20);}}
  return {left:2*left/viewport.width-1,right:2*right/viewport.width-1,top:1-2*top/viewport.height,bottom:1-2*bottom/viewport.height};
}
function syncDimensions(){
  if(!state.dimensions||!model)return;
  if(!dimensionLayer)dimensionLayer=new CabinetDimensions(scene,$('dimensionLabels'),$('dimensionNote'));
  dimensionLayer.setEnabled(true);dimensionLayer.sync({model,metadata:metadataDocument,refs,originals,mode:state.mode,selection:state.selection,focused:$('componentPanel').classList.contains('is-focused')||(state.sceneMode==='room'&&Boolean(state.selection)&&!state.selection.key.startsWith('room:')),sceneMode:state.sceneMode,roomMetadata:roomEnvironment?.metadata,direction:viewingDirection()});
}
function setDimensions(enabled){
  state.dimensions=Boolean(enabled);setPressed('dimensionsView',state.dimensions);const label=`${state.dimensions?'隐藏':'显示'}尺寸标注（cm）`;$('dimensionsView').title=label;$('dimensionsView').setAttribute('aria-label',label);$('stage').classList.toggle('dimensions-on',state.dimensions);
  if(!state.dimensions)dimensionLayer?.setEnabled(false);else syncDimensions();
  if(renderer?.domElement)resize();
  if(state.loaded){pauseRotation();if(state.selection&&$('componentPanel').classList.contains('is-focused'))focusComponent();else{const d=intendedViewingDirection();fitView(Math.atan2(d.x,d.z),Math.asin(d.y));}}
  announce(state.dimensions?'已显示厘米尺寸标注。基础尺寸为闭合外形；虚线仅为托盘范围，不含开门及人员通道。':'已隐藏尺寸标注');
}
function zoom(factor){stopDemo();pauseRotation();if(camera.isOrthographicCamera){camera.zoom=THREE.MathUtils.clamp(camera.zoom/factor,.4,4);camera.updateProjectionMatrix();return;}const direction=camera.position.clone().sub(controls.target);const distance=THREE.MathUtils.clamp(direction.length()*factor,controls.minDistance,controls.maxDistance);moveCamera(controls.target.clone().add(direction.setLength(distance)),controls.target.clone(),.45);}
function orbitTo(angle,elevation,radius,target,duration=.9){
  pauseRotation();cancelTween(camera.position);cancelTween(controls.target);
  const offset=camera.position.clone().sub(controls.target),fromRadius=offset.length(),fromAngle=Math.atan2(offset.x,offset.z);
  const difference=Math.atan2(Math.sin(angle-fromAngle),Math.cos(angle-fromAngle));
  if(reducedMotion||duration<=0){controls.target.copy(target);camera.position.copy(target).add(new THREE.Vector3(Math.sin(angle)*Math.cos(elevation),Math.sin(elevation),Math.cos(angle)*Math.cos(elevation)).multiplyScalar(radius));orbitMotion=null;return;}
  orbitMotion={fromAngle,toAngle:fromAngle+difference,fromElevation:Math.asin(offset.y/fromRadius),elevation,fromRadius,radius,fromTarget:controls.target.clone(),target:target.clone(),start:performance.now(),duration:duration*1000};
}
function rotate(amount){if(camera.isOrthographicCamera)return;stopDemo();const offset=camera.position.clone().sub(controls.target);orbitTo(Math.atan2(offset.x,offset.z)+amount,Math.asin(offset.y/offset.length()),offset.length(),controls.target.clone(),.65);} 

function inferBay(object){
  if(state.mode==='single')return 'S1';
  for(let node=object;node;node=node.parent){
    const data=node.userData||{};if(data.bay_id||data.bayId)return String(data.bay_id||data.bayId);
    const match=node.name.match(/(?:^|_)([AB][1-9])(?:_|$)/);if(match)return match[1];
  }
  return '';
}
function inferModule(object){for(let node=object;node;node=node.parent){const match=node.name.match(/^Module_(Left|Center|Right)/);if(match)return match[1];}return '';}
function inherited(object,key){for(let node=object;node;node=node.parent)if(node.userData?.[key]!==undefined)return node.userData[key];return undefined;}
function isDoorPivot(node){return /^(DoorPivot_|RearDoorPivot_|EquipmentDoorPivot|SingleDoorPivot)/.test(node.name)||(!node.isMesh&&node.userData?.interaction==='door');}
function doorAncestor(object){for(let node=object;node;node=node.parent)if(isDoorPivot(node))return node;return null;}
function movingAnchor(object){
  for(let node=object.parent;node;node=node.parent)if(isDoorPivot(node)||/^(Tray_|Laptop_|Bay_|Module_)/.test(node.name)||node.userData?.interaction==='tray')return node;
  return model;
}
function housingName(name){return name.startsWith('Housing_')||/_BaseIntake|_BaseLabel|_Title|_Subtitle|^Center_UpperExhaust/.test(name);}
function fallbackKey(mesh,bay,door){
  const name=mesh.name;
  if(name.startsWith('TouchDisplay_'))return 'screen';
  if(name.startsWith('Glass_'))return `glass:${bay}`;
  if(door)return door.name.startsWith('RearDoorPivot_')?`rear:${door.name.replace('RearDoorPivot_','')}`:door.name==='EquipmentDoorPivot'?'equipment_bay':`door:${bay}`;
  if(bay){
    if(/PowerAdapter/.test(name))return `adapter:${bay}`;
    if(/Laptop|Keyboard|Trackpad|LockedDisplay|_Lid|Webcam/.test(name))return `laptop:${bay}`;
    if(/Tray|SlideMoving/.test(name))return `tray:${bay}`;
    if(/ACOutlet|OutletSlot/.test(name))return `outlet:${bay}`;
    if(/Network/.test(name))return `network:${bay}`;
    if(/Detection/.test(name))return `detection:${bay}`;
    if(/LED|LightChannel/.test(name))return `lighting:${bay}`;
    return `bay:${bay}`;
  }
  const part=name.match(/^Equipment_(UPS|MiniPC|Switch24|Control12|DC24V|Breaker|FanHousing|FanCore|PDU)/);
  if(part)return `equipment:${part[1]}`;
  return 'cabinet';
}
function describeMesh(mesh){
  const bay=inferBay(mesh),door=doorAncestor(mesh),module=inferModule(mesh);
  let key=String(inherited(mesh,'component_key')||fallbackKey(mesh,bay,door));
  if(state.mode==='cabinet'&&key==='wiring:network'&&bayIds.includes(bay))key=`wiring:network:${bay}`;
  const action=inherited(mesh,'action')||inherited(mesh,'interaction')||'';
  return {key,bay,module,doorName:door?.name||'',action,name:mesh.name,housing:housingName(mesh.name)||key==='single:housing',glass:/^(single:glass$|glass:)/.test(key)||mesh.name.startsWith('Glass_')||String(mesh.material?.name||'').startsWith('Glass'),status:mesh.name.includes('_StatusLED')};
}
function normalizeMetadata(data){
  metadataDocument=data||{};const source=data?.components||data?.items||data||{};
  if(Array.isArray(source))metadata=Object.fromEntries(source.map(item=>[String(item.key||item.component_key||item.name),item]));else metadata=source;
  if(Array.isArray(data?.empty_bays)){emptyBays.clear();data.empty_bays.forEach(id=>emptyBays.add(id));}
}
function createFallbackMetadata(){
  fallbackMetadata.cabinet={title:'笔记本智能管理存储柜',dimensions_mm:[3300,650,1850],basis:'model',notes:'按用户18仓要求扩展：左右各3列×3层，三模块宽度1350 + 600 + 1350 mm。'};
  fallbackMetadata.screen={title:'32 英寸竖向触摸屏',dimensions_mm:[398.5,null,708.4],basis:'user',notes:'可视区域；外框 435 × 750 × 50 mm 为模型示意。中心离地 1285 mm。'};
  fallbackMetadata.equipment_bay={title:'屏下设备舱',dimensions_mm:[540,500,680],basis:'model',notes:'参考有效包络；文档建议净高 650–700 mm，模型取 680 mm。'};
  for(const id of bayIds){
    const height=1250-Math.floor((Number(id[1])-1)/3)*450;
    fallbackMetadata[`bay:${id}`]={title:`${id} 仓位${emptyBays.has(id)?' · 空仓':''}`,dimensions_mm:[420,420,420],basis:'document',notes:`建议有效净空不小于 420 × 420 × 420 mm。承托面离地 ${height} mm。`};
    fallbackMetadata[`door:${id}`]={title:`${id} 透明仓门`,dimensions_mm:null,basis:'model',notes:'左侧铰链，右侧锁闭。玻璃厚度模型取 6 mm；最终装配需选型校核。'};
    fallbackMetadata[`glass:${id}`]={title:`${id} 安全玻璃`,dimensions_mm:null,basis:'model',notes:'玻璃厚度模型取 6 mm。'};
    fallbackMetadata[`tray:${id}`]={title:`${id} 抽拉托盘`,dimensions_mm:null,basis:'model',notes:'抽拉行程模型取 320 mm，文档建议范围 300–350 mm。'};
    fallbackMetadata[`laptop:${id}`]={title:`${id} 笔记本`,dimensions_mm:[320,225,18],basis:'model',notes:'电脑机型与开盖姿态为占位示意。'};
    fallbackMetadata[`adapter:${id}`]={title:`${id} 电源适配器`,dimensions_mm:null,basis:'model'};
    for(const [key,title] of [['outlet','电源插座'],['network','网络连接'],['detection','检测接口预留'],['lighting','仓内照明']])fallbackMetadata[`${key}:${id}`]={title:`${id} ${title}`,basis:'model'};
  }
  for(const [key,title] of Object.entries({UPS:'UPS 后备设备',MiniPC:'紧凑主机',Switch24:'24 口交换机',Control12:'锁控采集控制器',DC24V:'24V 低压电源',Breaker:'配电保护器件',FanHousing:'设备舱风机',FanCore:'设备舱风机',PDU:'配电单元'}))fallbackMetadata[`equipment:${key}`]={title,basis:'model'};
  for(const [key,title] of [['Left','左模块后维护门'],['Center','中央后维护门'],['Right','右模块后维护门']])fallbackMetadata[`rear:${key}`]={title,basis:'model',notes:'后维护门可开启，门体与通风孔为结构示意。'};
}
function getMeta(descriptor){
  const data=(descriptor.key.startsWith('room:')?roomEnvironment?.metadata?.components?.[descriptor.key]:metadata[descriptor.key])||fallbackMetadata[descriptor.key]||{};
  if(descriptor.key==='room:layout')return {...data,title:data.title||'机要室空间布局',basis:'model',facts:[...(data.facts||[]),{label:'柜前建议操作区',value:`${roomEnvironment.metadata.operation_zone_mm} mm`,basis:'model'},{label:'后侧安装间距',value:`${roomEnvironment.metadata.rear_clearance_mm} mm`,basis:'model'},{label:'背面维护',value:'本布局不可开启后门；独立整柜视图查看'}]};
  return {...data,title:data.title||data.name||descriptor.name||'内部部件',basis:data.basis||'model'};
}
function registerComponents(){
  refs.components.clear();refs.housings.length=0;
  model.traverse(mesh=>{if(!mesh.isMesh)return;const descriptor=meshDescriptors.get(mesh)||describeMesh(mesh);meshDescriptors.set(mesh,descriptor);if(!refs.components.has(descriptor.key))refs.components.set(descriptor.key,[]);refs.components.get(descriptor.key).push(mesh);if(descriptor.housing)refs.housings.push(mesh);});
  if(state.mode==='cabinet'){
    const routes=metadataDocument.wiring_design?.fixed_routes||[];
    for(const route of routes){if(route.kind!=='network'||!bayIds.includes(route.bay_id))continue;const bay=route.bay_id,key=`wiring:network:${bay}`;if(!refs.components.has(key))continue;const port=(bay[0]==='B'?9:0)+Number(bay.slice(1));metadata[key]={title:`${bay} 仓 → 交换机 ${String(port).padStart(2,'0')} 口`,basis:'model',facts:[{label:'固定路径长度',value:`${route.length_mm} mm`,basis:'model'},{label:'连接方式',value:'独立星形网络支线'}],notes:'路径长度为当前模型中心线的设计值，不含仓内活动网线、端接或施工下料余量；实际线长与弯曲半径须工程复核。'};}
    const networks=[...refs.components].filter(([key])=>key==='wiring:network'||key.startsWith('wiring:network:')).flatMap(([,meshes])=>meshes);if(networks.length)refs.components.set('wiring:network',[...new Set(networks)]);
  }
  if(state.mode==='single'){
    const keys=['single:interface_panel','single:network','single:ac_socket','single:adapter','single:adapter_bracket'];if(!refs.components.has('single:interface_panel'))keys.push('single:power');
    refs.components.set('single:interfaces',[...new Set(keys.flatMap(key=>refs.components.get(key)||[]))]);
    if(refs.usb.has('S1')){refs.components.set('single:usb_system',[...new Set(['single:usb_nic','single:usb','single:cables','single:tray'].flatMap(key=>refs.components.get(key)||[]))]);metadata['single:usb_system']={title:'托盘USB网卡与活动接线',basis:'model',notes:'网卡留在托盘，蓝色Ethernet始终连接并随盘；USB短线随盘，DC线独立活动。设备与夹具为结构示意，实际规格须选型验证。'};}
  }
  if(state.mode==='cabinet'){const keys=metadataDocument.wiring_view?.fixed_component_keys||[...refs.components.keys()].filter(key=>/^(trunk|duct|fixed_data|fixed_ac|fixed_control):/.test(key));const meshes=[...new Set(keys.flatMap(key=>refs.components.get(key)||[]))];if(meshes.length){refs.components.set('wiring:fixed',meshes);metadata['wiring:fixed']={title:'后侧固定布线与分区线槽',basis:'model',notes:'18仓星形数据支线、固定AC与低压控制分区。主干沿固定框架布置，结构剖视保持模块原位。查看布线时暂时隐藏可拆AC盖板，关闭浮窗后恢复；实际器件、线槽、保护与额定值仍需工程选型验证。'};}}
}

function optimizeMeshes(root){
  root.updateMatrixWorld(true);const groups=new Map();
  root.traverse(mesh=>{
    if(!mesh.isMesh)return;
    const descriptor=describeMesh(mesh);meshDescriptors.set(mesh,descriptor);
    if(Array.isArray(mesh.material)||mesh.isSkinnedMesh||mesh.morphTargetInfluences?.length||mesh.userData.dynamicCable||mesh.userData.preserveCable||!isVisible(mesh)||mesh.name.startsWith('TouchDisplay_')||/^[AB][1-9]_PowerAdapter$/.test(mesh.name))return;
    const anchor=movingAnchor(mesh);if(!anchor)return;
    const attributes=Object.keys(mesh.geometry.attributes).sort().join(',');
    const key=[anchor.uuid,descriptor.key,descriptor.bay,descriptor.doorName,descriptor.action,descriptor.housing,descriptor.glass,descriptor.status,mesh.material.uuid,attributes,Boolean(mesh.geometry.index)].join('|');
    if(!groups.has(key))groups.set(key,{anchor,descriptor,material:mesh.material,sources:[],geometries:[]});
    const group=groups.get(key),geometry=mesh.geometry.clone();
    geometry.applyMatrix4(new THREE.Matrix4().copy(anchor.matrixWorld).invert().multiply(mesh.matrixWorld));
    group.geometries.push(geometry);group.sources.push(mesh);
  });
  for(const group of groups.values()){
    const geometry=mergeGeometries(group.geometries,false);
    if(!geometry){group.geometries.forEach(g=>g.dispose());continue;}
    let material=group.material;
    if(group.descriptor.status){material=material.clone();refs.statuses.set(group.descriptor.bay,material);}
    const mesh=new THREE.Mesh(geometry,material);mesh.name=`Component_${group.descriptor.key}_${group.anchor.name}`;
    mesh.userData={...group.sources[0].userData,component_key:group.descriptor.key,bay_id:group.descriptor.bay,action:group.descriptor.action};
    meshDescriptors.set(mesh,{...group.descriptor});mesh.castShadow=!group.descriptor.glass;mesh.receiveShadow=true;group.anchor.add(mesh);
    group.sources.forEach(source=>source.removeFromParent());group.geometries.forEach(g=>g.dispose());
  }
  registerComponents();
}

function relatedDoor(descriptor){
  if(descriptor.key.startsWith('room:'))return null;
  if(state.mode==='single')return refs.doors.get('SingleDoorPivot');
  if(descriptor.doorName)return refs.doors.get(descriptor.doorName);
  const rear=state.sceneMode!=='room'&&viewingDirection().z < -.12;
  if(descriptor.bay){
    const module=descriptor.module||(descriptor.bay.startsWith('A')?'Left':'Right');
    if(rear&&refs.doors.has(`RearDoorPivot_${module}`))return refs.doors.get(`RearDoorPivot_${module}`);
    return refs.doors.get(`DoorPivot_${descriptor.bay}`);
  }
  if(descriptor.module==='Center'&&!descriptor.name.startsWith('TouchDisplay_')&&!descriptor.housing){
    return refs.doors.get(rear?'RearDoorPivot_Center':'EquipmentDoorPivot');
  }
  return null;
}
function trayIsClosed(tray){return Math.abs(tray.node.position.z-originals.get(tray.node).position.z)<=1e-6;}
function doorClearsTray(door){
  const actual=Math.abs(THREE.MathUtils.radToDeg(door.node.rotation.y-originals.get(door.node).rotation.y));
  const required=Math.min(Math.abs(door.swing),Math.max(0,Number(door.node.userData.min_open_degrees??95)));
  return door.open&&actual+.02>=required;
}
function setDoor(doorOrName,open,delay=0){
  const door=typeof doorOrName==='string'?refs.doors.get(doorOrName):doorOrName;if(!door)return;
  if(open&&door.kind==='rear'&&state.sceneMode==='room'){announce('房间后距仅10 cm，后维护门保持关闭。请切换整柜视图检修。');return;}
  const tray=door.bay&&refs.trays.get(door.bay);
  if(!open&&tray&&(tray.open||!trayIsClosed(tray)))setTray(door.bay,false);
  door.open=Boolean(open);const original=originals.get(door.node);
  tween(door.node.rotation,'y',original.rotation.y+(open?THREE.MathUtils.degToRad(door.swing):0),.85,delay,!open&&tray?()=>trayIsClosed(tray):null);
  if(renderer)renderer.shadowMap.needsUpdate=true;updatePanelActions();
  announce(`${door.title}${open?'已打开':'已关闭'}`);
}
function setTray(bay,open){
  const tray=refs.trays.get(bay);if(!tray)return;
  const door=refs.doors.get(state.mode==='single'?'SingleDoorPivot':`DoorPivot_${bay}`);
  if(open&&door&&!door.open)setDoor(door,true);
  tray.open=Boolean(open);tween(tray.node.position,'z',originals.get(tray.node).position.z+(open?tray.travel:0),.8,0,open&&door?()=>doorClearsTray(door):null);
  if(renderer)renderer.shadowMap.needsUpdate=true;updatePanelActions();
  if(!state.demo&&state.selection?.bay===bay&&$('componentPanel').classList.contains('is-focused'))focusComponent({trayBay:bay});
}
function setGlass(transparent){if(!refs.glassMaterial)return;state.glass=transparent;refs.glassMaterial.opacity=transparent?.09:.78;refs.glassMaterial.color.set(transparent?0xd5e9ed:0xa5bdcb);setPressed('glassView',transparent);}
function toggleAllDoors(){
  stopDemo();closePanel();const direction=intendedViewingDirection(),rear=state.sceneMode!=='room'&&direction.z<-.12;
  const doors=[...refs.doors.values()].filter(door=>state.mode==='single'||(rear?door.kind==='rear':door.kind!=='rear'));
  const open=doors.some(door=>!door.open);doors.forEach((door,index)=>setDoor(door,open,reducedMotion?0:index*.025));
  fitView(Math.atan2(direction.x,direction.z),Math.asin(direction.y),false,mechanismTargetBounds());
}
function setStructure(on){
  if(state.switching)return;
  if(state.sceneMode==='room'){announce('结构剖视将切换到独立整柜，保留房间中的安装位置。');setMode('cabinet').then(()=>setStructure(on));return;}
  stopDemo();closePanel();state.structure=on;setPressed('structureView',on);
  refs.housings.forEach(mesh=>mesh.visible=!on);
  for(const [name,node]of refs.modules){const offset=on&&!refs.components.has('wiring:fixed')?(name==='Left'?-.16:name==='Right'?.16:0):0;tween(node.position,'x',originals.get(node).position.x+offset);}
  for(const door of refs.doors.values())if(door.kind==='equipment'||door.kind==='rear')setDoor(door,on);
  fitView(viewingDirection().z<0?Math.PI+Math.PI/9:Math.PI/9,.12,false,mechanismTargetBounds());
}
function restoreOccupancy(){
  for(const [id,node]of refs.laptops){cancelTween(node.position);node.position.copy(originals.get(node).position);node.visible=!emptyBays.has(id);node.userData.demoHideAt=0;node.userData.reconnectAt=0;setBayCablesParked(id,false);}
  for(const node of refs.adapters.values()){cancelTween(node.position);node.position.copy(originals.get(node).position);node.visible=originals.get(node).visible;node.userData.demoHideAt=0;}
}
function updateDemoOccupancy(time){
  let moving=false;
  for(const [bay,node]of refs.laptops){
    if(node.userData.demoHideAt&&time>=node.userData.demoHideAt){node.visible=false;node.userData.demoHideAt=0;moving=true;}
    if(node.userData.reconnectAt&&time>=node.userData.reconnectAt){node.userData.reconnectAt=0;setBayCablesParked(bay,false);}
  }
  return moving;
}
function resetView(){
  if(!state.loaded)return;stopDemo();pauseRotation();closePanel();state.structure=false;setPressed('structureView',false);
  refs.housings.forEach(mesh=>mesh.visible=true);for(const [name,node]of refs.modules)tweenVector(node.position,originals.get(node).position,.6);
  if(state.mode==='single'){
    setTray('S1',false);setDoor('SingleDoorPivot',true);restoreOccupancy();setGlass(true);fitView(singleDefaultAngle,.2,false,mechanismTargetBounds());return;
  }
  for(const door of refs.doors.values())setDoor(door,false);for(const id of refs.trays.keys())if(!refs.doors.has(`DoorPivot_${id}`))setTray(id,false);
  restoreOccupancy();setGlass(true);if(state.sceneMode==='room'){setRoomView('overview');return;}fitView(Math.PI/8,.12,false,fitBox);
}
function setWiringInspection(on){state.wiringInspection=Boolean(on);for(const mesh of refs.components.get('wiring:ac_cover')||[])mesh.visible=!on;if(renderer)renderer.shadowMap.needsUpdate=true;}
function closePanel(){if(state.wiringInspection)setWiringInspection(false);state.selection=null;selectionMeshes=[];$('componentPanel').hidden=true;$('componentPanel').classList.remove('is-focused');}
function number(value){return Number.isFinite(Number(value))?new Intl.NumberFormat('zh-CN',{maximumFractionDigits:2}).format(Number(value)):'—';}
function addFact(label,value,basis){
  const row=document.createElement('div');row.className='fact-row';const labelNode=document.createElement('span'),valueNode=document.createElement('strong');labelNode.textContent=lengthTextToCm(label);valueNode.textContent=lengthTextToCm(value);
  if(basis){const tag=document.createElement('small');tag.className='inline-basis';tag.textContent=basis==='document'?'文档基准':basis==='user'?'用户指定':'模型示意';valueNode.append(tag);}row.append(labelNode,valueNode);$('componentFacts').append(row);
}
function showComponent(descriptor){
  if(state.wiring)setWiring(false);
  $('componentPanel').scrollTop=0;
  stopDemo();pauseRotation();state.selection=descriptor;selectionMeshes=refs.components.get(descriptor.key)||[];
  const data=getMeta(descriptor);$('componentTitle').textContent=lengthTextToCm(data.title);
  const basis=['document','model','user'].includes(data.basis)?data.basis:'model';$('componentBasis').dataset.basis=basis;$('componentBasis').textContent=basis==='document'?'文档基准':basis==='user'?'用户指定':'模型示意';
  const dimensions=data.dimensions_mm||data.dimensions;const list=$('componentDimensions');list.replaceChildren();list.classList.toggle('empty',!Array.isArray(dimensions));
  if(Array.isArray(dimensions))['宽','深','高'].forEach((label,index)=>{const div=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=dimensions[index]==null?'—':formatLengthCm(dimensions[index]);const unit=document.createElement('small');unit.textContent='cm';dd.append(unit);div.append(dt,dd);list.append(div);});
  $('componentFacts').replaceChildren();
  if(descriptor.bay&&state.mode==='cabinet'&&!descriptor.key.startsWith('wiring:network:')){
    const support=1250-Math.floor((Number(descriptor.bay[1])-1)/3)*450;
    addFact('仓内建议净空','≥420 × 420 × 420 mm','document');addFact('承托面离地',`${support} mm`,'document');
    if(emptyBays.has(descriptor.bay))addFact('当前模型','空仓');
    if(descriptor.doorName||descriptor.glass)addFact('玻璃厚度','6 mm','model');
    if(refs.trays.has(descriptor.bay))addFact('托盘行程',`${number(refs.trays.get(descriptor.bay).travel*1000)} mm`,'model');
  }
  if(descriptor.name.startsWith('TouchDisplay_')||descriptor.key==='screen'){
    addFact('面板对角线','81.28 cm','user');addFact('可视区域','398.5 × 708.4 mm','user');addFact('外框参考','435 × 750 × 50 mm','model');addFact('中心离地','1285 mm','document');
  }
  if(Array.isArray(data.facts))data.facts.forEach(fact=>addFact(fact.label||fact.name,fact.value||'',fact.basis));
  const notes=Array.isArray(data.notes)?data.notes.join('\n'):String(data.notes||'');$('componentNotes').textContent=lengthTextToCm(notes);$('componentNotes').hidden=!notes;
  $('componentPanel').classList.remove('is-focused');$('componentPanel').hidden=false;updatePanelActions();announce(`${data.title}，${$('componentBasis').textContent}`);if(state.dimensions){syncDimensions();const d=intendedViewingDirection();fitView(Math.atan2(d.x,d.z),Math.asin(d.y));}
}
function updatePanelActions(){
  const descriptor=state.selection;if(!descriptor)return;
  const door=relatedDoor(descriptor),doorButton=$('toggleComponentDoor');doorButton.hidden=!door||(state.sceneMode==='room'&&door.kind==='rear');
  if(door){const label=`${door.open?'关闭':'打开'}${door.title}`;doorButton.title=label;doorButton.setAttribute('aria-label',label);doorButton.setAttribute('aria-pressed',String(door.open));doorButton.querySelector('svg').innerHTML=door.open?icon.doorClose:icon.doorOpen;}
  const tray=descriptor.key.startsWith('wiring:network:')?null:refs.trays.get(descriptor.bay),trayButton=$('toggleComponentTray');trayButton.hidden=!tray;
  if(tray){const label=`${tray.open?'收回':'抽出'} ${descriptor.bay} 托盘`;trayButton.title=label;trayButton.setAttribute('aria-label',label);trayButton.setAttribute('aria-pressed',String(tray.open));trayButton.querySelector('svg').innerHTML=tray.open?icon.trayIn:icon.trayOut;}
  $('inspectSingle').hidden=state.mode==='single'||!descriptor.bay;
  $('focusSinglePorts').hidden=state.mode!=='single';$('focusSingleTray').hidden=state.mode!=='single';
}
function componentBox(descriptor){
  if(descriptor.key.startsWith('room:'))return roomEnvironment.componentBox(descriptor.key);
  const box=new THREE.Box3();
  // A bay-level inspection must keep its opened door, tray and contents together.
  // Dedicated device/port/lock selections continue to use only their component.
  const bayLevel=/^(glass|door|tray|bay):[AB][1-9]$/.test(descriptor.key);
  const bayNode=state.mode==='single'&&descriptor.key==='single:tray'?model.getObjectByName('SingleTray'):state.mode==='single'&&/^single:(door|glass)$/.test(descriptor.key)?model:bayLevel&&descriptor.bay?model.getObjectByName(`Bay_${descriptor.bay}`):null;
  if(bayNode){model.updateMatrixWorld(true);bayNode.traverse(mesh=>{if(mesh.isMesh&&isVisible(mesh))box.expandByObject(mesh,Boolean(mesh.morphTargetInfluences?.length));});}
  else for(const mesh of refs.components.get(descriptor.key)||[])if(isVisible(mesh))box.expandByObject(mesh,Boolean(mesh.morphTargetInfluences?.length));
  if(state.mode==='single'&&descriptor.key==='single:tray')for(const key of ['single:tray','single:cables'])for(const mesh of refs.components.get(key)||[])if(isVisible(mesh))box.expandByObject(mesh,Boolean(mesh.morphTargetInfluences?.length));
  if(!box.isEmpty())return box;
  const data=getMeta(descriptor);const anchor=data.anchor;
  if(Array.isArray(anchor)&&anchor.length===3){const point=new THREE.Vector3(...anchor);return new THREE.Box3(point.clone().addScalar(-.1),point.clone().addScalar(.1));}
  return fitBox.clone();
}
function focusPoseForBox(box,direction,aspect,fov,region){
  const center=box.getCenter(new THREE.Vector3()),right=new THREE.Vector3().crossVectors(new THREE.Vector3(0,1,0),direction).normalize(),up=new THREE.Vector3().crossVectors(direction,right).normalize();
  const tangent=Math.tan(THREE.MathUtils.degToRad(fov/2)),tx=tangent*aspect,ty=tangent;
  const cx=(region.left+region.right)/2,cy=(region.bottom+region.top)/2;let distance=.65;
  for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z]){
    const p=new THREE.Vector3(x,y,z).sub(center),px=p.dot(right)/tx,py=p.dot(up)/ty,depth=p.dot(direction);
    distance=Math.max(distance,(px+region.right*depth)/(region.right-cx),(-px-region.left*depth)/(cx-region.left),(py+region.top*depth)/(region.top-cy),(-py-region.bottom*depth)/(cy-region.bottom));
  }
  distance+=.03;
  const target=center.clone().addScaledVector(right,-cx*distance*tx).addScaledVector(up,-cy*distance*ty);
  return {target,position:target.clone().addScaledVector(direction,distance),distance};
}
function frontalDirectionForRegion(region,aspect,fov,slope=.2){
  // The HUD moves the optical target away from the part. Compensate that shift
  // in yaw and pitch so the camera itself stays directly in front of the bay.
  const t=Math.tan(THREE.MathUtils.degToRad(fov/2)),p=(region.left+region.right)/2*t*aspect,q=(region.bottom+region.top)/2*t,m=1+q*q;
  const tilt=Math.asin(slope*Math.sqrt((m+p*p)/(m*(1+slope*slope)))),elevation=Math.atan(q)+tilt,yaw=Math.atan2(p,Math.cos(elevation)+q*Math.sin(elevation));
  return new THREE.Vector3(Math.sin(yaw)*Math.cos(elevation),Math.sin(elevation),Math.cos(yaw)*Math.cos(elevation));
}
function focusComponent(options={}){
  if(camera.isOrthographicCamera){useRoomProjection(false);state.roomView='inspect';updateSceneControls();options={...options,direction:new THREE.Vector3(.15,.25,1).normalize()};}
  const descriptor=state.selection;if(!descriptor)return;stopDemo();$('componentPanel').classList.add('is-focused');$('componentPanel').scrollTop=0;
  const focusDescriptor=options.trayBay?{...descriptor,key:state.mode==='single'?'single:tray':`bay:${options.trayBay}`,bay:options.trayBay}:descriptor;
  const box=mechanismTargetBounds(()=>{const targetBox=componentBox(focusDescriptor);if(state.dimensions){syncDimensions();targetBox.union(dimensionLayer.getBounds(true));}return targetBox;});const direction=options.direction?.clone()||viewingDirection();if(state.sceneMode==='room'&&/^(glass|door|tray|bay):[AB][1-9]$/.test(focusDescriptor.key))direction.set(0,.2,1);if(state.mode==='single'&&!/^single:(housing|door|glass|hinges|ventilation)$/.test(focusDescriptor.key))direction.set(/^single:(interfaces|interface_panel|network|power|ac_socket|adapter|adapter_bracket|cables|usb_nic|usb|usb_system)$/.test(focusDescriptor.key)?.4:Math.tan(singleDefaultAngle),.2,1);direction.y=THREE.MathUtils.clamp(direction.y,.1,.36);direction.normalize();
  const panel=$('componentPanel').getBoundingClientRect(),view=$('viewer').getBoundingClientRect();
  let left=24,right=viewport.width-24,top=viewport.height*.06,bottom=viewport.height*.94;
  if(viewport.width>620)right=Math.max(viewport.width*.25,panel.left-view.left-24);
  else {left=viewport.width*.05;right=viewport.width*.95;bottom=Math.max(viewport.height*.22,panel.top-view.top-18);}
  const region={left:2*left/viewport.width-1,right:2*right/viewport.width-1,top:1-2*top/viewport.height,bottom:1-2*bottom/viewport.height};
  if(state.sceneMode==='room'&&/^(glass|door|tray|bay):[AB][1-9]$/.test(focusDescriptor.key)){
    const bayNode=model.getObjectByName(`Bay_${focusDescriptor.bay}`),x=bayNode?bayNode.getWorldPosition(new THREE.Vector3()).x:box.getCenter(new THREE.Vector3()).x,half=Math.max(Math.abs(box.min.x-x),Math.abs(box.max.x-x));
    box.min.x=x-half;box.max.x=x+half;direction.copy(frontalDirectionForRegion(region,camera.aspect,camera.fov));
  }
  const pose=focusPoseForBox(box,direction,camera.aspect,camera.fov,region);if(state.sceneMode==='room'&&!roomEnvironment.bounds().containsPoint(pose.position)){setRoomCutaway(true);state.roomView='inspect';updateSceneControls();}controls.maxDistance=Math.max(16,pose.distance*1.25);moveCamera(pose.position,pose.target);
}
function accessible(descriptor){
  if(state.structure||descriptor.doorName||descriptor.housing||descriptor.name.startsWith('TouchDisplay_')||descriptor.key==='cabinet')return true;
  const door=relatedDoor(descriptor);return !door||door.open;
}
function hitTest(clientX,clientY){
  if(!model)return null;const rectangle=renderer.domElement.getBoundingClientRect(),pointer=new THREE.Vector2((clientX-rectangle.left)/rectangle.width*2-1,-(clientY-rectangle.top)/rectangle.height*2+1);
  const raycaster=new THREE.Raycaster();raycaster.setFromCamera(pointer,camera);
  for(const hit of raycaster.intersectObjects(state.sceneMode==='room'?[model,roomEnvironment.model]:[model],true)){if(!isVisible(hit.object)||hit.object.userData.ignorePicking)continue;return {hit,descriptor:hit.object.userData.roomComponentKey?roomEnvironment.descriptor(hit.object):meshDescriptors.get(hit.object)||describeMesh(hit.object)};}
  return null;
}
function setupPicking(){
  let start=null,hoverAt=0;
  renderer.domElement.addEventListener('pointerdown',event=>{start={x:event.clientX,y:event.clientY,time:performance.now()};});
  renderer.domElement.addEventListener('pointerup',event=>{
    if(state.switching)return;
    if(!start||Math.hypot(event.clientX-start.x,event.clientY-start.y)>6||performance.now()-start.time>800)return;
    const result=hitTest(event.clientX,event.clientY);if(!result){closePanel();return;}stopDemo();pauseRotation();const descriptor=result.descriptor;
    if(descriptor.doorName){const door=refs.doors.get(descriptor.doorName);if(door)setDoor(door,!door.open);}
    else if(!accessible(descriptor)){const door=relatedDoor(descriptor);if(door)setDoor(door,true);}
    showComponent(descriptor);
  });
  renderer.domElement.addEventListener('pointermove',event=>{if(event.pointerType==='touch'||event.buttons||performance.now()-hoverAt<90)return;hoverAt=performance.now();$('viewer').classList.toggle('is-interactive',Boolean(hitTest(event.clientX,event.clientY)));});
  renderer.domElement.addEventListener('pointerleave',()=>$('viewer').classList.remove('is-interactive'));
}

function makeDemoScreen(){
  const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;
  screenTexture=new THREE.CanvasTexture(canvas);screenTexture.colorSpace=THREE.SRGBColorSpace;screenTexture.flipY=false;
  demoScreenMaterial=new THREE.MeshBasicMaterial({map:screenTexture});return canvas;
}
let demoCanvas;
function drawDemoScreen(title,subtitle,bay,complete=false){
  if(!screenMesh)return;if(!demoCanvas)demoCanvas=makeDemoScreen();const ctx=demoCanvas.getContext('2d');
  ctx.fillStyle='#eff7fb';ctx.fillRect(0,0,1080,1920);ctx.fillStyle='#ffffff';ctx.fillRect(0,0,1080,175);
  ctx.fillStyle='#143e58';ctx.font='bold 40px -apple-system,sans-serif';ctx.fillText('笔记本智能管理存储柜',65,108);
  ctx.fillStyle='#4596a9';ctx.font='30px -apple-system,sans-serif';ctx.fillText('自助借还 · 流程演示',70,280);
  ctx.fillStyle='#163e56';ctx.font='bold 66px -apple-system,sans-serif';ctx.fillText(title,70,395);
  ctx.fillStyle='#7b97a7';ctx.font='32px -apple-system,sans-serif';ctx.fillText(subtitle,70,475);
  ctx.fillStyle='#fff';ctx.beginPath();ctx.roundRect(70,570,940,610,35);ctx.fill();
  ctx.strokeStyle='#368ca6';ctx.lineWidth=9;ctx.lineJoin='round';
  if(complete){ctx.beginPath();ctx.arc(540,775,86,0,Math.PI*2);ctx.stroke();ctx.beginPath();ctx.moveTo(494,774);ctx.lineTo(530,809);ctx.lineTo(591,742);ctx.stroke();}
  else{ctx.strokeRect(463,710,154,105);ctx.beginPath();ctx.moveTo(443,838);ctx.lineTo(637,838);ctx.stroke();}
  ctx.textAlign='center';ctx.fillStyle='#285972';ctx.font='bold 52px -apple-system,sans-serif';ctx.fillText(`${bay} 仓位`,540,995);
  ctx.fillStyle='#8da5b3';ctx.font='29px -apple-system,sans-serif';ctx.fillText(complete?'电子记录已生成':'请按提示操作',540,1072);
  ctx.fillStyle='#2c829d';ctx.beginPath();ctx.roundRect(70,1280,940,130,24);ctx.fill();ctx.fillStyle='#fff';ctx.font='bold 40px -apple-system,sans-serif';ctx.fillText(complete?'完成':'正在演示',540,1360);
  ctx.textAlign='left';ctx.fillStyle='#89a1b0';ctx.font='27px -apple-system,sans-serif';ctx.fillText('模拟状态 · 不连接真实硬件',70,1535);ctx.fillText('需要帮助，请联系现场管理员',70,1590);
  screenTexture.needsUpdate=true;screenMesh.material=demoScreenMaterial;
}
function stopDemo(){
  clearTimeout(demoTimer);if(!state.demo)return;
  state.demo=false;setPressed('demoToggle',false);$('demoToggle').title='播放借还演示';$('demoToggle').setAttribute('aria-label','播放借还演示');
  const id=state.demoBay;if(id){if(refs.doors.has(`DoorPivot_${id}`))setDoor(`DoorPivot_${id}`,false);else setTray(id,false);}restoreOccupancy();if(screenMesh)screenMesh.material=screenMaterial;
}
function startDemo(){
  if(state.mode!=='cabinet'||state.switching)return;
  if(state.demo){stopDemo();return;}resetView();
  const id=bayIds.find(bay=>refs.laptops.has(bay)&&!emptyBays.has(bay));if(!id)return;
  state.demo=true;state.demoBay=id;demoIndex=-1;closePanel();setPressed('demoToggle',true);$('demoToggle').title='停止借还演示';$('demoToggle').setAttribute('aria-label','停止借还演示');fitView(.12,.08);
  const steps=[
    [2200,()=>drawDemoScreen('身份核验','核验借用权限',id)],
    [1800,()=>drawDemoScreen('选择设备','定位可借用设备',id)],
    [1400,()=>{drawDemoScreen('授权开门','请找到亮灯仓位',id);setDoor(`DoorPivot_${id}`,true);}],
    [1700,()=>{drawDemoScreen('抽出托盘','固定适配器留在独立托架',id);setTray(id,true);}],
    [1800,()=>{drawDemoScreen('取走设备',refs.usb.has(id)?'USB端随盘停靠，网线保留连接':'线头归入固定停车卡座',id);setBayCablesParked(id,true);for(const node of [refs.laptops.get(id)])if(node){tween(node.position,'y',originals.get(node).position.y+.2,.8);tween(node.position,'z',originals.get(node).position.z+.1,.8);node.userData.demoHideAt=performance.now()+850;}}],
    [1700,()=>{drawDemoScreen('关闭锁定','分别确认门位与锁位',id);setTray(id,false);setDoor(`DoorPivot_${id}`,false,.6);}],
    [2500,()=>drawDemoScreen('借用完成','电子借用记录',id,true)],
    [1800,()=>drawDemoScreen('归还电脑','再次核验身份与设备',id)],
    [1900,()=>{drawDemoScreen('打开归还仓','将设备放回所选仓位',id);setDoor(`DoorPivot_${id}`,true);setTray(id,true);}],
    [2100,()=>{drawDemoScreen('放置与接线',refs.usb.has(id)?'连接USB与DC，确认网络与设备状态':'电源、网络、检测接口逐项确认',id);for(const node of [refs.laptops.get(id)])if(node){node.visible=true;node.userData.demoHideAt=0;node.position.copy(originals.get(node).position).add(new THREE.Vector3(0,.2,.1));tweenVector(node.position,originals.get(node).position,.9);node.userData.reconnectAt=performance.now()+950;}}],
    [1700,()=>{drawDemoScreen('关闭锁定','门位与锁位分别确认',id);setTray(id,false);setDoor(`DoorPivot_${id}`,false,.6);}],
    [3000,()=>drawDemoScreen('设备已接收','电子回执 · 待检测',id,true)]
  ];
  const advance=()=>{if(!state.demo)return;demoIndex++;if(demoIndex>=steps.length){stopDemo();return;}const [duration,action]=steps[demoIndex];action();demoTimer=setTimeout(advance,duration);};advance();
}

function validPoint(point){return Array.isArray(point)&&point.length===3&&point.every(Number.isFinite);}
function cableCurve(cable,delta){
  const fixed=new THREE.Vector3(...cable.spec.fixed),moving=new THREE.Vector3(...cable.spec.moving);moving.z+=delta;
  const guides=cable.guides,first=guides[0],last=guides.at(-1);
  // Deform only the service loop between its supported lead-ins. Both connectors
  // remain exact; the final lead-in follows the measured tray translation.
  const makeCurve=scale=>{
    const points=[fixed];
    guides.forEach((guide,index)=>{
      const t=guides.length===1?.5:index/(guides.length-1),base=first.clone().lerp(last,t);
      const point=base.addScaledVector(guide.clone().sub(base),scale);
      point.z+=delta*t;points.push(point);
    });
    points.push(moving);
    const filtered=points.filter((point,index)=>index===0||point.distanceToSquared(points[index-1])>1e-10);
    const curve=new THREE.CatmullRomCurve3(filtered,false,'centripetal');curve.arcLengthDivisions=192;return curve;
  };
  const rest=Number(cable.spec.rest_length_mm)/1000;
  let low=0,high=1,lowCurve=makeCurve(low),highCurve=makeCurve(high),curve;
  if(!Number.isFinite(rest)||rest<=0){curve=makeCurve(1-Math.min(Math.abs(delta)/.32,1)*.45);}
  else if(lowCurve.getLength()>=rest){curve=lowCurve;}
  else if(highCurve.getLength()<=rest){
    const addSlack=amplitude=>{
      const points=highCurve.getPoints(32).map((point,index)=>{const t=index/32;point.z+=amplitude*Math.sin(4*Math.PI*t)*Math.pow(Math.sin(Math.PI*t),2);return point;});
      const result=new THREE.CatmullRomCurve3(points,false,'centripetal');result.arcLengthDivisions=192;return result;
    };
    let minimum=0,maximum=.12;
    for(let i=0;i<13;i++){const amplitude=(minimum+maximum)/2,candidate=addSlack(amplitude);if(candidate.getLength()<rest)minimum=amplitude;else maximum=amplitude;}
    curve=addSlack((minimum+maximum)/2);
  }
  else {
    for(let i=0;i<13;i++){const middle=(low+high)/2,candidate=makeCurve(middle);if(candidate.getLength()<rest)low=middle;else high=middle;}
    curve=makeCurve((low+high)/2);
  }
  return curve;
}
function hasControlledPath(spec){return Array.isArray(spec.guide_points)&&Array.isArray(spec.guide_points_extended)&&spec.guide_points.length>1&&spec.guide_points.length===spec.guide_points_extended.length&&spec.guide_points.every(validPoint)&&spec.guide_points_extended.every(validPoint);}
function cablePathPoints(cable,delta){
  const amount=cable.kind==='stowed'?0:THREE.MathUtils.clamp(delta/cable.tray.travel,0,1);
  return (cable.spec.guide_points||[]).map((point,index)=>{const result=new THREE.Vector3(...point);return hasControlledPath(cable.spec)?result.lerp(new THREE.Vector3(...cable.spec.guide_points_extended[index]),amount):result;});
}
function pathLength(points){return points.slice(1).reduce((sum,point,index)=>sum+point.distanceTo(points[index]),0);}
function rebuildCable(cable,delta){
  if(cable.kind==='stowed'){cable.lastDelta=0;cable.length=cable.spec.guide_points?.length>1?pathLength(cablePathPoints(cable,0)):Number(cable.spec.rest_length_mm)/1000;return;}
  if(cable.kind==='morph'){
    const amount=THREE.MathUtils.clamp(delta/cable.tray.travel,0,1);
    for(const {mesh,index} of cable.targets)mesh.morphTargetInfluences[index]=amount;
    cable.lastDelta=delta;cable.length=hasControlledPath(cable.spec)?pathLength(cablePathPoints(cable,delta)):Number(cable.spec.rest_length_mm)/1000;return;
  }
  let curve;
  if(cable.kind==='controlled'){
    const points=cablePathPoints(cable,delta);curve=new THREE.CurvePath();for(let i=1;i<points.length;i++)curve.add(new THREE.LineCurve3(points[i-1],points[i]));
  }else curve=cableCurve(cable,delta);
  const geometry=new THREE.TubeGeometry(curve,cable.kind==='controlled'?Math.max(120,cable.spec.guide_points.length*2):80,Number(cable.spec.radius_mm||2.2)/1000,cable.kind==='controlled'?10:7,false);
  const previous=cable.mesh.geometry;cable.mesh.geometry=geometry;if(previous)previous.dispose();cable.lastDelta=delta;cable.length=curve.getLength();
}
function setBayCablesParked(bay,parked){
  for(const cable of refs.cables){
    if(cable.bay!==bay||cable.kind==='stowed')continue;const keepConnected=cable.spec.keep_connected_when_empty===true;cable.parked=Boolean(parked)&&!keepConnected;const cableParked=cable.parked;
    cable.meshes.forEach(mesh=>mesh.visible=!cableParked);cable.connectorMeshes.forEach(mesh=>mesh.visible=!cableParked);cable.parkingMeshes.forEach(mesh=>mesh.visible=cableParked);
  }
  const usb=refs.usb.get(bay);if(usb){usb.parked=Boolean(parked)||!usb.initialOccupied;usb.nic.visible=true;usb.connected.forEach(mesh=>mesh.visible=!usb.parked);usb.parking.forEach(mesh=>mesh.visible=usb.parked);}
}
function prepareUsbConnections(){
  const specs=Array.isArray(metadataDocument.usb_connections)?metadataDocument.usb_connections:[];
  const canonical=name=>String(name).replace(/[.\[\]/:]/g,'').replace(/_Mesh$/,'');const nodes=new Map();model.traverse(node=>{const key=canonical(node.name);if(!nodes.has(key))nodes.set(key,[]);nodes.get(key).push(node);});
  const meshes=names=>{const result=new Set();for(const name of names||[])for(const node of nodes.get(canonical(name))||[])node.traverse(mesh=>{if(mesh.isMesh){mesh.userData.preserveCable=true;result.add(mesh);}});return [...result];};
  for(const spec of specs){const bay=state.mode==='single'?'S1':String(spec.bay_id||''),nic=model.getObjectByName(spec.nic_node)||nodes.get(canonical(spec.nic_node))?.[0],connected=meshes(spec.connected_node_names),parking=meshes(spec.parked_node_names),initialOccupied=spec.initial_occupied??refs.laptops.has(bay);if(!nic||!refs.trays.has(bay)||!parking.length||(initialOccupied&&!connected.length))throw new Error(`USB接线组件不完整：${bay}`);nic.traverse(mesh=>{if(mesh.isMesh)mesh.userData.preserveCable=true;});refs.usb.set(bay,{spec,nic,connected,parking,initialOccupied:Boolean(initialOccupied),parked:!initialOccupied});setBayCablesParked(bay,!initialOccupied);}
}
function prepareDynamicCables(){
  const paths=Array.isArray(metadataDocument.cable_paths)?metadataDocument.cable_paths:[],materials=new Map(),nodeIndex=new Map();
  const canonical=name=>String(name).replace(/[.\[\]/:]/g,'').replace(/_Mesh$/,'');
  model.traverse(node=>{const name=canonical(node.name);if(!nodeIndex.has(name))nodeIndex.set(name,[]);nodeIndex.get(name).push(node);});
  const namedMeshes=names=>{const result=new Set();for(const name of names||[])for(const node of nodeIndex.get(canonical(name))||[])node.traverse(child=>{if(child.isMesh)result.add(child);});return [...result];};
  for(const spec of paths){
    const bay=state.mode==='single'?'S1':String(spec.bay_id||''),stowed=spec.stowed===true||spec.motion==='stowed'||(state.mode==='cabinet'&&emptyBays.has(bay)&&spec.keep_connected_when_empty!==true);
    if(!['bay_local_gltf','single_local_gltf'].includes(spec.space)||!validPoint(spec.fixed)||(!stowed&&!validPoint(spec.moving)))throw new Error(`线缆路径参数不完整：${spec.id}`);
    const tray=refs.trays.get(bay),parent=model.getObjectByName(spec.parent_node||(state.mode==='single'?'SingleCabinetRoot':`Bay_${bay}`));
    if(!tray||!parent)throw new Error(`线缆所属仓位或托盘缺失：${spec.id}`);
    const sources=namedMeshes(spec.source_node_names),parkingMeshes=namedMeshes(spec.parking_node_names),connectorMeshes=namedMeshes(spec.moving_connector_node_names);
    for(const mesh of [...sources,...parkingMeshes,...connectorMeshes])mesh.userData.preserveCable=true;
    const cable={spec,bay,tray,parent,meshes:sources,parkingMeshes,connectorMeshes,parked:stowed,lastDelta:NaN,length:0};
    if(stowed){
      if(!sources.length)throw new Error(`固定收纳线缆网格缺失：${spec.id}`);
      cable.kind='stowed';sources.forEach(mesh=>{mesh.visible=true;if(mesh.morphTargetInfluences)mesh.morphTargetInfluences.fill(0);});refs.cables.push(cable);rebuildCable(cable,0);continue;
    }
    parkingMeshes.forEach(mesh=>mesh.visible=false);connectorMeshes.forEach(mesh=>mesh.visible=true);
    const targets=spec.morph_target?sources.map(mesh=>({mesh,index:mesh.morphTargetDictionary?.[spec.morph_target]})).filter(target=>Number.isInteger(target.index)):[];
    if(targets.length){
      targets.forEach(({mesh})=>{mesh.userData.dynamicCable=true;mesh.userData.component_key=spec.component_key||(state.mode==='single'?'single:cables':`cables:${bay}`);mesh.castShadow=false;});
      Object.assign(cable,{kind:'morph',targets});refs.cables.push(cable);rebuildCable(cable,tray.node.position.z-originals.get(tray.node).position.z);continue;
    }
    const controlled=hasControlledPath(spec);
    if(!controlled&&(state.mode==='single'||spec.morph_target||metadataDocument.cable_system==='controlled_native_v2'))throw new Error(`受控活动线缆缺少形态键或同拓扑路径：${spec.id}`);
    sources.forEach(node=>node.removeFromParent());
    const color=spec.color||'#18212b';if(!materials.has(color))materials.set(color,new THREE.MeshStandardMaterial({color,roughness:.45,metalness:.08}));
    const mesh=new THREE.Mesh(new THREE.BufferGeometry(),materials.get(color));mesh.name=`LiveCable_${spec.id}`;
    mesh.userData={component_key:spec.component_key||`cables:${bay}`,bay_id:bay,dynamicCable:true,cable_id:spec.id};mesh.castShadow=false;mesh.receiveShadow=true;parent.add(mesh);
    let guides=(spec.guide_points||[]).filter(validPoint).map(point=>new THREE.Vector3(...point));
    if(guides.length<2){const fixed=new THREE.Vector3(...spec.fixed),moving=new THREE.Vector3(...spec.moving);guides=[fixed.clone().add(new THREE.Vector3(0,.04,-.035)),fixed.clone().lerp(moving,.5).add(new THREE.Vector3(0,.06,-.11)),moving.clone().add(new THREE.Vector3(0,.035,-.035))];}
    Object.assign(cable,{kind:controlled?'controlled':'curve',mesh,meshes:[mesh],guides});refs.cables.push(cable);
    const descriptor={key:mesh.userData.component_key,bay,module:bay.startsWith('A')?'Left':'Right',doorName:'',action:'component',name:mesh.name,housing:false,glass:false,status:false};meshDescriptors.set(mesh,descriptor);
    rebuildCable(cable,tray.node.position.z-originals.get(tray.node).position.z);
  }
}
function updateDynamicCables(){
  for(const cable of refs.cables){if(cable.kind==='stowed')continue;const delta=cable.tray.node.position.z-originals.get(cable.tray.node).position.z;if(Math.abs(delta-cable.lastDelta)>1e-7)rebuildCable(cable,delta);}
}

function setupModel(){
  model.updateMatrixWorld(true);
  refs.glassMaterial=new THREE.MeshPhysicalMaterial({color:0xd5e9ed,roughness:.07,metalness:0,transparent:true,opacity:.09,depthWrite:false,side:THREE.DoubleSide,clearcoat:1,clearcoatRoughness:.09,envMapIntensity:.75});
  const visitedMaterials=new Set();
  model.traverse(node=>{
    if(isDoorPivot(node)){
      const rear=node.name.startsWith('RearDoorPivot_'),equipment=node.name==='EquipmentDoorPivot',bay=inferBay(node),kind=rear?'rear':equipment?'equipment':'bay';
      const swing=Number(node.userData.swing_degrees??node.userData.open_degrees??(rear||equipment?105:-105));
      const title=rear?`${node.name.includes('Left')?'左模块':node.name.includes('Right')?'右模块':'中央'}后维护门`:equipment?'屏下设备舱门':`${bay} 仓门`;
      saveOrigin(node);refs.doors.set(node.name,{node,bay,kind,swing,open:false,title});
    }
    if(node.isMesh){
      if(describeMesh(node).glass)node.material=refs.glassMaterial;if(inherited(node,'initial_hidden')===true)node.visible=false;
      node.castShadow=node.material!==refs.glassMaterial;node.receiveShadow=true;
      const materials=Array.isArray(node.material)?node.material:[node.material];for(const material of materials)if(material&&!visitedMaterials.has(material)){visitedMaterials.add(material);if(material.emissiveIntensity>1.5)material.emissiveIntensity=1.5;}
      if(node.name.startsWith('TouchDisplay_'))screenMesh=node;
    }
  });
  for(const bay of bayIds){
    const tray=model.getObjectByName(`Tray_${bay}`),laptop=model.getObjectByName(`Laptop_${bay}`),adapter=model.getObjectByName(`${bay}_PowerAdapter`);
    if(tray){saveOrigin(tray);refs.trays.set(bay,{node:tray,open:false,travel:Number(tray.userData.travel_mm??320)/1000});}
    if(laptop){saveOrigin(laptop);refs.laptops.set(bay,laptop);}
    if(adapter){saveOrigin(adapter);refs.adapters.set(bay,adapter);}
  }
  for(const name of ['Left','Center','Right']){const node=model.getObjectByName(`Module_${name}`);if(node){saveOrigin(node);refs.modules.set(name,node);}}
  if(screenMesh)screenMaterial=screenMesh.material;
  restoreOccupancy();prepareDynamicCables();prepareUsbConnections();optimizeMeshes(model);fitBox=currentBounds();addInteriorLights();
}
function addInteriorLights(){
  const add=(position,doors,intensity,distance)=>{const closedIntensity=state.mode==='single'?intensity*.38:0,light=new THREE.PointLight(0xffeed5,closedIntensity,distance,2);light.position.copy(position);model.add(light);refs.interiorLights.push({light,doors,intensity,closedIntensity});};
  if(state.mode==='single'){
    const box=currentBounds(),center=box.getCenter(new THREE.Vector3());add(new THREE.Vector3(center.x,box.max.y-.045,box.max.z-.055),['SingleDoorPivot'],.095,.85);
  }else{
    for(const side of ['A','B'])for(let row=0;row<3;row++)add(new THREE.Vector3(side==='A'?-.975:.975,1.25-row*.45+.32,.22),[...[1,2,3].map(n=>`DoorPivot_${side}${row*3+n}`),`RearDoorPivot_${side==='A'?'Left':'Right'}`],.16,1.16);
    add(new THREE.Vector3(0,.55,.17),['EquipmentDoorPivot','RearDoorPivot_Center'],.14,.88);
  }
}
function updateInteriorLights(delta){
  for(const item of refs.interiorLights){const open=item.doors.some(name=>refs.doors.get(name)?.open),goal=open||state.structure?item.intensity:item.closedIntensity;item.light.intensity=THREE.MathUtils.damp(item.light.intensity,goal,6,delta);}
}
function captureContext(){return {model,refs,metadata,metadataDocument,fitBox:fitBox.clone(),screenMesh,screenMaterial,structure:state.structure,glass:state.glass};}
function applyContext(context){({model,refs,metadata,metadataDocument,fitBox,screenMesh,screenMaterial}=context);state.structure=context.structure;state.glass=context.glass;}
function normalizeSingleMetadata(source){
  const document={...source,components:{},cable_paths:[]};
  const components=source?.components||{};
  if(!Object.keys(components).length)throw new Error('精细单仓组件参数不完整');
  for(const [key,value] of Object.entries(components))document.components[key]={...value,title:value.title||value.name||key,dimensions_mm:value.dimensions_mm||value.dimensions,basis:value.basis||'model'};
  document.components['single:interfaces']={title:'左侧电源与网络接口',basis:'model',notes:'整体查看接口面板、RJ45、AC插座及独立适配器托架。点击具体部件可查看各自尺寸。'};
  document.cable_paths=(source.cable_paths||[]).map(spec=>({...spec,bay_id:'S1',space:'single_local_gltf',parent_node:spec.parent_node||'SingleCabinetRoot',component_key:spec.component_key||'single:cables'}));
  return document;
}
function setupSingleModel(){
  model.updateMatrixWorld(true);
  refs.glassMaterial=new THREE.MeshPhysicalMaterial({color:0xd5e9ed,roughness:.07,metalness:0,transparent:true,opacity:.09,depthWrite:false,side:THREE.DoubleSide,clearcoat:1,clearcoatRoughness:.09,envMapIntensity:.75});
  const materials=new Set();
  model.traverse(node=>{
    if(node.name==='SingleDoorPivot'){saveOrigin(node);refs.doors.set(node.name,{node,bay:'S1',kind:'bay',swing:Number(node.userData.swing_degrees??node.userData.open_degrees??metadataDocument.interactions?.door?.angle_degrees??-100),open:false,title:'精细单仓玻璃门'});}
    if(node.name==='SingleTray'){saveOrigin(node);refs.trays.set('S1',{node,open:false,travel:Number(node.userData.travel_mm??320)/1000});}
    if(node.isMesh){if(inherited(node,'initial_hidden')===true)node.visible=false;const descriptor=describeMesh(node);if(descriptor.glass)node.material=refs.glassMaterial;node.castShadow=!descriptor.glass;node.receiveShadow=true;for(const material of Array.isArray(node.material)?node.material:[node.material])if(material&&!materials.has(material)){materials.add(material);if(material.emissiveIntensity>1.2)material.emissiveIntensity=1.2;}}
  });
  if(!refs.doors.size||!refs.trays.size)throw new Error('精细单仓门或托盘节点缺失');
  const laptop=model.getObjectByName('Laptop')||model.getObjectByName('SingleLaptop');if(laptop){saveOrigin(laptop);refs.laptops.set('S1',laptop);}
  prepareDynamicCables();prepareUsbConnections();optimizeMeshes(model);fitBox=currentBounds();addInteriorLights();
}
async function setModelMode(mode){
  if(state.switching||mode===state.mode||!state.loaded)return;
  state.switching=true;stopDemo();pauseRotation();closePanel();$('loadError').hidden=true;document.querySelectorAll('.toolbar button:not(#fullscreen)').forEach(button=>button.disabled=true);
  try{
    let asset;
    if(mode==='single'&&!modelContexts.has('single')){
      $('loading').hidden=false;$('loading').setAttribute('aria-label','正在加载精细单仓');
      singleAssetPromise??=Promise.all([new GLTFLoader().loadAsync('./assets/smart_cabinet_single_compartment.glb?v=20261108-room-v1'),fetch('./assets/single_compartment.json?v=20261108-room-v1').then(response=>{if(!response.ok)throw new Error('精细单仓参数无法读取');return response.json();})]).catch(error=>{singleAssetPromise=null;throw error;});
      asset=await singleAssetPromise;
    }
    // Complete in-flight mechanisms before suspending their context.
    for(const motion of tweens)motion.object[motion.property]=motion.to;tweens.length=0;orbitMotion=null;updateDynamicCables();
    modelContexts.set(state.mode,captureContext());model.visible=false;
    const previousMode=state.mode;state.mode=mode;
    try{
      if(modelContexts.has(mode))applyContext(modelContexts.get(mode));
      else{refs=makeRefs();metadataDocument=normalizeSingleMetadata(asset[1]);metadata=metadataDocument.components;model=asset[0].scene;screenMesh=null;screenMaterial=null;state.structure=false;state.glass=true;scene.add(model);setupSingleModel();setDoor('SingleDoorPivot',true);modelContexts.set(mode,captureContext());}
    }catch(error){model?.removeFromParent();state.mode=previousMode;applyContext(modelContexts.get(previousMode));throw error;}
    model.visible=true;controls.minDistance=mode==='single'?.18:.35;
    setPressed('singleView',mode==='single');setPressed('structureView',state.structure);setGlass(state.glass);
    $('singleView').title=mode==='single'?'返回18仓整柜':'单仓精细展示';$('singleView').setAttribute('aria-label',$('singleView').title);
    $('demoToggle').disabled=mode==='single';$('viewer').setAttribute('aria-label',mode==='single'?'精细单仓三维展示，可点击玻璃门、托盘和接口':'智能柜三维展示，可旋转、缩放并点击柜门和内部部件');
    setStageScale(mode==='single');fitView(mode==='single'?singleDefaultAngle:Math.PI/8,mode==='single'?.2:.12,true,mechanismTargetBounds());controls.update();renderer.shadowMap.needsUpdate=true;announce(mode==='single'?'精细单仓已就绪。可开关玻璃门，点击内部部件查看参数。':'已返回18仓整柜。');
  }catch(error){if(mode==='single'&&!modelContexts.has('single'))singleAssetPromise=null;model.visible=true;console.error('Model switch failed:',error);const message=`${error.message}，点击重试。整柜仍可操作。`;announce(message);$('singleView').title=message;$('singleView').setAttribute('aria-label',message);$('loadError').title=message;$('loadError').setAttribute('aria-label',message);$('loadError').hidden=false;loadErrorAction=()=>setMode(mode);}
  finally{state.switching=false;$('loading').hidden=true;document.querySelectorAll('.toolbar button:not(#fullscreen)').forEach(button=>button.disabled=false);$('demoToggle').disabled=state.mode==='single';}
}
function settleCabinetClosed(){
  stopDemo();pauseRotation();if(state.wiring)setWiring(false);closePanel();tweens.length=0;orbitMotion=null;
  // Retract first, then close: no suspended gate or callback survives a scene switch.
  for(const tray of refs.trays.values()){tray.node.position.copy(originals.get(tray.node).position);tray.open=false;}
  updateDynamicCables();
  for(const door of refs.doors.values()){door.node.rotation.copy(originals.get(door.node).rotation);door.open=false;}
  for(const node of refs.modules.values())node.position.copy(originals.get(node).position);
  refs.housings.forEach(mesh=>mesh.visible=true);state.structure=false;setPressed('structureView',false);restoreOccupancy();setGlass(true);model.updateMatrixWorld(true);updateDynamicCables();modelContexts.set(state.mode,captureContext());
}
function updateSceneControls(){
  for(const button of document.querySelectorAll('[data-scene-mode]')){const selected=button.dataset.sceneMode===state.sceneMode;button.setAttribute('aria-selected',String(selected));button.classList.toggle('active',selected);button.disabled=state.switching||!state.loaded;}
  const room=state.sceneMode==='room';$('stage').classList.toggle('room-mode',room);$('roomControls').hidden=!room;
  document.querySelectorAll('.toolbar button:not(#fullscreen),.room-controls button').forEach(button=>button.disabled=state.switching||!state.loaded||(button.id==='demoToggle'&&state.mode==='single')||(room&&camera.isOrthographicCamera&&['rotateLeft','rotateRight','autoRotate'].includes(button.id)));
  for(const [id,normal,label]of [['frontView','正面视图','机要室室内视角'],['backView','背面视图','机要室俯视'],['allDoors','开关当前侧全部柜门','开关全部正面柜门']]){$(id).title=room?label:normal;$(id).setAttribute('aria-label',$(id).title);}
  $('viewer').setAttribute('aria-label',room?'机要室布局与智能柜，可点击柜门、抽盘和房间部件':state.mode==='single'?'精细单仓三维展示，可点击玻璃门、托盘和接口':'智能柜三维展示，可旋转、缩放并点击柜门和内部部件');
  for(const [id,key]of [['roomOverview','overview'],['roomInterior','interior'],['roomTop','top']])setPressed(id,state.roomView===key);
  if(renderer?.domElement&&lastSceneModeLayout!==state.sceneMode){lastSceneModeLayout=state.sceneMode;resize();}
}
function setRoomCutaway(on){if(state.sceneMode!=='room')return;roomEnvironment.setCutaway(on);setPressed('roomCutaway',on);renderer.shadowMap.needsUpdate=true;}
function useRoomProjection(orthographic){
  if(Boolean(camera.isOrthographicCamera)===orthographic)return;orbitMotion=null;cancelTween(camera.position);cancelTween(controls.target);const previous=camera;
  if(orthographic){perspectiveCamera=camera;topCamera??=new THREE.OrthographicCamera(-3,3,3,-3,.025,80);camera=topCamera;camera.zoom=1;camera.up.set(0,0,-1);}else{camera=perspectiveCamera;camera.aspect=viewport.width/viewport.height;camera.updateProjectionMatrix();}
  camera.position.copy(previous.position);controls.object=camera;controls.enabled=!orthographic;
}
function fitRoomTop(bounds){
  const center=bounds.getCenter(new THREE.Vector3()),size=bounds.getSize(new THREE.Vector3()),aspect=viewport.width/viewport.height,region=state.selection?dimensionViewRegion():{left:-1,right:1,top:1,bottom:-1},wf=(region.right-region.left)/2,hf=(region.top-region.bottom)/2,span=Math.max(size.z/hf,size.x/(aspect*wf))*1.2,cx=(region.left+region.right)/2,cy=(region.top+region.bottom)/2;
  center.x-=cx*span*aspect/2;center.z+=cy*span/2;
  camera.left=-span*aspect/2;camera.right=span*aspect/2;camera.top=span/2;camera.bottom=-span/2;camera.zoom=1;camera.position.set(center.x,bounds.max.y+8,center.z);controls.target.copy(center);camera.lookAt(center);camera.updateProjectionMatrix();camera.updateMatrixWorld(true);
}
function setRoomView(view='overview',immediate=false){
  if(state.sceneMode!=='room'||!roomEnvironment?.active)return;stopDemo();pauseRotation();closePanel();state.roomView=view;setRoomCutaway(view!=='interior');
  useRoomProjection(view==='top');if(!camera.isOrthographicCamera){camera.fov=view==='interior'?65:35;camera.updateProjectionMatrix();}
  for(const [id,key]of [['roomOverview','overview'],['roomInterior','interior'],['roomTop','top']])setPressed(id,key===view);
  if(view==='interior'){
    const pose=roomEnvironment.metadata.camera?.interior||{position:[.12,1.6,2.38],target:[0,1.02,.05]};moveCamera(new THREE.Vector3(...pose.position),new THREE.Vector3(...pose.target),immediate?0:.9);
  }else fitView(view==='top'?0:Math.PI/7,view==='top'?1.38:.61,immediate,roomEnvironment.bounds().expandByScalar(.12));
  updateSceneControls();
}
async function setMode(next){
  if(!['cabinet','single','room'].includes(next)||!state.loaded||state.switching||next===state.sceneMode)return;
  if(state.wiring)setWiring(false);
  if(next==='room'){
    state.switching=true;updateSceneControls();$('loading').hidden=false;$('loading').setAttribute('aria-label','正在加载机要室环境');$('loadError').hidden=true;
    try{roomEnvironment??=new CabinetRoom(scene);await roomEnvironment.load();}
    catch(error){announce(`${error.message}；产品视图仍可使用。`);$('loadError').hidden=false;$('loadError').title='机要室载入失败，点击重试';$('loadError').setAttribute('aria-label',$('loadError').title);loadErrorAction=()=>setMode('room');state.switching=false;$('loading').hidden=true;updateSceneControls();return;}
    state.switching=false;
    if(state.mode!=='cabinet')await setModelMode('cabinet');
    if(state.mode!=='cabinet'){updateSceneControls();return;}
    settleCabinetClosed();roomEnvironment.activate(stageLights,groundPool);state.sceneMode='room';controls.minDistance=.35;controls.maxDistance=30;setRoomView('overview',true);$('loading').hidden=true;renderer.shadowMap.needsUpdate=true;announce('机要室已就绪。后距10 cm，后维护门保持关闭；可操作正面仓门与托盘。');
  }else{
    if(state.sceneMode==='room'){settleCabinetClosed();useRoomProjection(false);camera.fov=35;camera.updateProjectionMatrix();roomEnvironment.deactivate();state.sceneMode='cabinet';setStageScale(false);}
    await setModelMode(next);state.sceneMode=state.mode;
    if(next==='cabinet'&&state.mode==='cabinet'){controls.minDistance=.35;fitView(Math.PI/8,.12,true,fitBox);}
    renderer.shadowMap.needsUpdate=true;
  }
  updateSceneControls();
}
async function inspectWiringInModel(target){
  setWiring(false);stopDemo();pauseRotation();
  if(target==='usb'){
    await setMode('single');if(state.mode!=='single'||!refs.components.has('single:usb_system')){announce('当前单仓资产尚未包含USB网卡接线。');return;}if(state.structure)setStructure(false);setDoor('SingleDoorPivot',true);setTray('S1',true);selectSingleComponent('single:usb_system');return;
  }
  await setMode('cabinet');if(state.mode!=='cabinet'||!refs.components.has('wiring:fixed')){announce('当前整柜资产尚未包含后侧固定主干。');return;}
  if(state.structure)setStructure(false);for(const door of refs.doors.values())if(door.kind==='rear')setDoor(door,true);
  setWiringInspection(true);
  const descriptor={key:'wiring:fixed',bay:'',module:'',doorName:'',name:'后侧固定布线',housing:false};showComponent(descriptor);focusComponent({direction:new THREE.Vector3(.12,.14,-1).normalize()});
}
function selectSingleComponent(key){
  const meshes=refs.components.get(key);if(!meshes?.length)return;const door=refs.doors.get('SingleDoorPivot');if(door&&!door.open)setDoor(door,true);const descriptor={...(meshDescriptors.get(meshes[0])||describeMesh(meshes[0])),key};if(key==='single:interfaces')descriptor.doorName='';showComponent(descriptor);focusComponent();
}
function setStageScale(single){
  const scale=single?.26:1;groundPool.scale.set(scale,scale,scale);groundPool.position.y=fitBox.min.y-.008;
  groundPool.children[0].scale.set(single?.5:1,single?2.8:1,1);
  const center=fitBox.getCenter(new THREE.Vector3());stageLights.key.target.position.copy(center);stageLights.front.target.position.copy(center);stageLights.back.target.position.copy(center);
  stageLights.left.target.position.set(single?-.16:-1.05,center.y,0);stageLights.right.target.position.set(single?.16:1.05,center.y,0);
  stageLights.left.intensity=single?32:55;stageLights.right.intensity=single?29:50;
  stageLights.key.shadow.camera.left=single?-.85:-3.1;stageLights.key.shadow.camera.right=single?.85:3.1;stageLights.key.shadow.camera.top=single?.85:2.7;stageLights.key.shadow.camera.bottom=single?-.85:-2.7;stageLights.key.shadow.camera.updateProjectionMatrix();
}
function createStage(){
  scene=new THREE.Scene();scene.background=new THREE.Color(0x000000);scene.fog=new THREE.Fog(0x000000,13,30);
  const pmrem=new THREE.PMREMGenerator(renderer),room=new RoomEnvironment();scene.environment=pmrem.fromScene(room,.035).texture;scene.environmentIntensity=.22;room.dispose();pmrem.dispose();
  const hemi=new THREE.HemisphereLight(0xd9eaf7,0x111319,.36);scene.add(hemi);
  const key=new THREE.DirectionalLight(0xfff2e2,2.35);key.position.set(-3.6,5,4.5);key.target.position.set(0,.8,0);key.castShadow=true;key.shadow.mapSize.set(2048,2048);key.shadow.camera.near=.5;key.shadow.camera.far=14;key.shadow.bias=-.00012;key.shadow.normalBias=.003;key.shadow.radius=3.5;scene.add(key,key.target);
  const front=new THREE.DirectionalLight(0xdcefff,.56);front.position.set(1.7,1.8,4.5);scene.add(front,front.target);
  const left=new THREE.SpotLight(0x64c4ed,55,16,.46,.8,2);left.position.set(-4.1,3.2,-2.5);left.target.position.set(-1.05,.9,0);scene.add(left,left.target);
  const right=new THREE.SpotLight(0xffbd85,50,16,.46,.8,2);right.position.set(4.2,3.5,-2.8);right.target.position.set(1.05,.9,0);scene.add(right,right.target);
  const back=new THREE.DirectionalLight(0xd9e8f4,.68);back.position.set(-1.5,2,-5);scene.add(back,back.target);stageLights={key,front,left,right,back,hemi};
  // A feathered receiving surface catches real model shadows without a horizon.
  const canvas=document.createElement('canvas');canvas.width=512;canvas.height=512;const ctx=canvas.getContext('2d'),gradient=ctx.createRadialGradient(256,256,16,256,256,252);
  gradient.addColorStop(0,'rgba(129,151,171,.54)');gradient.addColorStop(.35,'rgba(105,132,155,.4)');gradient.addColorStop(.7,'rgba(66,94,120,.12)');gradient.addColorStop(1,'rgba(0,0,0,0)');ctx.fillStyle=gradient;ctx.fillRect(0,0,512,512);
  const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
  groundPool=new THREE.Mesh(new THREE.PlaneGeometry(6.8,4.5),new THREE.MeshStandardMaterial({color:0x394b5d,map:texture,transparent:true,roughness:.96,metalness:0,depthWrite:false}));groundPool.rotation.x=-Math.PI/2;groundPool.position.y=-.008;groundPool.receiveShadow=true;scene.add(groundPool);
  // Subtle contact occlusion stays attached to the footprint as the camera orbits.
  const contactCanvas=document.createElement('canvas');contactCanvas.width=256;contactCanvas.height=256;const c=contactCanvas.getContext('2d'),g=c.createRadialGradient(128,128,10,128,128,126);g.addColorStop(0,'rgba(0,0,0,.7)');g.addColorStop(.5,'rgba(0,0,0,.38)');g.addColorStop(1,'rgba(0,0,0,0)');c.fillStyle=g;c.fillRect(0,0,256,256);
  const contact=new THREE.Mesh(new THREE.PlaneGeometry(3.65,1.08),new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(contactCanvas),transparent:true,depthWrite:false}));contact.position.set(0,0,.002);groundPool.add(contact);
}
function requestedInitialMode(search){const mode=new URLSearchParams(search).get('view');return ['room','single'].includes(mode)?mode:'cabinet';}

async function init(){
  try{
    renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,1.7));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.98;renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFShadowMap;renderer.shadowMap.autoUpdate=false;
    $('viewer').append(renderer.domElement);createStage();
    camera=new THREE.PerspectiveCamera(35,1,.025,60);camera.position.set(1.3,1.6,4.2);
    controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,.925,0);controls.enableDamping=true;controls.dampingFactor=.08;controls.minDistance=.35;controls.maxDistance=16;controls.maxPolarAngle=Math.PI*.49;controls.minPolarAngle=Math.PI*.1;controls.enablePan=true;controls.autoRotateSpeed=.65;
    controls.addEventListener('start',()=>{orbitMotion=null;cancelTween(camera.position);cancelTween(controls.target);stopDemo();pauseRotation();});
    const observer=new ResizeObserver(resize);observer.observe($('viewer'));resize();
    const [gltf,meta]=await Promise.all([
      new GLTFLoader().loadAsync('./assets/smart_cabinet.glb?v=20261108-room-v1'),
      fetch('./assets/components.json?v=20261108-room-v1',{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error('组件参数文件无法读取');return response.json();})
    ]);
    if(!meta?.components||typeof meta.components!=='object'||!Array.isArray(meta.cable_paths))throw new Error('组件或动态线缆参数不完整');
    normalizeMetadata(meta);createFallbackMetadata();model=gltf.scene;scene.add(model);setupModel();
    state.loaded=true;document.querySelectorAll('.toolbar button:disabled').forEach(button=>button.disabled=false);
    modelContexts.set('cabinet',captureContext());setStageScale(false);setupPicking();fitView(Math.PI/8,.12,true);controls.update();$('loading').hidden=true;renderer.shadowMap.needsUpdate=true;
    window.cabinetShowcase={state,scene,renderer,get camera(){return camera;},controls,setDimensions,setWiring,inspectWiringInModel,setRoomView,setRoomCutaway,get room(){return roomEnvironment;},get wiring(){return wiringPanel;},get dimensions(){return dimensionLayer;},get refs(){return refs;},get model(){return model;},get metadata(){return metadata;},setDoor,setTray,setMode,resetView,setStructure,focusComponent,selectSingleComponent,showComponent,getDiagnostics:()=>({loaded:state.loaded,mode:state.mode,sceneMode:state.sceneMode,cachedModes:[...modelContexts.keys()],doors:refs.doors.size,rearDoors:[...refs.doors.values()].filter(d=>d.kind==='rear').length,trays:refs.trays.size,usbConnections:refs.usb.size,emptyBays:[...emptyBays],components:refs.components.size,dynamicCables:refs.cables.filter(cable=>cable.kind!=='stowed').length,stowedCables:refs.cables.filter(cable=>cable.kind==='stowed').length,cablesTotal:refs.cables.length,cableLengths:refs.cables.map(cable=>({id:cable.spec.id,length_mm:Math.round(cable.length*1000),rest_length_mm:cable.spec.rest_length_mm})),metadataEntries:Object.keys(metadata).length,meshes:(()=>{let n=0;model.traverse(o=>{if(o.isMesh)n++;});return n;})(),drawCalls:renderer.info.render.calls})};
    announce('机柜已就绪。可直接点击仓门、维护门与内部部件。');
    updateSceneControls();const initialMode=requestedInitialMode(location.search);if(initialMode!=='cabinet')await setMode(initialMode);
  }catch(error){console.error('Cabinet initialization failed:',error);$('loading').hidden=true;const message=location.protocol==='file:'?'请双击启动演示.command，经本地HTTP地址打开页面':`${error.message||'模型未能载入'}，请确认本地服务和assets文件完整后重试`;$('loadError').title=message;$('loadError').setAttribute('aria-label',message);$('loadError').hidden=false;announce(message);}
}
function resize(){
  const element=$('viewer');viewport={width:Math.max(element.clientWidth,1),height:Math.max(element.clientHeight,1)};
  if(!renderer||!camera)return;renderer.setSize(viewport.width,viewport.height);camera.aspect=viewport.width/viewport.height;camera.updateProjectionMatrix();if(state.loaded&&!state.selection&&!state.demo)resized=true;
}
function animate(time){
  requestAnimationFrame(animate);if(!renderer||!scene||!camera||!controls)return;
  const delta=Math.min((time-lastFrame)/1000,.05);lastFrame=time;
  if(resized){resized=false;if(!(state.sceneMode==='room'&&state.roomView==='interior')){const d=viewingDirection();fitView(Math.atan2(d.x,d.z),Math.asin(d.y));}}
  let moving=updateTweens(time);
  if(orbitMotion){
    const m=orbitMotion,p=Math.min((time-m.start)/m.duration,1),e=p<.5?4*p*p*p:1-Math.pow(-2*p+2,3)/2;
    const angle=THREE.MathUtils.lerp(m.fromAngle,m.toAngle,e),elevation=THREE.MathUtils.lerp(m.fromElevation,m.elevation,e),radius=THREE.MathUtils.lerp(m.fromRadius,m.radius,e);
    controls.target.lerpVectors(m.fromTarget,m.target,e);camera.position.copy(controls.target).add(new THREE.Vector3(Math.sin(angle)*Math.cos(elevation),Math.sin(elevation),Math.cos(angle)*Math.cos(elevation)).multiplyScalar(radius));
    if(p===1)orbitMotion=null;
  }
  if(state.loaded){
    updateDynamicCables();updateInteriorLights(delta);
    moving=updateDemoOccupancy(time)||moving;
    for(const [id,material]of refs.statuses){const active=state.demo&&state.demoBay===id;material.emissiveIntensity=active?1.1+Math.sin(time*.006)*.45:.9;}
  }
  if(moving)renderer.shadowMap.needsUpdate=true;if(!camera.isOrthographicCamera)controls.update(delta);if(state.dimensions){syncDimensions();camera.updateMatrixWorld();const p=$('componentPanel'),v=$('viewer').getBoundingClientRect(),r=p.getBoundingClientRect();dimensionLayer.render(camera,viewport,p.hidden?null:{left:r.left-v.left,top:r.top-v.top});}renderer.render(scene,camera);
  if(state.loaded&&!renderDiagnosticsLogged&&['127.0.0.1','localhost'].includes(location.hostname)){
    renderDiagnosticsLogged=true;console.info('[Cabinet WebGL] '+JSON.stringify({mode:state.mode,drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles,geometries:renderer.info.memory.geometries,textures:renderer.info.memory.textures,morphCables:refs.cables.filter(c=>c.kind==='morph').length,stowedCables:refs.cables.filter(c=>c.kind==='stowed').length}));
  }
}

$('zoomIn').addEventListener('click',()=>zoom(.82));$('zoomOut').addEventListener('click',()=>zoom(1.22));
document.querySelectorAll('[data-scene-mode]').forEach(button=>button.addEventListener('click',()=>setMode(button.dataset.sceneMode)));
document.querySelector('.scene-tabs').addEventListener('keydown',event=>{const buttons=[...document.querySelectorAll('[data-scene-mode]')],i=buttons.indexOf(event.target);if(i<0||!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const index=event.key==='Home'?0:event.key==='End'?2:(i+(event.key==='ArrowRight'?1:2))%3;buttons[index].focus();setMode(buttons[index].dataset.sceneMode);});
$('roomOverview').addEventListener('click',()=>setRoomView('overview'));$('roomInterior').addEventListener('click',()=>setRoomView('interior'));$('roomTop').addEventListener('click',()=>setRoomView('top'));$('roomCutaway').addEventListener('click',()=>setRoomCutaway(!roomEnvironment?.cutaway));$('roomInfo').addEventListener('click',()=>showComponent({key:'room:layout',bay:'',module:'',doorName:'',name:'机要室布局'}));

$('rotateLeft').addEventListener('click',()=>rotate(-Math.PI/8));$('rotateRight').addEventListener('click',()=>rotate(Math.PI/8));
$('autoRotate').addEventListener('click',()=>{stopDemo();closePanel();state.autoRotate=!state.autoRotate;controls.autoRotate=state.autoRotate;setPressed('autoRotate',state.autoRotate);});
$('resetView').addEventListener('click',resetView);
$('frontView').addEventListener('click',()=>{if(state.sceneMode==='room'){setRoomView('interior');return;}stopDemo();closePanel();fitView(0,.07);});$('backView').addEventListener('click',()=>{if(state.sceneMode==='room'){setRoomView('top');return;}stopDemo();closePanel();fitView(Math.PI,.07);});
$('dimensionsView').addEventListener('click',()=>setDimensions(!state.dimensions));
$('wiringView').addEventListener('click',()=>setWiring(!state.wiring));
document.querySelector('.toolbar').addEventListener('click',event=>{if(state.wiring&&event.target.closest('button')?.id!=='wiringView')setWiring(false);},true);
$('allDoors').addEventListener('click',toggleAllDoors);$('singleView').addEventListener('click',()=>setMode(state.mode==='single'?'cabinet':'single'));
$('inspectSingle').addEventListener('click',()=>setMode('single'));$('focusSinglePorts').addEventListener('click',()=>selectSingleComponent('single:interfaces'));$('focusSingleTray').addEventListener('click',()=>selectSingleComponent('single:tray'));
$('glassView').addEventListener('click',()=>setGlass(!state.glass));$('structureView').addEventListener('click',()=>setStructure(!state.structure));$('demoToggle').addEventListener('click',startDemo);
$('fullscreen').addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await $('stage').requestFullscreen();}catch{announce('当前浏览器不支持全屏。');}});
$('panelClose').addEventListener('click',()=>{closePanel();if(state.dimensions){const d=intendedViewingDirection();fitView(Math.atan2(d.x,d.z),Math.asin(d.y));}});$('focusComponent').addEventListener('click',focusComponent);
$('toggleComponentDoor').addEventListener('click',()=>{const door=state.selection&&relatedDoor(state.selection);if(door){stopDemo();setDoor(door,!door.open);}});
$('toggleComponentTray').addEventListener('click',()=>{const bay=state.selection?.bay,tray=refs.trays.get(bay);if(tray){stopDemo();setTray(bay,!tray.open);}});
$('loadError').addEventListener('click',()=>loadErrorAction());
window.addEventListener('keydown',event=>{if(state.wiring){if(event.key==='Escape')setWiring(false);return;}if(event.key==='Escape'){closePanel();stopDemo();}if(!state.loaded||state.switching||event.target.closest('button'))return;if(event.key==='+'||event.key==='=')zoom(.82);if(event.key==='-')zoom(1.22);if(event.key==='ArrowLeft'){event.preventDefault();rotate(-Math.PI/8);}if(event.key==='ArrowRight'){event.preventDefault();rotate(Math.PI/8);}});
document.addEventListener('visibilitychange',()=>{if(document.hidden){stopDemo();pauseRotation();}});
requestAnimationFrame(animate);init();
