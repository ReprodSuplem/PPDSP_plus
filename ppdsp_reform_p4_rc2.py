# ppdsp_reform_p4_rc2.py

from ppdsp_reform_ins_gen import PPDSP_reform
from ppdsp_reform_utils import PPDSP_utils
from pysat.pb import *
from pysat.formula import *
from pysat.card import CardEnc

class PPDSP_MaxSAT_p4(PPDSP_reform):
	def __init__(self, tsplib, request, vehicle, knn):
		super().__init__(tsplib, request, vehicle, knn)
		self.knn = int(knn)
		self.wcnf = WCNF()
		self.cnf = CNF()
		self.vpool = None
		self.hVarLits = [[[] for j in range(self.lenOfLocation)] for i in range(self.lenOfVehicle)]
		self.insName = f"p4_{tsplib}_r{request}v{vehicle}k{knn}"

	def atLeastOne(self, varList):
		self.wcnf.append(varList)

	def atMostOne(self, varList):
		for i in range(len(varList)):
			for j in range(1+i, len(varList)):
				self.wcnf.append([(-1 * varList[i]), (-1 * varList[j])])

	def exactlyOne(self, varList):
		self.atMostOne(varList)
		self.atLeastOne(varList)

	def twoSumsEqvt(self, litList1, litList2):
		return (
			[[-x] + litList2 for x in litList1] +
			[[-y] + litList1 for y in litList2]
		)

	def genSoftClause(self):
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				self.wcnf.append([self.yVarList[i][j]], weight = self.requestList[i][0])
		for i in range(self.lenOfVehicle):
			for j in range(1+self.lenOfLocation):
				for k in range(1+self.lenOfLocation):
					#if k != j:
					self.wcnf.append([-self.xVarList[i][j][k]], weight = self.my_round_int(self.vehicleList[i][1]*self.locaList[j][k]))

	def genHardClauseForEq3(self):
		for i in range(self.lenOfRequest):
			varList = []
			for j in range(self.lenOfVehicle):
				varList.append(self.yVarList[i][j])
			self.atMostOne(varList)

	def genHardClauseForEq4(self):
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				varList = [-self.yVarList[i][j]]
				for k in range(1+self.lenOfLocation):
					if k != self.requestList[i][2] and k != self.requestList[i][3]:
						varList.append(self.xVarList[j][k][self.requestList[i][2]])
				self.wcnf.append(varList)

	def genHardClauseForEq5(self):
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				varList = [-self.yVarList[i][j]]
				for k in range(self.lenOfLocation):
					if k != self.requestList[i][3]:
						varList.append(self.xVarList[j][k][self.requestList[i][3]])
				self.wcnf.append(varList)

	def genHardClauseForEq6(self):
		for i in range(self.lenOfVehicle):
			for j in range(1+self.lenOfLocation):
				litList1 = []
				litList2 = []
				for k in range(1+self.lenOfLocation):
					litList1.append(self.xVarList[i][j][k])
					litList2.append(self.xVarList[i][k][j])
				cnf_obj = self.twoSumsEqvt(litList1, litList2)
				for clause in cnf_obj:
					self.wcnf.append(clause)

	def genHardClauseForEq7(self):
		for i in range(self.lenOfVehicle):
			for j in range(1+self.lenOfLocation):
				varList = []
				for k in range(1+self.lenOfLocation):
					if k != j:
						varList.append(self.xVarList[i][j][k])
				self.atMostOne(varList)

	# MTZ-SEC
	def genHardClauseForEq8_1(self):
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				for k in range(self.lenOfLocation):
					if k != j:
						clause = [-self.xVarList[i][j][k]] + [l for l in self.nuVarList[i][k]]
						self.wcnf.append(clause)

	def genHardClauseForEq8_2(self):
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				for k in range(self.lenOfLocation):
					if k != j:
						for l in range(self.lenOfLocation): # p: from 0 to |V|-2
							for m in range(self.lenOfLocation):
								if m != l - 1: # p': from 0 to |V|-2 and inconsistent with p-1
									clause = [-self.xVarList[i][j][k], -self.nuVarList[i][k][l], -self.nuVarList[i][j][m]]
									self.wcnf.append(clause)

	def genHardClauseForEq9_1(self):
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				for k in range(self.lenOfLocation): # p: from 0 to |V|-2
					for l in range(1 + k): # p': from 0 to p
						clause = [-self.yVarList[i][j], -self.nuVarList[j][self.requestList[i][2]][k], -self.nuVarList[j][self.requestList[i][3]][l]]
						self.wcnf.append(clause)

	def genHardClauseForKnn(self): # Adding k-NN pruning constraints
		for t in range(self.lenOfVehicle):
			for i in range(len(self.adjMatrx)):
				for j in range(len(self.adjMatrx[i])):
					if self.adjMatrx[i][j] == 0:
						x_var = self.xVarList[t][i][j]
						self.wcnf.append([-x_var])

	def genHardClauseFoRec(self):
		"""
		REC (Redundancy Elimination Constraints) enforces that a vehicle k only visits node i if it serves a request at i.
		Constraint: x[j][i][k] -> OR(y[r][k] for r where i is pickup/drop of r)
		
		This prevents empty vehicles from visiting nodes, and prevents loaded vehicles
		from making detours to non-target nodes.
		"""
		# Pre-compute request map for each node
		# node_requests[i] = list of request indices that start or end at i
		node_requests = [[] for _ in range(self.lenOfLocation)]
		for r in range(self.lenOfRequest):
			pickup = self.requestList[r][2]
			dropoff = self.requestList[r][3]
			node_requests[pickup].append(r)
			node_requests[dropoff].append(r)
			
		rec_count = 0
		for k in range(self.lenOfVehicle):
			for i in range(self.lenOfLocation): # Target node i (exclude Depot)
				# Collect requests relevant to node i
				service_lits = [self.yVarList[r][k] for r in node_requests[i]]
				# For all incoming edges (j -> i), add constraint
				for j in range(self.lenOfLocation + 1): # j can be Depot
					if j == i: continue
					
					x_var = self.xVarList[k][j][i]
					
					# Clause: -x^k_{ji} v y^k_{r1} v y^k_{r2} ...
					self.wcnf.append([-x_var] + service_lits)
					rec_count += 1		
		print(f"[REC] Added {rec_count} clauses.")

	def genHardClauseForSbc(self):
		"""
		SBC (Symmetry Breaking Constraints) for Homogeneous Fleet (Auto-Grouping version).
		1. Groups vehicles by (capacity, cost).
		2. Applies lexicographic ordering within each group:
			For group [v1, v2, v3...]:
				- v1 is 'leader' of v2
				- v2 is 'leader' of v3
		Constraint: If vehicle 'follower' uses request r,
		vehicle 'leader' must have served a request < r.
		"""
		# 1. Auto-grouping: find all homogeneous vehicles
		# Key: (capacity, cost), Value: [vehicle_id_1, vehicle_id_2, ...]
		groups = {}
		for t in range(self.lenOfVehicle):
			# Convert list to tuple for dict key
			cap = self.vehicleList[t][0]
			cost = self.vehicleList[t][1]
			key = (cap, cost)
			
			if key not in groups:
				groups[key] = []
			groups[key].append(t)
			
		# 2. Apply chain constraints within each group of homogeneous vehicles
		sbc_count = 0
		for key, veh_ids in groups.items():
			if len(veh_ids) < 2:
				continue # Only one vehicle of this type, no SBC needed
			# print(f"[SBC] Group {key}: vehicles {veh_ids}")

			# Chain constraints: v[0] is leader of v[1], v[1] is leader of v[2], ...
			for i in range(len(veh_ids) - 1):
				leader = veh_ids[i]
				follower = veh_ids[i+1]
				
				for r in range(self.lenOfRequest):
					# y[r][follower] -> (y[0][leader] v ... v y[r-1][leader])
					clause = [-self.yVarList[r][follower]]
					for prev_r in range(r):
						clause.append(self.yVarList[prev_r][leader])
					
					self.wcnf.append(clause)
					sbc_count += 1
		print(f"[SBC] Added {sbc_count} clauses.")

	def genMaxsatFormular(self):
		self.genXVarList()
		self.genYVarList()
		self.genNuVarList()

		self.genSoftClause()
		self.genHardClauseForEq3()
		self.genHardClauseForEq4()
		self.genHardClauseForEq5()
		self.genHardClauseForEq6()
		self.genHardClauseForEq7()
		self.genHardClauseForEq8_1()
		self.genHardClauseForEq8_2()
		self.genHardClauseForEq9_1()
		self.genHardClauseFoRec() if self.knn == 0 else self.genHardClauseForKnn()
		self.genHardClauseForSbc()

		print(f"[rc2] Generating instance: {self.insName}.wcnf ...")
		self.wcnf.extend(self.cnf)
		self.wcnf.to_file(self.insName + ".wcnf")
		PPDSP_utils.export_meta(self, self.insName + ".meta")

	def solve(self, verbose=1, time_limit=5):
		wcnf_file = self.insName + ".wcnf"
		lastY = self.getLastYVarID()
		meta_file = self.insName + ".meta"
		assumption_file = wcnf_file + ".asp"
		log_file  = wcnf_file + ".out"

		# Run uwrmaxsat with meta file and assumption file
		# -ppdsp-assume={assumption_file}
		cmd = f"stdbuf -oL uwrmaxsat -no-bin -no-sat -no-par -no-scip -ppdsp-time={time_limit} -ppdsp-lastY={lastY} -ppdsp={meta_file} {wcnf_file} | tee {log_file}"
		print(f"[UWrMaxSAT] Running command:\n  {cmd}")
		os.system(cmd)
		# PPDSP_utils.run_uwrmaxsat(cmd, log_file, time_limit)

		# Parse model
		model = []
		with open(log_file, "r") as f:
			for line in f:
				line = line.strip()
				if line.startswith("v "):
					for lit in line.split()[1:]: # Ignore 1st char 'v'
						if lit != "0":
							model.append(int(lit))
			
		if not model:
			with open(log_file, "a") as f:
				f.write("\n[UWrMaxSAT] No solution.\n")
			print("[UWrMaxSAT] No solution.")
			return None

		# Decode XY domain only
		filtered_model = PPDSP_utils.extractXYModel(self, model)

		PPDSP_utils.printVehRoutes(self, filtered_model)
		obj_val = PPDSP_utils.evaluateSolution(self, filtered_model)

		with open(log_file, "a") as f:
			f.write(f"[UWrMaxSAT] OBJ: {obj_val}")

		return filtered_model

