# Finding JLCPCB / LCSC part numbers: how it was done, and what went wrong

Notes from the Scorbot controller project, for another agent doing JLC assembly files.

## What worked

1. **Web search, not page fetches.** From the sandbox, lcsc.com, jlcpcb.com and
   datasheet sites all failed: blocked by the proxy, or DNS failures. Web search
   results did include the LCSC/JLC part pages, with specs, stock, price and the
   Basic/Extended tag in the snippets.
   - Good queries:
     - `jlcpcb partdetail <MPN> <value> <package>`
     - `LCSC <C-number> <MPN>`
     - `JLCPCB basic part <value> <package>`
     - `lcsc.com product-detail <value> <package> <MPN>`
   - Use "extended" search mode when the standard one comes back thin.
2. **Search by manufacturer part number (MPN), then read off the C-number.** The
   UNI-ROYAL resistor MPNs follow a pattern, for example 0603WAF2491T5E = 2.49 kΩ
   1% 0603. Build the MPN, search for it, and get the C-number from the
   lcsc.com/jlcpcb.com hit (C22908).
3. **Confirm every C-number against its own listing**, in a separate search for
   that C-number, before writing it into a BOM. Check:
   - value
   - package
   - voltage rating
   - tolerance
   - Basic or Extended
4. **Prefer Basic parts.** Each unique Extended part costs a $3 setup fee per
   order. Search "JLCPCB basic part <value> <package>". If a value has no Basic
   part, a nearby Basic value or package may do: 2.4 k instead of 2.49 k, or a
   0402 22 nF instead of 0603. Check what the change does to the circuit, and
   update the firmware if it touches scaling (here, current-sense volts per amp).
5. **Have the human check the final list.** Give them a table of C-number,
   expected description and package. They search each one on jlcpcb.com/parts
   and report the real description. That caught errors this process missed.

## Mistakes to avoid (all of these happened)

- **C-numbers from memory are unreliable.** Three were wrong or unverifiable:
  - C17714 was taken as a 47 Ω 1206 resistor; it's 0805, 125 mW.
  - C84256 was taken as a blue LED; it's red.
  - C21122 couldn't be confirmed as a 22 nF 0603.

  Treat any C-number you "know" as a guess until a search confirms it.
- **Near-miss parts.** C13585 was assumed to be 10 µF 25 V; it's the 50 V
  version (CL31A106**KB**HNNNE, not KAHNNNE). Read the MPN letter by letter.
- **Prices and Basic status change.** The user's quote showed C13585 at
  $0.24, against about $0.06 in the search snippet. A neighbouring part
  (C1531) had moved from Basic to Extended. Tell the user to confirm price
  and status on the live page.
- **Power ratings.** A 47 Ω LED resistor dissipating about 0.3 W needed a
  2512 1 W part, not 0603/0805. Check P = I²R before picking a package.

## JLC file formats that worked

- **BOM columns:** `Comment, Designator, Footprint, LCSC Part #`. One row per
  LCSC number, with designators comma-separated in one quoted cell.
- **CPL columns:** `Designator, Mid X, Mid Y, Layer, Rotation`. KiCad's
  `kicad-cli pcb export pos --format csv --units mm --side front --smd-only`,
  with columns renamed, values like `106.1mm`, and Layer `Top`.
- **The BOM and CPL must list exactly the same designators.** JLC rejected a
  per-board BOM (C1) uploaded with a panel CPL (C1_1 … C1_6) with "BOM doesn't
  match CPL / no components on top side". Generate both from the same board
  file, and diff the designator sets before handing them over.
- **Panels:** give each copy unique designators (`R2_1 … R2_6`). Use "Panel by
  Customer". Put the V-cut lines on the outline layer, and say so in the order
  remark.
- **Leave hand-soldered parts out of both files.** That covers through-hole
  parts and "fit one of these" alternates.

## Rotation

JLC's footprint models don't always share KiCad's zero orientation. TSSOPs and
HTSSOPs needed −90° (JLC's pin 1 sits bottom-left with the pins along the top
and bottom). Ask the user for screenshots of JLC's placement preview and check
the pin-1 dot on each IC, the cathode band on each diode and the LED polarity.
Put the corrections in a per-footprint table in the generator, not hand-edits
to the CSV.

## Final parts used (all confirmed by search or by the user)

| Part | LCSC | Type |
|---|---|---|
| DRV8874PWPR | C1855818 | Extended |
| 10 µF 25 V X5R 0805 (CL21A106KAYNNNE) | C15850 | Basic |
| 100 nF 50 V X7R 0603 (CC0603KRX7R9BB104) | C14663 | Basic |
| 22 nF 50 V X7R 0402 (0402B223K500NT) | C1532 | Basic |
| 10 k 1% 0603 (0603WAF1002T5E) | C25804 | Basic |
| 2.4 k 1% 0603 (0603WAF2401T5E) | C22940 | Basic |
| 20 k 1% 0603 (0603WAF2002T5E) | C4184 | Basic |
| TCA9555PWR | C465732 | Extended |
| ADS1115IDGSR | C37593 | Extended |
| 47 Ω 2512 1 W | C341654 | Extended |
| Red 0805 LED | C84256 | — |
| Green 0805 LED | C2297 | — |
