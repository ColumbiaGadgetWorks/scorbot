"""JLCPCB files for the DRV8874 carrier: a 3x2 V-cut panel with 5 mm rails.

    python3 gen_fab.py

fab/<version>/panel/   gerbers zip, jlc_bom.csv, jlc_cpl.csv for the panel (order this)
fab/<version>/single/  the same for one board, in case you let JLC panelize instead

Versions: "a" (drv8874_carrier.kicad_pcb, traces) and "b"
(drv8874_carrier_b.kicad_pcb, Pololu-style pours and pad vias).

Each panel copy's designators get a suffix (R2_1 .. R2_6) so the CPL has one
line per placed part.
"""
import csv
import os
import shutil
import subprocess
import tempfile
import zipfile

import pcbnew

import gen_board as gb

MM = pcbnew.FromMM
COLS, ROWS, RAIL = 3, 2, 5.0
FAB = os.path.join(gb.PROJ, "fab")
LCSC = {ref: lcsc for ref, _, _, _, _, lcsc in gb.PARTS}
# JLC's HTSSOP model sits 90 degrees from KiCad's (as with the TSSOPs on the
# master board): check U1 in JLC's placement preview.
ROT_FIX = {"U1": -90}


def seg(board, a, b, layer=pcbnew.Edge_Cuts):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetLayer(layer)
    s.SetWidth(MM(0.1))
    s.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
    s.SetEnd(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])))
    board.Add(s)


def tooling_hole(board, ref, x, y):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference(ref)
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    pad = pcbnew.PAD(fp)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetSize(pcbnew.VECTOR2I(MM(1.152), MM(1.152)))
    pad.SetDrillSize(pcbnew.VECTOR2I(MM(1.152), MM(1.152)))
    ls = pcbnew.LSET()
    ls.AddLayer(pcbnew.F_Mask)
    ls.AddLayer(pcbnew.B_Mask)
    pad.SetLayerSet(ls)
    fp.Add(pad)
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    board.Add(fp)
    fp.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))


def fiducial(board, ref, x, y):
    fp = pcbnew.FootprintLoad(f"{gb.KISYS}/Fiducial.pretty", "Fiducial_1mm_Mask2mm")
    fp.SetReference(ref)
    fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    board.Add(fp)
    fp.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))


def make_panel(src, dst):
    panel = pcbnew.LoadBoard(src)
    ox, oy = gb.ORIGIN
    items = (list(panel.GetFootprints()) + list(panel.GetTracks()) + list(panel.Zones())
             + [d for d in panel.GetDrawings() if d.GetLayer() != pcbnew.Edge_Cuts])
    for d in panel.GetDrawings():   # single-board outline off the edge layer (Remove() is unsafe here)
        if d.GetLayer() == pcbnew.Edge_Cuts:
            d.SetLayer(pcbnew.Cmts_User)
    refs = {fp.GetReference() for fp in panel.GetFootprints()}
    copies = [(r, c) for r in range(ROWS) for c in range(COLS)]
    for r, c in copies[1:]:          # duplicate from the unmoved originals
        for it in items:
            new = it.Duplicate()
            panel.Add(new)
            new.Move(pcbnew.VECTOR2I(MM(c * gb.W), MM(RAIL + r * gb.H)))
    for it in items:
        it.Move(pcbnew.VECTOR2I(0, MM(RAIL)))
    for fp in panel.GetFootprints():  # suffix each copy's designators: R2_1 .. R2_6
        if fp.GetReference() in refs:
            pos = fp.GetPosition()
            c = int((pcbnew.ToMM(pos.x) - ox) // gb.W)
            r = int((pcbnew.ToMM(pos.y) - oy - RAIL) // gb.H)
            fp.SetReference(f"{fp.GetReference()}_{r * COLS + c + 1}")
    pw, ph = COLS * gb.W, ROWS * gb.H + 2 * RAIL
    # outline, plus V-cut lines right across the panel (JLC reads straight
    # lines through the panel on the outline layer as V-cuts)
    for a, b in (((0, 0), (pw, 0)), ((pw, 0), (pw, ph)), ((pw, ph), (0, ph)), ((0, ph), (0, 0))):
        seg(panel, (ox + a[0], oy + a[1]), (ox + b[0], oy + b[1]))
    for r in range(ROWS + 1):
        y = oy + RAIL + r * gb.H
        seg(panel, (ox, y), (ox + pw, y))
    for c in range(1, COLS):
        x = ox + c * gb.W
        seg(panel, (x, oy), (x, oy + ph))
    for i, (x, y) in enumerate(((3, 2.5), (pw - 3, 2.5), (3, ph - 2.5), (pw - 3, ph - 2.5)), 1):
        tooling_hole(panel, f"H{i}", ox + x, oy + y)
    for i, (x, y) in enumerate(((8, 2.5), (pw - 8, 2.5), (8, ph - 2.5)), 1):
        fiducial(panel, f"FID{i}", ox + x, oy + y)
    t = pcbnew.PCB_TEXT(panel)
    t.SetText("DRV8874 CARRIER x6 - V-CUT")
    t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(MM(1.0), MM(1.0)))
    t.SetTextThickness(MM(0.15))
    t.SetPosition(pcbnew.VECTOR2I(MM(ox + pw / 2), MM(oy + ph - 2.5)))
    panel.Add(t)
    panel.Save(dst)
    panel = pcbnew.LoadBoard(dst)
    panel.BuildConnectivity()
    pcbnew.ZONE_FILLER(panel).Fill(panel.Zones())
    panel.Save(dst)


def fab(pcb, out):
    shutil.rmtree(out, ignore_errors=True)
    gdir = os.path.join(out, "gerbers")
    os.makedirs(gdir)
    layers = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
    subprocess.run(["kicad-cli", "pcb", "export", "gerbers", "--layers", layers, "--subtract-soldermask",
                    "-o", gdir + "/", pcb], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
                    "--generate-map", "--map-format", "gerberx2", "-o", gdir + "/", pcb],
                   check=True, stdout=subprocess.DEVNULL)
    name = os.path.splitext(os.path.basename(pcb))[0]
    with zipfile.ZipFile(os.path.join(out, name + "_gerbers.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(gdir)):
            z.write(os.path.join(gdir, f), f)
    board = pcbnew.LoadBoard(pcb)
    groups = {}
    for fp in board.GetFootprints():
        base = fp.GetReference().split("_")[0]
        if base in LCSC:
            key = LCSC[base]
            g = groups.setdefault(key, {"values": [], "refs": [], "fp": fp.GetFPID().GetLibItemName().wx_str()})
            g["refs"].append(fp.GetReference())
            if fp.GetValue() not in g["values"]:
                g["values"].append(fp.GetValue())
    with open(os.path.join(out, "jlc_bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for part, g in groups.items():
            w.writerow([" / ".join(g["values"]), ",".join(sorted(g["refs"])), g["fp"], part])
    tmp = tempfile.mkdtemp()
    pos = os.path.join(tmp, "pos.csv")
    subprocess.run(["kicad-cli", "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "front",
                    "--smd-only", "-o", pos, pcb], check=True, stdout=subprocess.DEVNULL)
    n = 0
    with open(pos) as f, open(os.path.join(out, "jlc_cpl.csv"), "w", newline="") as g:
        w = csv.writer(g)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for row in csv.DictReader(f):
            base = row["Ref"].split("_")[0]
            if base in LCSC:
                rot = (float(row["Rot"]) + ROT_FIX.get(base, 0)) % 360
                w.writerow([row["Ref"], row["PosX"] + "mm", row["PosY"] + "mm", "Top", f"{rot:.6f}"])
                n += 1
    return sum(len(g["refs"]) for g in groups.values()), len(groups), n


def main():
    for version, pcb in (("a", gb.PCB), ("b", gb.PCB_B)):
        if not os.path.exists(pcb):
            continue
        panel = pcb.replace(".kicad_pcb", "_panel.kicad_pcb")
        make_panel(pcb, panel)
        for board, sub in ((pcb, "single"), (panel, "panel")):
            parts, lines, placed = fab(board, os.path.join(FAB, version, sub))
            print(f"{version}/{sub}: {parts} parts in {lines} BOM lines, {placed} placements")
    # the three files to upload to JLC for the 6-up panel of version B, in one place
    src, dst = os.path.join(FAB, "b", "panel"), os.path.join(FAB, "JLC_upload_6up_version_b")
    if os.path.isdir(src):
        shutil.rmtree(dst, ignore_errors=True)
        os.makedirs(dst)
        for a, b in (("drv8874_carrier_b_panel_gerbers.zip", "1_GERBERS_drv8874_6up.zip"),
                     ("jlc_bom.csv", "2_BOM_drv8874_6up.csv"), ("jlc_cpl.csv", "3_CPL_drv8874_6up.csv")):
            shutil.copy(os.path.join(src, a), os.path.join(dst, b))


if __name__ == "__main__":
    main()
