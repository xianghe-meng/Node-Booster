# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


def curve_to_points(curve) -> list:
    """get points coord from a curve"""

    pts=[]

    for p in curve.points:
        x,y = p.location.x, p.location.y

        h = "VECTOR" if (p.handle_type=="VECTOR") else "AUTO"
        pts.append([x,y,h])
        continue

    return pts

def reset_curve(curve):
    """clear all points of this curve (2 pts need to be left)"""

    points = curve.points

    while (len(curve.points)>2):
        points.remove(points[1])

    points[0].location = (0,0)
    points[1].location = (1,1)

    return None

def points_to_curve(curve, pts:list,):
    """apply a curve graph from given list of points"""   

    if (not pts):
        return None

    reset_curve(curve)

    #add new points
    while (len(curve.points)<len(pts)):
        curve.points.new(0,0)

    #assign points locations & handle
    for i,vec in enumerate(pts):
        x,y,*h = vec
        curve.points[i].location = (x,y)
        curve.points[i].handle_type = h[0] if (h) else "AUTO"
        continue

    return None
