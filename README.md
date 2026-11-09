# MaxSAT for Logic-Driven Routing: A Comparative Study of Pseudo-Boolean Constraint Encodings

This repository provides the source code, benchmark instance generators, raw execution logs, and result analysis scripts for the manuscript:

> **"MaxSAT for Logic-Driven Routing: A Comparative Study of Pseudo-Boolean Constraint Encodings"**

It implements an exact Weighted Partial MaxSAT (WPMS) resolution framework and an Integer Linear Programming (ILP) baseline for the **Profit-Maximizing Pickup and Delivery Selection Problem (PPDSP)**, evaluating five Pseudo-Boolean (PB) capacity constraint encodings across three deductive propagation hierarchies: Generalized Arc Consistency (GAC), Consistency Checking (CC), and Weak Propagation (WP).

---

## 1. Repository Structure

```text
.
├── A-n32-k5.vrp, P-n16-k8.vrp, P-n23-k8.vrp   # Base CVRPLIB coordinate instances
├── burma14.tsp, ulysses22.tsp, bays29.tsp     # Base TSPLIB coordinate instances
├── main.py                                    # Main entry point for instance generation and solving
├── ppdsp_reform_ins_arg.py                    # Graph sparsification (MST + k-NN) & request/fleet generator
├── ppdsp_reform_ins_gen.py                    # Core data loader and variable indexing base class
├── ppdsp_reform_p1_cplex.py                   # Numerical ILP baseline formulation (IBM ILOG CPLEX)
├── ppdsp_reform_p3_rc2.py                     # WPMS formulation (Order Encoding + PySAT PB capacity compilation)
├── ppdsp_reform_utils.py                      # Solution decoding, route verification, and objective evaluation
├── run_experiments.sh                         # Batch execution script for the 30 benchmark configurations
├── environment.yml                            # Conda environment specification
├── UWrMaxSat-SCIP-MaxPre/                     # UWrMaxSat solver binary and build directory
├── results_analyze/                           # Raw execution logs and aggregation scripts
│   ├── analyze_results_PB.py                  # Log & WCNF header parser generating summary metrics and CSV tables
│   ├── experiment_results_PB.csv              # Aggregated instance-level results (Table 3 & Appendix A)
│   ├── full_experiment_BA.log                 # Raw execution logs for Adder Networks (AN / BA)
│   ├── full_experiment_BDD.log                # Raw execution logs for Binary Decision Diagrams (BDD)
│   ├── full_experiment_BM.log                 # Raw execution logs for Binary Merge (BM)
│   ├── full_experiment_SN.log                 # Raw execution logs for Sorting Networks (SN)
│   ├── full_experiment_SWC.log                # Raw execution logs for Sequential Weight Counters (SWC)
│   └── full_experiment.log                    # Raw execution logs containing ILP (CPLEX) baseline and SBC ablation runs
└── LICENSE                                    # MIT License
```

*Note on Auxiliary Files:* This repository also retains auxiliary experimental scripts (`ppdsp_reform_p1_rc2.py`, `ppdsp_reform_p2_rc2.py`, `ppdsp_reform_p4..p6_rc2.py`, `*_z3.py`, `incr.py`, and `incr_exp_results_*`) used for cross-solver interface testing and preliminary incremental prototyping. They are not required to reproduce the static PB encoding evaluations reported in the manuscript.

---

## 2. Environment and Prerequisites

### 2.1 Python Environment
The framework runs on **Python 3.10** (tested on Ubuntu 24.04 LTS). Key Python dependencies include:
- `python-sat` (`pysat` v1.8.dev24 with `pypblib` v0.0.4)
- `cplex` (Python API for IBM ILOG CPLEX v22.1.1.0)
- `tsplib95` (v0.7.1)
- `networkx` (v2.8.8)
- `numpy` & `pandas`

To create and activate the Conda environment:
```bash
conda env create -f environment.yml
conda activate exp-env
```

### 2.2 External Solvers
- **UWrMaxSat**: Must be compiled from `UWrMaxSat-SCIP-MaxPre/`. A build script is provided to compile `uwrmaxsat` alongside its required libraries (COMiniSatPS, MaxPre, and SCIP) and register the binary on your system `PATH`. From the repository root, execute:
```bash
cd UWrMaxSat-SCIP-MaxPre
chmod +x code/starexec_build
./code/starexec_build
source ~/.bashrc
```
During execution, the solver is invoked with `-no-bin -no-sat -no-par -no-scip` to enforce single-threaded, pure core-guided MaxSAT resolution.

- **IBM ILOG CPLEX Optimization Studio (v22.1.1.0)**: Required for running the `mip` baseline mode (restricted to 1 thread and a 3600-second CPU time limit).

---

## 3. Reproducing the Experiments

### Step 1: Generate Preprocessed Benchmark CSVs
Before running the solvers, generate the sparsified adjacency matrices (`k=3` nearest neighbors augmented with the Euclidean minimum spanning tree and depot connections), paired pickup-and-delivery requests, and heterogeneous vehicle capacities (using fixed random seed `42`):

```bash
for inst in burma14.tsp ulysses22.tsp bays29.tsp P-n16-k8.vrp P-n23-k8.vrp A-n32-k5.vrp; do
    python main.py gen ./$inst
done
```

This step produces `2DNode_<inst>.csv`, `adjMatrx3_<inst>.csv`, `requestInfo<|R|>_<inst>.csv`, and `vehicleCap<|T|>_<inst>.csv` in the working directory.

### Step 2: Run Individual Solver Configurations
The command-line syntax for `main.py` is:

```bash
python main.py <mode> <method> <instance_name> <|R|> <|T|> <k-NN>
```

- **Run the ILP Baseline (CPLEX):**
  ```bash
  python main.py mip p1 burma14 7 2 3
  ```
  *(Note: `ppdsp_reform_p1_cplex.py` also includes an optional explicit symmetry-breaking method `self.mipSbc()`. By default, `#self.mipSbc()` is commented out in `genMipFormular()` so that CPLEX relies on its built-in symmetry detection. Both sets of runs—the 30 baseline runs without `mipSbc()` and the 17 ablation runs with `mipSbc()` enabled on instances with `|T| >= 4`—are recorded in `results_analyze/full_experiment.log`.)*

- **Run the WPMS Formulation (`p3` = Order Encoding + PB Capacity Compilation):**
  ```bash
  python main.py maxsat p3 burma14 7 2 3
  ```
  In `ppdsp_reform_p3_rc2.py` (within `genHardClauseForEq10`), the PB capacity encoding scheme is selected via PySAT's `PBEnc.equals(..., encoding=EncType.<type>)`, and the corresponding suffix (`_BA`, `_BDD`, `_BM`, `_SN`, or `_SWC`) is appended to `self.insName` so that each generated formula is saved as `p3_<inst>_r<|R|>v<|T|>k3_<ENC>.wcnf`:
  - `EncType.adder` — Adder Networks (**AN**, suffixed as `_BA` in `.wcnf` and `.log` filenames)
  - `EncType.bdd` — Binary Decision Diagrams (**BDD**, suffixed as `_BDD`)
  - `EncType.binmerge` — Binary Merge (**BM**, suffixed as `_BM`)
  - `EncType.sortnetwrk` — Sorting Networks (**SN**, suffixed as `_SN`)
  - `EncType.seqcounter` — Sequential Weight Counters (**SWC**, suffixed as `_SWC`)

To execute the full batch of 30 benchmark instances across all request-vehicle pairs $(|R|, |T|)$ listed in Table 2 of the manuscript, use:
```bash
bash run_experiments.sh
```
*(Tip: If you only wish to generate the `.wcnf` formula files to inspect formula sizes without running the 3600-second solver per instance, comment out `solver.solve(time_limit = 3600)` under the `elif mode == "maxsat":` branch in `main.py` before running the batch.)*

---

## 4. Analyzing Raw Logs and Generating Manuscript Tables

All raw execution logs from our 3600-second single-threaded benchmark runs and the pre-generated summary table (`experiment_results_PB.csv`) are archived in `results_analyze/`. Note that `full_experiment.log` archives both the 30 baseline ILP runs (using CPLEX's built-in symmetry detection) and 17 additional ILP runs with explicit `mipSbc()` inequalities enabled on instances with $|T| \ge 4$; `analyze_results_PB.py` automatically filters out the `mipSbc()` ablation runs (via the `[CPLEX] Added ... SBC inequalities.` log marker) when compiling the baseline comparison table.

### Prerequisite for Re-running `analyze_results_PB.py`
Because UWrMaxSat performs internal clause/variable preprocessing during parsing, our study reports the exact static CNF formula sizes (`Variables` and `Clauses` in Table 3 and Appendix A) directly from the raw `.wcnf` file headers (`p wcnf <vars> <clauses>`). Consequently, `analyze_results_PB.py` strictly requires all **150 `.wcnf` files** (30 instances $	imes$ 5 PB encodings, named `p3_<inst>_r<|R|>v<|T|>k3_<ENC>.wcnf` for `<ENC> in {BA, BDD, BM, SN, SWC}`) to be present in the repository root (or inside `results_analyze/`). Due to GitHub file size constraints, these multi-gigabyte `.wcnf` files are not tracked in the remote repository and must be generated locally via Step 2 above before running the parser.

Once the `.wcnf` files are present, run:

```bash
cd results_analyze
python analyze_results_PB.py
```

The script outputs:
1. Console summaries of proven optimal counts, total wins, average CNF formula sizes (variables and clauses), and mean unit propagations (UP) and logical conflicts per instance for each encoding.
2. `experiment_results_PB.csv`, containing the complete instance-by-instance breakdown across all 30 benchmark configurations.

---

## 5. License

This project is released under the [MIT License](LICENSE).
