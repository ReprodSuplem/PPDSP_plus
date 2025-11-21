# ppdsp_reform_p1_cplex.py

from ppdsp_reform_ins_gen import PPDSP_reform
from ppdsp_reform_utils import PPDSP_utils
import cplex
from cplex import SparsePair

class PPDSP_MIP(PPDSP_reform):
	def __init__(self, tsplib, request, vehicle, connect):
		super().__init__(tsplib, request, vehicle, connect)
		self.cpx = cplex.Cplex()
		self.cpx.objective.set_sense(self.cpx.objective.sense.maximize)
		self.insName = f"p1_{tsplib}_r{request}v{vehicle}c{connect}"

	def addXVars(self):
		for i in range(self.lenOfVehicle):
			for j in range(len(self.xVarList[i])):
				for k in range(len(self.xVarList[i][j])):
					self._addVar('x', self.xVarList[i][j][k], 0, 1, "B")

	def addYVars(self):
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				self._addVar('y', self.yVarList[i][j], 0, 1, "B")

	def addUVars(self):
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				self._addVar('u', self.uVarList[i][j], 0, self.lenOfLocation - 1, "I")

	def addHVars(self):
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				cap = int(self.vehicleList[i][0])
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
					if k == j:
						continue
					ind.append("x" + str(self.xVarList[i][j][k]))
					val.append(1.0)
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
		bigM = max(v[0] for v in self.vehicleList)
		for i in range(self.lenOfRequest):
			bigM += self.requestList[i][1]
		print(f"bigM @ Eq.10: {bigM}")

		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				for k in range(self.lenOfLocation):
					if k != j:
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
		self.mipObj()

	def writeLpFile(self):
		self.cpx.write(self.insName + ".lp", filetype="lp")

	def solve(self):
		import time
		start_time = time.time()

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
