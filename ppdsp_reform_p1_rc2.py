# ppdsp_reform_p1_rc2.py

from ppdsp_reform_ins_gen import PPDSP_reform
from pysat.pb import *
from pysat.formula import *
from pysat.card import CardEnc

class PPDSP_MaxSAT(PPDSP_reform):
	def __init__(self, tsplib, request, vehicle, connect):
		super().__init__(tsplib, request, vehicle, connect)
		self.wcnf = WCNF()
		self.cnf = CNF()
		self.vpool = None
		self.uVarLits = [[[] for j in range(self.lenOfLocation)] for i in range(self.lenOfVehicle)]
		self.hVarLits = [[[] for j in range(self.lenOfLocation)] for i in range(self.lenOfVehicle)]
		self.insName = f"p1_{tsplib}_r{request}v{vehicle}c{connect}"

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

	def resetVarIDforMaxSAT(self):
		self.varID = self.uVarList[0][0] - 1 # Reset to varID to 1st variable 'u^t_v'

	def genHardClauseForEq11(self): # Literals allocation for Eq.11
		self.resetVarIDforMaxSAT()
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				for k in range(int(self.vehicleList[i][0])):
					self.hVarLits[i][j].append(self.newVarID())

	def printHVarLits(self):
		for i in range(len(self.hVarLits)):
			for j in range(len(self.hVarLits[i])):
				print('h^{{{0}}}{1}_[{2}]'.format(i,'v', self.hVarList[i][j]))
				print(self.hVarLits[i][j])

	def genHardClauseForEq12(self): # Literals allocation for Eq.12
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				for k in range(self.lenOfLocation-1):
					self.uVarLits[i][j].append(self.newVarID())

	def printUVarLits(self):
		for i in range(len(self.uVarLits)):
			for j in range(len(self.uVarLits[i])):
				print('u^{{{0}}}{1}_[{2}]'.format(i,'v', self.uVarList[i][j]))
				print(self.uVarLits[i][j])

	# MTZ-SEC
	def genHardClauseForEq8(self):
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				for k in range(self.lenOfLocation):
					if k != j:
						litList = self.uVarLits[i][k] + [-1 * l for l in self.uVarLits[i][j]]

						#print("現在最大変数ID:", self.vpool.top) # Show current max varID in vpool

						cnf_obj = CardEnc.atleast(lits = litList, bound = 1 + len(self.uVarLits[i][j]), vpool = self.vpool, encoding = 6)
						for clause in cnf_obj.clauses:
							self.cnf.append([-self.xVarList[i][j][k]] + clause, update_vpool=True)

	def genHardClauseForEq9(self):
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				litList = self.uVarLits[j][self.requestList[i][2]] + [-1 * l for l in self.uVarLits[j][self.requestList[i][3]]]

				#print("Current max varID:", self.vpool.top) # Show current max varID in vpool

				cnf_obj = CardEnc.atmost(lits = litList, bound = len(self.uVarLits[j][self.requestList[i][3]]) - 1, vpool = self.vpool, encoding = 6)
				for clause in cnf_obj.clauses:
					self.cnf.append([-self.yVarList[i][j]] + clause, update_vpool=True)

	def genHardClauseForEq10(self):
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation): # j is 'o'
				for k in range(self.lenOfLocation): # k is 'd'
					if k != j:
						litList = []
						weightList = []
						equalBound = 0
						for l in range(self.lenOfRequest):
							if self.requestList[l][2] == k:
								litList.append(self.yVarList[l][i])
								weightList.append(self.requestList[l][1])
							elif self.requestList[l][3] == k:
								litList.append(-self.yVarList[l][i])
								weightList.append(self.requestList[l][1])
								equalBound += self.requestList[l][1]

						tmpListO = [1 for l in range(len(self.hVarLits[i][j]))]
						tmpListD = [1 for l in range(len(self.hVarLits[i][k]))]
						equalBound += len(self.hVarLits[i][k])
						litList += self.hVarLits[i][j] + [-1 * l for l in self.hVarLits[i][k]]
						weightList += tmpListO + tmpListD

						#print("当前最大变量ID:", self.vpool.top) # Show current max varID in vpool

						cnf_obj = PBEnc.equals(lits = litList, weights = weightList, bound = equalBound, vpool = self.vpool, encoding = EncType.best)
						for clause in cnf_obj.clauses:
							self.cnf.append([-self.xVarList[i][j][k]] + clause, update_vpool=True)
		#print(self.cnf.clauses)

	def genMaxsatFormular(self):
		self.genXVarList()
		self.genYVarList()
		self.genUVarList()
		self.genHVarList()

		self.genSoftClause()
		self.genHardClauseForEq3()
		self.genHardClauseForEq4()
		self.genHardClauseForEq5()
		self.genHardClauseForEq6()
		self.genHardClauseForEq7()
		self.genHardClauseForEq11()
		#self.printHVarLits()
		self.genHardClauseForEq12()
		#self.printUVarLits()
		self.vpool = IDPool(start_from = 1 + self.varID) # Setup vpool starting from varID+1 before running Eq8-10
		self.genHardClauseForEq8()
		self.genHardClauseForEq9()
		self.genHardClauseForEq10()

		print(f"rc2: Generating instance: {self.insName}.wcnf ...")
		self.wcnf.extend(self.cnf)
		self.wcnf.to_file(self.insName + ".wcnf")

	def solve(self, solver="rc2", use_stratified=False, verbose=1):
		import os
		from pysat.examples.rc2 import RC2, RC2Stratified

		if solver.lower() == "uwr":
			print(f"Solving using UWrMaxSat ...")
			ret = os.system(f"uwrmaxsat {self.insName}.wcnf > {self.insName}.out")
			if ret != 0:
				print(f"UWrMaxSat failed, exit: {ret}")
				return None
		else:
			solver_cls = RC2Stratified if use_stratified else RC2
			print(f"Solving using {'RC2Stratified' if use_stratified else 'RC2'} ...")
			with solver_cls(self.wcnf, incr=True, verbose=verbose) as rc2:
				model = rc2.compute()
				if model is None:
					print("Result: UNSAT")
					print(f"c oracle time: {rc2.oracle_time():.4f}")
					return None

				filtered_model = [i for i in model if i > 0 and i <= self.getLastYVarID()]

				print(f"Result: SAT, cost = {rc2.cost}")
				print(f"c oracle time: {rc2.oracle_time():.4f}")
				print(f"Model: {filtered_model}")

				return filtered_model



