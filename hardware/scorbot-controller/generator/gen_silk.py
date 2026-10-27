"""Silkscreen labels for the routed master board (run after gen_route.py).

    python3 gen_silk.py

Adds labels for every connector and pin a person wires or plugs into, the
large CGW logo bottom middle, and fixes the DevKit's 5V/3V3/GND marks.
Copper is untouched, so the board needn't be re-routed. Re-running replaces
the previous labels: they live in the group "silk_labels", and the front
logo is the only gr_poly on F.SilkS.
"""
import os
import re

import pcbnew

import netclasses
import silk_art

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.normpath(os.path.join(HERE, ".."))
PCB = os.path.join(PROJ, "scorbot_controller.kicad_pcb")
OX, OY = 30.0, 30.0
MM = pcbnew.FromMM
LOGO = (100.0, 114.8)     # board mm, centre of the CGW logo
LOGO_H = 23.0             # mm (was 14)

# (text, x, y, size mm, rotation deg, justify) in board mm; F.SilkS
LABELS = [
    # ---- power entry, left edge ----
    ("12V IN", 8.0, 8.6, 1.2, 0, "c"),
    ("(center +)", 21.0, 15.0, 0.9, 0, "c"),
    ("12 V DC, 18 V MAX", 22.0, 17.0, 0.9, 0, "c"),
    ("12V IN 2", 19.0, 30.15, 1.2, 0, "c"),
    ("+", 10.6, 27.61, 1.4, 0, "l"),
    ("-", 10.6, 32.69, 1.4, 0, "l"),
    ("FUSE (inline)", 10.55, 43.37, 0.8, 90, "c"),
    ("FUSE 5A blade", 20.3, 44.0, 1.1, 90, "c"),
    ("fit F1 OR J7", 22.3, 44.0, 0.8, 90, "c"),
    ("E-STOP (NC)", 11.3, 63.6, 1.0, 90, "c"),
    ("TVS: fit D1 OR D8", 46.0, 17.6, 0.8, 0, "c"),
    # ---- 12 V -> 5 V buck module socket (pins at x 15.8) ----
    ("IN+ 12V", 17.4, 66.33, 0.9, 0, "l"),
    ("IN- GND", 17.4, 68.87, 0.9, 0, "l"),
    ("OUT- GND", 17.4, 71.41, 0.9, 0, "l"),
    ("OUT+ 5V", 17.4, 73.95, 0.9, 0, "l"),
    ("12V -> 5V BUCK", 26.0, 77.4, 1.2, 0, "c"),
    ("set to 5.0 V before fitting the ESP32", 26.0, 79.4, 0.8, 0, "c"),
    # ---- I2C and GPIO headers (pins at y 62.53) ----
    ("3V3", 61.83, 66.3, 0.8, 90, "c"),
    ("GND", 64.37, 66.3, 0.8, 90, "c"),
    ("SDA", 66.91, 66.3, 0.8, 90, "c"),
    ("SCL", 69.45, 66.3, 0.8, 90, "c"),
    ("I2C", 65.64, 69.4, 1.0, 0, "c"),
    ("P06", 74.28, 66.3, 0.8, 90, "c"),
    ("P07", 76.81, 66.3, 0.8, 90, "c"),
    ("P17", 79.36, 66.3, 0.8, 90, "c"),
    ("GND", 81.89, 66.3, 0.8, 90, "c"),
    ("GPIO (TCA9555)", 78.1, 69.4, 0.9, 0, "c"),
    # ---- status LEDs ----
    ("VM", 55.8, 43.6, 0.8, 0, "c"),
    ("5V", 45.9, 65.3, 0.8, 0, "c"),
    ("STATUS", 77.0, 103.3, 0.8, 0, "c"),
    ("3V3", 86.2, 103.3, 0.8, 0, "c"),
    # ---- ESP32 DevKit (USB end at the right) ----
    ("USB", 52.3, 112.3, 1.2, 90, "c"),
    ("ESP32-DevKitC  38-pin", 26.0, 96.6, 1.0, 0, "c"),
    # ---- robot cable ----
    ("ROBOT CABLE", 176.0, 114.6, 1.0, 0, "c"),
    ("DD-50", 176.0, 116.4, 1.0, 0, "c"),
]
# motor driver sockets: label inside each outline (under the carrier)
JOINTS = ["BASE", "SHOULDER", "ELBOW", "WRIST A", "WRIST B", "GRIPPER"]
for i, j in enumerate(JOINTS):
    cx = 58 + i * 21.0 + 9.17
    LABELS += [(f"M{i + 1}", cx, 9.5, 2.0, 0, "c"), (j, cx, 13.0, 1.0, 0, "c")]


def top_level_blocks(text):
    """Split a .kicad_pcb into (gap, block) pairs, one per top-level item."""
    out, i = [], 0
    while True:
        j = text.find("\n  (", i)
        if j < 0:
            return out, text[i:]
        depth, k = 0, j + 3
        while True:
            c = text[k]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            elif c == '"':
                k = text.index('"', k + 1)
            k += 1
        out.append((text[i:j], text[j:k + 1]))
        i = k + 1


def strip_previous(path):
    """Remove the last run's labels (group "silk_labels") and the front logo
    (every gr_poly on F.SilkS) by editing the file: pcbnew's Remove() leaves
    dangling Python objects that crash later."""
    blocks, tail = top_level_blocks(open(path).read())
    uid = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    ids = set()
    for _, b in blocks:
        if b.startswith("\n  (group") and '"silk_labels"' in b:
            ids |= set(re.findall(uid, b[b.index("(members"):]))
    out, n = [], 0
    for gap, b in blocks:
        head = b[4:12]
        tstamp = re.search(r"\(tstamp (" + uid + r")\)", b)
        drop = ((head.startswith("gr_poly") and '(layer "F.SilkS")' in b)
                or (head.startswith("group") and '"silk_labels"' in b)
                or (head.startswith("gr_") and tstamp and tstamp.group(1) in ids))
        n += drop
        out.append(gap if drop else gap + b)
    open(path, "w").write("".join(out) + tail)
    return n


def P(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def main():
    print(f"removed {strip_previous(PCB)} old label/logo items")
    board = pcbnew.LoadBoard(PCB)
    group = pcbnew.PCB_GROUP(board)
    group.SetName("silk_labels")
    board.Add(group)
    just = {"l": pcbnew.GR_TEXT_H_ALIGN_LEFT, "c": pcbnew.GR_TEXT_H_ALIGN_CENTER, "r": pcbnew.GR_TEXT_H_ALIGN_RIGHT}
    for txt, x, y, size, rot, j in LABELS:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(txt)
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        t.SetTextThickness(MM(max(0.15, size * 0.15)))
        t.SetHorizJustify(just[j])
        t.SetTextAngleDegrees(rot)
        t.SetPosition(P(x, y))
        board.Add(t)
        group.AddItem(t)
    # arrow toward the DevKit's USB socket
    arrow = pcbnew.PCB_SHAPE(board)
    arrow.SetShape(pcbnew.SHAPE_T_POLY)
    arrow.SetLayer(pcbnew.F_SilkS)
    arrow.SetFilled(True)
    arrow.SetWidth(MM(0.1))
    arrow.SetPolyPoints([P(53.6, 110.9), P(55.2, 112.3), P(53.6, 113.7)])
    board.Add(arrow)
    group.AddItem(arrow)

    # DevKit: the 5V / 3V3 / GND marks sat between the end pins and the board
    # edge (cut off, or under the pins). Turn them and move them inward.
    u2 = board.FindFootprintByReference("U2")
    pads = {p.GetNumber(): p.GetPosition() for p in u2.Pads()}
    marks = {"5V": ("19", (2.2, 0)), "3V3": ("1", (0, -2.6)), "GND": ("20", (0, 2.7))}
    for it in u2.GraphicalItems():
        if "TEXT" in it.GetClass() and it.GetText() in ("5V", "3V3") and it.GetLayer() == pcbnew.F_SilkS:
            it.SetVisible(False)
    for txt, (pin, (dx, dy)) in marks.items():
        t = pcbnew.PCB_TEXT(board)
        t.SetText(txt)
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(MM(0.9), MM(0.9)))
        t.SetTextThickness(MM(0.15))
        t.SetTextAngleDegrees(90)
        p = pads[pin]
        t.SetPosition(pcbnew.VECTOR2I(p.x + MM(dx), p.y + MM(dy)))
        board.Add(t)
        group.AddItem(t)

    # references that the new labels would cover
    moves = {"J5": (65.64, 59.6, 0), "J6": (78.1, 59.6, 0), "J2": (4.1, 23.2, 0), "J7": (4.1, 36.8, 0),
             "J3": (4.1, 57.0, 0), "F1": (15.0, 34.8, 0)}
    for ref, (x, y, rot) in moves.items():
        r = board.FindFootprintByReference(ref).Reference()
        r.SetTextAngleDegrees(rot)
        r.SetPosition(P(x, y))

    board.Save(PCB)
    board = pcbnew.LoadBoard(PCB)
    n = silk_art.add_logo(board, os.path.join(PROJ, "art", "columbia_gadget_works_logo.png"), pcbnew.F_SilkS,
                          LOGO, LOGO_H, origin_mm=(OX, OY), mode="colored")
    board.Save(PCB)
    netclasses.write()   # Board.Save() resets the project's net classes
    print(f"{len(LABELS) + 3} labels, logo {LOGO_H} mm ({n} shapes) -> {os.path.relpath(PCB, PROJ)}")


if __name__ == "__main__":
    main()
