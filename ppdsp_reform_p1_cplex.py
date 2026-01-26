# ppdsp_reform_p1_cplex.py

from ppdsp_reform_ins_gen import PPDSP_reform
from ppdsp_reform_utils import PPDSP_utils
import cplex
from cplex import SparsePair

class PPDSP_MIP(PPDSP_reform):
	def __init__(self, tsplib, request, vehicle, knn):
		super().__init__(tsplib, request, vehicle, knn)
		self.knn = int(knn)
		self.cpx = cplex.Cplex()
		self.cpx.objective.set_sense(self.cpx.objective.sense.maximize)
		self.insName = f"p1_{tsplib}_r{request}v{vehicle}k{knn}"

	def addXVars(self):
		for i in range(len(self.xVarList)):
			for j in range(len(self.xVarList[i])):
				for k in range(len(self.xVarList[i][j])):
					self._addVar('x', self.xVarList[i][j][k], 0, 1, "B")

	def addYVars(self):
		for i in range(len(self.yVarList)):
			for j in range(len(self.yVarList[i])):
				self._addVar('y', self.yVarList[i][j], 0, 1, "B")

	def addUVars(self):
		for i in range(len(self.uVarList)):
			for j in range(len(self.uVarList[i])):
				self._addVar('u', self.uVarList[i][j], 0, self.lenOfLocation - 1, "I")

	def addHVars(self):
		for i in range(len(self.hVarList)):
			for j in range(len(self.hVarList[i])):
				cap = int(self.vehicleList[i][0])
				if j == self.lenOfLocation:
					self._addVar('h', self.hVarList[i][j], 0, 0, "I")
				else:
					self._addVar('h', self.hVarList[i][j], 0, cap, "I")

	def _addVar(self, prefix, var_id, lb, ub, vtype):
		self.cpx.variables.add(names=[f"{prefix}{var_id}"], lb=[lb], ub=[ub], types=[vtype])

	def mipObj(self):
		obj_terms = []
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				var_id = self.yVarList[i][j]
				profit = self.requestList[i][0]
				obj_terms.append((f"y{var_id}", profit))
		for i in range(self.lenOfVehicle):
			for j in range(1 + self.lenOfLocation):
				for k in range(1 + self.lenOfLocation):
					if j == k: continue
					if self.adjMatrx[j][k] == 0: continue
					var_id = self.xVarList[i][j][k]
					cost = -self.my_round_int(self.vehicleList[i][1] * self.locaList[j][k])
					obj_terms.append((f"x{var_id}", cost))
		self.cpx.objective.set_linear(obj_terms)

	def mipEq3(self):
		for i in range(self.lenOfRequest):
			ind, val = [], []
			for j in range(self.lenOfVehicle):
				ind.append("y" + str(self.yVarList[i][j]))
				val.append(1.0)
			self.cpx.linear_constraints.add(
				lin_expr=[SparsePair(ind=ind, val=val)],
				senses=['L'],
				rhs=[1.0]
			)

	def mipEq4(self):
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				ind, val = [], []
				for k in range(1 + self.lenOfLocation):
					if k != self.requestList[i][2] and k != self.requestList[i][3]:
						if self.adjMatrx[k][self.requestList[i][2]] == 0: continue
						ind.append("x" + str(self.xVarList[j][k][self.requestList[i][2]]))
						val.append(1.0)
				ind.append("y" + str(self.yVarList[i][j]))
				val.append(-1.0)
				self.cpx.linear_constraints.add(
					lin_expr=[SparsePair(ind=ind, val=val)],
					senses=['G'],
					rhs=[0.0]
				)

	def mipEq5(self):
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				ind, val = [], []
				for k in range(self.lenOfLocation):
					if k != self.requestList[i][3]:
						if self.adjMatrx[k][self.requestList[i][3]] == 0: continue
						ind.append("x" + str(self.xVarList[j][k][self.requestList[i][3]]))
						val.append(1.0)
				ind.append("y" + str(self.yVarList[i][j]))
				val.append(-1.0)
				self.cpx.linear_constraints.add(
					lin_expr=[SparsePair(ind=ind, val=val)],
					senses=['G'],
					rhs=[0.0]
				)

	def mipEq6(self):
		for i in range(self.lenOfVehicle):
			for j in range(1 + self.lenOfLocation):
				ind, val = [], []
				for k in range(1 + self.lenOfLocation):
					if k == j: continue
					if self.adjMatrx[j][k] != 0:
						ind.append("x" + str(self.xVarList[i][j][k]))
						val.append(1.0)
					if self.adjMatrx[k][j] != 0:
						ind.append("x" + str(self.xVarList[i][k][j]))
						val.append(-1.0)
				self.cpx.linear_constraints.add(
					lin_expr=[SparsePair(ind=ind, val=val)],
					senses=['E'],
					rhs=[0.0]
				)

	def mipEq7(self):
		for i in range(self.lenOfVehicle):
			for j in range(1 + self.lenOfLocation):
				ind, val = [], []
				for k in range(1 + self.lenOfLocation):
					if k != j:
						ind.append("x" + str(self.xVarList[i][j][k]))
						val.append(1.0)
				self.cpx.linear_constraints.add(
					lin_expr=[SparsePair(ind=ind, val=val)],
					senses=['L'],
					rhs=[1.0]
				)

	def mipEq8(self):
		n = self.lenOfLocation
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				for k in range(self.lenOfLocation):
					if k != j:
						if self.adjMatrx[j][k] == 0: continue
						ind = [
							"u" + str(self.uVarList[i][j]),
							"u" + str(self.uVarList[i][k]),
							"x" + str(self.xVarList[i][j][k])
						]
						val = [1.0, -1.0, float(n)]
						self.cpx.linear_constraints.add(
							lin_expr=[SparsePair(ind=ind, val=val)],
							senses=['L'],
							rhs=[float(n - 1)]
						)

	def mipEq9(self):
		n = self.lenOfLocation
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				ind = [
					"u" + str(self.uVarList[j][self.requestList[i][2]]),
					"u" + str(self.uVarList[j][self.requestList[i][3]]),
					"y" + str(self.yVarList[i][j])
				]
				val = [1.0, -1.0, float(n)]
				self.cpx.linear_constraints.add(
					lin_expr=[SparsePair(ind=ind, val=val)],
					senses=['L'],
					rhs=[float(n - 1)]
				)

	def mipEq10(self):
		total_demand = sum(self.requestList[r][1] for r in range(self.lenOfRequest))
		for i in range(self.lenOfVehicle):
			cap = self.vehicleList[i][0]
			bigM = cap + min(cap, total_demand)
			for j in range(1 + self.lenOfLocation):
				for k in range(self.lenOfLocation):
					if k != j:
						if self.adjMatrx[j][k] == 0: continue
						ind = ["h" + str(self.hVarList[i][j]),
							"h" + str(self.hVarList[i][k]),
							"x" + str(self.xVarList[i][j][k])]
						val = [1.0, -1.0, float(bigM)]

						for l in range(self.lenOfRequest):
							if self.requestList[l][2] == k:
								ind.append("y" + str(self.yVarList[l][i]))
								val.append(float(self.requestList[l][1]))
							elif self.requestList[l][3] == k:
								ind.append("y" + str(self.yVarList[l][i]))
								val.append(-float(self.requestList[l][1]))

						# left side <= bigM
						self.cpx.linear_constraints.add(
							lin_expr=[SparsePair(ind=ind, val=val)],
							senses=['L'],
							rhs=[float(bigM)]
						)

						# right side >= -bigM
						val_neg = val.copy()
						val_neg[2] = -float(bigM)  # flip sign of x coefficient
						self.cpx.linear_constraints.add(
							lin_expr=[SparsePair(ind=ind, val=val_neg)],
							senses=['G'],
							rhs=[-float(bigM)]
						)

	def mipKnn(self): # Applying k-NN sparsification
		indices = []
		values = []
		for t in range(self.lenOfVehicle):
			for i in range(len(self.adjMatrx)):
				for j in range(len(self.adjMatrx[i])):
					# x^t_{ij} has been pruned by k-NN, if adjMatrx[i][j] == 0
					if self.adjMatrx[i][j] == 0:
						var_id = self.xVarList[t][i][j]
						var_name = f"x{var_id}"
						indices.append(var_name)
						values.append(0.0)
		if indices:
			self.cpx.variables.set_upper_bounds(zip(indices, values))

	def mipRec(self):
		"""
		REC: x[t][j][i] <= Sum(y[r][t] for r at i)
		Linear form: x[t][j][i] - Sum(y[r][t]) <= 0
		"""
		node_requests = [[] for _ in range(self.lenOfLocation)]
		for r in range(self.lenOfRequest):
			pickup = self.requestList[r][2]
			dropoff = self.requestList[r][3]
			node_requests[pickup].append(r)
			node_requests[dropoff].append(r)
			
		rec_count = 0
		for t in range(self.lenOfVehicle):
			for i in range(self.lenOfLocation): # Target node i (exclude Depot)
				# For all incoming edges (j -> i), add constraint
				for j in range(self.lenOfLocation + 1): # Source j (can be Depot)
					if j == i: continue
					
					# Linear expression: x[t][j][i] - Sum(y[r][t] for r at i) <= 0
					ind = [f"x{self.xVarList[t][j][i]}"]
					val = [1.0]
					
					for r in node_requests[i]:
						ind.append(f"y{self.yVarList[r][t]}")
						val.append(-1.0)
						
					self.cpx.linear_constraints.add(
						lin_expr=[cplex.SparsePair(ind=ind, val=val)],
						senses=['L'],
						rhs=[0.0]
					)
					rec_count += 1
		print(f"[CPLEX] Added {rec_count} REC inequalities.")

	def mipSbc(self):
		"""
		SBC for Homogeneous Fleet (Grouped by capacity).
		Constraint: y[r][follower] <= Sum(y[prev_r][leader] for prev_r < r)
		"""
		groups = PPDSP_utils.get_sbc_groups(self.vehicleList)
		sbc_count = 0
		# Chain constraints within each group of homogeneous vehicles
		for key, veh_ids in groups.items():
			# v[0] <- v[1] <- v[2] ...
			for i in range(len(veh_ids) - 1):
				leader = veh_ids[i]
				follower = veh_ids[i+1]
				
				for r in range(self.lenOfRequest):
					# y[r][follower] - Sum(y[prev_r][leader] for prev_r < r) <= 0
					ind = [f"y{self.yVarList[r][follower]}"]
					val = [1.0]
					for prev_r in range(r):
						ind.append(f"y{self.yVarList[prev_r][leader]}")
						val.append(-1.0)
					self.cpx.linear_constraints.add(
						lin_expr=[cplex.SparsePair(ind=ind, val=val)],
						senses=['L'],
						rhs=[0.0]
					)
					sbc_count += 1
		print(f"[CPLEX] Added {sbc_count} SBC inequalities.")

	def genMipFormular(self):
		self.genXVarList()
		self.genYVarList()
		self.genUVarList()
		self.genHVarList()
		self.addXVars()
		self.addYVars()
		self.addUVars()
		self.addHVars()

		self.mipEq3()
		self.mipEq4()
		self.mipEq5()
		self.mipEq6()
		self.mipEq7()
		self.mipEq8()
		self.mipEq9()
		self.mipEq10()
		self.mipRec() if self.knn == 0 else	self.mipKnn()
		#self.mipSbc()
		self.mipObj()

	def writeLpFile(self):
		self.cpx.write(self.insName + ".lp", filetype="lp")

	def solve(self, time_limit=5):
		import time
		start_time = time.time()

		if time_limit is not None:
			print(f"[CPLEX] Setting time limit to {time_limit} seconds")
			self.cpx.parameters.timelimit.set(time_limit)

		self.cpx.parameters.threads.set(1)

		''' Do NOT use backbone branching (not good)
		# Set branching priority
		print("[CPLEX] Setting branching priorities (x, y: High, others: Low)...")
		high_priority_vars = []
		# xVars
		for i in range(self.lenOfVehicle):
			for j in range(len(self.xVarList[i])):
				for k in range(len(self.xVarList[i][j])):
					vid = self.xVarList[i][j][k]
					high_priority_vars.append((f"x{vid}", 100, self.cpx.order.branch_direction.up))
		# yVars
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				vid = self.yVarList[i][j]
				high_priority_vars.append((f"y{vid}", 200, self.cpx.order.branch_direction.up))
		self.cpx.order.set(high_priority_vars)
		'''

		# Read assumption file if exists, and set MIP start
		assumption_file = self.insName + ".lp.asp"
		if assumption_file and False:
			print(f"[CPLEX] Reading assumption from {assumption_file} ...")
			lits = PPDSP_utils.read_assumption_literals(assumption_file)

			if lits:
				ind = []
				val = []
				# 1. Check xVar
				for i in range(self.lenOfVehicle):
					for j in range(len(self.xVarList[i])):
						for k in range(len(self.xVarList[i][j])):
							vid = self.xVarList[i][j][k]
							if vid in lits:
								ind.append(f"x{vid}")
								val.append(1.0)
							elif -vid in lits:
								ind.append(f"x{vid}")
								val.append(0.0)
				# 2. Check yVar
				for i in range(self.lenOfRequest):
					for j in range(self.lenOfVehicle):
						vid = self.yVarList[i][j]
						if vid in lits:
							ind.append(f"y{vid}")
							val.append(1.0)
						elif -vid in lits:
							ind.append(f"y{vid}")
							val.append(0.0)
				if ind:
					print(f"[CPLEX] Applying MIP Start with {len(ind)} variables.")
					self.cpx.MIP_starts.add(
						cplex.SparsePair(ind=ind, val=val),
						self.cpx.MIP_starts.effort_level.auto
					)

		log_file = f"{self.insName}.lp.out"
		with open(log_file, "w") as f:
			def log(msg):
				print(msg)
				f.write(msg + "\n")
				f.flush()
		
			self.cpx.solve()
			elapsed = time.time() - start_time

			status = self.cpx.solution.get_status_string()
			log(f"[CPLEX] Status: {status}")

			if self.cpx.solution.is_primal_feasible():
				opt = self.cpx.solution.get_objective_value()
				varValues = self.cpx.solution.get_values()
				varNames = self.cpx.variables.get_names()

				raw_model = [varNames[i] for i, val in enumerate(varValues) if val > 1e-6]
				filtered_model = PPDSP_utils.convert_cplex_model(raw_model)

				log(f"[CPLEX] OPTIMAL OBJ: {opt}")
				log(f"[CPLEX] Runtime: {elapsed:.3f} sec")
				
				PPDSP_utils.printVehRoutes(self, filtered_model)
				PPDSP_utils.evaluateSolution(self, filtered_model)
				log("===== RAW XY MODEL =====")
				log(" ".join(str(v) for v in filtered_model))

				return filtered_model
			else:
				log("[CPLEX] No feasible solution.")
				log(f"[CPLEX] Runtime: {elapsed:.3f} sec")
				return None
