import * as THREE from 'three';
import { loadModel, loadJSON } from './asset-loader.js?v=20261109-front-variants-v2';

// Environment only: the cabinet is never reparented, cloned, scaled or moved.
export class CabinetRoom {
  constructor(scene){this.scene=scene;this.model=null;this.metadata=null;this.promise=null;this.active=false;this.cutaway=true;this.components=new Map();this.saved=null;}
  async load(){
    if(this.model)return this;
    this.promise??=Promise.all([
      loadModel('./assets/room_environment.glb?v=20261109-front-variants-v2'),
      loadJSON('./assets/room_metadata.json?v=20261109-front-variants-v2')
    ]).then(([gltf,metadata])=>{
      if(!gltf.scene.getObjectByName('RoomEnvironmentRoot')||!metadata.components||!metadata.interior_bounds_m)throw new Error('机要室环境或布局参数不完整');
      if(gltf.scene.getObjectByName('CabinetRoot')||gltf.scene.getObjectByName('DoorPivot_A1'))throw new Error('机要室环境不能包含重复机柜');
      this.model=gltf.scene;this.metadata=metadata;this.model.name='CabinetRoomEnvironment';this.model.visible=false;
      this.model.traverse(node=>{if(!node.isMesh)return;node.castShadow=true;node.receiveShadow=true;let owner=node;while(owner&&!owner.userData?.component_key)owner=owner.parent;const key=owner?.userData.component_key||'room:layout';node.userData.roomComponentKey=key;if(!this.components.has(key))this.components.set(key,[]);this.components.get(key).push(node);});
      this.scene.add(this.model);this.lights=new THREE.Group();this.lights.name='RoomLighting';this.lights.visible=false;
      const ambient=new THREE.HemisphereLight(0xe7f4ff,0x6a777e,.75),key=new THREE.DirectionalLight(0xfff8ed,2.05);key.position.set(-1.8,4.6,3);key.target.position.set(0,.7,.5);key.castShadow=true;key.shadow.mapSize.set(2048,2048);Object.assign(key.shadow.camera,{left:-4,right:4,top:4,bottom:-4,near:.1,far:12});key.shadow.camera.updateProjectionMatrix();key.shadow.bias=-.00015;key.shadow.normalBias=.002;key.shadow.radius=4;
      this.lights.add(ambient,key,key.target);for(const x of [-1.55,1.55]){const light=new THREE.PointLight(0xf4f9ff,3.8,7,2);light.position.set(x,2.55,1);this.lights.add(light);}this.scene.add(this.lights);this.setCutaway(true);return this;
    }).catch(error=>{this.promise=null;throw error;});
    return this.promise;
  }
  bounds(){const data=this.metadata?.interior_bounds_m||{min:[-2.55,0,-.425],max:[2.55,2.8,2.575]};return new THREE.Box3(new THREE.Vector3(...data.min),new THREE.Vector3(...data.max));}
  setCutaway(on){this.cutaway=Boolean(on);for(const name of this.metadata?.cutaway_node_names||['RoomWall_Front','RoomWall_Right','RoomRoof']){const node=this.model?.getObjectByName(name);if(node)node.visible=!on;}}
  activate(stageLights,groundPool){
    if(this.active||!this.model)return;this.saved={background:this.scene.background,fog:this.scene.fog,environmentIntensity:this.scene.environmentIntensity,lights:Object.values(stageLights).map(light=>[light,light.visible]),groundVisible:groundPool.visible};
    for(const [light]of this.saved.lights)light.visible=false;groundPool.visible=false;this.ground=groundPool;this.scene.background=new THREE.Color(0x101b23);this.scene.fog=null;this.scene.environmentIntensity=.32;this.model.visible=true;this.lights.visible=true;this.active=true;this.setCutaway(true);
  }
  deactivate(){if(!this.active)return;this.model.visible=false;this.lights.visible=false;Object.assign(this.scene,{background:this.saved.background,fog:this.saved.fog,environmentIntensity:this.saved.environmentIntensity});for(const [light,visible]of this.saved.lights)light.visible=visible;this.ground.visible=this.saved.groundVisible;this.active=false;this.saved=null;}
  descriptor(object){let node=object;while(node&&!node.userData?.roomComponentKey)node=node.parent;return {key:node?.userData.roomComponentKey||'room:layout',bay:'',module:'',doorName:'',name:node?.name||'机要室布局',housing:false};}
  componentBox(key){const box=new THREE.Box3();for(const mesh of this.components.get(key)||[])box.expandByObject(mesh);return box.isEmpty()?this.bounds():box;}
}
