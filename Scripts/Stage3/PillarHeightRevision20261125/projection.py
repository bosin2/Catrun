"""Offline cap projection evidence. No Unreal import, I/O, or scene mutation."""
import itertools
import math

POSES = {'GateMiddle':(-250.,-3400.,26.2), 'GateExtreme':(-945.,-4545.,26.2)}
OFFSET = (147.7898938366867,147.78989383668707,409.57602214449524)


def compare():
    pitch,yaw=map(math.radians,(-55.,-135.))
    forward=(math.cos(pitch)*math.cos(yaw),math.cos(pitch)*math.sin(yaw),math.sin(pitch))
    right=(-math.sin(yaw),math.cos(yaw),0.)
    up=(-math.sin(pitch)*math.cos(yaw),-math.sin(pitch)*math.sin(yaw),math.cos(pitch))
    result={'scope':'Projected 150x150cm capital top AABB corners only; not rendered visibility or occlusion QA',
            'selected_top_cm':900,'original_shaft_top_cm':840,'capital_height_cm':60,'proposals':[]}
    for height in (900.,600.):
        proposal={'top_cm':height,'poses':{}}
        for pose,cat in POSES.items():
            camera=[cat[i]+OFFSET[i] for i in range(3)]
            rows=[]
            for x,y in itertools.product((-720.,220.),(-3150.,-3450.,-3725.,-4025.,-4325.)):
                points=[]
                for dx,dy in itertools.product((-75.,75.),repeat=2):
                    v=[x+dx-camera[0],y+dy-camera[1],height-camera[2]]
                    points.append([sum(a*b for a,b in zip(v,axis)) for axis in (right,up,forward)])
                lo=[min(p[i] for p in points) for i in range(3)]
                hi=[max(p[i] for p in points) for i in range(3)]
                full=lo[0]>=-450 and hi[0]<=450 and lo[1]>=-253.125 and hi[1]<=253.125
                intersection=hi[0]>=-450 and lo[0]<=450 and hi[1]>=-253.125 and lo[1]<=253.125
                rows.append({'xy':[x,y],'screen_bounds_cm':[lo,hi],'top_fully_in_frame':full,
                             'aabb_intersects_frame':intersection,'within_near_far':lo[2]>=-4000 and hi[2]<=10000})
            proposal['poses'][pose]={'fully_in_frame_count':sum(r['top_fully_in_frame'] for r in rows),'rows':rows}
        result['proposals'].append(proposal)
    assert all(r['within_near_far'] for p in result['proposals'] for pose in p['poses'].values() for r in pose['rows'])
    return result


if __name__=='__main__':
    import json
    print(json.dumps(compare(),indent=2))
