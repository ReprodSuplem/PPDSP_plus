# ppdsp_reform_p1_z3.py

from ppdsp_reform_ins_gen import PPDSP_reform
from z3 import *

class PPDSP_SMT2(PPDSP_reform):
	def __init__(self, tsplib, request, vehicle, connect):
		super().__init__(tsplib, request, vehicle, connect)
		self.smt2Opt = Optimize()
		self.optimal = 0
		self.insName = f"p1_{tsplib}_r{request}v{vehicle}c{connect}"

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
		self.optimal = self.smt2Opt.maximize(Sum(profit) - Sum(cost))
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
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation): # j is 'o'
				for k in range(self.lenOfLocation): # k is 'd'
					if k == j:
						continue
					Gamma = 0
					for l in range(self.lenOfRequest):
						if self.requestList[l][2] == k:
							Gamma += self.requestList[l][1]
						elif self.requestList[l][3] == k:
							Gamma -= self.requestList[l][1]
					self.smt2Opt.add(Implies(self.smt2x[i][j][k], self.smt2h[i][k] == self.smt2h[i][j] + Gamma))

	def smt2Eq11(self):
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				self.smt2Opt.add(self.smt2h[i][j] <= int(self.vehicleList[i][0]))

	def smt2Eq12(self):
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				self.smt2Opt.add(self.smt2u[i][j] <= self.lenOfLocation - 1)
				self.smt2Opt.add(self.smt2u[i][j] >= 0)

	def genSmt2Formular(self):
		print("z3: adding varibles ...")
		self.genXVarList()
		self.genYVarList()
		self.genUVarList()
		self.genHVarList()
		self.addXVars()
		self.addYVars()
		self.addUVars()
		self.addHVars()

		print("z3: adding constraints ...")
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

	def solve(self):
		print(f"z3: solving instance: {self.insName} ...")
		if self.smt2Opt.check() == sat:
			model = self.smt2Opt.model()
			xModel = []
			for i in range(self.lenOfVehicle):
				for j in range(1 + self.lenOfLocation):
					for k in range(1 + self.lenOfLocation):
						val = model.evaluate(self.smt2x[i][j][k], model_completion=True)
						if is_true(val):
							xModel.append(f"x{self.xVarList[i][j][k]}")
			print("xVar:", " ".join(xModel))
			yModel = []
			for i in range(self.lenOfRequest):
				for j in range(self.lenOfVehicle):
					val = model.evaluate(self.smt2y[i][j], model_completion=True)
					if is_true(val):
						yModel.append(f"y{self.yVarList[i][j]}")
			print("yVar:", " ".join(yModel))
			print("max value =", self.smt2Opt.lower(self.optimal))
		else:
			print("UNSAT")


