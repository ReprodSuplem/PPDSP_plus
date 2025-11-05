# ppdsp_reform_ins_gen.py

import os
import sys
import math
import subprocess
import pandas as pd

class PPDSP_reform:
	varID = 0
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
	nuVarList = []
	uVarList = []
	hVarList = []

	id2Var = None

	def __init__(self, tsplib, request, vehicle, connect):
		self.coordCSV = f'2DNode_{tsplib}.csv'
		self.reqstCSV = f'requestInfo{request}_{tsplib}.csv'
		self.vehiCSV = f'vehicleCap{vehicle}_{tsplib}.csv'
		self.adjMxCSV = f'adjMatrx{connect}_{tsplib}.csv'
		self.readCSV()

		self.xVarList = [[[0] * (1 + self.lenOfLocation)
						  for j in range(1 + self.lenOfLocation)]
						  for i in range(self.lenOfVehicle)]
		self.yVarList = [[0] * self.lenOfVehicle for i in range(self.lenOfRequest)]
		self.nuVarList = [[[0] * self.lenOfLocation # Size of the set {0, ..., |V|-2} = self.lenOfLocation
						  for j in range(self.lenOfLocation)]
						  for i in range(self.lenOfVehicle)]
		self.uVarList = [[0] * self.lenOfLocation for i in range(self.lenOfVehicle)]
		self.hVarList = [[0] * self.lenOfLocation for i in range(self.lenOfVehicle)]

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

	# Variable 'nu^t_{dp}'
	def genNuVarList(self):
		for i in range(len(self.nuVarList)):
			for j in range(len(self.nuVarList[i])):
				for k in range(len(self.nuVarList[i][j])):
					self.nuVarList[i][j][k] = self.newVarID()

	def printNuVarList(self):
		for i in range(len(self.nuVarList)):
			print('nu^{{{0}}}{1}'.format(i,'dp'))
			for j in range(len(self.nuVarList[i])):
				print(self.nuVarList[i][j])

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

	def getLastXVarID(self):
		return self.xVarList[self.lenOfVehicle-1][self.lenOfLocation][self.lenOfLocation]

	def getLastYVarID(self):
		return self.yVarList[self.lenOfRequest-1][self.lenOfVehicle-1]

	def buildVarIndexMap(self):
		self.id2Var = {}
		# xVar
		for i in range(len(self.xVarList)):
			for j in range(len(self.xVarList[i])):
				for k in range(len(self.xVarList[i][j])):
					vid = self.xVarList[i][j][k]
					if vid is None or vid == 0:
						continue
					self.id2Var[vid] = ('x', i, j, k)
		# yVar
		for i in range(len(self.yVarList)):
			for j in range(len(self.yVarList[i])):
				vid = self.yVarList[i][j]
				if vid is None or vid == 0:
					continue
				self.id2Var[vid] = ('y', i, j)

	def decodeVarID(self):
		if not hasattr(self, 'id2Var'):
			self.buildVarIndexMap()
		return self.id2Var.get(vid, None)


__all__ = ["PPDSP_reform"]
