# ppdsp_reform_ins_gen.py

import os
import sys
import math
import subprocess
import pandas as pd
from pysat.formula import IDPool

class PPDSP_reform:
	def __init__(self, tsplib, request, vehicle, knn, increment=None):
		self.registry = increment
		self.varID = 0

		self.adjMatrx = []
		self.coordinates = []
		self.locaList = []
		self.requestList = []
		self.vehicleList = []
		self.lenOfCoord = 0
		self.lenOfLocation = 0
		self.lenOfRequest = 0
		self.lenOfVehicle = 0
		self.id2Var = None

		self.coordCSV = f'2DNode_{tsplib}.csv'
		self.reqstCSV = f'requestInfo{request}_{tsplib}.csv'
		self.vehiCSV = f'vehicleCap{vehicle}_{tsplib}.csv'
		self.adjMxCSV = f'adjMatrx{knn}_{tsplib}.csv'
		self.readCSV()

		self.xVarList = [[[0] * (1 + self.lenOfLocation)
						  for j in range(1 + self.lenOfLocation)]
						  for i in range(self.lenOfVehicle)]
		self.yVarList = [[0] * self.lenOfVehicle for i in range(self.lenOfRequest)]
		self.nuVarList = [[[0] * self.lenOfLocation # Size of the set {0, ..., |V|-2} = self.lenOfLocation
						  for j in range(self.lenOfLocation)]
						  for i in range(self.lenOfVehicle)]
		self.uVarList = [[0] * self.lenOfLocation for i in range(self.lenOfVehicle)]
		self.hVarList = [[0] * (1 + self.lenOfLocation) for i in range(self.lenOfVehicle)]

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
				elif self.adjMatrx[i][j] == 2: # free
					tmpList.append(0)
				elif self.adjMatrx[i][j] == 1: # edge
					tmpList.append(
						self.my_round_int(
							math.dist((self.coordinates[i][0], self.coordinates[i][1]),
									  (self.coordinates[j][0], self.coordinates[j][1]))))
			self.locaList.append(tmpList)
		
		self.floyd(self.locaList)
		self.lenOfLocation = len(self.locaList) - 1

		self.requestList = pd.read_csv(self.reqstCSV, header=None).values.tolist()
		self.lenOfRequest = len(self.requestList)
		self.vehicleList = pd.read_csv(self.vehiCSV, header=None).values.tolist()
		self.lenOfVehicle = len(self.vehicleList)

	def my_round_int(self, x):
		return int((x * 2 + 1) // 2)

	def floyd(self, tmpMatrix):
		for i in range(len(tmpMatrix)):
			for j in range(len(tmpMatrix)):
				for k in range(len(tmpMatrix)):
					tmpMatrix[j][k] = min(tmpMatrix[j][k], tmpMatrix[j][i] + tmpMatrix[i][k])

	def newVarID(self, var_type=None, *args):
		if self.registry is not None:
			if var_type is not None:
				return self.registry.get_id(var_type, *args)
			else:
				if self.vpool is None:
					self.vpool = IDPool(start_from=self.get_vpool_start_id())
				return self.vpool.id()
		else:
			self.varID += 1
			return self.varID

	# Variable 'x^t_{od}'
	def genXVarList(self):
		for i in range(len(self.xVarList)):
			for j in range(len(self.xVarList[i])):
				for k in range(len(self.xVarList[i][j])):
					self.xVarList[i][j][k] = self.newVarID('x', i, j, k)

	def printXVarList(self):
		for i in range(len(self.xVarList)):
			print('x^{{{0}}}{1}'.format(i,'od'))
			for j in range(len(self.xVarList[i])):
				print(self.xVarList[i][j])

	# Variable 'y^t_r'
	def genYVarList(self):
		for i in range(len(self.yVarList)):
			for j in range(len(self.yVarList[i])):
				self.yVarList[i][j] = self.newVarID('y', i, j)

	def printYVarList(self):
		print('y^t_r')
		for i in range(len(self.yVarList)):
			print(self.yVarList[i])

	# Variable 'nu^t_{dp}'
	def genNuVarList(self):
		for i in range(len(self.nuVarList)):
			for j in range(len(self.nuVarList[i])):
				for k in range(len(self.nuVarList[i][j])):
					self.nuVarList[i][j][k] = self.newVarID('nu', i, j, k)

	def printNuVarList(self):
		for i in range(len(self.nuVarList)):
			print('nu^{{{0}}}{1}'.format(i,'dp'))
			for j in range(len(self.nuVarList[i])):
				print(self.nuVarList[i][j])

	# Variable 'u^t_v'
	def genUVarList(self):
		for i in range(len(self.uVarList)):
			for j in range(len(self.uVarList[i])):
				self.uVarList[i][j] = self.newVarID('u', i, j)

	def printUVarList(self):
		for i in range(len(self.uVarList)):
			print('u^{{{0}}}{1}'.format(i,'v'))
			print(self.uVarList[i])

	# Variable 'h^t_v'
	def genHVarList(self):
		for i in range(len(self.hVarList)):
			for j in range(len(self.hVarList[i])):
				self.hVarList[i][j] = self.newVarID('h', i, j)

	def printHVarList(self):
		for i in range(len(self.hVarList)):
			print('h^{{{0}}}{1}'.format(i,'v'))
			print(self.hVarList[i])

	def getLastXVarID(self):
		return self.xVarList[-1][-1][-1]

	def getLastYVarID(self):
		if self.registry is not None: # incremental mode
			y_ids = [vid for key, vid in self.registry.varDict.items() if key[0] == 'y']
			return max(y_ids) if y_ids else 0
		else:
			return self.yVarList[-1][-1]

	def getLastNuVarID(self):
		return self.nuVarList[-1][-1][-1]

	def get_vpool_start_id(self):
		if self.registry is not None: # incremental mode
			return self.registry.get_max_core_id() + 1
		else:
			return self.varID + 1

__all__ = ["PPDSP_reform"]
