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

	def solve(self, solver="uwr", verbose=1):
		import time
		import subprocess

		if solver.lower() != "uwr":
			raise ValueError("Only UWrMaxSAT is supported now. Please set solver='uwr'.")

		wcnf_file = self.insName + ".wcnf"
		lastY = self.getLastYVarID()
		meta_file = self.insName + ".meta"
		log_file  = wcnf_file + ".out"

		# Run uwrmaxsat with meta file
		cmd = [
			"uwrmaxsat",
			f"-ppdsp-lastY={lastY}",
			f"-ppdsp={meta_file}",
			wcnf_file
		]
		start_time = time.time()
		proc = subprocess.Popen(
			cmd,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			text=True
		)
		stdout, stderr = proc.communicate()
		elapsed = time.time() - start_time

		# Parse model
		model = []
		for line in stdout.splitlines():
			line = line.strip()
			print(line)
			if line.startswith("v "):
				for lit in line.split()[1:]: # Ignore 1st char 'v'
					if lit != "0":
						model.append(int(lit))

		if not model:
			print("[UWrMaxSAT] No solution.")
			print(f"[UWrMaxSAT] Runtime: {elapsed:.3f} sec")
			with open(log_file, "w") as f:
				f.write("[UWrMaxSAT] No solution.\n")
				f.write(f"[UWrMaxSAT] Runtime: {elapsed:.3f} sec\n")
			return None

		# Decode XY domain only
		filtered_model = PPDSP_utils.extractXYModel(self, model)

		PPDSP_utils.printVehRoutes(self, filtered_model)
		obj_val = PPDSP_utils.evaluateSolution(self, filtered_model)

		with open(log_file, "w") as f:
			def log(msg):
				print(msg)
				f.write(msg + "\n")

			log(f"[UWrMaxSAT] OBJ: {obj_val}")
			log(f"[UWrMaxSAT] Runtime: {elapsed:.3f} sec")

			log("===== RAW XY MODEL =====")
			log(" ".join(str(x) for x in filtered_model))

		return filtered_model

