# DRV8874 carrier (Pololu #4035 clone)

A small board with TI's DRV8874 that plugs into the master board's motor
driver sockets in place of a Pololu #4035. It has the same 0.6" x 0.7" size,
the same 2x7 pinout and the same default resistor values, so the master board
and the firmware's DRV8874 settings work with either. JLC places every SMD
part; you solder the 0.1" pins.

## Files

| Path | What it is |
|---|---|
| `generator/gen_board.py` | Builds and routes `drv8874_carrier.kicad_pcb` (version A), then makes `drv8874_carrier_b.kicad_pcb` (version B). Needs `FREEROUTING_JAR` |
| `generator/gen_fab.py` | Makes a 3x2 panel of each version (`*_panel.kicad_pcb`) and the JLC files |
| `fab/b/panel/` | **Order this:** gerbers zip, `jlc_bom.csv`, `jlc_cpl.csv` for the version B panel |
| `fab/a/panel/` | The same for version A |
| `fab/<a or b>/single/` | One board, if you would rather let JLC panelize |
| `docs/` | Renders: `version_a.png`, `version_b.png` (front, and back as seen from below), `panel_b.png` |

## Two versions

Both have the same parts, placement and routing; B adds copper.

- **A:** VM, OUT1 and OUT2 are 1.0-1.2 mm traces. The thermal pad has six
  vias around the paste area.
- **B (recommended), closer to Pololu's board:** VM, OUT1 and OUT2 also get
  copper pours that fill the free space around their traces (on whichever
  layer each runs), and the thermal pad has 15 vias (a 5 x 3 grid) into the
  bottom GND pour. The middle row of vias sits in the pad's solder area, as
  on Pololu's board; a little solder wicks down them, which is normal.

```
cd generator
FREEROUTING_JAR=/path/freerouting-1.9.0.jar python3 gen_board.py
python3 gen_fab.py
```

## Circuit

It follows Pololu's DRV887x carrier schematic, with two changes:

- **No reverse-voltage MOSFET.** The master board already has reverse-polarity
  protection, so VIN and VM are tied together on the carrier. Don't use this
  carrier on its own without other protection.
- **One 100 nF on VM instead of two, and VCP uses 100 nF** (TI's
  recommended value; Pololu fits 220 nF).

| Ref | Part | LCSC | Notes |
|---|---|---|---|
| U1 | DRV8874PWPR (HTSSOP-16) | C1855818 | Extended part |
| C1, C2 | 10 uF 50 V X5R 1206 | C13585 | VM bulk |
| C3 | 100 nF 50 V 0603 | C14663 | VM bypass |
| C5 | 22 nF 50 V 0603 | C77571 | Charge-pump flying cap (CPH-CPL), Extended part |
| C6 | 100 nF 50 V 0603 | C14663 | VCP to VM |
| R2 | 10 k 0603 | C25804 | VREF pulled to SLEEP, as on Pololu's board |
| R3 | 2.49 k 1% 0603 | C22908 | CS (IPROPI) to GND: 1.12 V/A, about 2.9 A limit at VREF = 3.3 V |
| R4 | 20 k 0603 | C4184 | IMODE to GND, as on Pololu's board |

PMODE is left floating on the carrier, as on Pololu's board; the master
board ties it to GND (PH/EN mode).

**Pins**, top view, top to bottom:

| Left | Right |
|---|---|
| VM | VIN (tied to VM) |
| GND (square pad) | GND (square pad) |
| EN | OUT1 |
| PH | OUT2 |
| PMODE | IMODE |
| SLEEP | FAULT |
| VREF | CS |

The back has the pin names, like Pololu's.

## Layout

- 2 layers, 1.6 mm, 1 oz.
- VM, OUT1 and OUT2 are drawn by hand at 1.0-1.2 mm and locked; the
  autorouter does the rest. They neck down to 0.4 mm only for the last
  millimetre into the 0.65 mm-pitch chip pins.
- The chip's thermal pad has 0.3 mm vias to the bottom GND pour (6 in A,
  15 in B), and a solder-mask-defined opening so the paste stays on the pad.
- GND is poured on both layers.

## Ordering at JLCPCB

1. Upload `fab/b/panel/drv8874_carrier_b_panel_gerbers.zip`.
2. PCB options:
   - Layers 2, thickness 1.6 mm, 1 oz.
   - **Panel by Customer**, panel format 3 x 2 (6 boards per panel). The
     straight lines across the panel on the outline layer are V-cuts; say so
     in the order remark ("V-cut along all internal straight lines").
   - Edge rails: none (the panel already has 5 mm rails with fiducials and
     1.152 mm tooling holes).
   - Quantity 5 panels (the minimum).
3. Assembly: Economic, top side, **PCBA quantity 2 panels** (12 boards).
   Upload `fab/b/panel/jlc_bom.csv` and `fab/b/panel/jlc_cpl.csv`.
4. Check the placement preview:
   - **U1**: the pin-1 dot on the chip goes at the bottom-left, by the small
     triangle on the silkscreen (pins 1-8 run along the bottom edge). I've
     applied the same 90-degree correction that the master board's TSSOPs
     needed; if the chip's leads cross the pads, rotate it by 90 degrees.
   - Capacitors and resistors have no polarity.
5. Consider "Confirm Parts Placement: Yes".

To let JLC panelize instead, use the `fab/b/single/` files and choose "Panel by
JLCPCB" (check that JLC offers assembly with that option for your order).

## After assembly

- Solder two 1x7 male 0.1" headers, long pins down, components up.
- Firmware: the default build is set for DRV8874 carriers (CS 1.12 V/A,
  2.5 A software trip). See `firmware/README.md`.
- First power-up: one carrier, motor disconnected, current-limited bench
  supply at 12 V. Check that VM draws a few mA, then try a motor from the
  web UI's motor test.
