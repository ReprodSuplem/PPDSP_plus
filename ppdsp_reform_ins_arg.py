# ppdsp_reform_ins_arg.py

import sys
import tsplib95
import math
import random
import pandas as pd
import networkx as nx
from typing import List, Tuple

def my_round_int(x: float) -> int:
    return int((x * 2 + 1) // 2)

def read_tsplib_coords(tspPath: str) -> Tuple[List[Tuple[float, float]], str]:
	"""
	Read TSPLIB file and return coordinates list (with depot at the end) and tsp name (without extension).
	"""
	problem = tsplib95.load(tspPath)
	nodes = sorted(problem.get_nodes())
	coords = []
	# Add all coordainates to coords (depot = the last pair of coordinates)
	for i in range(1, 1+len(nodes)):
		coords.append([100 * j for j in problem.node_coords[i]])
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
		size = my_round_int(random.uniform(lowerVol, upperVol))

		pickup = sortedPairList[i][0]
		dropoff = sortedPairList[i][1]

		pd_dist = math.dist(coords[pickup], coords[dropoff])
		base_reward = avgDistance * 0.5
		raw_profit = (pd_dist + base_reward) * (1 + 0.2 * (size / avgVol))
		rand_factor = random.uniform(0.9, 1.1)
		profit = my_round_int(raw_profit * rand_factor)
		
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

def gen_adj_matrs(coords: List[Tuple[float, float]], start_k: int, sizeOfGList: int, skip: int, tspName: str, outDir: str = "."):
	"""
	Generate adjacency matrices using Union of k-NN and MST.
	Ensures connectivity without relying solely on Depot transit.
	
	Strategy: Edge is kept if it is in k-NN OR it is in the Euclidean MST.
	"""
	lenOfCoord = len(coords)
	depot_idx = lenOfCoord - 1
	
	# 1. Build a complete graph with weights to compute MST
	G_complete = nx.Graph()
	all_dists = [[0]*lenOfCoord for _ in range(lenOfCoord)]
	
	for i in range(lenOfCoord):
		all_dists[i][i] = (0, i)
		for j in range(i + 1, lenOfCoord):
			dist = math.dist(coords[i], coords[j])
			G_complete.add_edge(i, j, weight=dist)
			all_dists[i][j] = (dist, j)
			all_dists[j][i] = (dist, i) # Symmetric

	# 2. Compute Minimum Spanning Tree (MST)
	# This guarantees the graph is connected with minimum total length
	mst_edges = set(nx.minimum_spanning_edges(G_complete, algorithm="kruskal", data=False)) # Using Kruskal algorithm
	# mst_edges looks like {(u, v), (x, y)...}

	for iter_idx in range(sizeOfGList):
		current_k = int(start_k + iter_idx * skip)
		
		# Initialize with 0s
		adjMatrix = [[0]*lenOfCoord for _ in range(lenOfCoord)]
			
		# --- A. Add k-NN Edges ---
		for i in range(lenOfCoord):
			# Sort neighbors by distance
			neighbors = sorted(all_dists[i], key=lambda x: x[0])
			
			# Keep top-K (neighbors[0] is self, so range is 1 to K+1)
			limit = min(lenOfCoord, current_k + 1)
			for rank in range(1, limit):
				target_node = neighbors[rank][1]
				adjMatrix[i][target_node] = 1
				adjMatrix[target_node][i] = 1 # Symmetry preferred for undirected logic

		# --- B. Add MST Edges (Safety Net) ---
		for u, v in mst_edges:
			adjMatrix[u][v] = 1
			adjMatrix[v][u] = 1

		# --- C. Force Depot Connectivity ---
		# Even with MST, direct access to Depot is crucial for vehicle dispatch logic
		for i in range(lenOfCoord):
			adjMatrix[depot_idx][i] = 1
			adjMatrix[i][depot_idx] = 1

		# Save to CSV
		df = pd.DataFrame(adjMatrix)
		df.to_csv(f'{outDir}/adjMatrx{current_k}_{tspName}.csv', header=False, index=False)

		fullAdjMatrix = [[1]*lenOfCoord for _ in range(lenOfCoord)]
		for r in range(lenOfCoord):
			fullAdjMatrix[r][r] = 0 # Block self-loop
		df_full = pd.DataFrame(fullAdjMatrix)
		df_full.to_csv(f'{outDir}/adjMatrx0_{tspName}.csv', header=False, index=False)

def gen_vehic_caps(fullRequestList: List[List[int]], cutLens: List[int], tspName: str, outDir: str = "."):
	"""
	Dynamically determine vehicle count based on the specific request set being used.
	"""
	avgCap = 20

	for length in cutLens:
		real_len = min(length, len(fullRequestList))
		current_requests = fullRequestList[:real_len]
		
		total_demand = sum([r[1] for r in current_requests]) # r[1] is size
		
		# STANDARD: Scarcity / Tightness
		# We want Total Demand > Total Fleet Capacity.
		# This forces two behaviors:
		# 1. Selection: The solver MUST reject some requests because it physically can't carry them all at once.
		# 2. Interleaving: To serve more requests, the vehicle MUST drop off items to free up space (capacity reuse).
		
		# Setting ratio to 1.5 means: Total Demand is 150% of Total Static Capacity.
		# Even if all cars go out, they can only hold ~67% of the goods at any single instant.
		demand_to_capacity_ratio = 1.5
		
		# Calculate needed capacity
		num_vehicles = math.ceil(total_demand / (avgCap * demand_to_capacity_ratio))
		
		# Ensure at least 2 vehicles to keep it a Multi-Vehicle problem
		num_vehicles = max(2, num_vehicles)

		vehicleList = []
		for i in range(num_vehicles):
			# --- SBC Coefficients ---
			# Use small gaps (0.1) to break symmetry without creating unrealistic cost disparities.
			capactCoeffi = [1, 0, -1]
			cost_factor = 1 + 0.1 * capactCoeffi[i % 3]
			
			# Capacity slightly varies around 20 (e.g., 15, 20, 25)
			# This heterogeneity also helps Solver distinguish vehicles.
			this_cap = avgCap + 5 * capactCoeffi[i % 3]
			
			vehicleList.append([this_cap, cost_factor])
			
		csv_filename = f'{outDir}/vehicleCap{num_vehicles}_{tspName}.csv'
		
		df = pd.DataFrame(vehicleList)
		df.to_csv(csv_filename, header=False, index=False)

def gen_all_ins_arg(tspPath: str,
					repetRateList: List[float] = [3, 2.5, 2, 1.5, 1],
					start_k: int = 3,
					sizeOfGList: int = 2,
					skip: int = 2,
					outDir: str = ".",
					seed: int = None):
	"""
	Main function: Given a TSP file and several parameters, generate all related CSV files (nodes, requests, vehicles, and adjacency matrices).
	- repetRateList: a list repet rates used to split the request file
	- start_k, sizeOfGList, skip: parameters controlling the generation of adjacency matrices
	"""
	if seed is not None:
		random.seed(seed)

	# 1. Read Nodes
	coords, tspName = read_tsplib_coords(tspPath)
	lenOfCoord = len(coords)
	write_nodes_csv(coords, tspName, outDir=outDir)

	# 2. Generate Requests
	# Use the LARGEST repeat rate to generate the master list
	max_repet_rate = max(repetRateList)
	requestList = gen_request_list(coords, max_repet_rate, seed=seed)
	cutLens = [my_round_int((lenOfCoord-1) * r / 2) for r in repetRateList]
	write_request_csvs(requestList, tspName, cutLens, outDir=outDir)

	# 3. Generate Adjacency Matrices (k-NN + MST)
	gen_adj_matrs(coords, start_k, sizeOfGList, skip, tspName, outDir=outDir)

	# 4. Generate Vehicles
	gen_vehic_caps(requestList, cutLens, tspName, outDir=outDir)

	#print("Generation Completed.", tspName)

# ------------------------------
if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("Usage: python instance_gen.py <tsp-file> [outDir]")
		sys.exit(1)
	tsp_file = sys.argv[1]
	outDir = sys.argv[2] if len(sys.argv) > 2 else "."
	gen_all_ins_arg(tsp_file, outDir=outDir, seed=42)
