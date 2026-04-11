# Circuit DNA -- Genetic Algorithm Circuit Optimizer for KiCad

Circuit DNA is a KiCad 9.x action plugin that uses a genetic algorithm to automatically optimize passive component values (resistors, capacitors, inductors) in SPICE circuits. It runs headless ngspice simulations in a loop, evolving component values across generations to meet user-defined performance specifications.

The plugin is generic and works with any SPICE netlist. It supports both AC and transient analysis, handles complex-valued frequency-domain data, and snaps optimized values to the E24 preferred number series for practical manufacturability.

---

## Table of Contents

1. [Features](#features)
2. [Screenshots](#screenshots)
3. [Architecture](#architecture)
4. [File Structure](#file-structure)
5. [Installation](#installation)
6. [Usage](#usage)
7. [Example Workflows](#example-workflows)
8. [Fitness Metrics](#fitness-metrics)
9. [Genetic Algorithm Details](#genetic-algorithm-details)
10. [Known Limitations](#known-limitations)
11. [Dependencies](#dependencies)

---

## Features

- Five-tab GUI built with wxPython: Load Circuit, Define Specs, Evolve, Results, Settings.
- Automatic SPICE netlist parsing with component type detection (R, C, L, V, D, Q, M, X, U).
- Five built-in fitness metrics: gain at frequency, 3dB bandwidth, peak voltage, dominant frequency, and rise time.
- Preset specification templates for common topologies (low-pass filter, high-pass filter, amplifier, oscillator).
- Headless ngspice simulation with subprocess isolation and configurable timeout.
- Raw file parser supporting both ASCII and binary ngspice output formats, including complex-valued AC data.
- E24 preferred value snapping for all optimized component values.
- Tournament selection, single-point crossover, log-scale Gaussian mutation, and elitism.
- HTML optimization report with fitness convergence charts, specification results, component change tables, gene value trajectories, and before/after waveform comparison.
- Optimized netlist export and direct netlist application.
- Internal behavioral model components (latch capacitors, high-impedance resistors) are automatically excluded from optimization.

---

## Screenshots

### Loading and parsing a SPICE netlist

The Load Circuit tab parses a SPICE netlist and identifies all components. R, C, and L components are automatically marked as mutable (eligible for optimization). Voltage sources and other non-passive components are excluded.

![Load Circuit](screenshots/01_load_circuit.png)

### Defining performance specifications

The Define Specs tab allows users to set target performance metrics. Each specification consists of a name, a metric type, a comparison operator, a target value, and an optional frequency parameter. Multiple specifications can be combined to define competing constraints.

![Define Specs](screenshots/02_define_specs.png)

### Running the genetic algorithm

The Evolve tab shows real-time progress during optimization. Each generation displays the best fitness, average fitness, and the number of specifications met. In this example, the GA achieves 2/2 specs met from generation 0 and continues improving fitness over 15 generations.

![Evolve](screenshots/03_evolve.png)

### Viewing optimized results

The Results tab displays the optimized component values alongside their original values and percent change. The specification results table confirms which targets were met. In this run, the passband gain measured 27.03 dB (target >= -3 dB) and the stopband attenuation measured -40.25 dB (target <= -20 dB).

![Results](screenshots/04_results.png)

### HTML optimization report

The generated HTML report provides a complete record of the optimization run, including a summary, fitness convergence charts, specification results, and component change tables.

![Report Summary](screenshots/05_report_summary.png)

![Report Specs and Components](screenshots/06_report_specs.png)

### Gene value trajectories

The report includes a log-scale chart showing how each component value evolved across generations. This provides insight into the GA's search behavior and convergence patterns.

![Value Trajectories](screenshots/07_report_trajectories.png)

### Algorithm configuration

All GA parameters used during the run are recorded in the report for reproducibility.

![Algorithm Configuration](screenshots/08_report_config.png)

---

## Architecture

```
                 +------------------+
                 |   KiCad 9.x     |
                 |  (PCB Editor)    |
                 +--------+---------+
                          |
                  __init__.py (ActionPlugin entry)
                          |
                  +-------v--------+
                  |  MainWindow    |  <-- wxPython 5-tab dialog
                  |  (main_window) |
                  +--+---+---+---+-+
                     |   |   |   |
         +-----------+   |   |   +------------+
         |               |   |                |
   +-----v-----+  +-----v---v----+   +--------v--------+
   | NetlistParser| | GeneticAlgorithm|   | ReportGenerator |
   | (netlist_   | | (genetic_       |   | (report.py)     |
   |  parser.py) | |  algorithm.py)  |   +-----------------+
   +-----+-------+ +---+--------+--+
         |             |        |
         |       +-----v-----+  |
         |       |  Fitness   |  |
         |       | Evaluator  |  |
         |       | (fitness.py)|  |
         |       +------------+  |
         |                       |
         |    +---------+--------+
         |    |
   +-----v---v-------+
   |  NgspiceRunner   |
   |  (ngspice_       |
   |   runner.py)     |
   +------------------+
         |
   [ngspice.exe -b]
```

Data flow during optimization:

1. NetlistParser reads the SPICE netlist file and identifies mutable R/C/L components.
2. GeneticAlgorithm initializes a population of candidate solutions (random component values in log-space).
3. For each individual, NetlistParser generates a modified netlist with substituted values.
4. NgspiceRunner writes the netlist to a temp directory, injects a .control block, runs ngspice in batch mode, and parses the resulting .raw file.
5. FitnessEvaluator extracts the relevant metric from simulation data and scores each individual against user-defined specifications.
6. The GA applies tournament selection, crossover, mutation, and elitism to produce the next generation.
7. After all generations complete, ReportGenerator runs both original and optimized netlists through ngspice and produces an HTML report with before/after waveform comparison.

---

## File Structure

```
circuit-dna/
    __init__.py           Plugin entry point (ActionPlugin registration)
    main_window.py        wxPython GUI with 5 tabs (23 KB)
    netlist_parser.py     SPICE netlist parser and modified netlist generator (6 KB)
    ngspice_runner.py     Headless ngspice subprocess runner and .raw file parser (9 KB)
    fitness.py            Fitness evaluator with 5 metrics and scoring system (9 KB)
    genetic_algorithm.py  GA engine with tournament selection and E24 snapping (9 KB)
    config.py             Configuration manager for persistent settings (2 KB)
    report.py             HTML report generator with Chart.js visualizations (6 KB)
    test_core.py          Unit tests for parser, fitness, and GA components (5 KB)
    README.md             This file
    screenshots/          Plugin and report screenshots
```

---

## Installation

Prerequisites:
- KiCad 9.0 or later (Windows)
- ngspice (included with FOSSEE eSim at C:\FOSSEE\nghdl-simulator\bin\ngspice.exe, or any standalone ngspice installation)

Steps:

1. Locate your KiCad plugin directory. In KiCad's PCB Editor, go to Tools > External Plugins > Open Plugin Directory. This typically opens:
   ```
   C:\Users\<username>\Documents\KiCad\9.0\scripting\plugins\
   ```

2. Copy the entire `circuit-dna` folder into that directory. The folder must contain `__init__.py` at its root.

3. Restart KiCad. The plugin should appear under Tools > External Plugins > Circuit DNA.

4. If the plugin does not appear, open KiCad's scripting console (Tools > Scripting Console) and run:
   ```python
   import pcbnew
   pcbnew.ActionPlugin.register()
   ```
   Then click Tools > External Plugins > Refresh Plugins.

5. Verify the ngspice path in the Settings tab. The default path is:
   ```
   C:\FOSSEE\nghdl-simulator\bin\ngspice.exe
   ```
   Change this if your ngspice installation is elsewhere.

---

## Usage

### Step 1: Load Circuit

Open a PCB project in KiCad's PCB Editor, then launch Circuit DNA from Tools > External Plugins.

In the Load Circuit tab, either:
- Click "Browse" to select a SPICE netlist file (.cir, .spice, .sp, .net), or
- Click "Auto-detect from project" to find a netlist in the project directory.

Click "Parse Netlist." The component table will populate with all detected components. R, C, and L components are marked as mutable by default. Voltage sources, diodes, transistors, and subcircuit instances are marked as non-mutable. Internal behavioral model components (such as latch elements with very high impedance values) are automatically excluded.

### Step 2: Define Specifications

Switch to the Define Specs tab. For each performance target:

1. Enter a descriptive name (e.g., "passband_gain").
2. Select a metric from the dropdown.
3. Choose an operator (>=, <=, ==, ~=).
4. Enter the target value.
5. Enter the frequency in Hz (required for frequency-domain metrics, use 0 for time-domain metrics).
6. Click "+ Add Spec."

Alternatively, select a preset from the Preset dropdown to load a standard set of specifications for common circuit topologies.

### Step 3: Evolve

Switch to the Evolve tab and click "Start Evolution." The log window will display progress for each generation, including best fitness, average fitness, and the number of specifications met.

Click "Stop" at any time to halt evolution early. The best individual found so far will be preserved.

### Step 4: Review Results

The Results tab shows:
- A table of component values that were changed, with original and optimized values and percent change.
- A specification results table showing measured values and pass/fail status for each spec.

Three actions are available:
- "Apply to Netlist" writes the optimized values back to the source netlist file.
- "Generate HTML Report" produces a detailed optimization report and opens it in the default browser.
- "Export Optimized Netlist" saves the optimized netlist to a new file.

### Step 5: Settings

The Settings tab exposes all GA parameters:
- ngspice executable path
- Population size (default: 20)
- Number of generations (default: 15)
- Mutation rate (default: 0.3)
- Crossover rate (default: 0.7)
- Elite count (default: 2)
- Mutation scale (default: 0.5)
- Tournament size (default: 3)
- Simulation timeout in seconds (default: 30)

Click "Save Settings" to persist changes across sessions.

---

## Example Workflows

### Second-Order LC Low-Pass Filter

Netlist (lc_filter.cir):
```spice
.title Second Order LC Low Pass Filter
V1 IN 0 DC 0 AC 1
R1 IN N1 100
L1 N1 OUT 10m
C1 OUT 0 100n
R2 OUT 0 10k
.ac dec 100 1 1e6
.end
```

Specifications:
- passband: gain_db_at_freq >= -3 dB at 1000 Hz
- stopband: gain_db_at_freq <= -20 dB at 10000 Hz

Expected result: The GA modifies R1, L1, C1, and R2 to position the LC resonant frequency and damping such that both specifications are met. A second-order filter provides -40 dB/decade rolloff, which is sufficient to achieve -20 dB attenuation one decade above the cutoff frequency. Typical optimized values reduce the series resistance (less damping, sharper rolloff) and adjust L and C to shift the resonant frequency.

### RC Low-Pass Filter (Single Pole)

Netlist (rc_filter.cir):
```spice
.title RC Low Pass Filter
V1 IN 0 DC 0 AC 1
R1 IN OUT 10k
C1 OUT 0 100n
.ac dec 100 1 1e6
.end
```

Specifications:
- passband: gain_db_at_freq >= -3 dB at 1000 Hz
- stopband: gain_db_at_freq <= -20 dB at 10000 Hz

Expected result: The GA will find values that satisfy the passband specification but will be unable to fully meet the stopband specification. A single-pole RC filter has a rolloff of -20 dB/decade, making it physically impossible to achieve -20 dB attenuation at exactly one decade above the cutoff frequency. This is a correct result that demonstrates the GA respecting the topology's physical limits rather than producing invalid solutions.

### 555 Timer Astable Oscillator

Netlist (555_timer_test.cir):
```spice
.title 555 Timer Blinker
v1 VCC 0 DC 9
R1 VCC DISCH 22k
R2 DISCH THRESH 56k
C1 THRESH 0 10u IC=0
R3 OUT 0 1k
BUP LATCH 0 I = (V(THRESH)>6)*(-1m) + (V(THRESH)<3)*(1m)
CLATCH LATCH 0 1u IC=5
RLATCH LATCH 0 1e9
S1 DISCH 0 LATCH 0 SWLO
.model SWLO SW(VT=2.5 VH=0.1 RON=10 ROFF=1e9)
BOUT OUT 0 V = (V(LATCH)>2.5)*9
.option rshunt=1e12
.tran 0.1ms 4s uic
.end
```

This uses a behavioral model of the 555 timer (capacitor-based SR latch with voltage-controlled switch) because the eSim LM555N subcircuit uses XSPICE mixed-signal components that cause convergence failures in ngspice 35's batch mode. The behavioral model is functionally equivalent for astable operation.

Specifications:
- blink_rate: dominant_frequency >= 2 Hz
- output_voltage: peak_voltage >= 8 V
- fast_rise: rise_time <= 0.001 s

---

## Fitness Metrics

All metrics operate on simulation output data and return a scalar value. The evaluator scores each metric against its target using the specified operator and sums weighted scores to produce the individual's fitness.

| Metric | Analysis Type | Description |
|--------|--------------|-------------|
| gain_db_at_freq | AC | Computes 20*log10(abs(V(out))) at the specified frequency. Finds the nearest frequency point in the simulation data. |
| bandwidth_3db | AC | Finds the frequency at which the output magnitude drops below peak/sqrt(2). Returns the -3dB frequency in Hz. |
| peak_voltage | Transient | Returns the maximum value of V(out) across the entire simulation time span. |
| dominant_frequency | Transient | Counts zero-crossings of V(out) relative to its mean value, computes average period from consecutive same-direction crossings, and returns the reciprocal as frequency in Hz. |
| rise_time | Transient | Measures the time for V(out) to transition from 10% to 90% of its total voltage swing. |

Signal selection priority: the evaluator first searches for a voltage signal whose name contains "out" (e.g., v(out), v(output)). If none is found, it falls back to the last non-supply voltage signal. Current signals (i(...)) are never selected as output.

---

## Genetic Algorithm Details

Representation: Each individual is a dictionary mapping component reference designators to numeric values (in SI units). The search space is log-uniform between 0.01x and 100x the original component value.

Initialization: The first individual in the population uses the original netlist values. All others are randomly sampled in log-space.

Selection: Tournament selection with configurable tournament size (default: 3).

Crossover: Single-point crossover on the ordered list of component references. Applied with probability equal to the crossover rate (default: 0.7).

Mutation: Log-scale Gaussian perturbation. Each gene is independently mutated with probability equal to the mutation rate (default: 0.3). The standard deviation is proportional to the gene's log-space range, scaled by the mutation scale parameter.

Elitism: The top N individuals (default: 2) are copied unchanged to the next generation.

Value snapping: After mutation, all values are snapped to the nearest E24 preferred number series value. This ensures optimized components correspond to standard commercially available parts.

Fitness: Weighted sum of individual specification scores. A failed simulation (ngspice error or timeout) receives a penalty fitness of -1,000,000. A metric that cannot be computed (e.g., no zero-crossings for dominant_frequency) receives a score of -100 for that specification.

---

## Known Limitations

- The plugin only optimizes passive components (R, C, L). Active device parameters (transistor W/L, op-amp gain) are not modified.
- Netlist topology is fixed. The GA cannot add, remove, or reconnect components.
- Convergence depends heavily on the initial netlist being simulatable. If the original circuit fails in ngspice, all individuals will fail.
- The 555 timer example uses a behavioral model because the eSim LM555N subcircuit (which uses XSPICE mixed-signal blocks) causes convergence failures in ngspice 35 batch mode. This is a known ngspice limitation, not a plugin bug.
- For AC analysis, the netlist must include an AC source (e.g., V1 IN 0 DC 0 AC 1) and an .ac analysis directive.
- The plugin generates temporary files in the system temp directory during evolution. These are not cleaned up automatically.
- The HTML report requires an internet connection to load Chart.js from CDN.

---

## Dependencies

- KiCad 9.0+ (provides pcbnew Python API and wxPython)
- ngspice 35+ (SPICE simulator, included with FOSSEE eSim)
- Chart.js 4.x (loaded from CDN in HTML reports, no local installation required)

No additional Python packages are required. The plugin uses only the Python standard library and the KiCad/wxPython runtime.

---

## Author

Developed as part of the FOSSEE eSim Summer Fellowship 2026, IIT Bombay.


