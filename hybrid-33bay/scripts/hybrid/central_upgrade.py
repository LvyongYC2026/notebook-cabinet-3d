"""33-way central capacity placeholders with real, individually named ports.
Not a manufacturer-specific switch/PDU or electrical certification.
"""
import bpy,math
from geometry import remove

def upgrade_central(b,root,meta,M,intentional):
    # Delete only the enumerated old device fittings. Other equipment remains.
    prefixes=('Switch_Port','Switch_LED','Switch_Text','Switch_Label','PDU_Outlet','PDU_Contact','PDU_Status','PDU_Text','Controller18_','Control_Text','Wiring_SwitchPlug_','Wiring_PDUPlug_','Wiring_PDUBranch_')
    exact={'Equipment_Switch24','Equipment_PDU18','Equipment_Control18_DesignPlaceholder'}
    for name in [o.name for o in bpy.context.scene.objects]:
        o=bpy.data.objects.get(name)
        if o and (name in exact or name.startswith(prefixes)):
            intentional.extend(q.name for q in [o,*o.children_recursive]);remove(o)
    white,steel,black,blue,green,graphite,label=[M[k] for k in ['white','steel','black','blue','green','graphite','label']]
    def box(n,loc,dims,mat,key,role='service'):
        return b.box(n,loc,dims,mat,root,key,bevel=.0007,role=role)
    switch=box('Equipment_Switch48_DesignPlaceholder',(0,-.030,.698),(.440,.300,.044),graphite,'switch')
    netports={}
    for i in range(48):
        r,c=divmod(i,24);x=-.199+c*.0173;z=.687+r*.021
        n='HybridSwitch_Port_%02d'%(i+1)
        ob=box(n,(x,-.181,z),(.014,.004,.012),black,'switch','connector');ob['port_number']=i+1
        box(n+'_Contacts',(x,-.1832,z+.002),(.010,.0005,.003),steel,'switch','connector')
        box(n+'_LED',(x+.005,-.1834,z+.007),(.002,.0005,.0015),green,'switch','connector')
        netports[i+1]=(x,-.200,z)
        if i<38:box('HybridSwitch_Plug_%02d'%(i+1),(x,-.191,z),(.012,.018,.009),blue,'wiring:network','connector')
    b.text('HybridSwitch_Label','48 PORT GIGABIT / DESIGN CAPACITY',(0,-.184,.716),.004,label,root,'switch')
    # The controller and PDU are capacity/packaging studies, not rated hardware.
    box('Equipment_PDU33_DesignPlaceholder',(0,.196,.623),(.440,.018,.144),graphite,'pdu')
    acports={}
    for i in range(33):
        if i<9:x=-.196+i*.049;z=.579
        else:
            row,col=divmod(i-9,3);x=-.189+.054*row;z=.611+.032*col
        n='HybridPDU_Outlet_%02d'%(i+1)
        ob=box(n,(x,.208,z),(.026,.006,.028),black,'pdu','connector');ob['circuit_number']=i+1
        for dx in [-.007,.007]:box(n+'_Contact',(x+dx,.2115,z),(.004,.001,.010),steel,'pdu','connector')
        box(n+'_Status',(x,.212,z+.017),(.005,.001,.003),green,'pdu','connector')
        box('HybridPDU_Plug_%02d'%(i+1),(x,.219,z),(.026,.018,.028),black,'wiring:ac','connector')
        acports[i+1]=(x,.228,z)
    box('Equipment_Control33_DesignPlaceholder',(.118,.030,.465),(.160,.180,.048),graphite,'controller')
    terminal_rows=[('LockOutput',-.012),('DoorStateInput',.034),('LockStateInput',.080)]
    for typ,y in terminal_rows:
        box('HybridControl_'+typ+'_Carrier',(.118,y,.495),(.151,.020,.008),steel,'controller')
        for i in range(33):
            o=box('HybridControl_'+typ+'_%02d'%(i+1),(.046+i*.0045,y,.501),(.0038,.012,.007),black,'controller','connector');o['channel_number']=i+1;o['channel_role']=typ
    b.text('HybridControl_Label','33 LOCK OUT / 66 STATE IN',(.118,-.061,.474),.008,label,root,'controller')
    ids=['A'+str(i) for i in range(1,10)]+['B'+str(i) for i in range(1,25)]
    management=['server','lock_controller','pdu','ups','external_management']
    for port,name in enumerate(['Server','LockController','PDUManagement','UPSManagement','ExternalManagement'],34):
        ob=bpy.data.objects.get('Wiring_'+name+'_ID')
        if ob and ob.type=='FONT':
            ob.data=ob.data.copy();ob.data.body=str(port)+' '+name;intentional.append(ob.name)
    meta['components']['wiring:control']={'title':'33仓锁控与状态扩展端子','dimensions_mm':None,'basis':'model','notes':'33路锁控输出、两组各33路门位/锁位输入；功能容量、额定值与协议待实际选型，不以造型代表电气能力已验证。'}
    meta['switch_port_plan']=[{'port':i+1,'endpoint':code,'role':'bay_data','port_node':'HybridSwitch_Port_%02d'%(i+1)} for i,code in enumerate(ids)]+[{'port':i,'endpoint':name,'role':'device_or_management','port_node':'HybridSwitch_Port_%02d'%i} for i,name in enumerate(management,34)]+[{'port':i,'endpoint':'spare','role':'spare','port_node':'HybridSwitch_Port_%02d'%i} for i in range(39,49)]
    meta['power_branch_plan']=[{'circuit':i+1,'bay_id':code,'port_node':'HybridPDU_Outlet_%02d'%(i+1),'rated_power_w':None} for i,code in enumerate(ids)]
    meta['control_channel_budget']={'lock_outputs':33,'door_state_inputs':33,'lock_state_inputs':33,'additional_functions':'temperature/lighting and management selected separately','basis':'design capacity; electrical hardware not selected'}
    meta['components']['switch']={'title':'48口以太网交换设备示意','dimensions_mm':[440,300,44],'basis':'model','notes':'前端面2×24真实独立端口；33仓＋5管理占38口、10口备用。外形及端口排布待设备选型，非额定性能验证。'}
    meta['components']['pdu']={'title':'33路受控配电示意','dimensions_mm':[440,39,144],'basis':'model','notes':'33个独立支路端接；紧凑后安装体积为设计占位，电气额定/保护/温升/器件深度待选型。原9路左仓近端位置保留。'}
    meta['components']['controller']={'title':'33仓锁控与状态采集示意','dimensions_mm':[160,180,64],'basis':'model','notes':'33路锁控输出、33路门位＋33路锁位输入，新增99个独立端子。电气容量待选型。'}
    return netports,acports
