"""Helpers for the CAD map buildings (tools/cad/<app>_cad.py): SolidCraft commands written in the original
building's own frame, glTF metres, Y up, so tools/art/cad_building.py bakes them without any fitting.

    CAD X = x * 1000, CAD Y = -z * 1000, CAD Z = y * 1000   (SolidCraft mm, Z up; the inverse of cad_building.load_obj)

Every helper takes game coordinates in metres. Bodies are kept separate where they only touch (ribs, sills,
frames): bake drops the faces hidden inside another body, and SolidCraft booleans are the slow part. Cuts
(recesses) are real booleans, one combine per opening.
"""
import json
import math

import numpy as np


def cad(p):
    return [round(p[0] * 1000, 2), round(-p[2] * 1000, 2), round(p[1] * 1000, 2)]


def cad_dir(v):
    return np.array([v[0], -v[2], v[1]], float)


def axis_angle(m):
    """Rotation matrix -> (axis, degrees)."""
    ang = math.acos(max(-1.0, min(1.0, (np.trace(m) - 1) / 2)))
    if ang < 1e-9:
        return None, 0.0
    if abs(ang - math.pi) < 1e-6:
        # 180 degrees: the axis is the eigenvector of +1
        w, v = np.linalg.eigh((m + np.eye(3)) / 2)
        ax = v[:, w.argmax()]
    else:
        ax = np.array([m[2, 1] - m[1, 2], m[0, 2] - m[2, 0], m[1, 0] - m[0, 1]]) / (2 * math.sin(ang))
    return ax, math.degrees(ang)


class Builder:
    def __init__(self):
        self.cmds = []
        self.n_sk = 0
        self.n_tool = 0

    def c(self, command, **params):
        self.cmds.append({"command": command, "params": params})

    def _sketch(self, plane, offset, flip=None):
        self.n_sk += 1
        name = f"sk{self.n_sk}"
        p = {"plane": plane, "offset": round(offset, 2), "name": name}
        if flip is not None:
            p["flip"] = flip
        self.c("sketch.create", **p)
        return name

    # --- volumes --------------------------------------------------------------
    def prism_z(self, name, poly_xy, z0, z1):
        """Polygon in (x, y) extruded along game z from z0 to z1."""
        sk = self._sketch("XZ", -z0 * 1000, flip=True)  # flipped XZ: sketch (x, y) = (X, Z), extrudes toward -Y = +z
        self.c("sketch.line", points=[[round(x * 1000, 2), round(y * 1000, 2)] for x, y in poly_xy], closed=True)
        self.c("sketch.finish")
        self.c("solid.extrude", distance=round((z1 - z0) * 1000, 2), sketch=sk, body_name=name, operation="new")
        return name

    def prism_y(self, name, poly_xz, y0, y1):
        """Polygon in (x, z) extruded up from y0 to y1."""
        sk = self._sketch("XY", y0 * 1000)
        self.c("sketch.line", points=[[round(x * 1000, 2), round(-z * 1000, 2)] for x, z in poly_xz], closed=True)
        self.c("sketch.finish")
        self.c("solid.extrude", distance=round((y1 - y0) * 1000, 2), sketch=sk, body_name=name, operation="new")
        return name

    def prism_x(self, name, poly_zy, x0, x1):
        """Polygon in (z, y) extruded along game x from x0 to x1 (built along z, then turned a quarter)."""
        # sketch it as a z-prism in (x', y) = (-z, y) running from x0..x1 along z, then turn -90 deg about Y
        sk = self._sketch("XZ", 0.0, flip=True)
        self.c("sketch.line", points=[[round(-z * 1000, 2), round(y * 1000, 2)] for z, y in poly_zy], closed=True)
        self.c("sketch.finish")
        self.c("solid.extrude", distance=round((x1 - x0) * 1000, 2), sketch=sk, body_name=name, operation="new")
        # body now spans CAD X = -z, CAD -Y in [0, L]; rotate about CAD Z by -90 deg: (X, Y) -> (Y, -X)
        self.c("solid.move", bodies=[name], axis=[0, 0, 1], angle="90 deg")
        self.c("solid.move", bodies=[name], translate=[round(x0 * 1000, 2), 0, 0])
        return name

    def loft_y(self, name, poly0_xz, y0, poly1_xz, y1):
        """A frustum: polygon at height y0 lofted to another (same vertex count) at y1."""
        a = self._sketch("XY", y0 * 1000)
        self.c("sketch.line", points=[[round(x * 1000, 2), round(-z * 1000, 2)] for x, z in poly0_xz], closed=True)
        self.c("sketch.finish")
        b = self._sketch("XY", y1 * 1000)
        self.c("sketch.line", points=[[round(x * 1000, 2), round(-z * 1000, 2)] for x, z in poly1_xz], closed=True)
        self.c("sketch.finish")
        self.c("solid.loft", sections=[{"sketch": a}, {"sketch": b}], body_name=name, operation="new")
        return name

    def box(self, name, lo, hi, chamfer=0.0, chamfer_edges=None):
        lo, hi = np.array(lo, float), np.array(hi, float)
        size = hi - lo
        ctr = (lo + hi) / 2
        self.c("solid.box", length=round(size[0] * 1000, 2), width=round(size[2] * 1000, 2), height=round(size[1] * 1000, 2),
               center=cad(ctr), body_name=name, operation="new")
        if chamfer:
            edges = chamfer_edges if chamfer_edges is not None else box_edges(lo, hi, "top")
            self.c("solid.chamfer", edges=[cad(e) for e in edges], distance=round(chamfer * 1000, 2), body=name)
        return name

    def obox(self, name, center, t, b, n, size):
        """A box with its local x, y, z along game directions t, b, n (right-handed), size (along t, b, n)."""
        self.c("solid.box", length=round(size[0] * 1000, 2), width=round(size[1] * 1000, 2), height=round(size[2] * 1000, 2),
               center=[0, 0, 0], body_name=name, operation="new")
        m = np.c_[cad_dir(t), cad_dir(b), cad_dir(n)]
        ax, deg = axis_angle(m)
        if ax is not None:
            self.c("solid.move", bodies=[name], axis=[round(float(x), 6) for x in ax], angle=f"{deg:.4f} deg")
        self.c("solid.move", bodies=[name], translate=cad(center))
        return name

    def cut(self, target, tool):
        self.c("solid.combine", target=target, tools=[tool], operation="cut")

    def join(self, target, tools):
        self.c("solid.combine", target=target, tools=list(tools), operation="join")

    # --- relief ---------------------------------------------------------------
    def recess(self, target, o, depth, grow=0.0, surface_shift=0.0, round_ends=False):
        """Cut a window or door recess for an opening from cad_building.py openings (dict: center, t, b, n, w, h).
        surface_shift moves the wall plane back (an inset wall); the tool also reaches 5 cm in front of it."""
        self.n_tool += 1
        n, t, b = (np.array(o[k], float) for k in ("normal", "t", "b"))
        front = 0.05
        c = np.array(o["center"]) - n * surface_shift + n * (front - depth) / 2
        w, h = o["w"] + 2 * grow, o["h"] + 2 * grow
        if round_ends and w > h:  # a slot: a box with half-round ends (cylinders along the normal)
            # the box is 1 cm shallower than the round ends: tangent faces make the kernel's boolean fail
            tool = self.obox(f"cut{self.n_tool}", c, t, b, n, (w - h, h - 0.01, depth + front))
            caps = []
            for k, sgn in enumerate((1, -1)):
                base = c + t * sgn * (w - h) / 2 - n * (depth + front) / 2
                nm = f"cut{self.n_tool}_{k}"
                self.c("solid.cylinder", radius=round(h / 2 * 1000, 2), height=round((depth + front) * 1000, 2),
                       base=cad(base), axis=[round(float(x), 6) for x in cad_dir(n)], body_name=nm, operation="new")
                caps.append(nm)
            self.cut(target, tool)
            for cp in caps:  # cut each piece on its own: a union of the box and its tangent cylinders fails
                self.cut(target, cp)
            return
        else:
            tool = self.obox(f"cut{self.n_tool}", c, t, b, n, (w, h, depth + front))
        self.cut(target, tool)

    def sill(self, name, o, proud=0.12, thick=0.08, overhang=0.12, surface_shift=0.0, top=False):
        """A sill under (or a hood over, top=True) an opening, standing proud of the wall."""
        n, t, b = (np.array(o[k], float) for k in ("normal", "t", "b"))
        sgn = 1 if top else -1
        c = np.array(o["center"]) - n * surface_shift + b * sgn * (o["h"] / 2 + thick / 2) + n * (proud / 2 - 0.02)
        return self.obox(name, c, t, b, n, (o["w"] + 2 * overhang, thick, proud + 0.02))

    def frame(self, name, o, width=0.08, proud=0.05, surface_shift=0.0):
        """Four bars around an opening, proud of the wall."""
        n, t, b = (np.array(o[k], float) for k in ("normal", "t", "b"))
        c0 = np.array(o["center"]) - n * surface_shift + n * (proud / 2 - 0.01)
        w, h = o["w"], o["h"]
        out = []
        for k, (dc, sz) in enumerate([(b * (h / 2 + width / 2), (w + 2 * width, width)), (-b * (h / 2 + width / 2), (w + 2 * width, width)),
                                      (t * (w / 2 + width / 2), (width, h)), (-t * (w / 2 + width / 2), (width, h))]):
            out.append(self.obox(f"{name}_{k}", c0 + dc, t, b, n, (sz[0], sz[1], proud + 0.01)))
        return out

    def dump(self, path=None):
        js = json.dumps({"commands": self.cmds}, indent=0)
        if path:
            with open(path, "w") as fh:
                fh.write(js)
        return js


def box_edges(lo, hi, which="top"):
    """Edge midpoints of an axis box (game coords): 'top' = the four top edges, 'vertical', 'all'."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    xm, ym, zm = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
    top = [(xm, y1, z0), (xm, y1, z1), (x0, y1, zm), (x1, y1, zm)]
    vert = [(x0, ym, z0), (x1, ym, z0), (x0, ym, z1), (x1, ym, z1)]
    return {"top": top, "vertical": vert, "all": top + vert}[which]
