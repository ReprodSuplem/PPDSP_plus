# main.py

import sys
from ppdsp_reform_ins_arg import gen_all_ins_arg
from ppdsp_reform_p1_cplex import PPDSP_MIP
from ppdsp_reform_p1_z3 import PPDSP_SMT2
from ppdsp_reform_p1_rc2 import PPDSP_MaxSAT

if len(sys.argv) < 2:
    print("Usage:")
    print("  python main.py gen <tsp-file> [outDir]") # <tsp-file>: its path
    print("  python main.py mip <tsplib> <request> <vehicle> <connect>") # <tsplib>: its name, not path, no '.tsp'
    print("  python main.py smt2 <tsplib> <request> <vehicle> <connect>")
    print("  python main.py maxsat <tsplib> <request> <vehicle> <connect>")
    sys.exit(1)

mode = sys.argv[1]

if mode == "gen":
    if len(sys.argv) < 3:
        print("Usage: python main.py gen <tsp-file> [outDir]")
        sys.exit(1)
    tsp_file = sys.argv[2]
    outDir = sys.argv[3] if len(sys.argv) > 3 else "."
    print(f"Generating instance arguments for {tsp_file} ...")
    gen_all_ins_arg(tsp_file, outDir=outDir, seed=42)
    print("Instance generation completed.")
else:
	if len(sys.argv) < 6:
		print("Usage: python main.py <mode> <tsplib> <request> <vehicle> <connect>")
		sys.exit(1)

	tsplib, request, vehicle, connect = sys.argv[2:6] # e.g., ['burma14', '7', '2', '10']

	if mode == "mip":
		solver = PPDSP_MIP(tsplib, request, vehicle, connect)
		solver.genMipFormular()
		solver.writeLpFile()
		solver.solve()
	elif mode == "smt2":
		solver = PPDSP_SMT2(tsplib, request, vehicle, connect)
		solver.genSmt2Formular()
		solver.solve()
	elif mode == "maxsat":
		solver = PPDSP_MaxSAT(tsplib, request, vehicle, connect)
		solver.genMaxsatFormular()
		solver.solve(solver="rc2")
	else:
		print(f"Unknown mode: {mode}")
		sys.exit(1)


