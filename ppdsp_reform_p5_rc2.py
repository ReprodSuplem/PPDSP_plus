# ppdsp_reform_p5_rc2.py

from ppdsp_reform_ins_gen import PPDSP_reform
from ppdsp_reform_utils import PPDSP_utils
from pysat.pb import *
from pysat.formula import *

class PPDSP_MaxSAT_p5(PPDSP_reform):
	def __init__(self, tsplib, request, vehicle, knn, increment=None):
		super().__init__(tsplib, request, vehicle, knn, increment)
		self.knn = int(knn)
		self.wcnf = WCNF()
		self.cnf = CNF()
		self.vpool = None
		self.insName = f"p5_{tsplib}_r{request}v{vehicle}k{knn}"

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
					if k != j:
						if self.adjMatrx[j][k] == 0: continue
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
						if self.adjMatrx[k][self.requestList[i][2]] != 0:
							varList.append(self.xVarList[j][k][self.requestList[i][2]])
				self.wcnf.append(varList)

	def genHardClauseForEq5(self):
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				varList = [-self.yVarList[i][j]]
				for k in range(self.lenOfLocation):
					if k != self.requestList[i][3]:
						if self.adjMatrx[k][self.requestList[i][3]] != 0:
							varList.append(self.xVarList[j][k][self.requestList[i][3]])
				self.wcnf.append(varList)

	def genHardClauseForEq6(self):
		for i in range(self.lenOfVehicle):
			for j in range(1+self.lenOfLocation):
				litList1 = []
				litList2 = []
				for k in range(1+self.lenOfLocation):
					if k != j and self.adjMatrx[j][k] != 0:
						litList1.append(self.xVarList[i][j][k])
					if k != j and self.adjMatrx[k][j] != 0:
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
	def genHardClauseForEq8_a(self):
		"""
		MTZ Constraints for Direct Encoding
		Logic: x[j][k] -> (u[k] == p -> u[j] == p-1)
		Clause: -x[j][k] v -nu[k][p] v nu[j][p-1]
		"""
		num_bits = self.lenOfLocation # |V|-1
		last_bit_idx = num_bits - 1 # Last bit index is |V|-2
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				for k in range(self.lenOfLocation):
					if k != j:
						if self.adjMatrx[j][k] == 0: continue # k-NN pruning
						# 1. Standard Chain: (p from 0 to last_bit_idx)
						# Logic: x -> (nu[k][p] -> nu[j][p-1])
						for p in range(num_bits):
							clause = [-self.xVarList[i][j][k], -self.nuVarList[i][k][p]]
							if p > 0:
								clause.append(self.nuVarList[i][j][p-1])
							# p=0: x -> -nu[k][0] (k cannot be first)
							self.wcnf.append(clause)
						# 2. Boundary Constraint (Explicit Fix):
						# If x_jk=1, j CANNOT be at the last position (must leave room for k)
						# Logic: x -> not nu[j][last]
						self.wcnf.append([-self.xVarList[i][j][k], -self.nuVarList[i][j][last_bit_idx]])

	def genHardClauseForEq9_a(self):
		"""
		Precedence Constraints for Direct Encoding
		Logic: y[r] -> u[drop] > u[pick]
		Includes Boundary Constraints for faster propagation.
		"""
		num_bits = self.lenOfLocation # |V|-1
		last_bit_idx = num_bits - 1 # Last bit index is |V|-2
		for i in range(self.lenOfRequest):
			pickup = self.requestList[i][2]
			dropoff = self.requestList[i][3]
			for j in range(self.lenOfVehicle):
				# 1. Pairwise Prohibition (Standard Direct Encoding)
				# Forbid: pick >= drop
				# Clause: -y v -nu[drop][k] v -nu[pick][l] (where l >= k)
				for k in range(1, num_bits): # p: from 1 to |V|-2
					for l in range(k, num_bits - 1): # p': from p to |V|-3
						clause = [-self.yVarList[i][j], -self.nuVarList[j][dropoff][k], -self.nuVarList[j][pickup][l]]
						self.wcnf.append(clause)
				# 2. Boundary Constraint (Explicit Fix)
				# If y=1, Dropoff CANNOT be the first position (0)
				self.wcnf.append([-self.yVarList[i][j], -self.nuVarList[j][dropoff][0]])
				# If y=1, Pickup CANNOT be the last position
				self.wcnf.append([-self.yVarList[i][j], -self.nuVarList[j][pickup][last_bit_idx]])

	def genHardClauseForOneHotNuVar(self):
		for t in range(self.lenOfVehicle):
			for i in range(self.lenOfLocation):
				self.exactlyOne(self.nuVarList[t][i])

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
		Applies lexicographic ordering within each group:
			For group [v1, v2, v3...]:
				- v1 is 'leader' of v2
				- v2 is 'leader' of v3
		Constraint: If vehicle 'follower' uses request r,
		vehicle 'leader' must have served a request < r.
		"""
		groups = PPDSP_utils.get_sbc_groups(self.vehicleList)
		sbc_count = 0
		# Apply chain constraints within each group of homogeneous vehicles
		for key, veh_ids in groups.items():
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
		self.genHardClauseForEq8_a()
		self.genHardClauseForEq9_a()
		self.genHardClauseForOneHotNuVar()
		self.genHardClauseFoRec() if self.knn == 0 else self.genHardClauseForKnn()
		self.genHardClauseForSbc()

		print(f"[rc2] Generating instance: {self.insName}.wcnf ...")
		self.wcnf.extend(self.cnf)
		self.wcnf.to_file(self.insName + ".wcnf")
		PPDSP_utils.export_meta(self, self.insName + ".meta")

	def solve(self, verbose=1, time_limit=5, assumption_file=None):
		wcnf_file = self.insName + ".wcnf"
		lastY = self.getLastYVarID()
		meta_file = self.insName + ".meta"
		log_file  = wcnf_file + ".out"

		# Run uwrmaxsat with meta file
		cmd = f"stdbuf -oL uwrmaxsat -no-bin -no-sat -no-par -no-scip -ppdsp-time={time_limit} -ppdsp-lastY={lastY} -ppdsp={meta_file}"
		if assumption_file is not None and os.path.exists(assumption_file):
			cmd += f" -ppdsp-assume={assumption_file}"
			print(f"  [Info] Injected Assumption file: {assumption_file}")
			
		cmd += f" {wcnf_file} | tee {log_file}"
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

