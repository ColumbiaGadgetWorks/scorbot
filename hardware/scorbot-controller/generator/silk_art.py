"""Turn a logo image into filled silkscreen rectangles on a KiCad board.

No tracing library needed: the image is thresholded on a grid of `res` mm,
each row becomes runs of 'ink' pixels, and identical runs on consecutive rows
merge into one rectangle. At 0.08 mm the steps are far below what silkscreen
can print.
"""
import pcbnew
from PIL import Image


def ink_mask(path, mode):
    """Return a function (x, y) -> bool over an RGBA image, and its size."""
    im = Image.open(path).convert("RGBA")
    px = im.load()
    if mode == "colored":     # anything that is not white/transparent
        def ink(x, y):
            r, g, b, a = px[x, y]
            return a > 128 and min(r, g, b) < 200
    elif mode == "dark":      # black only
        def ink(x, y):
            r, g, b, a = px[x, y]
            return a > 128 and max(r, g, b) < 90
    else:
        raise ValueError(mode)
    return im, ink


def add_logo(board, path, layer, center_mm, height_mm, origin_mm=(0, 0), mode="colored", mirror=False, res=0.08):
    im, _ = ink_mask(path, mode)
    w0, h0 = im.size
    rows = max(1, int(round(height_mm / res)))
    cols = max(1, int(round(w0 * rows / h0)))
    im = im.resize((cols, rows), Image.LANCZOS)
    tmp = "/tmp/_silk_art.png"
    im.save(tmp)
    im, ink = ink_mask(tmp, mode)
    MM = pcbnew.FromMM
    cx, cy = center_mm
    ox, oy = origin_mm
    x0 = cx - cols * res / 2
    y0 = cy - rows * res / 2

    def runs(y):
        out, x = [], 0
        while x < cols:
            if ink(x, y):
                s = x
                while x < cols and ink(x, y):
                    x += 1
                out.append((s, x))
            else:
                x += 1
        return out

    open_rects = {}  # (s, e) -> start row
    rects = []
    for y in range(rows + 1):
        cur = set(runs(y)) if y < rows else set()
        for key in list(open_rects):
            if key not in cur:
                rects.append((key[0], key[1], open_rects.pop(key), y))
        for key in cur:
            open_rects.setdefault(key, y)
    for s, e, ys, ye in rects:
        if mirror:  # drawn so it reads correctly when the board is viewed from the back
            s, e = cols - e, cols - s
        xa, xb = ox + x0 + s * res, ox + x0 + e * res
        ya, yb = oy + y0 + ys * res, oy + y0 + ye * res
        shape = pcbnew.PCB_SHAPE(board)
        shape.SetShape(pcbnew.SHAPE_T_POLY)
        shape.SetPolyPoints([pcbnew.VECTOR2I(MM(xa), MM(ya)), pcbnew.VECTOR2I(MM(xb), MM(ya)),
                             pcbnew.VECTOR2I(MM(xb), MM(yb)), pcbnew.VECTOR2I(MM(xa), MM(yb))])
        shape.SetFilled(True)
        shape.SetWidth(0)
        shape.SetLayer(layer)
        board.Add(shape)
    return len(rects)
