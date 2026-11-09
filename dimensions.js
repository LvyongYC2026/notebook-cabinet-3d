import * as THREE from 'three';
import { formatLengthCm } from './length-format.js?v=20261109-front-variants-v1';

const point=(x,y,z)=>new THREE.Vector3(x,y,z);
const cm=metres=>`${formatLengthCm(metres*1000)} cm`;
const progressCm=metres=>`${Math.round(metres*1000)/10} cm`;
const palette={body:0x88c9d6,tray:0xe7bc82};
const isVisible=object=>{for(let node=object;node;node=node.parent)if(!node.visible)return false;return true;};

// Measure only moving tray metal/handle/rail geometry. Laptop, plugs and flexible
// cables have their own envelopes; they must not redefine mechanical stroke.
export function measureTray(node,bay,mode,origin,travel,bodyDepth,cache=new WeakMap()){
  node.updateWorldMatrix(true,true);
  let local=cache.get(node);
  if(!local){
    local=new THREE.Box3();const inverse=node.matrixWorld.clone().invert(),key=mode==='single'?'single:tray':`tray:${bay}`,keys=new Set([key,...['drawer_front','drawer_body','drawer_handle','drawer_glass'].map(part=>mode==='single'?`single:${part}`:`${part}:${bay}`)]);
    node.traverse(mesh=>{if(!mesh.isMesh||!keys.has(mesh.userData.component_key)||!isVisible(mesh))return;mesh.geometry.computeBoundingBox();local.union(mesh.geometry.boundingBox.clone().applyMatrix4(inverse.clone().multiply(mesh.matrixWorld)));});
    if(local.isEmpty())return null;cache.set(node,local);
  }
  const matrix=new THREE.Matrix4().compose(origin.position,node.quaternion,node.scale);
  if(node.parent)matrix.premultiply(node.parent.matrixWorld);
  const closed=local.clone().applyMatrix4(matrix),axis=point(0,0,1).transformDirection(node.parent?.matrixWorld||new THREE.Matrix4());
  const extended=closed.clone().translate(axis.clone().multiplyScalar(travel)),progress=THREE.MathUtils.clamp(node.position.z-origin.position.z,0,travel);
  const front=bodyDepth/2,back=-bodyDepth/2;
  return {bay,closed,extended,travel,progress,front,back,inset:front-closed.max.z,protrusion:Math.max(0,extended.max.z-front),totalDepth:extended.max.z-back};
}

export class CabinetDimensions{
  constructor(scene,host=null,note=null){
    this.group=new THREE.Group();this.group.name='DimensionAnnotations';this.group.visible=false;this.group.userData.ignorePicking=true;scene.add(this.group);
    this.host=host;this.note=note;this.enabled=false;this.labels=[];this.cache=new WeakMap();this.bounds=new THREE.Box3();this.trayBounds=new THREE.Box3();this.signature='';this.context=null;this.summary=null;
    this.bodyBounds=new THREE.Box3();this.layoutKey='';this.pairDirections=new Map();this.layoutStats={domBuilds:0,layouts:0,frames:0,maxCorrectionStep:0,maxAnchorStep:0};
    if(host)host.hidden=true;if(note)note.hidden=true;
  }
  invalidateGeometry(){this.cache=new WeakMap();this.signature='';}
  setEnabled(enabled){this.enabled=Boolean(enabled);this.group.visible=this.enabled;if(this.host)this.host.hidden=!this.enabled;if(this.note)this.note.hidden=!this.enabled;if(!this.enabled)this.clear();}
  clear(){this.group.traverse(child=>{child.geometry?.dispose();child.material?.dispose();});this.group.clear();this.labels=[];this.host?.replaceChildren();this.signature='';this.layoutKey='';this.pairDirections.clear();this.bounds.makeEmpty();this.trayBounds.makeEmpty();this.trayGroup=null;this.drawingGroup=null;}
  sync(context){
    this.context=context;if(!this.enabled||!context.model)return;
    if(context.sceneMode==='room'&&(!context.selection||context.selection.key.startsWith('room:'))){this.syncRoom(context);return;}
    const {model,metadata,refs,originals,mode,selection,focused=false,direction}=context;
    const dimensions=metadata.cabinet_dimensions_mm;if(!Array.isArray(dimensions)||dimensions.length!==3)return;
    const [width,depth,height]=dimensions.map(value=>Number(value)/1000),bay=mode==='single'?'S1':refs.trays.has(selection?.bay)?selection.bay:'A7',tray=refs.trays.get(bay);if(!tray)return;
    model.updateMatrixWorld(true);
    const data=measureTray(tray.node,bay,mode,originals.get(tray.node),tray.travel,depth,this.cache);if(!data)return;
    data.accessType=tray.accessType||'hinged';this.summary={mode,bay,closedDimensionsMm:[...dimensions],...data};
    // Fixed world-side dimensions do not flip when the camera crosses an axis.
    // Parent/module translation moves the tray group, never rebuilds its DOM.
    const signature=[model.uuid,bay,focused,width,depth,height,context.sceneMode].join('|');
    if(signature!==this.signature){this.clear();this.signature=signature;this.build(width,depth,height,data,1,1,focused);this.layoutStats.domBuilds++;}
    const shift=data.closed.min.clone().sub(this.builtTrayClosed.min);this.trayGroup.position.copy(shift);
    for(const item of this.labels)if(item.tray)item.anchor.copy(item.baseAnchor).add(shift);
    this.trayBounds.copy(data.extended).union(data.closed).expandByScalar(mode==='single'?.075:.09);this.bounds.copy(this.bodyBounds).union(this.trayBounds);
    const label=this.labels.find(item=>item.id==='stroke');
    if(label){const detail=`当前 ${progressCm(data.progress)}`;if(label.detail!==detail){label.detail=detail;if(label.secondary)label.secondary.textContent=detail;}}
    if(this.progressLine){const base=this.builtTrayClosed,a=this.progressLine.geometry.attributes.position;a.setXYZ(0,base.min.x,base.max.y+.009,base.max.z+data.progress);a.setXYZ(1,base.max.x,base.max.y+.009,base.max.z+data.progress);a.needsUpdate=true;this.progressLine.geometry.computeBoundingSphere();}
  }
  syncRoom(context){
    const metadata=context.roomMetadata||{},b=metadata.interior_bounds_m||{min:[-2.55,0,-.425],max:[2.55,2.8,2.575]},min=point(...b.min),max=point(...b.max),size=max.clone().sub(min),operation=Number(metadata.operation_zone_mm||1200)/1000,rear=Number(metadata.rear_clearance_mm||100)/1000;
    this.summary={mode:'room',bay:null,closedDimensionsMm:[size.x*1000,size.z*1000,size.y*1000],operation,rear};
    const signature=['room',context.model.uuid,...b.min,...b.max,operation,rear].join('|');if(signature===this.signature)return;
    this.clear();this.signature=signature;this.layoutStats.domBuilds++;
    const y=max.y+.12,z=max.z+.1,x=min.x-.12;
    this.dimension('room-width',point(min.x,y,z),point(max.x,y,z),`室内宽 ${cm(size.x)}`,'净尺寸',point(0,1,0));
    this.dimension('room-depth',point(max.x+.12,.06,min.z),point(max.x+.12,.06,max.z),`室内深 ${cm(size.z)}`,'净尺寸',point(1,0,0));
    this.dimension('room-height',point(x,0,min.z),point(x,max.y,min.z),`室内高 ${cm(size.y)}`,'净尺寸',point(1,0,0));
    this.dimension('room-operation',point(-1.9,.04,.325),point(-1.9,.04,.325+operation),`柜前操作区 ${cm(operation)}`,'从闭合柜面起算',point(1,0,0),palette.tray);
    this.dimension('room-rear',point(.5,1.96,min.z),point(.5,1.96,-.325),`后距 ${cm(rear)}`,'后门不可开启',point(1,0,0),palette.tray);
    this.bodyBounds.copy(this.bounds);this.trayBounds.copy(this.bounds);
    if(this.note)this.note.textContent='机要室净尺寸 · 布置设计示意\n柜前120 cm为建议操作区；后距10 cm不具备背面检修空间';
  }
  line(segments,color=palette.body,dashed=false,opacity=.72){
    const geometry=new THREE.BufferGeometry().setFromPoints(segments),material=dashed?new THREE.LineDashedMaterial({color,dashSize:.035,gapSize:.025,transparent:true,opacity,depthTest:false,depthWrite:false}):new THREE.LineBasicMaterial({color,transparent:true,opacity,depthTest:false,depthWrite:false});
    const line=new THREE.LineSegments(geometry,material);if(dashed)line.computeLineDistances();line.renderOrder=20;line.userData.ignorePicking=true;(this.drawingGroup||this.group).add(line);return line;
  }
  dimension(id,a,b,title,detail,tickAxis,color=palette.body,extensions=[]){
    const tick=tickAxis.clone().multiplyScalar(this.context.mode==='single'?.012:.022);
    this.line([a,b,a.clone().sub(tick),a.clone().add(tick),b.clone().sub(tick),b.clone().add(tick)],color);
    if(extensions.length)this.line(extensions,color,true,.35);
    for(const p of [a,b,...extensions])this.bounds.expandByPoint(p);
    const anchor=a.clone().add(b).multiplyScalar(.5),label={id,anchor,baseAnchor:anchor.clone(),tray:Boolean(this.trayGroup),title,detail,color};
    if(this.host){
      const node=document.createElement('div');node.className=`dimension-label${color===palette.tray?' dimension-label-tray':''}`;node.dataset.dimension=id;
      const strong=document.createElement('strong'),small=document.createElement('small');strong.textContent=title;small.textContent=detail;node.append(strong,small);small.hidden=!detail;
      const leader=document.createElement('i');leader.className='dimension-leader';this.host.append(leader,node);label.node=node;label.secondary=small;label.leader=leader;
    }
    this.labels.push(label);
  }
  build(width,depth,height,data,side,frontSide,focused){
    const small=this.context.mode==='single',pad=small?.065:.16,half=width/2,front=depth/2,z=frontSide*(front+pad*.5),y=height+pad;
    if(!focused){
      this.dimension('width',point(-half,y,z),point(half,y,z),`宽 ${cm(width)}`,'',point(0,1,0),palette.body,[point(-half,height,z),point(-half,y+pad*.15,z),point(half,height,z),point(half,y+pad*.15,z)]);
      const x=-side*(half+pad);
      this.dimension('height',point(x,0,z),point(x,height,z),`高 ${cm(height)}`,'',point(1,0,0),palette.body,[point(-side*half,0,z),point(x,0,z),point(-side*half,height,z),point(x,height,z)]);
      const dx=side*(half+pad),dy=small?.03:.07;
      this.dimension('depth',point(dx,dy,-front),point(dx,dy,front),`深 ${cm(depth)}`,'',point(1,0,0),palette.body,[point(side*half,dy,-front),point(dx,dy,-front),point(side*half,dy,front),point(dx,dy,front)]);
    }
    this.bodyBounds.copy(this.bounds);this.builtTrayClosed=data.closed.clone();this.trayGroup=new THREE.Group();this.group.add(this.trayGroup);this.drawingGroup=this.trayGroup;
    const box=data.extended,size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3()),outlineSource=new THREE.BoxGeometry(size.x,size.y,size.z),wire=new THREE.EdgesGeometry(outlineSource);outlineSource.dispose();
    wire.translate(center.x,center.y,center.z);const envelope=new THREE.LineSegments(wire,new THREE.LineDashedMaterial({color:palette.tray,dashSize:.025,gapSize:.017,transparent:true,opacity:.42,depthWrite:false,depthTest:false}));envelope.computeLineDistances();envelope.renderOrder=18;envelope.userData.ignorePicking=true;this.trayGroup.add(envelope);
    const tint=new THREE.Mesh(new THREE.BoxGeometry(size.x,size.y,size.z),new THREE.MeshBasicMaterial({color:palette.tray,transparent:true,opacity:.035,depthWrite:false}));tint.position.copy(center);tint.userData.ignorePicking=true;this.trayGroup.add(tint);
    const sx=box.min.x-(small?.04:.06),sy=box.max.y+(small?.045:.065),ex=box.max.x+(small?.04:.06),ey=box.min.y-(small?.025:.04);
    this.dimension('stroke',point(sx,sy,data.closed.max.z),point(sx,sy,box.max.z),`${data.bay} 行程 ${cm(data.travel)}`,`当前 ${progressCm(data.progress)}`,point(1,0,0),palette.tray,[point(box.min.x,box.max.y,data.closed.max.z),point(sx,sy,data.closed.max.z),point(box.min.x,box.max.y,box.max.z),point(sx,sy,box.max.z)]);
    this.dimension('extension',point(ex,ey,data.front),point(ex,ey,box.max.z),`最大前伸 ${cm(data.protrusion)}`,`后侧至盘前缘 ${cm(data.totalDepth)}`,point(1,0,0),palette.tray,[point(box.max.x,ey,data.front),point(ex,ey,data.front),point(box.max.x,ey,box.max.z),point(ex,ey,box.max.z)]);
    this.progressLine=this.line([point(0,0,0),point(0,0,0)],palette.tray,false,.95);
    this.trayBounds.copy(box).union(data.closed).expandByScalar(small?.075:.09);this.bounds.union(this.trayBounds);
    if(this.note)this.note.textContent=`闭合外形 ${cm(width)} × ${cm(depth)} × ${cm(height)}（宽×深×高） · 设计示意\n虚线为 ${data.bay} 全抽${data.accessType==='drawer'?'抽屉':'托盘'}范围；不含门扇及人员通道`;
  }
  getBounds(trayOnly=false){return (trayOnly?this.trayBounds:this.bounds).clone();}
  render(camera,viewport,panel=null,time=performance.now()){
    if(!this.enabled||!this.host||!this.summary)return;
    const w=viewport.width,h=viewport.height,mobile=w<=620,pad=mobile?10:18,dt=Math.min(.05,Math.max(.001,(time-(this.lastRenderTime??time-16.67))/1000));this.lastRenderTime=time;
    const region={left:pad,right:w-pad,top:pad,bottom:h-pad};
    if(panel){if(mobile)region.bottom=Math.min(region.bottom,panel.top-12);else region.right=Math.min(region.right,panel.left-16);}
    const key=[this.signature,w,h,Boolean(panel),this.context.selection?.key||''].join('|'),relayout=key!==this.layoutKey;
    if(relayout){this.layoutKey=key;this.pairDirections.clear();this.layoutStats.layouts++;}
    const occupied=[],items=[],modelCenter=point(0,this.summary.closedDimensionsMm[2]/2000,0).project(camera),cx=(modelCenter.x+1)*w/2,cy=(1-modelCenter.y)*h/2;
    const clamp=item=>{item.x=THREE.MathUtils.clamp(item.x,region.left,region.right-item.w);item.y=THREE.MathUtils.clamp(item.y,region.top,region.bottom-item.h);};
    for(const label of this.labels){
      const projected=label.anchor.clone().project(camera),node=label.node;if(!node)continue;
      if(projected.z<-1||projected.z>1||Math.abs(projected.x)>2.3||Math.abs(projected.y)>2.3){node.hidden=true;label.leader.hidden=true;label.previousAnchor=null;continue;}
      // Set visible before measuring: display:none otherwise collapses width.
      node.hidden=false;
      const ax=(projected.x+1)*w/2,ay=(1-projected.y)*h/2,lw=node.offsetWidth||148,lh=node.offsetHeight||(label.detail?46:30);
      if(region.right-region.left<lw||region.bottom-region.top<lh){node.hidden=true;label.leader.hidden=true;continue;}
      if(relayout||!label.offset){
        const dx=ax-cx,dy=ay-cy,length=Math.hypot(dx,dy)||1,offset=mobile?18:24,candidates=[[ax+dx/length*offset-lw/2,ay+dy/length*offset-lh/2]];
        for(const r of [24,48,78,112,152])for(const [x,y]of [[0,-1],[0,1],[-1,0],[1,0],[-1,-1],[1,-1],[-1,1],[1,1]])candidates.push([ax+x*r-lw/2,ay+y*r-lh/2]);
        let best=null,score=Infinity;
        for(const [x,y]of candidates){const box={x,y,w:lw,h:lh};clamp(box);let value=Math.hypot(box.x+lw/2-ax,box.y+lh/2-ay);for(const b of occupied)value+=Math.max(0,Math.min(box.x+lw+6,b.x+b.w)-Math.max(box.x-6,b.x))*Math.max(0,Math.min(box.y+lh+6,b.y+b.h)-Math.max(box.y-6,b.y))*12;if(value<score){score=value;best=box;}}
        label.offset={x:best.x-ax,y:best.y-ay};label.position=null;
      }
      const item={label,ax,ay,w:lw,h:lh,x:ax+label.offset.x,y:ay+label.offset.y};clamp(item);items.push(item);occupied.push(item);
    }
    // Continuous separation keeps the chosen slots; there is no per-frame
    // candidate switch. Pair directions persist until the UI context changes.
    for(let pass=0;pass<7;pass++)for(let i=0;i<items.length;i++)for(let j=i+1;j<items.length;j++){
      const a=items[i],b=items[j],ox=Math.min(a.x+a.w+6,b.x+b.w+6)-Math.max(a.x,b.x),oy=Math.min(a.y+a.h+6,b.y+b.h+6)-Math.max(a.y,b.y);if(ox<=0||oy<=0)continue;
      const pair=`${a.label.id}|${b.label.id}`;let direction=this.pairDirections.get(pair);
      if(!direction){const axis=oy<ox?'y':'x',ac=a[axis]+a[axis==='x'?'w':'h']/2,bc=b[axis]+b[axis==='x'?'w':'h']/2;direction={axis,sign:ac<=bc?1:-1};this.pairDirections.set(pair,direction);}
      const {axis,sign}=direction,amount=(axis==='x'?ox:oy)+.4,oldA=a[axis],oldB=b[axis];a[axis]-=sign*amount/2;b[axis]+=sign*amount/2;clamp(a);clamp(b);
      const applied=Math.abs(a[axis]-oldA)+Math.abs(b[axis]-oldB),remaining=Math.max(0,amount-applied);if(remaining>.01){if(Math.abs(a[axis]-oldA)<amount*.49)b[axis]+=sign*remaining;else a[axis]-=sign*remaining;clamp(a);clamp(b);}
    }
    for(const item of items){
      const {label,ax,ay,w:lw,h:lh}=item,previous=label.position,anchor=label.previousAnchor;
      if(!previous||!anchor||relayout)label.position={x:item.x,y:item.y};
      else{
        const mx=ax-anchor.x,my=ay-anchor.y,baseX=previous.x+mx,baseY=previous.y+my,alpha=1-Math.exp(-dt*9);let dx=(item.x-baseX)*alpha,dy=(item.y-baseY)*alpha;const length=Math.hypot(dx,dy),limit=420*dt;if(length>limit){dx*=limit/length;dy*=limit/length;}
        label.position={x:baseX+dx,y:baseY+dy};this.layoutStats.maxCorrectionStep=Math.max(this.layoutStats.maxCorrectionStep,Math.hypot(dx,dy));this.layoutStats.maxAnchorStep=Math.max(this.layoutStats.maxAnchorStep,Math.hypot(mx,my));
      }
      label.position.x=THREE.MathUtils.clamp(label.position.x,region.left,region.right-lw);label.position.y=THREE.MathUtils.clamp(label.position.y,region.top,region.bottom-lh);
      label.previousAnchor={x:ax,y:ay};const {x:left,y:top}=label.position;label.node.style.transform=`translate(${left.toFixed(2)}px,${top.toFixed(2)}px)`;
      const tx=THREE.MathUtils.clamp(ax,left+4,left+lw-4),ty=THREE.MathUtils.clamp(ay,top+4,top+lh-4),distance=Math.hypot(tx-ax,ty-ay);
      label.leader.hidden=distance<6;label.leader.style.width=`${distance.toFixed(2)}px`;label.leader.style.transform=`translate(${ax.toFixed(2)}px,${ay.toFixed(2)}px) rotate(${Math.atan2(ty-ay,tx-ax)}rad)`;
    }
    this.layoutStats.frames++;
  }
}
