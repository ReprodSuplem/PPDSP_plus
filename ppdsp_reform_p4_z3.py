# ppdsp_reform_p4_z3.py

from ppdsp_reform_ins_gen import PPDSP_reform
from ppdsp_reform_utils import PPDSP_utils
from z3 import *

class PPDSP_SMT2_p4(PPDSP_reform):
	def __init__(self, tsplib, request, vehicle, connect):
		super().__init__(tsplib, request, vehicle, connect)
		self.smt2Opt = Optimize()
		self.optimal = 0
		self.insName = f"p4_{tsplib}_r{request}v{vehicle}c{connect}"

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
		self.obj = Int("obj")
		self.smt2Opt.add(self.obj == Sum(profit) - Sum(cost))
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

	def smt2Eq12(self):
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				self.smt2Opt.add(self.smt2u[i][j] <= self.lenOfLocation - 1)
				self.smt2Opt.add(self.smt2u[i][j] >= 0)

	def genSymmetryBreaking(self):
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
					
					y_follower = Bool(f"y{self.yVarList[r][follower]}")
					y_leader_vars = [Bool(f"y{self.yVarList[pr][leader]}") for pr in range(r)]
					
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
		self.smt2Eq12()
		self.genSymmetryBreaking()

	def solve(self, time_limit=5):
		import time
		from z3 import sat, unknown
		start_time = time.time()

		print(f"[Z3] Solving instance: {self.insName} ...")
		if time_limit is not None:
			print(f"[Z3] Setting time limit to {time_limit} seconds")
			self.smt2Opt.set("timeout", time_limit * 1000)
		PPDSP_utils.buildVarIndexMap(self)

		opt = self.smt2Opt
		log_file = f"{self.insName}.smt2.out"

		best_val = None
		best_model_xy = None
		with open(log_file, "w") as f:
			def log(msg):
				print(msg)
				f.write(msg + "\n")
				f.flush()

			while True:
				if time_limit is not None:
					elapsed_so_far = time.time() - start_time
					remaining_time = time_limit - elapsed_so_far
					
					if remaining_time <= 0:
						log("[Z3] Time limit exceeded before check.")
						res = None # Force timeout
					else:
						res = PPDSP_utils.solve_z3_with_interrupt(opt, remaining_time)
				else:
					res = opt.check()
				if res != sat:
					elapsed = time.time() - start_time
					if best_model_xy is None:
						log("[Z3] UNSAT.")
						log(f"[Z3] Runtime: {elapsed:.3f} sec")
						return None

					log(f"[Z3] Optimal model found, OBJ: {best_val}")
					log(f"[Z3] Runtime: {elapsed:.3f} sec")
					
					PPDSP_utils.printVehRoutes(self, best_model_xy)
					PPDSP_utils.evaluateSolution(self, best_model_xy)
					log("===== RAW XY MODEL =====")
					log(" ".join(str(v) for v in best_model_xy))
					return best_model_xy

				model = opt.model()
				filtered_model = PPDSP_utils.extractXYModel_z3(self, model)
				decoded = PPDSP_utils.decodeModel(self, filtered_model)
				veh_routes = []
				veh_reqs   = []
				for v in range(self.lenOfVehicle):
					veh_routes.append(decoded[v]['route'])
					veh_reqs.append(decoded[v]['requests'])

				violated_any = False
				for t in range(self.lenOfVehicle):
					violated, learnt_clause = PPDSP_utils.checkOverload(
						self,
						t,
						veh_routes[t],
						veh_reqs[t]
					)
					if violated:
						violated_any = True
						z3_clause = PPDSP_utils.learntClause_z3(self, learnt_clause)
						log(f"[Z3] Vehicle {t} overload → add lazy cut of size {len(z3_clause)}")
						opt.add( Or(z3_clause) )

				if violated_any:
					continue

				obj_val = model.evaluate(self.obj, model_completion=True).as_long()
				log(f"[Z3] Feasible model found, OBJ: {obj_val}")
				if best_val is None or obj_val > best_val:
					best_val = obj_val
					best_model_xy = list(filtered_model)
					opt.add(self.obj > best_val)


