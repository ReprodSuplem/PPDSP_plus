# ppdsp_reform_ins_arg.py

import sys
import tsplib95
import math
import random
import pandas as pd
import networkx as nx
import itertools
from typing import List, Tuple

def my_round_int(x: float) -> int:
    return int((x * 2 + 1) // 2)

def gnp_random_connected_graph(n: int, p: float, t: int, s: float) -> List[nx.Graph]:
	"""
	Generates a random undirected graph, similarly to an Erdős-Rényi 
	graph, but enforcing that the resulting graph is conneted
	- n: number of nodes
	- p: base probability of adding extra edges
	- t: number of graphs to generate
	- s: step increment for probability in subsequent graphs
	Returns a list of NetworkX graphs.
	"""
	GList = []
	for iter_idx in range(t):
		if iter_idx == 0:
			G = nx.Graph()
			G.add_nodes_from(range(n))
			# Connect at least one edge for each node to ensure connectivity
			edgesItr1 = itertools.combinations(random.sample(list(range(n)), n), 2)
			for _, node_edges in itertools.groupby(edgesItr1, key=lambda x: x[0]):
				random_edge = random.choice(list(node_edges))
				G.add_edge(*random_edge)
		else:
			G = GList[iter_idx-1].copy()

		edgesItr2 = itertools.combinations(range(n), 2)
		for e in edgesItr2:
			if iter_idx == 0 and (not G.has_edge(*e)) and random.random() > (1-p)/(1-2*(n-1)/(n**2-n)):
				G.add_edge(*e)
			if iter_idx != 0 and (not G.has_edge(*e)) and random.random() > (1-(p+iter_idx*s))/(1-(p+(iter_idx-1)*s)):
				G.add_edge(*e)
		GList.append(G.copy())
	return GList

def read_tsplib_coords(tspPath: str) -> Tuple[List[Tuple[float, float]], str]:
	"""
	Read TSPLIB file and return coordinates list (with depot at the end) and tsp name (without extension).
	"""
	problem = tsplib95.load(tspPath)
	nodes = sorted(problem.get_nodes())
	coords = []
	# Add all coordainates except depot to coords
	for i in range(1, len(nodes)):
		coords.append(problem.node_coords[1 + (i - 1)])
	# Add depot coordinate at the end of coords
	coords.append(problem.node_coords[1])
	tspName = tspPath.split('/')[-1].replace('.tsp', '')
	return coords, tspName
	
# Algorithm 1 in ICCS 2023 paper
def gen_repet_time_list(lenOfCoordExcluDepot: int, repetRate: float) -> List[int]:
	"""
	Generate a list indicating how many times each node (except depot) should appear in requests.
	- lenOfCoordExcluDepot: number of nodes excluding depot
	- repetRate: target average repetition rate
	Returns a list of length lenOfCoordExcluDepot with repetition counts.
	"""
	repeaTimeList = [1] * lenOfCoordExcluDepot
	target_total = my_round_int(lenOfCoordExcluDepot * repetRate)
	while sum(repeaTimeList) < target_total:
		idx = random.randrange(0, lenOfCoordExcluDepot)
		repeaTimeList[idx] += 1
	return repeaTimeList

# Algorithm 2 in ICCS 2023 paper
def gen_pair_list(lenOfCoordExcluDepot: int, repetRate: float) -> Tuple[List[int], List[List[int]]]:
	"""
	generate request (pickup/dropoff) pairs according to repetRate.
	"""
	repeaTimeList = gen_repet_time_list(lenOfCoordExcluDepot, repetRate)

	shuffList = []
	for i in range(lenOfCoordExcluDepot):
		shuffList += [i] * repeaTimeList[i]

	# randomly shuffle and pair up, avoiding same-node or duplicate pairs
	reshuffle = True
	pairList = []
	while reshuffle:
		random.shuffle(shuffList)
		pairList.clear()
		for i in range(int(len(shuffList)/2)):
			if shuffList[2*i] == shuffList[1+2*i] or [shuffList[2*i], shuffList[1+2*i]] in pairList:
				break
			else:
				pairList.append([shuffList[2*i], shuffList[1+2*i]])
				if i == int(len(shuffList)/2)-1:
					reshuffle = False
	return repeaTimeList, pairList

# Algorithm 3 in ICCS 2023 paper
def gen_sorted_pairList(lenOfCoordExcluDepot: int, repetRate: float) -> List[List[int]]:
	"""
	Sort the node pairs by the sum of the repeat times of each node in the node pair
	"""
	repeaTimeList, pairList = gen_pair_list(lenOfCoordExcluDepot, repetRate)

	headOfList = []
	tailOfList = []
	while len(pairList) > 0:
		### for the head of list
		i = 0
		while i < len(pairList):
			if repeaTimeList[pairList[i][0]] == 1 and repeaTimeList[pairList[i][1]] == 1:
				repeaTimeList[pairList[i][0]] -= 1
				repeaTimeList[pairList[i][1]] -= 1
				headOfList.insert(0, pairList.pop(i))
			elif repeaTimeList[pairList[i][0]] == 1 or repeaTimeList[pairList[i][1]] == 1:
				repeaTimeList[pairList[i][0]] -= 1
				repeaTimeList[pairList[i][1]] -= 1
				headOfList.append(pairList.pop(i))
			else:
				i += 1
		### for the tail of list
		maxIdx = -1
		tmpMax = 0
		for j in range(len(pairList)):
			if repeaTimeList[pairList[j][0]] + repeaTimeList[pairList[j][1]] > tmpMax:
				tmpMax = repeaTimeList[pairList[j][0]] + repeaTimeList[pairList[j][1]]
				maxIdx = j
		if maxIdx != -1:
			repeaTimeList[pairList[maxIdx][0]] -= 1
			repeaTimeList[pairList[maxIdx][1]] -= 1
			tailOfList.insert(0, pairList.pop(maxIdx))
	sortedPairList = headOfList + tailOfList
	return sortedPairList

# Algorithm 4 in ICCS 2023 paper
def gen_request_list(coords: List[Tuple[float, float]], repetRate: float, seed: int = None) -> List[List[int]]:
	"""
	- coords[i] = (x, y), coordsp[lenOfCoord-1] indicates depot
	- repetRate: average repetition rate for nodes (excluding depot)
	- seed: random seed for reproducibility
	Returns requestList with each item as [profit, size, pickup_idx, dropoff_idx].
	"""
	if seed is not None:
		random.seed(seed)

	sortedPairList = gen_sorted_pairList(len(coords) - 1, repetRate)

	lenOfCoord = len(coords)
	lenOfRequest = len(sortedPairList)

	# Calculate average distance between all pairs of nodes
	sumOfDistance = 0
	for i in range(lenOfCoord):
		for j in range(i+1, lenOfCoord):
			sumOfDistance += my_round_int(math.dist(coords[i], coords[j]))
	avgDistance = my_round_int(sumOfDistance / (lenOfCoord * (lenOfCoord-1) / 2))

	requestList = []
	avgVol = 5
	for i in range(lenOfRequest):
		lowerVol = 1
		upperVol = 2 * avgVol - lowerVol
		tmpRandVol = my_round_int(random.uniform(lowerVol, upperVol))
		profit = my_round_int(2 * avgDistance * tmpRandVol / avgVol)
		size = tmpRandVol
		pickup = sortedPairList[i][0]
		dropoff = sortedPairList[i][1]
		requestList.append([profit, size, pickup, dropoff])
	return requestList

def write_nodes_csv(coords: List[Tuple[float, float]], tspName: str, outDir: str = "."):
	df = pd.DataFrame(coords)
	df.to_csv(f'{outDir}/2DNode_{tspName}.csv', header=False, index=False)

def write_request_csvs(requestList: List[List[int]], tspName: str, cutLens: List[int], outDir: str = "."):
	"""
	A series of shortened requestList (cutLens: lengthes) will be generated by cutting down the full list.
	requestInfo<len>_<tsp>.csv
	"""
	for len in cutLens:
		df = pd.DataFrame(requestList[:len])
		df.to_csv(f'{outDir}/requestInfo{len}_{tspName}.csv', header=False, index=False)

def gen_adj_matrs(lenOfCoord: int, connectRatio: float, sizeOfGList: int, skip: float, tspName: str, outDir: str = "."):
	"""
	# Generate adjacency matrices corresponding to connected random graphs
	adjMatrx{int(10*(connectRatio+i*skip))}_{tspName}.csv
	"""
	GList = gnp_random_connected_graph(lenOfCoord, connectRatio, sizeOfGList, skip)
	#plt.figure(figsize=(8,5))
	#nx.draw(GList[0], node_color='lightblue', with_labels=True, node_size=500)
	#plt.show()
	for i, G in enumerate(GList): # 0:=no_edge, 1:=edge, and 2:=free_edge (cost=0)
		# Initialize with 0s, with 1s on the main diagonal.
		adjMatrix = [[0]*lenOfCoord for _ in range(lenOfCoord)]
		for r in range(lenOfCoord):
			adjMatrix[r][r] = 1
		#for i in range(lenOfCoord):
		#	adjMatrix[-1][i] = 2
		#	adjMatrix[i][-1] = 2
		for (u, v) in G.edges():
			adjMatrix[u][v] = 1
			adjMatrix[v][u] = 1
		coefficient = int(10 * (connectRatio + i * skip))
		df = pd.DataFrame(adjMatrix)
		df.to_csv(f'{outDir}/adjMatrx{coefficient}_{tspName}.csv', header=False, index=False)

def gen_vehic_caps(nOfVehicList: List[int], tspName: str, outDir: str = "."):
	avgCap = 20
	for num in nOfVehicList:
		vehicleList = []
		for i in range(num):
			capactCoeffi = [1, 0, -1]
			vehicleList.append([avgCap + 5 * capactCoeffi[i % 3], 1 + 0.2 * capactCoeffi[i % 3]])
		df = pd.DataFrame(vehicleList)
		df.to_csv(f'{outDir}/vehicleCap{num}_{tspName}.csv', header=False, index=False)

def gen_all_ins_arg(tspPath: str,
					repetRateList: List[float] = [3, 2.5, 2, 1.5, 1],
					nOfVehicList: List[int] = [2, 4, 6, 8, 10],
					connectRatio: float = 0.2,
					sizeOfGList: int = 1,
					skip: float = 0.1,
					outDir: str = ".",
					seed: int = None):
	"""
	Main function: Given a TSP file and several parameters, generate all related CSV files (nodes, requests, vehicles, and adjacency matrices).
	- repetRateList: a list repet rates used to split the request file
	- nOfVehicList: a list of the number of vehicles
	- connectRatio, sizeOfGList, skip: parameters controlling the generation of adjacency matrices
	"""
	if seed is not None:
		random.seed(seed)

	coords, tspName = read_tsplib_coords(tspPath)
	lenOfCoord = len(coords)
	write_nodes_csv(coords, tspName, outDir=outDir)

	# Use the first repeat rate to generate a complete request list (then save different cuts of it).
	requestList = gen_request_list(coords, repetRateList[0], seed=seed)
	write_request_csvs(requestList, tspName, [my_round_int((lenOfCoord-1) * r / 2) for r in repetRateList], outDir=outDir)

	gen_adj_matrs(len(coords), connectRatio, sizeOfGList, skip, tspName, outDir=outDir)

	gen_vehic_caps(nOfVehicList, tspName, outDir=outDir)

	#print("Generation Completed.", tspName)

# ------------------------------
if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("Usage: python instance_gen.py <tsp-file> [outDir]")
		sys.exit(1)
	tsp_file = sys.argv[1]
	outDir = sys.argv[2] if len(sys.argv) > 2 else "."
	gen_all_ins_arg(tsp_file, outDir=outDir, seed=42)
