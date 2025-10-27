import os
import sys
import math
import subprocess
import pandas as pd

from pysat.pb import *
from pysat.formula import *
from pysat.card import CardEnc
from pysat.examples.rc2 import RC2 # Try to switch between RC2 and RC2Stratified

from z3 import *

#
#================================================
class ReForm:
	mip = ''
	varID = 0
	constrID = 0
	adjMxCSV = ''
	coordCSV = ''
	reqstCSV = ''
	vehiCSV = ''

	adjMatrx = []
	coordinates = []
	lenOfCoord = 0
	locaList = []
	lenOfLocation = 0
	requestList = []
	lenOfRequest = 0
	vehicleList = []
	lenOfVehicle = 0

	xVarList = []
	yVarList = []
	uVarList = []
	hVarList = []

	smt2Opt = None
	smt2x = []
	smt2y = []
	smt2u = []
	smt2h = []
	optimal = 0

	wcnf = None
	cnf = None
	vpool = None
	uVarLits = []
	hVarLits = []

	def __init__(self):
		self.mip = ''
		constrID = 0
		self.coordCSV = '2DNode_' + sys.argv[1] + '.csv'
		self.reqstCSV = 'requestInfo' + sys.argv[2] + '_' + sys.argv[1] + '.csv'
		self.vehiCSV = 'vehicleCap' + sys.argv[3] + '_' + sys.argv[1] + '.csv'
		self.adjMxCSV = 'adjMatrx' + sys.argv[4] + '_' + sys.argv[1] + '.csv'
		self.readCSV()

		self.xVarList = [[[0]*(1+self.lenOfLocation) for j in range(1+self.lenOfLocation)] for i in range(self.lenOfVehicle)]
		self.yVarList = [[0]*self.lenOfVehicle for i in range(self.lenOfRequest)]
		self.uVarList = [[0]*self.lenOfLocation for i in range(self.lenOfVehicle)]
		self.hVarList = [[0]*self.lenOfLocation for i in range(self.lenOfVehicle)]

		self.wcnf = WCNF()
		self.cnf = CNF()
		#self.vpool = IDPool(start_from = 1)
		self.uVarLits = [[[] for j in range(self.lenOfLocation)] for i in range(self.lenOfVehicle)]
		self.hVarLits = [[[] for j in range(self.lenOfLocation)] for i in range(self.lenOfVehicle)]

	def readCSV(self):
		# adjacency matrix
		self.adjMatrx = pd.read_csv(self.adjMxCSV, header=None).values.tolist()

		# <x, y> of location
		self.coordinates = pd.read_csv(self.coordCSV, header=None).values.tolist()
		#print(self.coordinates)
		self.lenOfCoord = len(self.coordinates)

		for i in range(self.lenOfCoord):
			tmpList = []
			for j in range(self.lenOfCoord):
				if self.adjMatrx[i][j] == 0: # block
					tmpList.append(999999)
				if self.adjMatrx[i][j] == 2: # free
					tmpList.append(0)
				if self.adjMatrx[i][j] == 1: # edge
					tmpList.append(self.my_round_int(math.dist( (self.coordinates[i][0], self.coordinates[i][1]), (self.coordinates[j][0], self.coordinates[j][1]) )))
			#print(tmpList)
			self.locaList.append(tmpList)
		self.floyd(self.locaList)
		#print(self.locaList)
		self.lenOfLocation = len(self.locaList)-1
		#print(self.lenOfLocation)

		# <profit, size, origin, destination> of request
		self.requestList = pd.read_csv(self.reqstCSV, header=None).values.tolist()
		#print(self.requestList)
		self.lenOfRequest = len(self.requestList)

		# <capacity, cost_coefficient> of vehicle
		self.vehicleList = pd.read_csv(self.vehiCSV, header=None).values.tolist()
		#print(self.vehicleList)
		self.lenOfVehicle = len(self.vehicleList)

	def my_round_int(self, x):
		return int((x * 2 + 1) // 2)

	def floyd(self, tmpMatrix):
		for i in range(len(tmpMatrix)):
			for j in range(len(tmpMatrix)):
				for k in range(len(tmpMatrix)):
					tmpMatrix[j][k] = min(tmpMatrix[j][k], tmpMatrix[j][i] + tmpMatrix[i][k])

	def newVarID(self):
		self.varID += 1
		return self.varID

	# Variable 'x^t_{od}'
	def genXVarList(self):
		for i in range(len(self.xVarList)):
			for j in range(len(self.xVarList[i])):
				for k in range(len(self.xVarList[i][j])):
					self.xVarList[i][j][k] = self.newVarID()

	def printXVarList(self):
		for i in range(len(self.xVarList)):
			print('x^{{{0}}}{1}'.format(i,'od'))
			for j in range(len(self.xVarList[i])):
				print(self.xVarList[i][j])

	# Variable 'y^t_r'
	def genYVarList(self):
		for i in range(len(self.yVarList)):
			for j in range(len(self.yVarList[i])):
				self.yVarList[i][j] = self.newVarID()

	def printYVarList(self):
		print('y^t_r')
		for i in range(len(self.yVarList)):
			print(self.yVarList[i])

	# Variable 'u^t_v'
	def genUVarList(self):
		for i in range(len(self.uVarList)):
			for j in range(len(self.uVarList[i])):
				self.uVarList[i][j] = self.newVarID()

	def printUVarList(self):
		for i in range(len(self.uVarList)):
			print('u^{{{0}}}{1}'.format(i,'v'))
			print(self.uVarList[i])

	# Variable 'h^t_v'
	def genHVarList(self):
		for i in range(len(self.hVarList)):
			for j in range(len(self.hVarList[i])):
				self.hVarList[i][j] = self.newVarID()

	def printHVarList(self):
		for i in range(len(self.hVarList)):
			print('h^{{{0}}}{1}'.format(i,'v'))
			print(self.hVarList[i])

	def newConstrID(self):
		self.constrID += 1
		return self.constrID

	def getLastXVarID(self):
		return self.xVarList[self.lenOfVehicle-1][self.lenOfLocation][self.lenOfLocation]

	def getLastYVarID(self):
		return self.yVarList[self.lenOfRequest-1][self.lenOfVehicle-1]

	def genMipObjFunc(self):
		isFirst = True
		self.mip += 'Maximize z\n\nSubject to\n'
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				if isFirst:
					self.mip += str(self.requestList[i][0]) + ' y' + str(self.yVarList[i][j])
					isFirst = False
				else:
					self.mip += ' + ' + str(self.requestList[i][0]) + ' y' + str(self.yVarList[i][j])
		for i in range(self.lenOfVehicle):
			for j in range(1+self.lenOfLocation):
				for k in range(1+self.lenOfLocation):
					#if k != j:
					self.mip += ' - ' + str(self.my_round_int(self.vehicleList[i][1]*self.locaList[j][k])) + ' x' + str(self.xVarList[i][j][k])
		self.mip += ' - z = 0\n'

	def genMipForEq3(self):
		for i in range(self.lenOfRequest):
			isFirst = True
			for j in range(self.lenOfVehicle):
				if isFirst:
					self.mip += 'c' + str(self.newConstrID()) + ': y' + str(self.yVarList[i][j])
					isFirst = False
				else:
					self.mip += ' + y' + str(self.yVarList[i][j])
			self.mip  += ' <= 1\n'

	def genMipForEq4(self):
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				isFirst = True
				for k in range(1+self.lenOfLocation):
					if k != self.requestList[i][2] and k != self.requestList[i][3]:
						if isFirst:
							self.mip += 'c' + str(self.newConstrID()) + ': x' + str(self.xVarList[j][k][self.requestList[i][2]])
							isFirst = False
						else:
							self.mip += ' + x' + str(self.xVarList[j][k][self.requestList[i][2]])
				self.mip += ' - y' + str(self.yVarList[i][j]) + ' >= 0\n'

	def genMipForEq5(self):
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				isFirst = True
				for k in range(self.lenOfLocation):
					if k != self.requestList[i][3]:
						if isFirst:
							self.mip += 'c' + str(self.newConstrID()) + ': x' + str(self.xVarList[j][k][self.requestList[i][3]])
							isFirst = False
						else:
							self.mip += ' + x' + str(self.xVarList[j][k][self.requestList[i][3]])
				self.mip += ' - y' + str(self.yVarList[i][j]) + ' >= 0\n'

	def genMipForEq6(self):
		for i in range(self.lenOfVehicle):
			for j in range(1+self.lenOfLocation):
				isFirst = True
				for k in range(1+self.lenOfLocation):
					if isFirst:
						self.mip += 'c' + str(self.newConstrID()) + ': x' + str(self.xVarList[i][j][k]) + ' - x' + str(self.xVarList[i][k][j])
						isFirst = False
					else:
						self.mip += ' + x' + str(self.xVarList[i][j][k]) + ' - x' + str(self.xVarList[i][k][j])
				self.mip += ' = 0\n'

	def genMipForEq7(self):
		for i in range(self.lenOfVehicle):
			for j in range(1+self.lenOfLocation):
				isFirst = True
				for k in range(1+self.lenOfLocation):
					if k != j:
						if isFirst:
							self.mip += 'c' + str(self.newConstrID()) + ': x' + str(self.xVarList[i][j][k])
							isFirst = False
						else:
							self.mip += ' + x' + str(self.xVarList[i][j][k])
				self.mip += ' <= 1\n'

	# MTZ-SEC
	def genMipForEq8(self):
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				for k in range(self.lenOfLocation):
					if k != j:
						self.mip += 'c' + str(self.newConstrID()) + ': u' + str(self.uVarList[i][j]) + ' - u' + str(self.uVarList[i][k]) + ' + ' + str(self.lenOfLocation) + ' x' + str(self.xVarList[i][j][k]) + ' <= ' + str(self.lenOfLocation-1) + '\n'

	def genMipForEq9(self):
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				self.mip += 'c' + str(self.newConstrID()) + ': u' + str(self.uVarList[j][self.requestList[i][2]]) + ' - u' + str(self.uVarList[j][self.requestList[i][3]]) + ' + ' + str(self.lenOfLocation) + ' y' + str(self.yVarList[i][j]) + ' < ' + str(self.lenOfLocation) + '\n'

	def genMipForEq10(self):
		bigMInEq10 = 0
		for i in range(self.lenOfVehicle):
			if self.vehicleList[i][0] > bigMInEq10:
				bigMInEq10 = self.vehicleList[i][0]
		for i in range(self.lenOfRequest):
			bigMInEq10 += self.requestList[i][1]
		print('bigM @ Eq.10: {0}'.format(bigMInEq10))
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation): # j is 'o'
				for k in range(self.lenOfLocation): # k is 'd'
					if k != j:
						Gamma = ''
						for l in range(self.lenOfRequest):
							if self.requestList[l][2] == k:
								Gamma += ' + ' + str(self.requestList[l][1]) + ' y' + str(self.yVarList[l][i])
							elif self.requestList[l][3] == k:
								Gamma += ' - ' + str(self.requestList[l][1]) + ' y' + str(self.yVarList[l][i])
						# for the leftside of Eq.10
						self.mip += 'c' + str(self.newConstrID()) + ': h' + str(self.hVarList[i][j]) + ' - h' + str(self.hVarList[i][k]) + ' + ' + str(bigMInEq10) + ' x' + str(self.xVarList[i][j][k]) + Gamma + ' <= ' + str(int(bigMInEq10)) + '\n'
						# for the rightside of Eq.10
						self.mip += 'c' + str(self.newConstrID()) + ': h' + str(self.hVarList[i][j]) + ' - h' + str(self.hVarList[i][k]) + ' - ' + str(bigMInEq10) + ' x' + str(self.xVarList[i][j][k]) + Gamma + ' >= ' + str(-1*int(bigMInEq10)) + '\n'

	def genMipForEq11(self):
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				self.mip += 'h' + str(self.hVarList[i][j]) + ' <= ' + str(int(self.vehicleList[i][0])) + '\n'

	def genMipForEq12(self):
		for i in range(self.lenOfVehicle):
			for j in range(self.lenOfLocation):
				self.mip += 'u' + str(self.uVarList[i][j]) + ' <= ' + str(self.lenOfLocation-1) + '\n'

	def declareBounds(self):
		self.mip += '\nBounds\n'
		self.genMipForEq11()
		self.genMipForEq12()

	def declareBooleanVar(self): # Eq.2
		self.mip += '\nBinary\n'
		for i in range(1, self.yVarList[0][0]):
			self.mip += 'x' + str(i) + '\n'
		for i in range(self.yVarList[0][0], self.uVarList[0][0]):
			self.mip += 'y' + str(i) + '\n'

	def declareIntVar(self):
		self.mip += '\nGeneral\n'
		for i in range(self.uVarList[0][0], self.hVarList[0][0]):
			self.mip += 'u' + str(i) + '\n'
		for i in range(self.hVarList[0][0], 1+self.varID):
			self.mip += 'h' + str(i) + '\n'
		self.mip += 'z\n'

	def genTailOfIPFile(self):
		self.mip += 'End'

	def writeMipFile(self, mipFileName):
		lpFile = open(mipFileName+'.lp', 'w')
		lpFile.write(self.mip)
		lpFile.close()

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	def initializeSmt2Opt(self):
		self.optimal = 0
		self.smt2Opt = Optimize()

		self.smt2x = [[[Bool(f"x{self.xVarList[i][j][k]}") for k in range(len(self.xVarList[i][j]))] for j in range(len(self.xVarList[i]))] for i in range(len(self.xVarList))]

		self.smt2y = [[Bool(f"y{self.yVarList[i][j]}") for j in range(len(self.yVarList[i]))] for i in range(len(self.yVarList))]

		self.smt2u = [[Int(f"u{self.uVarList[i][j]}") for j in range(len(self.uVarList[i]))] for i in range(len(self.uVarList))]
		
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

	def solveByZ3(self):
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

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

						print("現在最大変数ID:", self.vpool.top) # Show current max varID in vpool

						cnf_obj = CardEnc.atleast(lits = litList, bound = 1 + len(self.uVarLits[i][j]), vpool = self.vpool, encoding = 6)
						for clause in cnf_obj.clauses:
							self.cnf.append([-self.xVarList[i][j][k]] + clause, update_vpool=True)

	def genHardClauseForEq9(self):
		for i in range(self.lenOfRequest):
			for j in range(self.lenOfVehicle):
				litList = self.uVarLits[j][self.requestList[i][2]] + [-1 * l for l in self.uVarLits[j][self.requestList[i][3]]]

				print("Current max varID:", self.vpool.top) # Show current max varID in vpool

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

						print("当前最大变量ID:", self.vpool.top) # Show current max varID in vpool

						cnf_obj = PBEnc.equals(lits = litList, weights = weightList, bound = equalBound, vpool = self.vpool, encoding = EncType.best)
						for clause in cnf_obj.clauses:
							self.cnf.append([-self.xVarList[i][j][k]] + clause, update_vpool=True)
		#print(self.cnf.clauses)

	def solveByRC2(self, rc2):
		model = rc2.compute()
		model = [i for i in model if i > 0 and i <= self.getLastYVarID()]
		#print(model, self.getLastYVarID())
		return model
		
#================================================
#

#===========================
if __name__ == '__main__':
	insName = 'p1_' + sys.argv[1] + '_r' + sys.argv[2] + 'v' + sys.argv[3] + 'c' + sys.argv[4]

	reform = ReForm()
	reform.genXVarList()
	reform.printXVarList()
	reform.genYVarList()
	reform.printYVarList()
	reform.genUVarList()
	reform.printUVarList()
	reform.genHVarList()
	reform.printHVarList()

	reform.genMipObjFunc()
	reform.genMipForEq3()
	reform.genMipForEq4()
	reform.genMipForEq5()
	reform.genMipForEq6()
	reform.genMipForEq7()
	reform.genMipForEq8()
	reform.genMipForEq9()
	reform.genMipForEq10()
	
	reform.declareBounds()
	reform.declareBooleanVar()
	reform.declareIntVar()
	reform.genTailOfIPFile()
	reform.writeMipFile(insName)

	# SMT solving ->
	reform.initializeSmt2Opt()
	reform.smt2Obj()
	reform.smt2Eq3()
	myMode = 3 # Try to switch between mode 1 (arithmetic), 2 (implication), or 3 (CNF)
	reform.smt2Eq4(mode=myMode)
	reform.smt2Eq5(mode=myMode)
	reform.smt2Eq6()
	reform.smt2Eq7()
	#reform.smt2Eq8(mode=2) # Try to switch between mode 2 (implication), or 3 (CNF)
	#reform.smt2Eq9(mode=2) # Try to switch between mode 2 (implication), or 3 (CNF)
	reform.smt2Eq10()
	reform.smt2Eq11()
	#reform.smt2Eq12()
	#reform.solveByZ3()

	# MaxSAT encoding ->
	'''
	reform.genSoftClause()
	reform.genHardClauseForEq3()
	reform.genHardClauseForEq4()
	reform.genHardClauseForEq5()
	reform.genHardClauseForEq6()
	reform.genHardClauseForEq7()
	reform.genHardClauseForEq11()
	reform.printHVarLits()
	reform.genHardClauseForEq12()
	reform.printUVarLits()
	reform.vpool = IDPool(start_from = 1 + reform.varID) # Setup vpool starting from varID+1 before running Eq8-10
	reform.genHardClauseForEq8()
	reform.genHardClauseForEq9()
	reform.genHardClauseForEq10()
	reform.wcnf.extend(reform.cnf)
	reform.wcnf.to_file(insName + '.wcnf')

	#os.system(f"uwrmaxsat {insName}.wcnf >> {insName}.out")
	'''

''' Try to switch between RC2 and RC2Stratified
with RC2(reform.wcnf, incr=True, verbose=2) as rc2:
	model = reform.solveByRC2(rc2)
	if model != None:
		print('cost: {}'.format(rc2.cost))
		print('model: {}'.format(model))
		print('c oracle time: {0:.4f}'.format(rc2.oracle_time()))
	else:
		print('UNSAT')
		print('c oracle time: {0:.4f}'.format(rc2.oracle_time()))
'''









