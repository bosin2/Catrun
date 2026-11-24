"""Centimetre layout recovered from the user's v3 dimensions and original plan.

Plan right = world +X, plan up = world +Y. Room bounds are outer bounds,
not a promise of interior clearance. These coordinates resolve adjacency; the
dimensions and goal/door relationships come from the original conversations.
"""
ROOMS = {
    'Entrance': (0,0,300,200),
    'Lobby': (-400,200,700,800),
    'LowerHall': (-400,800,300,1600),
    'Exhibition': (-1000,1300,-400,2400),
    'Warehouse': (300,800,1200,1500),
    'CentralCorridor': (-50,1500,1200,1800),
    'CatBypass': (500,1800,1200,1950),
    'ControlAnnex': (-50,1800,500,1950),
    'ControlRoom': (-50,1950,950,2550),
    'UpperCorridor': (-350,2150,-50,2950),
    'GateHall': (-950,2950,550,4050),
}
EXPECTED_SIZES = [(300,200),(1100,600),(700,800),(600,1100),(900,700),(1250,300),(700,150),(550,150),(1000,600),(300,800),(1500,1100)]
# Continuous internal walls. Openings reserve a complete 200 cm portal module.
# orientation, fixed axis coordinate, start, end, [(center, type, identifier)]
INTERNAL = [
    ('h',500,-250,700,[(250,'cat','H1')]),
    ('v',150,500,800,[(650,'door','D0')]),
    ('h',800,-250,700,[]),
    ('v',300,1000,1500,[]),
    ('h',1500,300,900,[]),
    ('h',1800,-50,1200,[(100,'gate','D1'),(600,'cat','H2'),(1100,'cat','H3')]),
    ('v',500,1800,1950,[]),
    ('h',1950,500,950,[]),
    ('v',-50,2300,2550,[]),
    ('h',2350,-350,-50,[(-200,'gate','D2')]),
    # Open L-shaped 150 x 150 cm structure around objective E3.
    ('v',275,2175,2325,[]),('h',2325,275,425,[]),
]
PROPS = [
    ('Display1','SM_S3_WeaponDisplay',(-800,1640,0),90),
    ('Display2','SM_S3_WeaponDisplay',(-800,1890,0),90),
    ('DisplayJoint','SM_S3_WeaponDisplay_Joint',(-800,1765,0),90),
    ('Cabinet1','SM_S3_EquipmentCabinet',(450,920,0),0),
    ('Cabinet2','SM_S3_EquipmentCabinet',(750,920,0),0),
    ('Shield1','SM_S3_ShieldRack',(450,1170,0),0),
    ('Shield2','SM_S3_ShieldRack',(750,1170,0),0),
    ('ArmorRack1','SM_S3_ArmorPartsRack',(1050,920,0),0),
    ('ArmorRack2','SM_S3_ArmorPartsRack',(1050,1170,0),0),
    ('SupplyBox','SM_S3_SupplyBox_L',(450,1420,0),0),
    ('Maintenance','SM_S3_MaintenanceBench',(530,740,0),0),
    ('Bench','SM_S3_GuardBench',(560,570,0),0),
    ('Weapons','SM_S3_WeaponRack',(-900,2280,0),0),
    ('Console','SM_S3_GateControlConsole',(320,2480,0),0),
]
DEVICES = [(100,370,0),(1090,1660,0),(375,2240,0)]
STATUES = [((-550,1430,0),(-550,2250,0),'D1'),((760,2140,0),(760,2420,0),'D2')]
ARMORS = [
    ('LobbyPost',(-180,650,100),0,[]),
    ('LobbyPatrol',(340,650,100),0,[(340,650,100),(620,650,100)]),
    ('CentralPost',(660,1650,100),0,[]),
    ('ControlPatrol',(520,2140,100),90,[(520,2140,100),(520,2380,100),(150,2380,100),(150,2100,100)]),
    ('GateLeft',(-720,3900,100),0,[(-720,3900,100),(-230,3900,100)]),
    ('GateRight',(330,3900,100),180,[(330,3900,100),(-170,3900,100)]),
]
CANDLES = [
    ('Exhibition',(-700,1670,100),90,[(-700,1670,100),(-700,2080,100)]),
    ('WarehouseNorth',(380,1310,100),-35,[]),
    ('WarehouseSouth',(1135,855,100),145,[]),
    ('GateLeft',(-540,3400,100),0,[(-540,3260,100),(-740,3450,100),(-540,3650,100),(-380,3450,100)]),
    ('GateRight',(140,3400,100),180,[(140,3260,100),(340,3450,100),(140,3650,100),(-20,3450,100)]),
]

def cells():
    result=set()
    for x0,y0,x1,y1 in ROOMS.values():
        result.update((x,y) for x in range(x0,x1,50) for y in range(y0,y1,50))
    return result

def boundary_segments():
    occupied=cells(); lines={}
    for x,y in occupied:
        for dx,dy,orient,fixed,start,side in [(-50,0,'v',x,y,1),(50,0,'v',x+50,y,-1),(0,-50,'h',y,x,1),(0,50,'h',y+50,x,-1)]:
            if (x+dx,y+dy) not in occupied:
                lines.setdefault((orient,fixed,side),[]).append(start)
    out=[]
    for (orient,fixed,side), values in sorted(lines.items()):
        values=sorted(values); start=prev=values[0]
        for value in values[1:]+[10**9]:
            if value!=prev+50:
                out.append((orient,fixed,start,prev+50,side));start=value
            prev=value
    return out

def floor_rectangles():
    remaining=cells();out=[]
    while remaining:
        x,y=min(remaining,key=lambda p:(p[1],p[0]))
        width=50
        while width<200 and (x+width,y) in remaining: width+=50
        height=50
        while height<200 and all((xx,y+height) in remaining for xx in range(x,x+width,50)): height+=50
        for xx in range(x,x+width,50):
            for yy in range(y,y+height,50):remaining.remove((xx,yy))
        out.append((x,y,width,height))
    return out

assert [(x1-x0,y1-y0) for x0,y0,x1,y1 in ROOMS.values()]==EXPECTED_SIZES
