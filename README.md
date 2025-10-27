# PPDSP_Plus

This repository contains code for the **Profit-maximizing multi-vehicle Pickup and Delivery Selection Problem (PPDSP)** using multiple solvers including **Z3**, **CPLEX**, and **MaxSAT** (RC2 / UWRMaxSAT).

---

## 🧩 Environment

The project uses **Python 3** and requires the following dependencies:

- `z3-solver`
- `pysat`
- `numpy`
- `pandas`
- `cplex`

You can create and activate the environment using the included `environment.yml`:

```bash
conda env create -f environment.yml
conda activate exp-env
```

## 🚀 Usage
The main entry point is main.py.
It accepts the following command-line arguments:

```bash
python main.py <solver> <tsplib_file> <num_requests> <num_vehicles> <connectivity>
```

### Arguments
| Argument         | Description                             | Example                           |
| ---------------- | --------------------------------------- | --------------------------------- |
| `<solver>`       | Solver type                             | `mip`, `smt2`, `maxsat`           |
| `<tsplib_file>`  | TSPLIB instance file name               | `burma14`,`ulysses16`             |
| `<num_requests>` | Number of pickup-delivery requests      | `7`                               |
| `<num_vehicles>` | Number of available vehicles            | `2`                               |
| `<connectivity>` | Connectivity ratio for adjacency matrix | `10`                              |


## 💡 Example
Run PPDSP on a small TSPLIB instance:

```bash
# Generating instance agruments
python main.py gen ./burma14

# Solving by Z3 solver
python main.py smt2 burma14 7 2 10

# Solving by CPLEX solver
python main.py mip burma14 7 4 10

# Solving by RC2 solver
python main.py maxsat burma14 13 2 10
```

## ⚙️ Notes

- To add new TSPLIB instances, simply copy them into this repository and reference the filename in your command. Ensure all .tsp files are located in the same directory as main.py.

- For maxsat mode:

```python
# main.py
...
elif mode ==  "maxsat":
	solver = PPDSP_MaxSAT(tsplib, request, vehicle, connect)
	solver.genMaxsatFormular()
	solver.solve(solver="uwr")
	# solver.solve(solver="rc2")
	# solver.solve(solver="rc2", use_stratified=True)
...
```
The UWRMaxSAT solver must be installed and accessible in your system PATH, if you plan to use it.

- For smt2 mode:
```python
# ppdsp_reform_p1_z3.py
...
def  genSmt2Formular(self):
	...
	self.smt2Eq3()
	# Try to switch between mode 1 (arithmetic), 2 (implication), or 3 (CNF) in Eq.4 and Eq.5
	self.smt2Eq4(mode=2)
	self.smt2Eq5(mode=2)
	self.smt2Eq6()
	self.smt2Eq7()
	# Try to switch between mode 2 (implication), or 3 (CNF) in Eq.8 and Eq.9
	self.smt2Eq8(mode=2)
	self.smt2Eq9(mode=2)
...
```

1. _Arithmetic Mode_: Uses **arithmetic expressions** directly, such as $x \le y$. This mode keeps constraints in numerical form, allowing Z3 to reason using its arithmetic theory.

2. _Implication Mode_: Converts logical relationships into **implication form**, e.g. $x \to y$. This treats constraints as **Boolean logic implications**, reducing solver complexity while preserving logical structure.

3. _CNF Mode_: Encodes constraints into **Conjunctive Normal Form (CNF)** using only AND/OR/NOT over Boolean literals, e.g. $\lnot x \lor y$. This form is closer to SAT encoding and often used when exporting `.wcnf` files for MaxSAT solvers.

## ⚡ Quick Start
A quick guide from zero to running your first instance:

```bash
# 1️⃣ Clone this repository
git clone https://github.com/ReprodSuplem/PPDSP_plus.git
cd PPDSP_plus

# 2️⃣ Create the environment
conda env create -f environment.yml
conda activate exp-env

# 3️⃣ Run a test case
python main.py smt2 burma14 7 2 10
```

## 🧠 Citation
This implementation is inspired by the paper:

- ["A case study of the profit-maximizing multi-vehicle pickup and delivery selection problem for the road networks with the integratable nodes."](https://doi.org/10.1007/978-3-031-36024-4_35) In _ICCS 2023_.
