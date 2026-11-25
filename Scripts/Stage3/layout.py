"""Centimetre layout recovered from the user's v3 dimensions and original plan.

These are canonical DRAWING coordinates: right = +X, up = +Y. The final
Stage3 map uses world (X,-Y,Z), applied once by OrientationFix20261125/apply.py,
so Unreal's north-side top view shows the same handedness as the reference.
Do not treat these canonical Y values as saved-map world coordinates.
Room bounds are outer bounds,
not a promise of interior clearance. These coordinates resolve adjacency; the
dimensions and goal/door relationships come from the original conversations.
"""
ROOMS = {
    'Entrance': (0,0,300,200),
    'Lobby': (-400,200,700,800),
    'LowerHall': (-400,800,300,1600),
    'Exhibition': (-1150,1300,-550,2400),
    'Warehouse': (300,800,1200,1500),
    'CentralCorridor': (-50,1500,1200,1800),
    'CatBypass': (500,1800,1200,1950),
    'ControlAnnex': (-400,1950,150,2100),
    'ControlRoom': (-50,1950,950,2550),
    'UpperCorridor': (-400,2100,-100,2900),
    'GateHall': (-1000,2900,500,4000),
}
# Circulation pieces recover the reference plan's two stepped connections.
# They are not additional named rooms in EXPECTED_SIZES. The 550x150 annex
# rectangle overlaps the main room by 200x150 at its lower-left corner; its
# outer dimensions therefore must not be reported as 8.25 m2 of added area.
CONNECTORS = {
    'ExhibitionBridge': (-550,1300,-400,1600),
    'MainEntry': (-50,1800,500,1950),
}
EXPECTED_SIZES = [(300,200),(1100,600),(700,800),(600,1100),(900,700),(1250,300),(700,150),(550,150),(1000,600),(300,800),(1500,1100)]
# Continuous internal walls. Openings reserve a complete 200 cm portal module.
# orientation, fixed axis coordinate, start, end, [(center, type, identifier)]
INTERNAL = [
    ('h',500,-250,550,[(250,'cat','H1')]),
    ('v',150,500,800,[(650,'door','D0')]),
    ('h',800,-250,700,[]),
    ('v',300,1000,1500,[]),
    ('h',1500,300,900,[]),
    ('h',1800,-50,1200,[(100,'gate','D1'),(600,'cat','H2'),(1100,'cat','H3')]),
    ('v',500,1800,1950,[]),
    ('h',1950,500,950,[]),
    # The main room's west wall is now an exterior boundary above the elbow.
    ('h',2300,-400,-100,[(-250,'gate','D2')]),
    # Open L-shaped 150 x 150 cm structure around objective E3.
    ('v',275,2175,2325,[]),('h',2325,275,425,[]),
]
PROPS = [
    ('Display1','SM_S3_WeaponDisplay',(-950,1640,0),90),
    ('Display2','SM_S3_WeaponDisplay',(-950,1890,0),90),
    ('DisplayJoint','SM_S3_WeaponDisplay_Joint',(-950,1765,0),90),
    ('Cabinet1','SM_S3_EquipmentCabinet',(450,920,0),0),
    ('Cabinet2','SM_S3_EquipmentCabinet',(750,920,0),0),
    ('Shield1','SM_S3_ShieldRack',(450,1170,0),0),
    ('Shield2','SM_S3_ShieldRack',(750,1170,0),0),
    ('ArmorRack1','SM_S3_ArmorPartsRack',(1050,920,0),0),
    ('ArmorRack2','SM_S3_ArmorPartsRack',(1050,1170,0),0),
    ('SupplyBox','SM_S3_SupplyBox_L',(450,1420,0),0),
    ('Weapons','SM_S3_WeaponRack',(-1050,2280,0),0),
    ('Console','SM_S3_GateControlConsole',(320,2480,0),0),
]
DEVICES = [(100,370,0),(1090,1660,0),(375,2240,0)]
STATUES = [((-700,1430,0),(-700,2250,0),'D1'),((760,2140,0),(760,2420,0),'D2')]
ARMORS = [
    ('LobbyPost',(-180,650,100),0,[]),
    ('LobbyPatrol',(340,650,100),0,[(340,650,100),(620,650,100)]),
    ('CentralPost',(660,1650,100),0,[]),
    ('ControlPatrol',(520,2140,100),90,[(520,2140,100),(520,2380,100),(150,2380,100),(150,2100,100)]),
    ('GateLeft',(-770,3850,100),0,[(-770,3850,100),(-280,3850,100)]),
    ('GateRight',(280,3850,100),180,[(280,3850,100),(-220,3850,100)]),
]
CANDLES = [
    # L-shaped patrol stays left of the P1 push lane and below the display's
    # south end on its horizontal leg. Runtime clearance is checked separately.
    ('Exhibition',(-850,1670,100),90,[(-850,1410,100),(-1050,1410,100),(-850,1410,100),(-850,2140,100)]),
    ('WarehouseNorth',(380,1310,100),-35,[]),
    ('WarehouseSouth',(1135,855,100),145,[]),
    ('GateLeft',(-590,3350,100),0,[(-590,3210,100),(-790,3400,100),(-590,3600,100),(-430,3400,100)]),
    ('GateRight',(90,3350,100),180,[(90,3210,100),(290,3400,100),(90,3600,100),(-70,3400,100)]),
]

def cells():
    result=set()
    for x0,y0,x1,y1 in (*ROOMS.values(), *CONNECTORS.values()):
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
