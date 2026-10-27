"""RFQ package for version B: everything an assembler needs to quote.

    python3 gen_rfq.py      (after gen_board.py and gen_fab.py)

fab/b/rfq/
    drv8874_carrier_b_rfq.zip        all of the below in one file
    gerbers_panel.zip                3x2 V-cut panel (order this)
    gerbers_single.zip               one board, if the assembler panelizes
    BOM.csv                          complete BOM, manufacturer part numbers, per board and per panel
    CPL_panel.csv, CPL_single.csv    placements, mm from the lower-left corner, Y up
    RFQ_NOTES.txt                    board spec and assembly notes
"""
import csv
import os
import shutil
import zipfile

import pcbnew

import gen_board as gb
import gen_fab as gf

OUT = os.path.join(gb.PROJ, "fab", "b", "rfq")
PANEL = gb.PCB_B.replace(".kicad_pcb", "_panel.kicad_pcb")
PER_PANEL = gf.COLS * gf.ROWS

# LCSC -> (manufacturer, MPN, description)
PARTS = {
    "C1855818": ("Texas Instruments", "DRV8874PWPR", "Brushed DC motor driver, 37 V 6 A, HTSSOP-16 with thermal pad"),
    "C13585": ("Samsung Electro-Mechanics", "CL31A106KBHNNNE", "MLCC 10 uF 50 V X5R 10% 1206"),
    "C14663": ("YAGEO", "CC0603KRX7R9BB104", "MLCC 100 nF 50 V X7R 10% 0603"),
    "C77571": ("FH (Guangdong Fenghua)", "0603B223K500NT", "MLCC 22 nF 50 V X7R 10% 0603"),
    "C25804": ("UNI-ROYAL", "0603WAF1002T5E", "Resistor 10 k 1% 0.1 W 0603"),
    "C22908": ("UNI-ROYAL", "0603WAF2491T5E", "Resistor 2.49 k 1% 0.1 W 0603"),
    "C4184": ("UNI-ROYAL", "0603WAF2002T5E", "Resistor 20 k 1% 0.1 W 0603"),
}
PACKAGE = {"C_0603_1608Metric": "0603", "R_0603_1608Metric": "0603", "C_1206_3216Metric": "1206",
           "HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.46x2.31mm": "HTSSOP-16 (TI PWP)"}


def footprints(pcb):
    board = pcbnew.LoadBoard(pcb)
    out = []
    for fp in board.GetFootprints():
        base = fp.GetReference().split("_")[0]
        if base in gf.LCSC:
            out.append(fp)
    return board, out


def write_bom():
    _, fps = footprints(gb.PCB_B)
    rows = {}
    for fp in sorted(fps, key=lambda f: f.GetReference()):
        lcsc = gf.LCSC[fp.GetReference()]
        r = rows.setdefault(lcsc, {"refs": [], "value": fp.GetValue(),
                                   "pkg": PACKAGE[fp.GetFPID().GetLibItemName().wx_str()]})
        r["refs"].append(fp.GetReference())
    with open(os.path.join(OUT, "BOM.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Item", "Designator (per board)", "Qty per board", f"Qty per panel ({PER_PANEL} boards)",
                    "Value", "Description", "Package", "Manufacturer", "Manufacturer P/N", "LCSC P/N",
                    "Assembly"])
        item = 0
        for lcsc, r in rows.items():
            item += 1
            mfr, mpn, desc = PARTS[lcsc]
            n = len(r["refs"])
            w.writerow([item, ",".join(r["refs"]), n, n * PER_PANEL, r["value"], desc, r["pkg"], mfr, mpn, lcsc,
                        "SMT, top side"])
        item += 1
        w.writerow([item, "J1,J2", 2, 2 * PER_PANEL, "1x7 male header 2.54 mm",
                    "Pin header, 1 row x 7, 2.54 mm pitch, straight", "THT", "any", "-", "-",
                    "Do not fit (customer fits by hand)"])


def write_cpl(pcb, name, height):
    board, fps = footprints(pcb)
    ox, oy = gb.ORIGIN
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Value", "Package", "Mid X (mm)", "Mid Y (mm)", "Rotation (deg)", "Layer"])
        for fp in sorted(fps, key=lambda f: (f.GetReference().split("_")[0], f.GetReference())):
            p = fp.GetPosition()
            w.writerow([fp.GetReference(), fp.GetValue(), PACKAGE[fp.GetFPID().GetLibItemName().wx_str()],
                        f"{pcbnew.ToMM(p.x) - ox:.3f}", f"{oy + height - pcbnew.ToMM(p.y):.3f}",
                        f"{fp.GetOrientationDegrees() % 360:.0f}", "Top"])
    return len(fps)


NOTES = f"""DRV8874 carrier, version B - RFQ
=================================

Bare board
  Layers           2, FR-4, 1.6 mm, 1 oz copper both sides
  Finish           HASL (lead-free OK) or ENIG
  Mask / silk      any colour mask, white silk, both sides
  Min track/space  0.15 mm / 0.15 mm
  Min drill        0.3 mm vias (tented), 1.02 mm header holes, 1.152 mm NPTH tooling holes
  Board            15.24 x 17.78 mm (0.6 x 0.7 in)
  Panel            {gf.COLS} x {gf.ROWS} boards, {gf.COLS * gb.W:.2f} x {gf.ROWS * gb.H + 2 * gf.RAIL:.2f} mm, V-cut
                   between boards and along both rails (all straight internal lines on the
                   outline layer are V-cuts). 5 mm rails top and bottom with 3 fiducials
                   and 4 tooling holes.

Assembly
  SMT, top side only, {sum(1 for _ in gf.LCSC)} placements per board ({sum(1 for _ in gf.LCSC) * PER_PANEL} per panel).
  Bottom side has no parts. The 1x7 headers (J1, J2) are not fitted.
  U1 (DRV8874PWPR) has a thermal pad; solder it fully to the pad
  (solder-mask-defined opening, 2 paste windows, vias under the pad).
  Pin 1 of U1 is at the lower-left, next to the silkscreen triangle.

Placement files
  CPL_panel.csv / CPL_single.csv: centre of each part in mm from the lower-left
  corner of the panel (or board), Y up, rotation counter-clockwise in KiCad /
  IPC-7351 zero orientation. (For JLCPCB use fab/b/panel/jlc_cpl.csv, which
  has JLC's rotation correction for U1.)

Quantity
  e.g. 2 panels = 12 boards (bare boards: 5 panels minimum at most fabs)
"""


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    shutil.copy(os.path.join(gb.PROJ, "fab", "b", "panel", "drv8874_carrier_b_panel_gerbers.zip"),
                os.path.join(OUT, "gerbers_panel.zip"))
    shutil.copy(os.path.join(gb.PROJ, "fab", "b", "single", "drv8874_carrier_b_gerbers.zip"),
                os.path.join(OUT, "gerbers_single.zip"))
    write_bom()
    n_panel = write_cpl(PANEL, "CPL_panel.csv", gf.ROWS * gb.H + 2 * gf.RAIL)
    n_single = write_cpl(gb.PCB_B, "CPL_single.csv", gb.H)
    open(os.path.join(OUT, "RFQ_NOTES.txt"), "w").write(NOTES)
    files = sorted(f for f in os.listdir(OUT))
    with zipfile.ZipFile(os.path.join(OUT, "drv8874_carrier_b_rfq.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(OUT, f), f)
    print(f"rfq: {n_single} placements per board, {n_panel} per panel -> {os.path.relpath(OUT, gb.PROJ)}")


if __name__ == "__main__":
    main()
