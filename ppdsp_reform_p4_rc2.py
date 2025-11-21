# ppdsp_reform_p4_rc2.py

from ppdsp_reform_ins_gen import PPDSP_reform
from ppdsp_reform_utils import PPDSP_utils
from pysat.pb import *
from pysat.formula import *
from pysat.card import CardEnc

class PPDSP_MaxSAT_p4(PPDSP_reform):
	def __init__(self, tsplib, request, vehicle, connect):
		super().__init__(tsplib, request, vehicle, connect)
		self.wcnf = WCNF()
		self.cnf = CNF()
		self.vpool = None
		self.hVarLits = [[[] for j in range(self.lenOfLocation)] for i in range(self.lenOfVehicle)]
		self.insName = f"p4_{tsplib}_r{request}v{vehicle}c{connect}"

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

		print(f"[rc2] Generating instance: {self.insName}.wcnf ...")
		self.wcnf.extend(self.cnf)
		self.wcnf.to_file(self.insName + ".wcnf")
		PPDSP_utils.export_meta(self, self.insName + ".meta")

	def solve(self, verbose=1):
		wcnf_file = self.insName + ".wcnf"
		lastY = self.getLastYVarID()
		meta_file = self.insName + ".meta"
		log_file  = wcnf_file + ".out"

		# Run uwrmaxsat with meta file
		cmd = f"stdbuf -oL uwrmaxsat -ppdsp-lastY={lastY} -ppdsp={meta_file} {wcnf_file} | tee {log_file}"
		print(f"[UWrMaxSAT] Running command:\n  {cmd}")
		os.system(cmd)

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

