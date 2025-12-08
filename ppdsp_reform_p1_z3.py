# ppdsp_reform_p1_z3.py

from ppdsp_reform_ins_gen import PPDSP_reform
from ppdsp_reform_utils import PPDSP_utils
from z3 import *

class PPDSP_SMT2_p1(PPDSP_reform):
	def __init__(self, tsplib, request, vehicle, knn):
		super().__init__(tsplib, request, vehicle, knn)
		self.knn = int(knn)
		self.smt2Opt = Optimize()
		self.optimal = 0
		self.insName = f"p1_{tsplib}_r{request}v{vehicle}k{knn}"

	def addXVars(self):
		self.smt2x = [[[Bool(f"x{self.xVarList[i][j][k]}") for k in range(len(self.xVarList[i][j]))] for j in range(len(self.xVarList[i]))] for i in range(len(self.xVarList))]

	def addYVars(self):
		self.smt2y = [[Bool(f"y{self.yVarList[i][j]}") for j in range(len(self.yVarList[i]))] for i in range(len(self.yVarList))]

	def addUVars(self):
		self.smt2u = [[Int(f"u{self.uVarList[i][j]}") for j in range(len(self.uVarList[i]))] for i in range(len(self.uVarList))]

	def addHVars(self):
		self.smt2h = [[Int(f"h{self.hVarList[i][j]}") for j in range(len(self.hVarList[i]))] for i in range(len(self.hVarList))]

	def smt2Obj(self):
		profit = []
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				profit.append(self.requestList[i][0] * If(self.smt2y[i][j], 1, 0))
		cost = []
		for i in range(self.lenOfVehicle):
			for j in range(1+self.lenOfLocation):
				for k in range(1+self.lenOfLocation):
					cost.append(self.my_round_int(self.vehicleList[i][1] * self.locaList[j][k]) * If(self.smt2x[i][j][k], 1, 0))
		self.obj = Sum(profit) - Sum(cost)
		self.optimal = self.smt2Opt.maximize(self.obj)
		#print(self.smt2Opt.objectives())

	def smt2Eq3(self):
		for i in range(self.lenOfRequest):
			self.smt2Opt.add(
				Sum([If(self.smt2y[i][j], 1, 0) for j in range(self.lenOfVehicle)]) <= 1
			)

	def smt2Eq4(self, mode=1):
		'''
			mode=1 (arithmetic): y ≤ Σ x_i
			mode=2 (implication): y → (x1 ∨ x2 ∨ ...)
			mode=3 (CNF): ¬y ∨ x1 ∨ x2 ∨ ...
		'''
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				xVars = []
				for k in range(1 + self.lenOfLocation):
					if k != self.requestList[i][2] and k != self.requestList[i][3]:
						xVars.append(self.smt2x[j][k][self.requestList[i][2]])
				if mode == 1:
					self.smt2Opt.add(
						If(self.smt2y[i][j], 1, 0) <= Sum([If(x, 1, 0) for x in xVars])
					)
				elif mode == 2:
					self.smt2Opt.add(
						Implies(self.smt2y[i][j], Or(xVars))
					)
				elif mode == 3:
					self.smt2Opt.add(
						Or([Not(self.smt2y[i][j])] + xVars)
					)
				else:
					raise ValueError("Invalid mode: choose 1 (arithmetic), 2 (implication), or 3 (CNF)")

	def smt2Eq5(self, mode=1):
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				xVars = []
				for k in range(self.lenOfLocation):
					if k != self.requestList[i][3]:
						xVars.append(self.smt2x[j][k][self.requestList[i][3]])
				if mode == 1:
					self.smt2Opt.add(
						If(self.smt2y[i][j], 1, 0) <= Sum([If(x, 1, 0) for x in xVars])
					)
				elif mode == 2:
					self.smt2Opt.add(
						Implies(self.smt2y[i][j], Or(xVars))
					)
				elif mode == 3:
					self.smt2Opt.add(
						Or([Not(self.smt2y[i][j])] + xVars)
					)
				else:
					raise ValueError("Invalid mode: choose 1 (arithmetic), 2 (implication), or 3 (CNF)")

	def smt2Eq6(self):
		for i in range(self.lenOfVehicle):
			for j in range(1 + self.lenOfLocation):
				out_flow = [If(self.smt2x[i][j][k], 1, 0) for k in range(1 + self.lenOfLocation)]
				in_flow = [If(self.smt2x[i][k][j], 1, 0) for k in range(1 + self.lenOfLocation)]
				self.smt2Opt.add(Sum(out_flow) - Sum(in_flow) == 0)

	def smt2Eq7(self):
		for i in range(self.lenOfVehicle):
			for j in range(1 + self.lenOfLocation):
				xVars = [
					self.smt2x[i][j][k]
					for k in range(1 + self.lenOfLocation)
					if k != j
				]
				if xVars:
					self.smt2Opt.add(Sum([If(x, 1, 0) for x in xVars]) <= 1)

	def smt2Eq8(self, mode=2):
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				for k in range(self.lenOfLocation):
					if k == j:
						continue
					u_o = self.smt2u[i][j]
					u_d = self.smt2u[i][k]
					x_od = self.smt2x[i][j][k]
					#if mode == 1:
					#	self.smt2Opt.add(u_o - u_d + self.lenOfLocation * If(x_od, 1, 0) <= self.lenOfLocation - 1)
					if mode == 2:
						self.smt2Opt.add(Implies(x_od, u_d - u_o >= 1))
					elif mode == 3:
						self.smt2Opt.add(Or(Not(x_od), u_d - u_o >= 1))
					else:
						raise ValueError("mode must be 2 (implication), or 3 (CNF)")

	def smt2Eq9(self, mode=2):
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				o = self.requestList[i][2]
				d = self.requestList[i][3]
				if mode == 2:
					self.smt2Opt.add(Implies(self.smt2y[i][j], self.smt2u[j][d] > self.smt2u[j][o]))
				elif mode == 3:
					self.smt2Opt.add(Or(Not(self.smt2y[i][j]), self.smt2u[j][d] > self.smt2u[j][o]))
				else:
					raise ValueError("mode must be 2 (implication), or 3 (CNF)")

	def smt2Eq10(self):
		node_requests = [ {'pickup': [], 'drop': []} for _ in range(self.lenOfLocation) ]
		for r in range(self.lenOfRequest):
			node_requests[self.requestList[r][2]]['pickup'].append(r)
			node_requests[self.requestList[r][3]]['drop'].append(r)
			
		for i in range(self.lenOfVehicle):
			for j in range(1 + self.lenOfLocation): # j is 'o'
				for k in range(self.lenOfLocation): # k is 'd'
					if k == j:
						continue
					Gamma = 0
					# + Pickup Load (only when vehicle i serves request r)
					for r in node_requests[k]['pickup']:
						size = self.requestList[r][1]
						Gamma += If(self.smt2y[r][i], size, 0)
					# - Drop Load (only when vehicle i serves request r)
					for r in node_requests[k]['drop']:
						size = self.requestList[r][1]
						Gamma -= If(self.smt2y[r][i], size, 0)
					# Add constraint: x_{jk} -> h_k == h_j + Gamma
					self.smt2Opt.add(
						Implies(
							self.smt2x[i][j][k], 
							self.smt2h[i][k] == self.smt2h[i][j] + Gamma
						)
					)

	def smt2Eq11(self):
		for i in range(self.lenOfVehicle):
			cap = int(self.vehicleList[i][0])
			for j in range(1 + self.lenOfLocation):
				if j == self.lenOfLocation:
					self.smt2Opt.add(self.smt2h[i][j] == 0)
				else:
					self.smt2Opt.add(self.smt2h[i][j] >= 0)
					self.smt2Opt.add(self.smt2h[i][j] <= cap)

	def smt2Eq12(self):
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				self.smt2Opt.add(self.smt2u[i][j] <= self.lenOfLocation - 1)
				self.smt2Opt.add(self.smt2u[i][j] >= 0)

	def smt2Knn(self):
		for t in range(self.lenOfVehicle):
			for i in range(len(self.adjMatrx)):
				for j in range(len(self.adjMatrx[i])):
					if self.adjMatrx[i][j] == 0:
						self.smt2Opt.add(Not(self.smt2x[t][i][j]))

	def smt2Rec(self):
		"""
		REC: Implies(x[t][j][i], Or(y[r][t]...))
		"""
		print("[Z3] Adding Redundancy Elimination Constraints (REC)...")
		
		node_requests = [[] for _ in range(self.lenOfLocation)]
		for r in range(self.lenOfRequest):
			pickup = self.requestList[r][2]
			dropoff = self.requestList[r][3]
			node_requests[pickup].append(r)
			node_requests[dropoff].append(r)
			
		rec_count = 0
		for t in range(self.lenOfVehicle):
			for i in range(self.lenOfLocation): # Target node i (exclude Depot)
				# Collect requests relevant to node i
				service_lits = [self.smt2y[r][t] for r in node_requests[i]]
				# Service Condition: False for empty service_lits
				if service_lits:
					service_condition = Or(service_lits)
				else:
					service_condition = False 

				for j in range(self.lenOfLocation + 1): # Source j (can be Depot)
					if j == i: continue
					
					# Constraint: x -> service
					if service_condition is False:
						# Block incoming edges if no requests at node i
						self.smt2Opt.add(Not(self.smt2x[t][j][i]))
					else:
						self.smt2Opt.add(Implies(self.smt2x[t][j][i], service_condition))
					rec_count += 1
		print(f"[Z3] Added {rec_count} REC implications.")

	def smt2Sbc(self):
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
					y_follower = self.smt2y[r][follower]
					y_leader_vars = [self.smt2y[prev_r][leader] for prev_r in range(r)]
					
					if y_leader_vars:
						self.smt2Opt.add(Implies(y_follower, Or(y_leader_vars)))
					else:
						# r=0, follower cannot serve request 0 (must be leader)
						self.smt2Opt.add(Not(y_follower))
					sbc_count += 1
		print(f"[SBC] Added {sbc_count} clauses.")

	def genSmt2Formular(self):
		print("[Z3] Adding varibles ...")
		self.genXVarList()
		self.genYVarList()
		self.genUVarList()
		self.genHVarList()
		self.addXVars()
		self.addYVars()
		self.addUVars()
		self.addHVars()

		print("[Z3] Adding constraints ...")
		self.smt2Obj()
		self.smt2Eq3()
		# Try to switch between mode 1 (arithmetic), 2 (implication), or 3 (CNF) in Eq.4 and Eq.5
		self.smt2Eq4(mode=2)
		self.smt2Eq5(mode=2)
		self.smt2Eq6()
		self.smt2Eq7()
		# Try to switch between mode 2 (implication), or 3 (CNF) in Eq.8 and Eq.9
		self.smt2Eq8(mode=2)
		self.smt2Eq9(mode=2)
		self.smt2Eq10()
		self.smt2Eq11()
		self.smt2Eq12()
		self.smt2Rec() if self.knn == 0 else self.smt2Knn()
		self.smt2Sbc()

	def solve(self, time_limit=5):
		import time
		start_time = time.time()

		print(f"[Z3] Solving instance: {self.insName} ...")
		#if time_limit is not None:
		#	print(f"[Z3] Setting time limit to {time_limit} seconds")
		#	self.smt2Opt.set("timeout", time_limit * 1000)
		PPDSP_utils.buildVarIndexMap(self)

		opt = self.smt2Opt

		# Read assumption file if exists, and set assumptions
		assumption_file = self.insName + ".smt2.asp"
		assumption_faile = False
		if assumption_file:
			print(f"[Z3] Reading assumption from {assumption_file} ...")
			lits = PPDSP_utils.read_assumption_literals(assumption_file)
			
			if lits:
				z3_assumps = [] # Z3 assumptions list (BoolRef) only including x and y vars
				PPDSP_utils.buildVarIndexMap(self)
				for vid in lits:
					z3_var = PPDSP_utils.get_z3_var(self, vid)
					if z3_var is not None:
						if vid > 0:
							z3_assumps.append(z3_var)
						else:
							z3_assumps.append(Not(z3_var))
				
				if z3_assumps:
					print("[Z3] Verifying assumption model...")
					check_res = opt.check(z3_assumps)
					
					if check_res == sat:
						model = opt.model()
						obj_val = model.evaluate(self.obj).as_long()
						print(f"[Z3] Assumption VALID. Starting objective: {obj_val}")
						
						# Update lower bound, and keep searching a better opt obj
						opt.add(self.obj > obj_val)
					else:
						assumption_faile = True
						print("[Z3] Assumption INVALID (UNSAT with current constraints). Ignoring.")

		log_file = f"{self.insName}.smt2.out"
		with open(log_file, "w") as f:
			def log(msg):
				print(msg)
				f.write(msg + "\n")
				f.flush()

			if time_limit is not None:
				res = PPDSP_utils.solve_z3_with_interrupt(opt, time_limit)
			else:
				res = opt.check()
			elapsed = time.time() - start_time
			if res != sat:
				if assumption_faile:
					if res is None or str(res) == 'unknown':
						log("[Z3] Timeout / Unknown.")
					else:
						log("[Z3] UNSAT.")
					log(f"[Z3] Runtime: {elapsed:.3f} sec")
					return None
				else:
					if res is None:
						log("[Z3] Timeout.")
					log(f"[Z3] Runtime: {elapsed:.3f} sec")

			if assumption_faile:
				model = opt.model()
			filtered_model = PPDSP_utils.extractXYModel_z3(self, model)
			
			log("[Z3] Optimal model found.")
			log(f"[Z3] Runtime: {elapsed:.3f} sec")
			
			PPDSP_utils.printVehRoutes(self, filtered_model)
			PPDSP_utils.evaluateSolution(self, filtered_model)
			log("===== RAW XY MODEL =====")
			log(" ".join(str(v) for v in filtered_model))

			return filtered_model


