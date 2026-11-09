"""One parameterised shallow drawer. Fixed service hardware stays at the rear."""
import math
from geometry import gltf, bezier, controlled_u, native_cable, length, min_radius, mark_hidden

def build_drawer(b, parent, bay_id, support, cx, p, mats, metadata, single=False):
    k=lambda part:'single:'+part if single else part+':'+bay_id
    def comp(part,title,dims,notes):
        metadata['components'][k(part)]={'title':bay_id+' '+title,'dimensions_mm':dims,'basis':'model','notes':notes,'bay_id':bay_id}
    bay=b.empty('SingleDrawerRoot' if single else 'Bay_'+bay_id,parent,k('bay'),bay_id,(cx,0,support))
    bay['access_type']='drawer';bay['support_height_mm']=support*1000
    tray=b.empty('SingleTray' if single else 'Tray_'+bay_id,bay,k('tray'),bay_id,role='tray')
    tray['interaction']='tray';tray['travel_mm']=p['tray_travel_mm']
    occupied=bay_id not in p['empty_bays'];bay['occupied']=occupied
    white,steel,black,blue,purple,green,graphite,silver,label=[mats[x] for x in ['white','steel','black','blue','purple','green','graphite','silver','label']]
    def box(name,loc,dims,mat=white,par=bay,part='bay',role='structure',bevel=.0005):
        return b.box(bay_id+'_'+name,loc,dims,mat,par,k(part),bay_id,bevel,role)
    def tube(name,pts,r,mat,par=bay,part='cables',role='cable_fixed'):
        return b.tube(name+'_'+bay_id,pts,r,mat,par,k(part),bay_id,role)

    # The rubber bearing surface is Z0. Deck and rails are below it; 30mm
    # laptop + 100mm unobstructed headroom therefore really totals 130mm.
    if not single:box('FixedShelf',(0,-.015,-.0294),(.420,.560,.0012),role='structure')
    for x in [-.198,.198]:
        sign=1 if x>0 else -1
        box('RailFixedWeb',(sign*.204,-.013,-.017),(.002,.512,.020),steel,part='tray',role='slide_fixed')
        for z in [-.0065,-.02725]:box('RailFixedReturn',(sign*.197,-.013,z),(.016,.512,.0015),steel,part='tray',role='slide_fixed')
        box('RailMoving',(sign*.195,-.035,-.015),(.008,.450,.014),silver,tray,'tray','slide_moving')
        for y in [-.21,.17]:
            box('RailSupport',(x,y,-.0284),(.016,.025,.0008),steel,part='tray',role='fastener')
            box('RailCapturedRoller',(sign*.201,y,-.015),(.004,.010,.008),black,part='tray',role='slide_fixed',bevel=.001)
        box('RailRearStop',(x,.238,-.017),(.012,.008,.018),black,part='tray',role='slide_fixed')
        box('RailDrawerBracket',(x*.96,-.055,-.008),(.010,.090,.008),steel,tray,'tray','slide_moving')
    box('Deck',(0,-.055,-.004),(.376,.470,.002),white,tray,'drawer_body','tray')
    for x in [-.187,.187]:box('SideFold',(x,-.055,.0005),(.002,.470,.009),white,tray,'drawer_body','tray')
    box('RearFold',(0,.179,.0005),(.376,.002,.009),white,tray,'drawer_body','tray')
    for x in [-.09,.155]:
        for y in [-.23,-.07]:box('SupportPad',(x,y,-.0015),(.030,.025,.003),black,tray,'tray','supportpad')
    for x in [-.17,.17]:box('FrontBridge',(x,-.289,-.008),(.030,.042,.010),steel,tray,'drawer_body','tray')

    # Genuine rectangular aperture in the front skin, with a recessed black
    # cup and grip lip. No white face is left over the opening.
    z0,z1=-.028,.126;hole_w=.112;ha,hb=.063,.087
    front=b.empty('DrawerFront_'+bay_id,tray,k('drawer_front'),bay_id,role='drawer_front')
    def facebox(name,loc,dims,mat=white,part='drawer_front'):
        o=box(name,loc,dims,mat,front,part,'drawer_front');o['action']='drawer';return o
    for sign in [-1,1]:facebox('FrontSkinSide',(sign*(.222+hole_w/2)/2,-.324,(z0+z1)/2),(.222-hole_w/2,.002,z1-z0))
    facebox('FrontSkinTop',(0,-.324,(hb+z1)/2),(hole_w,.002,z1-hb))
    facebox('FrontSkinBottom',(0,-.324,(z0+ha)/2),(hole_w,.002,ha-z0))
    for x in [-.221,.221]:facebox('FrontReturnSide',(x,-.316,(z0+z1)/2),(.002,.016,z1-z0))
    for z in [z0+.001,z1-.001]:facebox('FrontReturnHorizontal',(0,-.316,z),(.442,.016,.002))
    facebox('HandleCupBack',(0,-.309,.075),(.116,.002,.028),black,'drawer_handle')
    for x in [-.057,.057]:facebox('HandleCupSide',(x,-.316,.075),(.002,.014,.028),black,'drawer_handle')
    for z in [.062,.088]:facebox('HandleCupHorizontal',(0,-.316,z),(.114,.014,.002),black,'drawer_handle')
    facebox('HandleGrip',(0,-.318,.067),(.090,.005,.005),black,'drawer_handle')
    facebox('StatusLens',(-.166,-.3248,.091),(.012,.0004,.004),green)
    facebox('DrawerLockFace',(.168,-.3247,.076),(.014,.0005,.014),graphite)
    b.text('DrawerLabel_'+bay_id,bay_id+'  /  DATA DRAWER',(-.112,-.3249,.109),.008,label,front,k('drawer_front'),bay_id)
    # Latch body lies outside the laptop/headroom measurement footprint.
    box('FixedLock',(.205,-.268,.104),(.008,.026,.022),graphite,part='lock',role='service')
    box('LockMount',(.216,-.268,.104),(.014,.034,.002),steel,part='lock',role='fastener')
    box('MovingLockTarget',(.204,-.295,.104),(.008,.014,.018),steel,tray,'lock','connector')

    # New complete closed laptop, not a rotated open-screen whole-object.
    lap=b.empty('Laptop' if single else 'Laptop_'+bay_id,tray,k('laptop'),bay_id,role='laptop')
    box('LaptopBase',(.030,-.150,.0125),(.300,.210,.025),silver,lap,'laptop','laptop',.003)
    box('LaptopClosedLid',(.030,-.150,.028),(.300,.210,.004),silver,lap,'laptop','laptop',.002)
    box('LaptopLidSeal',(.030,-.150,.0255),(.296,.206,.001),black,lap,'laptop','laptop',.0003)
    for x in [-.085,.145]:box('LaptopHinge',(x,-.047,.025),(.025,.004,.008),steel,lap,'laptop','laptop',.001)
    box('LaptopDCIn',(-.1202,-.075,.026),(.001,.011,.006),black,lap,'laptop','connector')
    box('LaptopUSBIn',(-.1202,-.220,.018),(.001,.012,.006),black,lap,'laptop','connector')
    mark_hidden(lap,not occupied)

    nic=b.empty('NIC_'+bay_id,tray,k('usb_nic'),bay_id,role='service')
    box('NICBody',(-.146,-.050,.012),(.028,.040,.018),graphite,nic,'usb_nic','service',.002)
    box('NICFoot',(-.146,-.050,-.001),(.034,.046,.004),steel,nic,'usb_nic','fastener')
    for x in [-.162,-.130]:box('NICClip',(x,-.050,.005),(.002,.014,.014),steel,nic,'usb_nic','fastener')
    box('NICRJ45',(-.143,-.0705,.012),(.014,.001,.010),black,nic,'usb_nic','connector')
    box('NICNetworkPlug',(-.143,-.077,.012),(.012,.014,.009),blue,nic,'usb_nic','connector')
    box('NICUSBEntry',(-.1605,-.045,.018),(.001,.010,.006),black,nic,'usb_nic','connector')
    box('NICLinkLED',(-.140,-.045,.0213),(.003,.004,.0005),green,nic,'usb_nic','service')

    # Every fixed fitting sits behind the load cavity. A removable panel has
    # socket/adapter stand-offs; branch openings are cut in the trunk stage.
    box('RearServicePlate',(0,.301,.065),(.430,.002,.126),steel,part='interfaces',role='service')
    col=0 if single else (int(bay_id[1:])-1)%3
    for side in [-1,1]:
        wall=.2235 if single or (side<0 and col==0) or (side>0 and col==2) else .2244
        for zz in [.012,.118]:box('ServicePlateMountEar',(side*(.215+wall)/2,.301,zz),(wall-.215,.012,.008),steel,part='interfaces',role='fastener')
    box('FixedNetworkSocket',(-.199,.249,.090),(.022,.036,.026),blue,part='network',role='connector')
    box('FixedACSocket',(-.100,.227,.100),(.034,.036,.038),black,part='ac_socket',role='connector')
    for x,y,z,w in [(-.199,.275,.09,.022),(-.100,.264,.10,.034)]:
        for dx in [-w/2-.0015,w/2+.0015]:box('SocketSupport',(x+dx,y,z-(.016 if x<-.15 else .022)),(.003,2*(.300-y),.006),steel,part='interfaces',role='fastener')
    box('AdapterBasketBase',(.065,.245,.018),(.060,.092,.002),white,part='adapter_bracket',role='service')
    for x in [.036,.094]:
        for y in [.202,.288]:box('AdapterBasketPost',(x,y,.063),(.002,.002,.090),white,part='adapter_bracket',role='service')
    for z in [.030,.060,.090,.109]:
        for x in [.036,.094]:box('AdapterBasketRail',(x,.245,z),(.002,.090,.002),white,part='adapter_bracket',role='service')
    for x in [.042,.088]:box('AdapterBasketBracket',(x,.294,.016),(.012,.014,.004),steel,part='adapter_bracket',role='fastener')
    box('AdapterBearingPad',(.065,.245,.0195),(.048,.080,.001),black,part='adapter_bracket',role='fastener')
    box('PowerAdapter',(.065,.245,.065),(.048,.080,.090),black,part='adapter',role='service',bevel=.003)
    box('AdapterACIn',(.038,.245,.080),(.008,.014,.012),black,part='power',role='connector')
    box('AdapterDCOut',(.065,.202,.035),(.012,.008,.008),black,part='power',role='connector')
    acpts=bezier((-.100,.209,.100),(-.100,.150,.100),(-.045,.245,.080),(.035,.245,.080),36)
    tube('FixedAdapterAC',acpts,.0028,black,part='power')
    dcfeed=bezier((.065,.198,.035),(.020,.180,.035),(-.160,.175,.026),(-.199,.175,.026),36)
    tube('FixedAdapterDC',dcfeed,p['dc_radius_mm']/1000,black)
    net=[(-.199,.231,.090)]
    net += [(-.199,.231+.028*math.cos(t),.062+.028*math.sin(t)) for t in [math.pi/2+i*math.pi/32 for i in range(1,17)]]
    net += [(-.199,.203,.040)]
    net += [(-.199,.175+.028*math.cos(t),.040+.028*math.sin(t)) for t in [-i*math.pi/32 for i in range(1,17)]]
    tube('FixedNetworkFeed',net,p['network_radius_mm']/1000,blue)

    # Controlled horizontal U loops: fixed leg grows by travel/2, moving leg
    # shortens equally. Geometry and native shape keys keep constant length.
    for kind,z,end_y,rad,mat in [('network',.012,-.084,p['network_radius_mm']/1000,blue),('power',.026,-.075,p['dc_radius_mm']/1000,black)]:
        cp=controlled_u(0,z,end_y);ep=controlled_u(.320,z,end_y)
        o=native_cable(b,'DynamicCable_'+bay_id+'_'+kind,cp,ep,rad,mat,bay,tray,k('cables'),bay_id)
        record={'id':'cable_'+bay_id+'_'+kind,'bay_id':bay_id,'component_key':k('cables'),'space':'single_local_gltf' if single else 'bay_local_gltf','parent_node':bay.name,'tray_node':tray.name,'source_node_names':[o.name],'morph_target':'TrayExtended320mm','motion':'native_morph','stowed':False,'initial_occupied':occupied,'fixed':gltf(cp[:1])[0],'moving':gltf(cp[-1:])[0],'guide_points':gltf(cp),'guide_points_extended':gltf(ep),'radius_mm':rad*1000,'color':'#266cac' if kind=='network' else '#151b22','travel_mm':320,'bend_radius_mm':28,'rest_length_mm':length(cp),'closed_length_mm':length(cp),'extended_length_mm':length(ep)}
        if kind=='network':record['keep_connected_when_empty']=True;record['connection_mode']='tray_usb_nic'
        else:
            plug=box('DCMovingPlug',(-.131,-.075,.026),(.024,.011,.007),black,tray,'power','connector')
            # Parking adds a smooth vertical rise; shift the U by bisection
            # to preserve the same physical cable centreline length.
            def park(loop):
                q=controlled_u(0,z,end_y,loop_y=loop)
                return [(x,y,z+(.065-z)*(.5-.5*math.cos(math.pi*max(0,min(1,(y-(end_y-.09))/.09))))) if j>=42 else (x,y,z) for j,(x,y,z) in enumerate(q)]
            lo,hi=-.265,-.220
            for _ in range(35):
                mid=(lo+hi)/2
                if length(park(mid))>length(cp):lo=mid
                else:hi=mid
            pp=park((lo+hi)/2);parkroot=b.empty('DCParked_'+bay_id,bay,k('cables'),bay_id,role='cable_fixed')
            po=tube('ParkingCable_power',pp,rad,black,parkroot)
            pk=box('ParkingDCPlug',(-.143,-.075,.065),(.018,.016,.008),black,parkroot,'power','connector')
            box('DCParkingBracket',(-.182,-.075,.058),(.084,.020,.002),steel,part='interfaces',role='service')
            box('DCParkingClip',(-.143,-.075,.060),(.022,.019,.004),black,part='interfaces',role='service')
            mark_hidden(o,not occupied);mark_hidden(plug,not occupied);mark_hidden(parkroot,occupied)
            record.update(parking_node_names=[parkroot.name],moving_connector_node_names=[plug.name],parking_guide_points=gltf(pp),parking_length_mm=length(pp),parking_min_sampled_radius_mm=min_radius(pp))
        metadata['cable_paths'].append(record)

    start=(-.161,-.045,.018);end=(-.126,-.220,.018);parkend=(-.100,-.278,.018)
    conpts=bezier(start,(-.230,-.045,.018),(-.200,-.220,.018),end,48)
    parkpts=bezier(start,(-.230,-.070,.018),(-.200,-.278,.018),parkend,48)
    con=b.empty('USBConnected_'+bay_id,tray,k('usb'),bay_id,role='connector')
    parked=b.empty('USBParked_'+bay_id,tray,k('usb'),bay_id,role='connector')
    tube('USBConnectedCable',conpts,.0016,purple,con,'usb','connector')
    tube('USBParkedCable',parkpts,.0016,purple,parked,'usb','connector')
    cup=box('USBConnectedPlug',(-.125,-.220,.018),(.014,.010,.006),purple,con,'usb','connector')
    pup=box('USBParkedPlug',parkend,(.014,.010,.006),purple,parked,'usb','connector')
    box('USBParkingClip',(-.100,-.278,.005),(.020,.016,.010),black,tray,'usb','connector')
    mark_hidden(con,not occupied);mark_hidden(parked,occupied)
    metadata['usb_connections'].append({'bay_id':bay_id,'nic_node':nic.name,'tray_node':tray.name,'connected_node_names':[con.name],'parked_node_names':[parked.name],'endpoint_plug_nodes':[cup.name,pup.name],'initial_occupied':occupied,'space':'tray_local_gltf','connected_guide_points':gltf(conpts),'parked_guide_points':gltf(parkpts),'radius_mm':1.6,'connected_min_sampled_radius_mm':min_radius(conpts),'parked_min_sampled_radius_mm':min_radius(parkpts)})

    comp('bay','闭盖笔电抽屉仓',[420,420,130],'载物净高130 mm：闭盖整机30 mm＋上方100 mm；有效净高到最低固定障碍。后部固定服务区不计作载物区。')
    metadata['components'][k('bay')].update({'access_type':'drawer','occupied':occupied,'side':'right','row':0 if single else (int(bay_id[1:])-1)//3,'column':0 if single else (int(bay_id[1:])-1)%3,'support_height_mm':support*1000,'tray_node':tray.name,'travel_mm':320,'net_height_mm':130,'payload_bounds_blender_mm':{'min':[-120,-255,0],'max':[180,-45,130]},'remove_path_m':p['remove_path_m']})
    comp('tray','抽拉机构',[412,512,30],'32 cm行程；载荷及循环寿命待实际滑轨选型验证。')
    comp('drawer_body','白色浅抽屉盘',[376,470,2],'金属盘面在电脑承托面下3 mm，橡胶垫顶作为净高起点。')
    comp('drawer_front','齐平抽屉前板',[444,16,154],'关闭前表面与65 cm柜体包络齐平；真实嵌入拉手孔。')
    comp('drawer_handle','嵌入式拉手',[112,16,24],'槽口和黑色凹盒独立建模，无外凸把手。')
    comp('laptop','无品牌闭合笔记本',[300,210,30],'闭合整机总厚30 mm为设计假设；新底壳/屏盖/合缝几何，非旧开盖模型旋转。')
    comp('usb_nic','随抽屉USB以太网网卡',[28,40,18],'网卡留柜随盘；机型驱动、USB接口及速率待选型。')
    comp('usb','USB短线与停靠夹',None,'短线两端均随盘；取机前停靠，落位后再接线。')
    comp('adapter','固定后部电源适配器',[48,80,90],'AC固定、DC受控随动；外形与额定值未定型。')
    comp('adapter_bracket','固定网孔托架',[60,92,92],'适配器留在后部服务区，不随抽屉运动。')
    comp('interfaces','后部固定接口与停靠支架',[430,2,126],'重排原25 cm高侧面板；后侧固定支架/AC/网络端接。')
    comp('network','固定RJ45座体',[22,36,26],'固定网络口接后主干，蓝Ethernet活动段接移动网卡。')
    comp('ac_socket','固定AC座体',[34,36,38],'每仓独立受控电源设计，电气能力待选型。')
    comp('power','DC插接与固定AC馈线',None,'DC借出停车，适配器及AC不随盘。')
    comp('cables','受控随动线束',None,'R28 mm低位U形、32 cm行程；实际线型弯曲寿命待验证。')
    comp('lock','抽屉锁与位置检测',[8,26,22],'锁止/门位/锁位能力为待选型设计，不以网格代表认证。')
    return bay,tray,lap
