"""Generate a DRV8874 carrier board: a drop-in clone of the Pololu #4035 pinout.

    FREEROUTING_JAR=/path/freerouting-1.9.0.jar python3 gen_board.py

Same size (0.6" x 0.7") and the same 2x7 pins as the Pololu DRV887x carrier,
so it plugs into the master board's carrier sockets. Follows Pololu's
schematic with two changes: no reverse-voltage MOSFET (the master board has
its own protection), so VIN and VM are tied together; and VCP uses 100 nF (TI's
recommended value).

Steps: place parts -> autoroute (Freerouting) -> widen power tracks -> GND
pours -> DRC. gen_fab.py then makes the 3x2 panel and the JLC files.
"""
import os
import re
import subprocess
import sys
import tempfile

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.normpath(os.path.join(HERE, ".."))
PCB = os.path.join(PROJ, "drv8874_carrier.kicad_pcb")
sys.path.insert(0, os.path.join(PROJ, "..", "scorbot-controller", "generator"))
from gen_route import _find, _sexp, prune_floating_vias, stitch  # noqa: E402  (shared with the master board)

MM = pcbnew.FromMM
W, H = 15.24, 17.78          # board, mm (600 x 700 mil)
ORIGIN = (100.0, 100.0)      # board top-left on the KiCad sheet
KISYS = "/usr/share/kicad/footprints"

# Carrier pins, top view, top to bottom (Pololu's labelled pinout).
LEFT = ["VM", "GND", "EN", "PH", "PMODE", "SLEEP", "VREF"]      # x = 1.27
RIGHT = ["VM", "GND", "OUT1", "OUT2", "IMODE", "FAULT", "CS"]   # x = 13.97, top pin is VIN (tied to VM)
RIGHT_LABELS = ["VIN", "GND", "OUT1", "OUT2", "IMODE", "FLT", "CS"]
LEFT_LABELS = ["VM", "GND", "EN", "PH", "PMODE", "SLP", "VREF"]

# DRV8874 (HTSSOP-16, PWP) pin -> net
DRV = {1: "EN", 2: "PH", 3: "SLEEP", 4: "FAULT", 5: "VREF", 6: "CS", 7: "IMODE", 8: "OUT1",
       9: "GND", 10: "OUT2", 11: "VM", 12: "VCP", 13: "CPH", 14: "CPL", 15: "GND", 16: "PMODE", 17: "GND"}

R0603 = ("Resistor_SMD", "R_0603_1608Metric")
C0603 = ("Capacitor_SMD", "C_0603_1608Metric")
C1206 = ("Capacitor_SMD", "C_1206_3216Metric")

# ref, value, footprint, pad nets, (x, y, rot) in board mm, LCSC part
# DRV8874 position (rotated 90 deg: pins 1-8 along the bottom, pin 1 at left)
CX, CY = 7.37, 11.3
TY, BY = CY - 2.8625, CY + 2.8625          # pin rows (top: pins 16..9 left to right)


def top_x(pin):
    return CX - 2.275 + 0.65 * (16 - pin)


def bot_x(pin):
    return CX - 2.275 + 0.65 * (pin - 1)


PARTS = [
    ("U1", "DRV8874PWPR", None, DRV, (CX, CY, 90), "C1855818"),
    ("C1", "10uF 50V", C1206, {1: "GND", 2: "VM"}, (6.1, 3.0, 0), "C13585"),
    ("C2", "10uF 50V", C1206, {1: "VM", 2: "GND"}, (10.7, 3.0, 0), "C13585"),
    ("C3", "100nF 50V", C0603, {1: "VM", 2: "GND"}, (9.8, 4.9, 0), "C14663"),
    ("C5", "22nF 50V", C0603, {1: "CPL", 2: "CPH"}, (5.6, 5.75, 90), "C77571"),
    ("C6", "100nF 50V", C0603, {1: "VCP", 2: "VM"}, (7.15, 5.7, 90), "C14663"),
    ("R2", "10k", R0603, {1: "SLEEP", 2: "VREF"}, (3.5, 15.3, 90), "C25804"),
    ("R3", "2.49k 1%", R0603, {1: "GND", 2: "CS"}, (8.0, 16.6, 0), "C22908"),
    ("R4", "20k", R0603, {1: "IMODE", 2: "GND"}, (11.6, 15.7, 0), "C4184"),
]

# Power copper, drawn by hand and locked before autorouting (the autorouter
# left 0.3 mm necks on these). net: [(layer, width mm, [points])], board mm.
F, B = "F", "B"
VMX, O2X, O1X = top_x(11), top_x(10), bot_x(8)
POWER_COPPER = {
    "VM": [(F, 1.2, [(1.27, 1.27), (13.97, 1.27)]),          # J1 VM - J2 VIN, both layers
           (B, 1.2, [(1.27, 1.27), (13.97, 1.27)]),
           (F, 1.0, [(VMX, 1.27), (VMX, 6.3)]),               # down to pin 11
           (F, 0.4, [(VMX, 6.3), (VMX, TY)])],
    "OUT2": [(F, 0.4, [(O2X, TY), (O2X, 7.4), (O2X + 0.655, 6.8)]),   # pin 10 up, two vias, B.Cu to J2
             (F, 0.8, [(O2X + 0.655, 6.8), (O2X + 1.455, 6.8)]),
             (B, 1.2, [(O2X + 0.655, 6.8), (O2X + 1.455, 6.8), (13.97, 8.89)])],
    "OUT1": [(F, 0.4, [(O1X, BY), (O1X + 0.8, BY)]),                 # pin 8 right, up the right side
             (F, 1.2, [(O1X + 0.8, 14.2), (12.3, 14.2), (12.3, 7.9), (13.97, 6.35)])],
    "GND": [(F, 0.4, [(top_x(9), TY), (top_x(9), 9.9)]),            # pins 9 and 15 into the thermal land
            (F, 0.4, [(top_x(15), TY), (top_x(15), 9.9)]),
            (F, 0.4, [(12.425, 15.7), (12.425, 16.85)])],            # R4's GND pad to a via
}
POWER_VIAS = {"OUT2": [(O2X + 0.655, 6.8), (O2X + 1.455, 6.8)],   # 0.8 / 0.4 mm
              "GND": [(12.425, 16.85)]}

# Freerouting classes: (width um, clearance um, via). Power nets leave
# 0.65 mm-pitch pins, so they route at 0.3 mm and are widened afterwards.
POWER = ("VM", "OUT1", "OUT2", "GND")
CLASSES = {"Power": (300, 150, "Via_800:400"), "kicad_default": (200, 150, "Via_600:300")}
VIAS = {"Via_600:300": (600, 300), "Via_800:400": (800, 400)}
WIDEN = [1.5, 1.2, 1.0, 0.8, 0.6, 0.5]   # mm, tried widest first
EDGE_KEEP = 0.35                          # mm copper to board edge


def P(x, y):
    return pcbnew.VECTOR2I(MM(ORIGIN[0] + x), MM(ORIGIN[1] + y))


def drv_footprint():
    """HTSSOP-16 with a solder-mask-defined thermal pad and six 0.3 mm vias in
    the copper land outside the paste area (tented, so solder isn't wicked
    away). JLC's standard 2-layer process drills 0.3 mm."""
    fp = pcbnew.FootprintLoad(f"{KISYS}/Package_SO.pretty",
                              "HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.46x2.31mm")
    for x in (-1.1, 0.0, 1.1):
        for y in (-1.85, 1.85):
            v = pcbnew.PAD(fp)
            v.SetNumber("17")
            v.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
            v.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
            v.SetSize(pcbnew.VECTOR2I(MM(0.6), MM(0.6)))
            v.SetDrillSize(pcbnew.VECTOR2I(MM(0.3), MM(0.3)))
            ls = pcbnew.LSET()
            ls.AddLayer(pcbnew.F_Cu)
            ls.AddLayer(pcbnew.B_Cu)
            v.SetLayerSet(ls)
            v.SetPos0(pcbnew.VECTOR2I(MM(x), MM(y)))
            v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
            fp.Add(v)
    return fp


def header(board, ref, x, nets, labels, net):
    fp = pcbnew.FootprintLoad(f"{KISYS}/Connector_PinHeader_2.54mm.pretty", "PinHeader_1x07_P2.54mm_Vertical")
    fp.SetReference(ref)
    fp.SetValue("1x7 0.1in pins (hand-soldered)")
    fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    board.Add(fp)
    fp.SetPosition(P(x, 1.27))
    for pad in fp.Pads():
        n = nets[int(pad.GetNumber()) - 1]
        pad.SetShape(pcbnew.PAD_SHAPE_RECT if n == "GND" else pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetSize(pcbnew.VECTOR2I(MM(1.6), MM(1.6)))
        pad.SetDrillSize(pcbnew.VECTOR2I(MM(1.02), MM(1.02)))
        pad.SetNet(net(n))
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    for item in fp.GraphicalItems():   # the header's own silk/courtyard would sit off the board
        item.SetLayer(pcbnew.Cmts_User)
    # pin labels on the back, like Pololu's
    for i, lab in enumerate(labels):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(lab)
        t.SetLayer(pcbnew.B_SilkS)
        t.SetMirrored(True)
        t.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
        t.SetTextThickness(MM(0.14))
        left = x < W / 2
        # text starts beside the pad, reading inward on the back
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT if left else pcbnew.GR_TEXT_H_ALIGN_LEFT)
        t.SetPosition(P(x + (1.25 if left else -1.25), 1.27 + 2.54 * i))
        board.Add(t)


def build():
    board = pcbnew.BOARD()
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.m_CopperEdgeClearance = MM(EDGE_KEEP)
    ds.m_MinClearance = MM(0.15)
    ds.m_TrackMinWidth = MM(0.15)
    ds.m_ViasMinSize = MM(0.6)
    ds.m_MinThroughDrill = MM(0.3)
    nc = ds.m_NetSettings.m_DefaultNetClass
    nc.SetClearance(MM(0.15))
    nc.SetTrackWidth(MM(0.25))
    nc.SetViaDiameter(MM(0.6))
    nc.SetViaDrill(MM(0.3))

    nets = {}

    def net(name):
        if name not in nets:
            nets[name] = pcbnew.NETINFO_ITEM(board, name)
            board.Add(nets[name])
        return nets[name]

    # outline
    corners = [(0, 0), (W, 0), (W, H), (0, H)]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(MM(0.1))
        s.SetStart(P(*a))
        s.SetEnd(P(*b))
        board.Add(s)

    header(board, "J1", 1.27, LEFT, LEFT_LABELS, net)
    header(board, "J2", 13.97, RIGHT, RIGHT_LABELS, net)

    for ref, val, lib, pads, (x, y, rot), lcsc in PARTS:
        fp = drv_footprint() if lib is None else pcbnew.FootprintLoad(f"{KISYS}/{lib[0]}.pretty", lib[1])
        fp.SetReference(ref)
        fp.SetValue(val)
        fp.SetProperty("LCSC", lcsc)
        board.Add(fp)
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            if pad.GetNumber():
                pad.SetNet(net(pads[int(pad.GetNumber())]))
        fp.Value().SetVisible(False)
        r = fp.Reference()
        r.SetTextSize(pcbnew.VECTOR2I(MM(0.6), MM(0.6)))
        r.SetTextThickness(MM(0.1))
        r.SetVisible(False)   # no room for refdes; the README has a placement map

    # silk: name along the middle of the back (the front has no room)
    for text, layer, (x, y), rot in (("DRV8874  CGW", pcbnew.B_SilkS, (W / 2, 7.6), 90),):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetLayer(layer)
        t.SetMirrored(layer == pcbnew.B_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
        t.SetTextThickness(MM(0.14))
        t.SetPosition(P(x, y))
        t.SetTextAngleDegrees(rot)
        board.Add(t)
    # hand-routed power copper, locked so the autorouter keeps it
    for name, runs in POWER_COPPER.items():
        for layer, w, pts in runs:
            for a, b in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(P(*a))
                t.SetEnd(P(*b))
                t.SetWidth(MM(w))
                t.SetLayer(pcbnew.F_Cu if layer == F else pcbnew.B_Cu)
                t.SetNet(net(name))
                t.SetLocked(True)
                board.Add(t)
        for x, y in POWER_VIAS.get(name, []):
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(P(x, y))
            v.SetWidth(MM(0.8))
            v.SetDrill(MM(0.4))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(net(name))
            v.SetLocked(True)
            board.Add(v)
    board.Save(PCB)
    return board


# ---- routing -----------------------------------------------------------------
def rewrite_dsn(text):
    def shrink(m):
        xy = [int(v) for v in m.group(2).split()]
        xs, ys = xy[0::2], xy[1::2]
        e = int(EDGE_KEEP * 1000)
        x0, x1, y0, y1 = min(xs) + e, max(xs) - e, min(ys) + e, max(ys) - e
        return f"{m.group(1)}{x1} {y0}  {x0} {y0}  {x0} {y1}  {x1} {y1}  {x1} {y0})"
    text = re.sub(r'(\(boundary\s*\(path pcb 0\s+)([-\d\s]+)\)', shrink, text, count=1)
    stacks = "".join(f'    (padstack "{n}"\n      (shape (circle F.Cu {d}))\n      (shape (circle B.Cu {d}))\n'
                     f'      (attach off)\n    )\n' for n, (d, _) in VIAS.items())
    text = re.sub(r'(\(library\n)', lambda m: m.group(1) + stacks, text, count=1)
    text = re.sub(r'\(via "Via\[0-1\][^"]*"\)', "(via " + " ".join(f'"{n}"' for n in VIAS) + ")", text)
    m = re.search(r'\(class kicad_default "" (.*?)\(circuit', text, re.S)
    members = m.group(1).split()
    power = [n for n in members if n in POWER]
    rest = [n for n in members if n not in POWER]

    def cls(name, ms, w, clr, via):
        return (f'    (class {name} {" ".join(ms)}\n      (circuit\n        (use_via "{via}")\n      )\n'
                f'      (rule\n        (width {w})\n        (clearance {clr})\n      )\n    )\n')
    block = cls("kicad_default", ['""'] + rest, *CLASSES["kicad_default"]) + cls("Power", power, *CLASSES["Power"])
    end = text.index("\n    )\n", text.index("(rule", m.end())) + len("\n    )\n")
    return text[:m.start()] + block.lstrip() + text[end:]


def import_ses(board, ses_path):
    ses = _sexp(open(ses_path).read())
    routes = _find(ses, "routes")[0]
    to_nm = 1000.0 / float(_find(routes, "resolution")[0][2])
    layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    for n in _find(_find(routes, "network_out")[0], "net"):
        ni = board.FindNet(n[1])
        for wire in _find(n, "wire"):
            for path in _find(wire, "path"):
                xy = [float(v) for v in path[3:] if not isinstance(v, list)]
                pts = [pcbnew.VECTOR2I(int(xy[i] * to_nm), int(-xy[i + 1] * to_nm)) for i in range(0, len(xy), 2)]
                for a, b in zip(pts, pts[1:]):
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(a)
                    t.SetEnd(b)
                    t.SetWidth(int(float(path[2]) * to_nm))
                    t.SetLayer(layers[path[1]])
                    t.SetNet(ni)
                    board.Add(t)
        for via in _find(n, "via"):
            d, drill = VIAS.get(via[1], (600, 300))
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(int(float(via[2]) * to_nm), int(-float(via[3]) * to_nm)))
            v.SetWidth(d * 1000)
            v.SetDrill(drill * 1000)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(ni)
            board.Add(v)


def route(jar):
    tmp = tempfile.mkdtemp()
    dsn, ses = os.path.join(tmp, "b.dsn"), os.path.join(tmp, "b.ses")
    board = pcbnew.LoadBoard(PCB)
    if not pcbnew.ExportSpecctraDSN(board, dsn):
        sys.exit("DSN export failed")
    text = rewrite_dsn(open(dsn).read())
    open(dsn, "w").write(text)
    subprocess.run(["xvfb-run", "-a", "java", "-jar", jar, "-de", dsn, "-do", ses, "-mp", "100", "-oit", "100"],
                   check=True, cwd=tmp, timeout=900, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import_ses(board, ses)   # the session leaves out the locked (fixed) power copper
    board.Save(PCB)


# ---- finishing -----------------------------------------------------------------
def widen(board):
    """Widen power-net tracks as far as clearance allows (widest of WIDEN that
    keeps 0.2 mm from other nets and EDGE_KEEP from the edge)."""
    clr = MM(0.2)
    others = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            others.append(pad)
    tracks = list(board.GetTracks())
    x0, y0, x1, y1 = MM(ORIGIN[0] + EDGE_KEEP), MM(ORIGIN[1] + EDGE_KEEP), MM(ORIGIN[0] + W - EDGE_KEEP), MM(ORIGIN[1] + H - EDGE_KEEP)
    n = 0
    for t in tracks:
        if t.GetClass() != "PCB_TRACK" or t.GetNetname() not in POWER:
            continue
        layer = t.GetLayer()
        old = t.GetWidth()
        for w in WIDEN:
            if MM(w) <= old:
                break
            t.SetWidth(MM(w))
            r = MM(w) // 2
            ok = all(x0 + r <= p.x <= x1 - r and y0 + r <= p.y <= y1 - r for p in (t.GetStart(), t.GetEnd()))
            if ok:
                shape = t.GetEffectiveShape(layer)
                for o in others + tracks:
                    if o is t or o.GetNetCode() == t.GetNetCode() or not o.IsOnLayer(layer):
                        continue
                    if shape.Collide(o.GetEffectiveShape(layer), clr):
                        ok = False
                        break
            if ok:
                n += 1
                break
            t.SetWidth(old)
    return n


def pours(board):
    gnd = board.FindNet("GND")
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(gnd)
        z.SetLocalClearance(MM(0.2))
        z.SetMinThickness(MM(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        poly = z.Outline()
        poly.NewOutline()
        for x, y in ((0, 0), (W, 0), (W, H), (0, H)):
            p = P(x, y)
            poly.Append(p.x, p.y)
        board.Add(z)
    # header GND pads: thermal reliefs so they solder by hand (power pads stay solid)
    for fp in board.GetFootprints():
        if fp.GetReference().startswith("J"):
            for pad in fp.Pads():
                if pad.GetNetname() == "GND":
                    pad.SetZoneConnection(pcbnew.ZONE_CONNECTION_THERMAL)


def drc(path):
    """Error-level DRC findings by kind (KiCad 7's kicad-cli has no drc command)."""
    report = path + ".drc.txt"
    pcbnew.WriteDRCReport(pcbnew.LoadBoard(path), report, pcbnew.EDA_UNITS_MILLIMETRES, True)
    text = open(report).read()
    os.remove(report)
    kinds = {}
    for block in re.split(r"\n(?=\[)", text):
        m = re.match(r"\[(\w+)\].*?Severity: (error|warning)", block, re.S)
        if m:
            kinds.setdefault(m.group(2), {}).setdefault(m.group(1), []).append(block.strip())
    return kinds


def drop_crowded_vias(board, min_web=0.25):
    """GND stitching vias whose hole sits too close to another hole
    (stitch() only checks copper, not drills)."""
    holes = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.HasHole():
                holes.append((pad.GetPosition(), pad.GetDrillSize().x))
    # stitching vias are the unlocked 0.3 mm GND ones (routed vias are 0.4 mm)
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"
            and not t.IsLocked() and t.GetDrillValue() == MM(0.3)]
    gone = []
    for v in vias:
        p, d = v.GetPosition(), v.GetDrillValue()
        others = holes + [(o.GetPosition(), o.GetDrillValue()) for o in board.GetTracks()
                          if o.GetClass() == "PCB_VIA" and o is not v and o not in gone]
        if any((p - q).EuclideanNorm() - (d + e) / 2 < MM(min_web) for q, e in others):
            gone.append(v)
    return [(pcbnew.ToMM(v.GetPosition().x), pcbnew.ToMM(v.GetPosition().y)) for v in gone]


def remove_vias_in_file(path, spots):
    """Delete vias at the given positions by editing the file (pcbnew's
    Remove() leaves dangling Python objects that crash later)."""
    text = open(path).read()
    for x, y in spots:
        pat = re.compile(r"\n\s*\(via \(at %s %s\)[^\n]*" % (re.escape(f"{x:g}"), re.escape(f"{y:g}")))
        text, n = pat.subn("", text, count=1)
        if n != 1:
            raise SystemExit(f"via at {x} {y} not found in {path}")
    open(path, "w").write(text)


# ---- version B: Pololu-style copper ----------------------------------------------
PCB_B = os.path.join(PROJ, "drv8874_carrier_b.kicad_pcb")
POUR_MARGIN = 1.0   # mm of copper either side of each power track's centreline


def pololu_style(src, dst):
    """Copy the routed board and add what Pololu's carrier has: a grid of
    vias through the thermal pad, and poured copper (not just traces) along
    VM, OUT1 and OUT2 on whichever layer each runs."""
    board = pcbnew.LoadBoard(src)
    gnd = board.FindNet("GND")
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() != "GND":
                pad.SetZoneConnection(pcbnew.ZONE_CONNECTION_INHERITED)
    for dx in (-1.0, 0.0, 1.0):          # 3x3 vias in the pad, between the footprint's six
        for dy in (-1.1, 0.0, 1.1):
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(P(CX + dx, CY + dy))
            v.SetWidth(MM(0.6))
            v.SetDrill(MM(0.3))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(gnd)
            v.SetLocked(True)
            board.Add(v)
    for name in ("VM", "OUT1", "OUT2"):
        net = board.FindNet(name)
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            segs = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == net.GetNetCode()
                    and t.GetLayer() == layer and t.GetWidth() >= MM(0.6)]
            if not segs:
                continue
            z = pcbnew.ZONE(board)
            z.SetLayer(layer)
            z.SetNet(net)
            z.SetAssignedPriority(1)
            z.SetLocalClearance(MM(0.2))
            z.SetMinThickness(MM(0.25))
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
            poly = z.Outline()
            r = MM(POUR_MARGIN)
            for t in segs:   # a hexagon-capped band around each segment
                a, b = t.GetStart(), t.GetEnd()
                d = b - a
                n = max(d.EuclideanNorm(), 1)
                ux, uy = d.x / n, d.y / n
                px, py = -uy, ux
                pts = [(a.x - ux * r + px * r, a.y - uy * r + py * r), (b.x + ux * r + px * r, b.y + uy * r + py * r),
                       (b.x + ux * r - px * r, b.y + uy * r - py * r), (a.x - ux * r - px * r, a.y - uy * r - py * r)]
                poly.NewOutline()
                for x, y in pts:
                    poly.Append(int(x), int(y))
            poly.Simplify(pcbnew.SHAPE_POLY_SET.PM_FAST)
            board.Add(z)
    board.Save(dst)


def unrouted(path):
    return len(drc(path).get("error", {}).get("unconnected_items", []))


def main():
    jar = os.environ.get("FREEROUTING_JAR")
    if not jar:
        sys.exit("set FREEROUTING_JAR to freerouting-1.9.0.jar")
    tries = int(os.environ.get("FREEROUTING_TRIES", "6"))
    best = None
    # Freerouting is not deterministic: retry and keep the best result.
    for attempt in range(1, tries + 1):
        build()
        route(jar)
        n = unrouted(PCB)
        print(f"attempt {attempt}: {n} unrouted")
        if best is None or n < best[0]:
            best = (n, open(PCB).read())
        if n == 0:
            break
    open(PCB, "w").write(best[1])
    board = pcbnew.LoadBoard(PCB)
    print(f"widened {widen(board)} power segments")
    pours(board)
    board.Save(PCB)
    board = pcbnew.LoadBoard(PCB)
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    # tie the two pours together wherever both have room for a via
    added = stitch(board, pitch_mm=1.5, via_mm=0.6, drill_mm=0.3, keep_mm=0.25)
    board.Save(PCB)
    for _ in range(2):
        board = pcbnew.LoadBoard(PCB)
        board.BuildConnectivity()
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pruned = prune_floating_vias(board) if _ == 0 else 0
        board.Save(PCB)
    # in a child process: pcbnew's Python objects misbehave after Remove()
    subprocess.run([sys.executable, __file__, "--drop-crowded"], check=True)
    board = pcbnew.LoadBoard(PCB)
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(PCB)
    print(f"stitching vias: {added - pruned}")
    kinds = drc(PCB)
    for sev in ("error", "warning"):
        print(f"DRC {sev}s:", {k: len(v) for k, v in kinds.get(sev, {}).items()})
    for k, v in kinds.get("error", {}).items():
        print("\n".join(v[:5]))
    # version B: Pololu-style pours and pad vias on the same routing
    subprocess.run([sys.executable, __file__, "--version-b"], check=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--drop-crowded"]:
        path = sys.argv[2] if len(sys.argv) > 2 else PCB
        spots = drop_crowded_vias(pcbnew.LoadBoard(path))
        remove_vias_in_file(path, spots)
        print(f"dropped {len(spots)} crowded stitching vias")
    elif sys.argv[1:] == ["--version-b"]:
        pololu_style(PCB, PCB_B)
        subprocess.run([sys.executable, __file__, "--drop-crowded", PCB_B], check=True)
        b = pcbnew.LoadBoard(PCB_B)
        b.BuildConnectivity()
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        b.Save(PCB_B)
        kinds = drc(PCB_B)
        for sev in ("error", "warning"):
            print(f"version B DRC {sev}s:", {k: len(v) for k, v in kinds.get(sev, {}).items()})
        for k, v in kinds.get("error", {}).items():
            print("\n".join(v[:5]))
    else:
        main()
