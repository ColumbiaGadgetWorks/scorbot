# Scorbot ER-4u ESP32 controller: project summary and handoff notes

Status as of 2026-11-07. Repository: https://github.com/ColumbiaGadgetWorks/scorbot (public, branch `main`).
The plan doc is the Claude Docs artifact "Scorbot ER-4u ESP32 Controller Plan"
(https://claude.ai/code/artifact/aec69967-902b-482a-b253-e4a6e6f54147). It is **out of date**: it still
describes Pololu DRV8874 carriers, and it predates the custom carrier, the flasher and the silkscreen work.

## What the project is

A replacement controller for an Intelitek SCORBOT-ER 4u robot arm.

- **Master board.** An ESP32-DevKitC (WROOM-32D/E, 38-pin, rows 1.0" apart) and six plug-in motor-driver
  carriers sit on it. The robot's DD-50 cable plugs straight in. 12 V supply.
- **Firmware.** ESP-IDF. Closed-loop control of 6 motors with quadrature encoders and home switches. Built-in
  web UI for control, test, calibration and settings.
- **Custom DRV8874 carrier.** Same pinout as the Pololu #4035, for JLC assembly.
- **Web flasher.** On GitHub Pages.

## Repository layout

| Path | What |
|---|---|
| `hardware/scorbot-controller/` | Master board. KiCad project generated from Python (`generator/design.py` is the single source of truth). `generate.sh` runs the whole pipeline. `fab/` holds the JLC files. |
| `hardware/drv8874-carrier/` | DRV8874 carrier (Pololu #4035 clone). `generator/gen_board.py` builds and routes it. `gen_fab.py` makes the 3x2 panel and the JLC files. `gen_rfq.py` makes the RFQ package. |
| `firmware/` | ESP-IDF 5.3 firmware. `main/core/` is portable robot logic. `test/` holds the host tests and simulator. `web/index.html` is the embedded UI. |
| `flasher/` | Web installer page (ESP Web Tools 10.4.0, bundled under `vendor/`). `build_firmware.py` builds all driver variants. `serve.py` is an optional local server. |
| `.github/workflows/firmware.yml` | CI. Runs the host tests for all 3 driver settings and builds the firmware variants. Deploys GitHub Pages, and replaces the `firmware-latest` release. |

## Master board (hardware/scorbot-controller), v0.4

**Status:** ordered from JLC and **received**. Not yet tested with the robot.

**Design decisions**

- **Power input:** barrel jack J1 (PJ-102AH, centre +) or screw terminal J2.
- **Fuse:** F1 (Keystone 3568, 5 A mini blade) or J7 (screw terminal for an inline fuse). Fit one.
- **Reverse polarity:** crowbar style. D1 (SMBJ18A, SMB) or D8 (1.5KE18A THT, DO-201AD) shorts a reversed
  supply and blows the fuse. Fit one.
  - A 1N5822 or 1N540x also works in D8: reverse protection only, no over-voltage clamp.
  - Cathode band goes to VIN (the "K" square pad).
  - **There is no series blocking FET.** Weak spot: a current-limited supply may not blow the fuse, leaving
    the rail at about −1 V. An inline reverse-polarity module on the 12 V lead is the most robust fix. A
    P-FET stage is a candidate for the next revision.
- **E-stop:** NC contacts in the VM line (J3). There's no relay, and logic stays powered.
- **5 V:** a DROK mini buck module on a 4-pin socket (IN+, IN−, OUT−, OUT+). **Set it to 5.0 V before
  fitting the ESP32.** D5 (SS14) keeps DevKit USB 5 V from back-feeding.
- **I/O:**
  - TCA9555 (0x20): home switches, PH lines, nFAULT, VM sense.
  - 2× ADS1115 (0x48 and 0x49): CS1–6 and VM/5.7.
  - Encoder pull-ups. 47 Ω 2512 1 W resistors for the encoder LEDs.
- **R21–R26:** not fitted. An optional VREF-to-GND resistor per socket lowers that driver's current limit.
  - About 1.5 A with 10 k, 1.0 A with 4.7 k (CGW carrier).
  - Leave them empty. Consider R26 = 4.7 k if the gripper squeezes too hard.
- **Other pull-ups:** R12 is the 3V3 LED. R13/R14 are 4.7 k I2C pull-ups. R15 and R16 are 10 k pull-ups on
  EXP_INT and nFAULT.
- **J5:** I2C expansion (3V3, GND, SDA, SCL).
- **J6:** spare TCA9555 I/O (P06, P07, P17, GND).
- **Copper:** 2 layers, 1 oz. Autorouted with Freerouting 1.9; GND poured on both layers.
- **Silkscreen:** `gen_silk.py`, run after routing, labels all connectors and pins. It adds the large CGW
  logo bottom middle, plus a Stealie on the back. The silkscreen label update came **after** the board was
  ordered: it's in git for the next revision.
- **JLC:** places the passives, LEDs, TCA9555 and both ADS1115s. The CPL has a −90° rotation fix for
  TSSOPs, checked in JLC's preview.

**Pipeline:** `cd hardware/scorbot-controller && FREEROUTING_JAR=... ./generate.sh`.

- Needs KiCad 7 (pcbnew Python), kiutils, Java, xvfb-run and Freerouting 1.9.0. Run Freerouting with
  `-oit 100`; its optimizer hangs.
- The `gen_route.py` SES importer is custom, because `ImportSpecctraSES` doesn't work headless.
- `netclasses.write()` must run after any `Board.Save()`, because Save wipes the net classes.

## DRV8874 carrier (hardware/drv8874-carrier), version B

**Why it exists:** the user bought DRV8833 modules. They don't fit, and they're rated only to 10.8 V. Pololu
carriers are about $11 each, so this clone is for JLC assembly.

**Status:** ready to order. **Not ordered yet** as of this summary. Upload files:

- `fab/JLC_upload_6up_version_b/`: 1_GERBERS, 2_BOM and 3_CPL for the 3x2 V-cut panel (6 boards).
- `fab/JLC_upload_single_version_b/`: the same for a single board, for comparing quotes.
- `fab/b/rfq/`: generic RFQ package (BOM with MPNs, CPLs measured from the lower-left corner, notes).
  **Don't upload its BOM/CPL to JLC**: different designators and format.

**Circuit:** Pololu's DRV887x carrier schematic, with these differences:

- No reverse-voltage MOSFET (Q1, D1, R1): the master board has the crowbar. VIN and VM are tied together.
- VCP capacitor is 100 nF (TI's value).
- R3 is 2.4 k instead of 2.49 k, for a Basic part. CS therefore reads **1.08 V/A**, and the driver limits at
  about 3.1 A with VREF at 3.3 V.
- No R5 (VREF-to-GND resistor) footprint: the master board's R21–R26 do the same job.

| Ref | Part | LCSC |
|---|---|---|
| U1 | DRV8874PWPR (Extended, the only one) | C1855818 |
| C1, C2 | 10 µF 25 V X5R 0805 | C15850 |
| C3, C4, C6 | 100 nF 50 V 0603 | C14663 |
| C5 | 22 nF 50 V X7R 0402 | C1532 |
| R2 | 10 k (VREF to SLEEP) | C25804 |
| R3 | 2.4 k 1% (CS) | C22940 |
| R4 | 20 k (IMODE) | C4184 |

**Layout**

- 15.24 × 17.78 mm. 2×7 pins, 0.5" between rows. GND pins are the square pads.
- VM, OUT1 and OUT2 are hand-drawn locked copper, 1.0–1.2 mm wide.
- Version B adds power pours and 15 thermal vias, 0.3 mm each.
- A no-tracks rule area keeps the B.Cu area under U1 clear for the thermal pour. DRC is clean.

**Before ordering, check:**

1. The DRV8874 PWP exposed-pad size from TI's datasheet fits the footprint (3.4×5 mm copper,
   2.46×2.31 mm mask opening). TI's site wasn't reachable from the sandbox, so this hasn't been verified.
2. C15850, C1532 and C22940 still show Basic and in stock.
3. JLC placement preview: U1's pin-1 dot sits bottom-left, by the silk triangle (CPL rotation 0 after the
   −90° fix).

**Order settings:**

- 2 layers, 1.6 mm, 1 oz.
- Panel by Customer, 3×2, no edge rails. Remark: "V-cut along all internal straight lines".
- 5 panels.
- PCBA Economic, top side, 2 panels (12 boards). Confirm Parts Placement: Yes.
- Optional: JLC "Depanel" service.

**Combining shipping with LCSC (loose parts such as headers):**

1. Order at JLC first, shipped to LCSC's Hong Kong warehouse (address in LCSC's combine guide).
2. Then place the LCSC order to your own address, choosing "combine with JLCPCB order".
3. Use the same account and currency for both.

**Depaneling:** snap along the V-cuts with support right up to the groove. Ceramic capacitors near the edge
can crack if the board flexes.

**First power-up:** one carrier, current-limited 12 V, no motor; then one motor.

## Firmware (firmware/)

- **Tasks:**
  - Control loop at 1 kHz on core 1: PCNT encoders, PID, trapezoid moves, differential wrist
    (motors 4 and 5).
  - I/O task at 500 Hz on core 0: I2C reads from the TCA9555 and both ADS1115s.
- **Safety:**
  - E-stop latch (VM loss).
  - nFAULT.
  - Over-current: trips after 500 ms above the trip current, so the stall and following-error checks can
    report a jam first.
  - Following error.
- **Driver choice:** `idf.py menuconfig` → Scorbot → Motor driver carriers.

  | Choice | Current sense | Driver limit | Software trip |
  |---|---|---|---|
  | CGW carrier (default) | 1.08 V/A | about 3.06 A | 2.5 A |
  | Pololu #4035 | 1.12 V/A | about 2.94 A | 2.5 A |
  | Pololu #4036 | 2.49 V/A | about 1.33 A | 1.2 A |

  On the host: `-DSCORBOT_POLOLU_4035` or `-DSCORBOT_DRV8876`. The values are in `main/core/config.h`.
- **Wi-Fi:** station mode, falling back to the AP `Scorbot-XXXX` (password `scorbot1`) with a captive
  portal at 192.168.4.1. mDNS name `scorbot.local`.
- **Web UI tabs:** Control (3D view, jog), Test (self-test, switch lamps, motor test with Flip, encoders),
  Calibrate (measure travel, homing), Settings.
- **Tests:** `make -C firmware/test run`. 58 checks, run under all 3 driver settings. CI runs them too.
- **Builds:** compiled cleanly for ESP32 (about 0.97 MB, 39% of the app partition free). **Never run on real
  hardware yet.**

## Web flasher

- **Live at https://columbiagadgetworks.github.io/scorbot/.** Use Chrome or Edge.
- **Steps:** browser check, pick the driver variant, prepare (motor power off, USB), install, join the
  controller's Wi-Fi, first-run checklist.
- **Erase:** only on a first install. Erasing wipes NVS (Wi-Fi and calibration). The parts are flashed at
  their own offsets (0x1000, 0x8000, 0x10000) so that updates keep NVS.
- **CI** rebuilds and redeploys on every push to `main` that touches `firmware/`, `flasher/` or the
  workflow. Pages source is set to "GitHub Actions" (done).
- **Offline:** `python3 flasher/serve.py` (`--download`, `--build`, `--zip`).

## Repo conventions and gotchas

- **Commit authorship:** commits are authored as **adman234**
  (`2827928+adman234@users.noreply.github.com`), with **no Claude co-author or session trailers**. This is
  the user's explicit request. History was rewritten to match on 2026-10-27.
- **Don't open PRs unless asked;** push to `main`.
- **pcbnew Python (KiCad 7):** `board.Remove()` leaves dangling objects that segfault later. The generators
  remove items by editing the `.kicad_pcb` text instead (`gen_silk.strip_previous`,
  `gen_board.remove_vias_in_file`), or move them to another layer.
- **Sandbox network:** LCSC, JLC, TI and Docker Hub pages are blocked. Use web search snippets for part
  numbers, and `mirror.gcr.io/espressif/idf:v5.3.2` for ESP-IDF in Docker (run `dockerd` first). The ESP
  component registry is blocked, so local builds need mDNS stubbed out; CI has full access.
- **JLC part numbers:** see `JLCPCB_PART_NUMBERS.md` (how they were found and checked, and the mistakes made).
  - Verify every C-number by searching for it.
  - The BOM and CPL must have identical designators.
  - Prefer Basic parts; each Extended part adds $3.

## Open items and ideas

1. Order the carriers (do the checks above first), then bring up one carrier and then the full arm.
2. Test the master board:
   - Fit the TVS or diode and a fuse.
   - Set the buck module to 5.0 V.
   - Flash from the Pages site.
   - Self-test, switches, Measure travel, Home all.
3. Update the plan doc artifact to match this summary.
4. Next master-board revision:
   - The new silkscreen is already in git.
   - Consider a P-MOSFET reverse-polarity stage at the 12 V input (rated 10 A or more).
   - DD-50 bracket holes (deferred by the user).
5. Optional: R26 (gripper current limit), and a JLC Depanel quote.
