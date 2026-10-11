"""Composite a copper SVG and a black-and-white silkscreen SVG into one PNG,
with the silkscreen drawn on top (kicad-cli draws copper pours over it)."""
import sys

import cairosvg
from PIL import Image

cu_svg, silk_svg, out = sys.argv[1:4]
tmp = out + ".tmp.png"
cairosvg.svg2png(url=cu_svg, write_to=out, output_width=2400, background_color="white")
cairosvg.svg2png(url=silk_svg, write_to=tmp, output_width=2400, background_color="white")
cu = Image.open(out).convert("RGB")
silk = Image.open(tmp).convert("L").resize(cu.size)
ink = silk.point(lambda v: 255 if v < 128 else 0)
cu.paste(Image.new("RGB", cu.size, (245, 240, 200)), mask=ink)
cu.save(out)
import os
os.remove(tmp)
