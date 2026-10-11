# Scorbot ER-4u ESP32 master board (KiCad)

KiCad project for the replacement controller: an ESP32 DevKit, six Pololu
DRV8874 carriers and a DROK mini 5 V buck module plug into a master board,
and the robot's DD-50 cable plugs straight into the board edge. JLCPCB
places the SMD parts: passives, LEDs, the SS14, the TCA9555 I/O expander and
two ADS1115 ADCs.

**Status: v0.4, generated: schematic complete, carrier and DD-50 footprints checked against their datasheets, PCB autorouted. Ready to order; check part orientation in JLC's preview.**

| File | What it is |
| --- | --- |
| `scorbot_controller.kicad_pro/.kicad_sch/.kicad_pcb` | The KiCad project (opens in KiCad 7, 8 or 9) |
| `lib/Scorbot.kicad_sym`, `lib/Scorbot.pretty/` | Custom parts: DevKit socket, DRV8874 carrier socket, DD-50 female R/A |
| `docs/schematic.pdf`, `docs/pcb_placement.png`, `docs/pcb_routed_F.png`, `docs/pcb_routed_B.png` | Previews (B side is mirrored) |
| `bom.csv` | Grouped BOM |
| `generator/design.py` | **Single source of truth**: every part, footprint, pin-to-net map and placement |
| `generate.sh` | Regenerates everything from `design.py`, then checks it |

## Regenerating

```sh
pip install kiutils cairosvg   # plus KiCad 7+ (kicad-cli and its pcbnew Python module)
# optional autorouting: Java 17+, xvfb-run and the Freerouting 1.9.0 jar
# (https://github.com/freerouting/freerouting/releases/tag/v1.9.0)
FREEROUTING_JAR=/path/freerouting-1.9.0.jar ./generate.sh
```

Routing takes about 3 minutes. `gen_route.py` retries up to `FREEROUTING_TRIES`
times (default 3) because Freerouting's result varies between runs, and it
keeps the run with the fewest unconnected items.

`generate.sh` writes the library, schematic, PCB and BOM, then:

- exports KiCad's own netlist from the schematic and checks it against
  `design.py` pin by pin (currently 354 connections, 0 mismatches);
- runs KiCad DRC on the board. Current result: 0 unconnected items, 0
  clearance or courtyard errors, and a few silkscreen and thermal-relief
  warnings. `lib_footprint_issues` only appears when the
  standard KiCad libraries aren't in the global library table.

Editing the `.kicad_sch` / `.kicad_pcb` by hand is fine once you take over
the design; just stop running the generator after that, or it overwrites your
changes.

## Must check before ordering boards

Done:

- **Pololu carrier pinout** is taken from Pololu's labeled top view: left
  row VM, GND, EN, PH, PMODE, SLEEP, VREF; right row VIN, GND, OUT1, OUT2,
  IMODE, FAULT, CS; rows 0.5" apart. Silkscreen marks VM (top left) and VIN
  (top right) on each socket: plug the carrier in components-up with its VM
  pin at the VM mark.
- **DevKit pinout** matches a photo of the board in hand (DevKitC V4 layout,
  3V3 at the antenna end).
- **Copper**: 1 oz. VIN/VM traces are 2.5 mm with 1.6/0.8 mm vias, motor
  traces 1.2 mm with 1.2/0.6 mm vias.
- **DevKit row spacing** confirmed at 1.0" (25.4 mm).
- **DD-50 footprint** follows Amphenol's D-Sub brochure for DD50S564TLF
  (stamped contacts, termination type 5): tail rows 2.54 mm apart, the row
  nearest the flange 10.40 mm from it, 2.77 mm pitch, 61.11 mm between the
  shell holes.
- **LCSC numbers** checked by search (C465732 is TI's TCA9555PWR; its LCSC
  attribute text is a generic I/O-expander template).

Still to check:

1. **DD-50 bracket holes** (not blocking): the brochure doesn't dimension
   the 50-way plastic bracket, so the two 3.2 mm holes sit on the shell-hole
   centres (61.11 mm apart), 12.94 mm behind the flange. The connector is
   held by its 50 soldered pins either way.
2. **R31-R36 LCSC number**: C341654 (Fenghua 47 R 2512 1 W, Extended;
   alternate C4347277). Confirm stock.
3. **Part orientation in JLC's placement preview** (see below). First pass
   checked: the TSSOPs were 90 degrees off and are now corrected in the CPL;
   D5 and the LEDs were already right. Re-check U5-U7 after re-uploading.
4. **Autorouted copper.** DRC-clean but not pretty; look over the VIN/VM
   and MOT paths, and the long parallel runs across the middle.
5. **Screw terminal wire entry** (J2, J3, J7) should face the board edge.
   Check in KiCad's 3D viewer.

Fit by hand, one of each pair:

- **D1 (SMBJ18A, SMB) or D8 (1.5KE18A / P6KE18A, through-hole)**: the
  reverse-polarity / over-voltage clamp. Neither is placed by JLC.
- **F1 (blade fuse holder) or J7 (screw terminal + inline fuse)**.
- **J1 (barrel jack) or J2 (screw terminal)** for the 12 V input.

## Silkscreen art

`art/columbia_gadget_works_logo.png` (front) and `art/stealie.png` (back)
are turned into filled silkscreen by `generator/silk_art.py` when the board
is generated. Positions and heights are `LOGO_FRONT` / `LOGO_BACK` in
`gen_pcb.py`. Silkscreen is one colour: every non-white area of the image
prints.

## Ordering at JLCPCB

`generator/gen_fab.py` (run by `generate.sh`) writes `fab/`:

- `scorbot_controller_gerbers.zip`: upload as the PCB (2 layers, 1.6 mm,
  1 oz copper).
- `jlc_bom.csv` and `jlc_cpl.csv`: upload for PCB Assembly, top side only.
  These list only the SMD parts JLC places. Everything else is
  hand-soldered: see the buy list in the plan doc.

### Checking the JLC part numbers

For each line of `fab/jlc_bom.csv`, search the LCSC number at
<https://jlcpcb.com/parts> and confirm:

- value and package match the Comment and Footprint columns (0805, 1206,
  SMA, TSSOP-24, MSOP/VSSOP-10);
- capacitors are X7R/X5R and 25 V or more; R31-R36 are 47 R, 2512, 1 W
  (they dissipate about 0.3 W each);
- Basic vs Extended (each Extended part adds a one-off loading fee, about
  $1.50-3);
- stock covers (quantity x number of boards).

If a number is wrong or out of stock, pick any equivalent Basic part and
change it in the `LCSC` table in `generator/gen_fab.py` (or edit the CSV).

### Checking orientation in JLC's placement preview

After uploading the BOM and CPL, JLC shows each part on the board. Zoom in
and check:

- **U5 (TCA9555), U6/U7 (ADS1115)**: the pin-1 dot on the chip sits on the
  pin-1 marker of the footprint.
- **D5 (SS14)**: the cathode band is on the pad marked as cathode (toward
  the DevKit's 5 V feed).
- **LEDs D3, D4, D6, D7** (green, green, red, green): the cathode mark
  faces the GND side.
- Resistors and capacitors have no polarity.

If a part is turned the wrong way, rotate it in JLC's tool (or add 90/180 to
its Rotation in `jlc_cpl.csv`). To make the fix permanent, add the
footprint to `ROT_FIX` in `generator/gen_fab.py`. It already turns the TSSOPs
(U5-U7) by -90 degrees, because JLC's TSSOP models sit 90 degrees from KiCad's.

## Design notes

- **DB50 pinout**: SCORBOT-ER 4u User Manual, Chapter 8 (identical to the
  ER III manual Table D-1). Pins 37-44 unused; pin 22 (gripper switch) has no
  connection in the arm. Motor +/- labels differ between manuals; firmware
  sets direction.
- **Encoders**: bare IR LEDs + phototransistors. 47 R per axis from 5 V for
  VLED (ER III reference value; check against the ER-4u's upgraded PC510
  encoders). P0/P1 have 4.7 k pull-ups to 3.3 V and 1 nF, straight into the
  ESP32 (no buffer); the PCNT glitch filter handles noise.
- **Power input, two options**: barrel jack J1 or screw terminal J2 (same
  nets; use one).
- **Fuse, two options**: fit EITHER the on-board mini blade holder F1
  (Keystone 3568, 5 A ATM fuse) OR the screw terminal J7 with an inline
  fuse holder wired across it. They are in parallel: two fuses in at once
  double the trip current, and a bare wire in J7 bypasses F1.
- **No reverse-polarity FET**: a reversed supply forward-biases the
  unidirectional SMBJ18A and blows the fuse.
- **E-stop**: no relay; the NC contacts sit in the VM line (J3), so they must
  be rated for total motor current. Logic stays powered.
- **Carrier current limit**: VREF is pulled to SLEEP (3.3 V) by 10 k on the
  carrier and CS has 2.49 k, giving about 2.9 A. R21-R26 (DNP) lower it.
- **Current sense**: two ADS1115IDGSR chips on the board (0x48: CS1-4,
  0x49: CS5, CS6 and VM/5.7; ADDR strapped to GND / 3V3). CS reads 1.1 V/A;
  use the ADS1115's +/-4.096 V range.
- Plan, firmware architecture and API: see the "Scorbot ER-4u ESP32
  Controller Plan" doc.
