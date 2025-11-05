# main.py

import sys
from ppdsp_reform_ins_arg import gen_all_ins_arg
from ppdsp_reform_p1_cplex import PPDSP_MIP
from ppdsp_reform_p1_z3 import PPDSP_SMT2_p1
#from ppdsp_reform_p2_z3 import PPDSP_SMT2_p2
from ppdsp_reform_p1_rc2 import PPDSP_MaxSAT_p1
from ppdsp_reform_p2_rc2 import PPDSP_MaxSAT_p2

if len(sys.argv) < 2:
	print("Usage:")
	print("  python main.py gen <tsp-file> [outDir]") # <tsp-file>: its path
	print("  python main.py <mode> <method> <tsplib> <request> <vehicle> <connect>") # <tsplib>: its name, not path, no '.tsp'
	print("    mode   : mip | smt2 | maxsat")
	print("    method : p1 | p2")
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
	if len(sys.argv) < 7:
		print("Usage: python main.py <mode> <method> <tsplib> <request> <vehicle> <connect>")
		sys.exit(1)

	method, tsplib, request, vehicle, connect = sys.argv[2:7] # e.g., ['p2', 'burma14', '7', '2', '10']

	if mode == "mip":
		solver = PPDSP_MIP(tsplib, request, vehicle, connect)
		solver.genMipFormular()
		solver.writeLpFile()
		solver.solve()
	elif mode == "smt2":
		if method == "p1":
			solver = PPDSP_SMT2_p1(tsplib, request, vehicle, connect)
		#elif method == "p2":
		#	solver = PPDSP_SMT2_p2(tsplib, request, vehicle, connect)
		else:
			print(f"Unknown method: {method}")
			sys.exit(1)
		solver.genSmt2Formular()
		solver.solve()
	elif mode == "maxsat":
		if method == "p1":
			solver = PPDSP_MaxSAT_p1(tsplib, request, vehicle, connect)
		elif method == "p2":
			solver = PPDSP_MaxSAT_p2(tsplib, request, vehicle, connect)
		else:
			print(f"Unknown method: {method}")
			sys.exit(1)
		solver.genMaxsatFormular()
		solver.solve(solver="uwr")
		#solver.solve(solver="rc2")
		#solver.solve(solver="rc2", use_stratified=True)
	else:
		print(f"Unknown mode: {mode}")
		sys.exit(1)


