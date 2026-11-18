"""Writes small G-code files by hand, in the comment style of each slicer, for the tests."""

STYLES = {
    # layer start, feature, the names of the features
    "bambu": ("; Z_HEIGHT: {z:.3f}\n; LAYER_HEIGHT: {h:.3f}\n", "; FEATURE: {f}\n; LINE_WIDTH: {w:.2f}\n",
              {"wall": "Outer wall", "support": "Support", "bridge": "Bridge", "infill": "Sparse infill"}),
    "prusa": (";LAYER_CHANGE\n;Z:{z:.3f}\n;HEIGHT:{h:.3f}\n", ";TYPE:{f}\n;WIDTH:{w:.2f}\n",
              {"wall": "External perimeter", "support": "Support material", "bridge": "Overhang perimeter",
               "infill": "Internal infill"}),
    "orca": (";LAYER_CHANGE\n;Z:{z:.3f}\n;HEIGHT:{h:.3f}\n", ";TYPE:{f}\n;WIDTH:{w:.2f}\n",
             {"wall": "Outer wall", "support": "Support", "bridge": "Bridge", "infill": "Sparse infill"}),
    "cura": (";LAYER:{n}\n", ";TYPE:{f}\n",
             {"wall": "WALL-OUTER", "support": "SUPPORT", "bridge": "SKIN", "infill": "FILL"}),
}
H, W = 0.2, 0.42


class Gcode:
    def __init__(self, style):
        self.style = style
        self.out = ["M83\nG90\n"]
        if style == "cura":
            self.out.insert(0, ";FLAVOR:Marlin\n;Layer height: 0.2\n")
        self.n = -1

    def layer(self, n):
        """Start layer n (0 is the first); its top is at (n + 1) * H."""
        self.n = n
        z = (n + 1) * H
        self.out.append(STYLES[self.style][0].format(z=z, h=H, n=n))
        self.out.append(f"G1 Z{z:.3f} F600\n")

    def path(self, kind, points, closed=False):
        """One printed path of a feature through the points."""
        self.out.append(STYLES[self.style][1].format(f=STYLES[self.style][2][kind], w=W))
        pts = list(points) + ([points[0]] if closed else [])
        self.out.append(f"G1 X{pts[0][0]:.3f} Y{pts[0][1]:.3f} F9000\n")
        for x, y in pts[1:]:
            self.out.append(f"G1 X{x:.3f} Y{y:.3f} E0.05\n")

    def box(self, kind, x0, y0, x1, y1):
        """A filled rectangle: a loop and lines along x inside it."""
        self.path(kind, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True)
        y = y0 + W
        while y < y1 - W / 2:
            self.path(kind, [(x0 + W, y), (x1 - W, y)])
            y += W

    def write(self, path):
        with open(path, "w") as f:
            f.write("".join(self.out))
        return str(path)
