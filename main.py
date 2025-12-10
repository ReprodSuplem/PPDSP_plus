# main.py

import sys
from ppdsp_reform_ins_arg import gen_all_ins_arg
from ppdsp_reform_p1_cplex import PPDSP_MIP
from ppdsp_reform_p1_z3 import PPDSP_SMT2_p1
from ppdsp_reform_p4_z3 import PPDSP_SMT2_p4
from ppdsp_reform_p1_rc2 import PPDSP_MaxSAT_p1
from ppdsp_reform_p2_rc2 import PPDSP_MaxSAT_p2
from ppdsp_reform_p3_rc2 import PPDSP_MaxSAT_p3
from ppdsp_reform_p4_rc2 import PPDSP_MaxSAT_p4

if len(sys.argv) < 2:
	print("Usage:")
	print("  python main.py gen <tsp-file> [outDir]") # <tsp-file>: its path
	print("  python main.py <mode> <method> <tsplib> <request> <vehicle> <knn>") # <tsplib>: its name, not path, no '.tsp'
	print("    mode   : mip | smt2 | maxsat")
	print("    method : p1 | p2")
	print("    tsplib : name of the TSP instance (e.g., burma14)")
	print("    request: number of requests (e.g., 7)")
	print("    vehicle: number of vehicles (e.g., 2)")
	print("    knn    : number of neighbors for k-NN adjacency matrix (e.g., 4), or 0 for complete graph")
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
		print("Usage: python main.py <mode> <method> <tsplib> <request> <vehicle> <knn>")
		sys.exit(1)

	method, tsplib, request, vehicle, knn = sys.argv[2:7] # e.g., ['p2', 'burma14', '7', '2', '4']

	if mode == "mip":
		solver = PPDSP_MIP(tsplib, request, vehicle, knn)
		solver.genMipFormular()
		solver.writeLpFile()
		solver.solve(time_limit = 60)
	elif mode == "smt2":
		if method == "p1":
			solver = PPDSP_SMT2_p1(tsplib, request, vehicle, knn)
		elif method == "p4":
			solver = PPDSP_SMT2_p4(tsplib, request, vehicle, knn)
		else:
			print(f"Unknown method: {method}")
			sys.exit(1)
		solver.genSmt2Formular()
		solver.solve(time_limit = 60)
	elif mode == "maxsat":
		if method == "p1":
			solver = PPDSP_MaxSAT_p1(tsplib, request, vehicle, knn)
		elif method == "p2":
			solver = PPDSP_MaxSAT_p2(tsplib, request, vehicle, knn)
		elif method == "p3":
			solver = PPDSP_MaxSAT_p3(tsplib, request, vehicle, knn)
		elif method == "p4":
			solver = PPDSP_MaxSAT_p4(tsplib, request, vehicle, knn)
		else:
			print(f"Unknown method: {method}")
			sys.exit(1)
		solver.genMaxsatFormular()
		solver.solve(time_limit = 60)
	else:
		print(f"Unknown mode: {mode}")
		sys.exit(1)


