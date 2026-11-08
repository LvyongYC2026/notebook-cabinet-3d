// A design overlay only: no GLB nodes, device configuration or upload services
// are changed by selecting a wiring mode.
export const wiringPorts=[
  ...Array.from({length:18},(_,index)=>({port:index+1,endpoint:`${index<9?'A':'B'}${index%9+1}`,kind:'bay'})),
  {port:19,endpoint:'服务器',kind:'service'},
  {port:20,endpoint:'锁控采集控制器',kind:'management'},
  {port:21,endpoint:'受控 PDU',kind:'management'},
  {port:22,endpoint:'UPS 管理',kind:'management'},
  {port:23,endpoint:'外部管理预留',kind:'reserved'},
  {port:24,endpoint:'备用',kind:'spare'}
];
export const wiringReferences=[
  {label:'USB 以太网接入架构',url:'https://media.startech.com/cms/pdfs/usb31000s2_datasheet.pdf',source:'StarTech.com 产品资料；仅作架构参考，不指定采购型号'},
  {label:'USB 主机与设备角色',url:'https://docs.kernel.org/driver-api/usb/gadget.html',source:'Linux 内核文档'},
  {label:'柜内分区布线',url:'https://www.electrical-installation.org/enwiki/EMC_implementation_-_Cabinet_cabling',source:'Schneider Electric 电气安装指南'},
  {label:'活动线缆与弯曲导向',url:'https://www.igus.co.uk/energy-chain/wiki/filling-rule',source:'igus 官方布线原则；具体弯曲半径按所选线材核定'},
  {label:'UPS 负载与后备选型',url:'https://www.se.com/ca/en/work/support/product-support/ups-buying-guide-for-selecting-a-battery-backup-system/',source:'Schneider Electric 官方指南'}
];
const modes={
  usb:{title:'USB 数据接入',status:'布线设计 · 待选型落模',description:'笔记本通过 USB 网卡进入柜内以太网，再向服务器传文件。网卡固定在托盘上；每仓仍只使用一个交换机端口。',steps:[['笔记本','USB host','usb'],['USB 以太网网卡','固定于同一托盘 · device','usb'],['固定仓 RJ45','蓝色活动网线 → 后侧主干','data'],['24 口交换机','18 仓各占 1 口','data'],['文件服务器','有线网络 → 授权接收服务','data']]},
  native:{title:'原生 RJ45 接入',status:'当前 3D · 仓内接线示意',description:'笔记本原生 RJ45 通过蓝色活动网线接同仓固定接口，再汇入中央交换机。这是现有模型与借还动画所表达的接入方式。',steps:[['笔记本原生 RJ45','蓝色活动网线','data'],['固定仓 RJ45','每仓独立星形支线','data'],['24 口交换机','18 仓各占 1 口','data'],['文件服务器','有线网络 → 授权接收服务','data']]}
};
const escape=text=>String(text).replace(/[&<>"']/g,character=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
const box=(x,y,w,h,title,detail,kind)=>`<g class="wire-node wire-${kind}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="10"/><text x="${x+w/2}" y="${y+31}" class="wire-node-title">${escape(title)}</text><text x="${x+w/2}" y="${y+55}" class="wire-node-detail">${escape(detail)}</text></g>`;
const connection=(path,kind)=>`<path class="wire-connection wire-${kind}" d="${path}" marker-end="url(#wire-arrow-${kind})"/>`;
const defs=prefix=>`<defs>${['data','usb','power'].map(kind=>`<marker id="${prefix}-${kind}" markerWidth="8" markerHeight="8" refX="6.6" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 8 4 0 8Z" class="wire-arrow wire-${kind}"/></marker>`).join('')}</defs>`;
export function networkDiagram(mode,mobile=false){
  const selected=modes[mode]||modes.usb,steps=selected.steps,n=steps.length,w=mobile?300:1020,h=mobile?n*100+14:137,nodeW=mobile?270:174,nodeH=76,gap=mobile?100:(w-28-nodeW)/(n-1),prefix=`wire-${mode}-${mobile?'m':'d'}`;
  const nodes=steps.map(([title,detail,kind],i)=>box(mobile?15:14+i*gap,mobile?8+i*gap:16,nodeW,nodeH,title,detail,kind)).join('');
  const lines=steps.slice(1).map((_,i)=>connection(mobile?`M150 ${84+i*gap}V${8+(i+1)*gap-7}`:`M${14+i*gap+nodeW} 54H${14+(i+1)*gap-7}`,mode==='usb'&&i===0?'usb':'data')).join('').replaceAll('wire-arrow-',`${prefix}-`);
  return `<svg class="wire-diagram ${mobile?'wire-mobile':'wire-desktop'}" viewBox="0 0 ${w} ${h}" role="img" aria-label="${escape(selected.steps.map(step=>step[0]).join('，连接至'))}">${defs(prefix)}${lines}${nodes}</svg>`;
}
export function powerDiagram(mobile=false){
  const steps=[['总保护与检修隔离','现场进线 · PE 保护接地'],['18 路受控分支','左 9 路 / 右 9 路'],['各仓 AC 插座','固定交流支路'],['原装电源适配器','固定在独立适配器篮'],['笔记本 DC 输入','黑色低压活动线']];
  const prefix=`wire-power-${mobile?'m':'d'}`,w=mobile?330:1020,h=mobile?754:292,gap=mobile?96:206,nodeW=mobile?270:174;
  let nodes=steps.map(([title,detail],i)=>box(mobile?45:14+i*gap,mobile?10+i*gap:12,nodeW,76,title,detail,'power')).join('');
  let lines=steps.slice(1).map((_,i)=>connection(mobile?`M180 ${86+i*gap}V${10+(i+1)*gap-7}`:`M${14+i*gap+nodeW} 50H${14+(i+1)*gap-7}`,'power')).join('');
  if(mobile){nodes+=box(45,545,270,76,'UPS 关键设备后备','容量与时长按实际负载验证','power')+box(45,661,270,76,'服务器 / 交换机 / 控制器','不承诺 18 台电脑全部后备','power');lines+=connection('M45 48H16V583H38','power')+connection('M180 621V654','power');}
  else {nodes+=box(260,181,240,76,'UPS 关键设备后备','容量与时长按实际负载验证','power')+box(586,181,360,76,'服务器 / 交换机 / 控制器','不承诺 18 台电脑全部后备','power');lines+=connection('M101 88V219H253','power')+connection('M500 219H579','power');}
  return `<svg class="wire-diagram ${mobile?'wire-mobile':'wire-desktop'}" viewBox="0 0 ${w} ${h}" role="img" aria-label="现场供电经总保护分别接18路受控仓位分支与UPS关键设备分支；电脑经原适配器供电">${defs(prefix)}${lines.replaceAll('wire-arrow-',`${prefix}-`)}${nodes}</svg>`;
}
function portTable(){
  return `<table class="wiring-port-table"><caption>18 仓固定端口映射</caption><thead><tr><th>端口</th><th>左柜仓位</th><th>端口</th><th>右柜仓位</th></tr></thead><tbody>${Array.from({length:9},(_,index)=>`<tr><td>${String(index+1).padStart(2,'0')}</td><td>A${index+1}${index===2?'<small>模型空仓</small>':''}</td><td>${String(index+10).padStart(2,'0')}</td><td>B${index+1}${[1,5].includes(index)?'<small>模型空仓</small>':''}</td></tr>`).join('')}</tbody></table><dl class="wiring-infrastructure">${wiringPorts.slice(18).map(port=>`<div><dt>${port.port}</dt><dd>${port.endpoint}</dd></div>`).join('')}</dl><p class="wiring-caption">空仓保留端口。控制器、PDU 或 UPS 无网络管理接口时，对应端口转为备用；增设独立管理设备时重新核算。</p>`;
}
export function wiringContent(mode='usb',modelStatus={}){
  const selected={...(modes[mode]||modes.usb)};
  if(modelStatus.usb){selected.status=mode==='native'?'替代接入说明 · 当前3D为USB网卡':'3D结构设计 · 待选型验证';if(mode==='native')selected.description='原生RJ45直连是可选接入方式，与USB网卡共用同仓网络端口、每仓择一。本次三维采用托盘USB网卡，未叠加第二套原生RJ45接线。';}
  const parking=mode==='native'?'借出电脑后，蓝色网线和黑色 DC 端均归固定停车卡座。现有 15 台电脑、A3 / B2 / B6 三个空仓的动画采用此逻辑。':'借出电脑后，USB 网卡留在托盘；蓝网线继续连接网卡并随盘。USB 电脑端停靠随盘卡座，黑色 DC 端归固定卡座。此逻辑需新增模型与动画，当前 3D 尚未实现。';
  const parkingText=modelStatus.usb?(mode==='native'?'原生RJ45替代模式下，借出后网线与DC端均可固定停车；此模式仅作连接说明，当前三维动画采用USB网卡留柜逻辑。':'借出电脑后，USB网卡留在托盘；蓝网线继续连接网卡并随盘。USB电脑端停靠随盘卡座，黑色DC端归固定卡座；当前三维已实现该占用切换示意。'):parking;
  const modelText=modelStatus.usb?'当前模型已呈现托盘USB网卡、USB短线、动态网线与DC的分开停靠逻辑'+(modelStatus.fixed?'，以及后侧固定主干和分区线槽。':'。')+'这些均为结构设计示意，器件与路由仍须选型、工程深化及端到端验收。':'现有仓内原生 RJ45 与 DC 随动接线可演示；USB 网卡未建模，中央接线及后侧固定主干仍是示意，不能作为 18 路端到端接线已完成的证明。';
  const modelActions=`<div class="wiring-model-actions"><button type="button" data-wiring-action="trunks" ${modelStatus.fixed?'':'disabled'} title="${modelStatus.fixed?'打开后维护门，查看固定主干和分区线槽':'三维固定主干资产准备中'}">在柜内查看布线 <span aria-hidden="true">↗</span></button><button type="button" data-wiring-action="usb" ${modelStatus.usb?'':'disabled'} title="${modelStatus.usb?'打开单仓托盘，聚焦USB网卡与活动线':'三维USB接线资产准备中'}">查看单仓 USB 接线 <span aria-hidden="true">↗</span></button></div>`;
  return `<section class="wiring-network"><div class="wiring-section-heading"><h3>${selected.title}</h3><span class="wiring-status">${selected.status}</span></div><p class="wiring-intro">${selected.description}</p><div class="wiring-legend"><span class="data">Ethernet 数据</span><span class="usb">USB 数据短线</span><span class="power">供电路径</span></div>${networkDiagram(mode)}${networkDiagram(mode,true)}${modelActions}<p class="wiring-keypoint">两种接入方式<strong>每仓择一，共用一个网络端口</strong>。USB 网卡不增加交换机端口数；不使用普通 USB Hub 将多台电脑主机直连服务器。</p></section>
  <div class="wiring-grid"><section class="wiring-card"><div class="wiring-section-heading"><h3>24 口分配</h3><span class="wiring-port-budget">23 <small>/ 24</small></span></div><p class="wiring-caption">18 仓 + 服务器 1 + 控制器 1 + PDU 1 + UPS 1 + 管理预留 1；剩余 1 口。</p>${portTable()}</section>
  <section class="wiring-card wiring-routing"><h3>固定主干与抽盘活动段</h3><ol><li><strong>后侧固定主干</strong><p>各仓独立星形数据线汇入交换机。AC、数据与低压控制分槽或使用核定隔板，沿后侧固定框架布置，不绑在维护门上。</p></li><li><strong>32 cm 抽盘行程</strong><p>活动段只有黑色 DC 线与蓝色网线；适配器及其 AC 线固定。两端设置应力释放与导向，线缆循环弯曲半径按实际选型核定。</p></li>${mode==='usb'?'<li><strong>USB 短线随托盘</strong><p>笔记本与网卡同随盘，USB 短线不承担整段抽盘相对位移。网卡使用可更换、通风的托盘夹座，保留插拔与停车空间。</p></li>':''}<li><strong>借出与空仓</strong><p>${parkingText}</p></li></ol></section></div>
  <section class="wiring-card wiring-power"><h3>供电与关键设备后备</h3><p class="wiring-caption">18 路电脑供电与 UPS 关键设备后备分开设计。网络管理链路只传命令和状态，不向笔记本供电。</p>${powerDiagram()}${powerDiagram(true)}<p class="wiring-caption">PE 连续连接需保护接地的柜架、门体与设备，不经支路开关或 UPS 输出切换。总保护、线径、PDU 及插座额定值须依据真实负载、启动冲击和现场条件深化；不以 USB 接口形状推断充电能力。</p></section>
  <section class="wiring-engineering"><h3>设计边界与下一步</h3><div class="wiring-grid"><p><strong>当前模型</strong>${modelText}</p><p><strong>设备与服务</strong>网卡需核对 Type-A / Type-C 数据端口、系统与驱动；带宽、散热、活动线耐弯与 UPS 时长须实测。并发上传吞吐取决于服务器上联、交换机与存储，须按业务量验证。真实上传还需经批准的客户端、用户文件选择、HTTPS 接收、完整性校验和审计服务；这些服务待实现。公开 H5 仅展示方案，不读取或传输文件，文件传输由柜内服务器及经批准客户端完成。</p></div></section>
  <footer class="wiring-references"><span>官方架构与选型参考</span>${wiringReferences.map(reference=>`<a href="${reference.url}" target="_blank" rel="noopener noreferrer" title="${escape(reference.source)}">${reference.label}<span aria-hidden="true"> ↗</span></a>`).join('')}</footer>`;
}

export class WiringPanel{
  constructor(host,onClose,onInspect=()=>{}){
    this.host=host;this.onClose=onClose;this.onInspect=onInspect;this.mode='usb';this.opened=false;this.modelStatus={usb:false,fixed:false};
    host.innerHTML=`<div class="wiring-heading"><div><p>18 仓 · 技术设计</p><h2 id="wiringTitle">布线方案</h2></div><button class="wiring-close" type="button" title="关闭布线方案" aria-label="关闭布线方案"><svg viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18"/></svg></button></div><div class="wiring-tabs" role="tablist" aria-label="选择仓内数据接入方案"><button id="wiringTabUsb" role="tab" aria-controls="wiringContent" data-mode="usb">USB 数据接入</button><button id="wiringTabNative" role="tab" aria-controls="wiringContent" data-mode="native">原生 RJ45 接入</button></div><div id="wiringContent" class="wiring-content" role="tabpanel" tabindex="0"></div>`;
    this.tabs=[...host.querySelectorAll('[role="tab"]')];this.content=host.querySelector('#wiringContent');this.closeButton=host.querySelector('.wiring-close');this.closeButton.addEventListener('click',()=>onClose());
    this.tabs.forEach(tab=>{tab.addEventListener('click',()=>this.setMode(tab.dataset.mode));tab.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();event.stopPropagation();const next=event.key==='Home'?this.tabs[0]:event.key==='End'?this.tabs[1]:this.tabs.find(button=>button!==tab);this.setMode(next.dataset.mode);next.focus();});});
    host.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();onClose();}});
    this.content.addEventListener('click',event=>{const button=event.target.closest('[data-wiring-action]');if(button&&!button.disabled)this.onInspect(button.dataset.wiringAction);});
    this.setMode(this.mode);
  }
  setMode(mode){this.mode=mode==='native'?'native':'usb';for(const tab of this.tabs){const selected=tab.dataset.mode===this.mode;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;}this.content.setAttribute('aria-labelledby',this.mode==='usb'?'wiringTabUsb':'wiringTabNative');this.content.innerHTML=wiringContent(this.mode,this.modelStatus);this.content.scrollTop=0;}
  setModelStatus(status){this.modelStatus={usb:Boolean(status.usb),fixed:Boolean(status.fixed)};this.setMode(this.mode);}
  setOpen(open){this.opened=Boolean(open);this.host.hidden=!this.opened;if(this.opened)this.closeButton.focus({preventScroll:true});}
}
