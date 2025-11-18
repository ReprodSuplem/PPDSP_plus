# ppdsp_reform_utils.py

class PPDSP_utils:

	# ----------------------------
	# Convert CPLEX varNames to int literal IDs
	# ----------------------------
	@staticmethod
	def convert_cplex_model(raw_model):
		"""
		Convert ['x303','y17','u80', ...] → [303,17]
		Only keep xVar and yVar.
		"""
		filtered = []
		for name in raw_model:
			if len(name) > 1 and (name[0] == 'x' or name[0] == 'y'):
				try:
					filtered.append(int(name[1:]))
				except:
					pass
		return filtered

	# ----------------------------
	# Build reverse mapping varID → (type, ...)
	# ----------------------------
	@staticmethod
	def buildVarIndexMap(self):
		self.id2Var = {}
		# xVar
		for t in range(self.lenOfVehicle):
			for o in range(len(self.xVarList[t])):
				for d in range(len(self.xVarList[t][o])):
					vid = self.xVarList[t][o][d]
					self.id2Var[vid] = ('x', t, o, d)
		# yVar
		for r in range(self.lenOfRequest):
			for t in range(self.lenOfVehicle):
				vid = self.yVarList[r][t]
				self.id2Var[vid] = ('y', r, t)

	# ----------------------------
	# Extract model (only xy domain)
	# ----------------------------
	@staticmethod
	def extractXYModel(self, model):
		return [i for i in model if 0 < i <= self.getLastYVarID()]

	# ----------------------------
	# Decode vehicle routes and assigned requests
	# ----------------------------
	@staticmethod
	def decodeModel(self, filtered_model):
		if self.id2Var is None:
			PPDSP_utils.buildVarIndexMap(self)

		veh_routes = {v: {'route': [], 'requests': []} for v in range(self.lenOfVehicle)}

		for vid in filtered_model:
			varInfo = self.id2Var.get(vid)
			if varInfo is None:
				continue
			if varInfo[0] == 'x':
				_, t, o, d = varInfo
				if o != d:
					veh_routes[t]['route'].append((o, d))
			elif varInfo[0] == 'y':
				_, r, t = varInfo
				veh_routes[t]['requests'].append(r)

		# Reconstruct actual ordered route (Hamiltonian cycle)
		for v in range(self.lenOfVehicle):
			edges = veh_routes[v]['route']
			if not edges:
				continue
			next_map = {o: d for (o, d) in edges}
			route = []
			cur = self.lenOfLocation # Start from depot := self.lenOfLocation
			while cur in next_map:
				nxt = next_map[cur]
				route.append((cur, nxt))
				cur = nxt
				if cur == self.lenOfLocation: # Return back to depot
					break
			veh_routes[v]['route'] = route
		return veh_routes

	# ----------------------------
	# Check overload and return learnt clause
	# ----------------------------
	@staticmethod
	def checkOverload(self, vehID, route, assigned_reqs):
		if not route:
			return False, []

		capacity = self.vehicleList[vehID][0]
		load = 0
		onboard = set()

		# Setup pickup/dropoff indices
		req_size    = {i: self.requestList[i][1] for i in range(self.lenOfRequest)}
		pickup_node = {i: self.requestList[i][2] for i in range(self.lenOfRequest)}
		drop_node   = {i: self.requestList[i][3] for i in range(self.lenOfRequest)}

		violated = False
		learnt_clause = []

		for step_idx, (o, d) in enumerate(route):
			for r in assigned_reqs:
				if d == pickup_node[r]:
					load += req_size[r]
					onboard.add(r)
				elif d == drop_node[r] and r in onboard:
					load -= req_size[r]
					onboard.remove(r)

			if load > capacity:
				violated = True
				# ---- Extract reason negation for clause learning ----
				yLits = [-self.yVarList[r][vehID] for r in onboard]
				xLits = []
				for r in assigned_reqs:
					for o in range(self.lenOfLocation):
						xLits.append(self.xVarList[vehID][o][self.requestList[r][3]])
				# Reason: if onboard_reqs overload, then at least one of them
				learnt_clause = yLits + xLits
				break

		return violated, learnt_clause

	# ----------------------------
	# Print each vehicle's route and request
	# ----------------------------
	@staticmethod
	def printVehRoutes(self, filtered_model):
		vehRoutes = PPDSP_utils.decodeModel(self, filtered_model)
		for vehID, info in vehRoutes.items():
			route = info['route']
			reqs  = info['requests']
			print(f"Vehicle {vehID} route: {route}, requests: {reqs}")

	# ----------------------------
	# Evaluate profit - cost
	# ----------------------------
	@staticmethod
	def evaluateSolution(self, filtered_model):
		if self.id2Var is None:
			PPDSP_utils.buildVarIndexMap(self)

		profit = 0
		cost = 0

		for vid in filtered_model:
			varInfo = self.id2Var.get(vid)
			if varInfo is None:
				continue

			if varInfo[0] == 'y':
				r = varInfo[1]
				profit += self.requestList[r][0]

			elif varInfo[0] == 'x':
				_, t, o, d = varInfo
				cost += self.my_round_int(self.vehicleList[t][1] * self.locaList[o][d])

		print("======== PPDSP OBJECTIVE ========")
		print(f"Profit    = {profit}")
		print(f"Cost      = {cost}")
		print(f"Objective = {profit - cost}")
		print("=================================")

		return profit - cost

	# ----------------------------
	# Export JSON meta for UWrMaxSAT
	# ----------------------------
	@staticmethod
	def export_meta_json(self, filename):
		"""
		Export all necessary PPDSP meta information into a JSON file
		so that the modified UWrMaxSAT solver can decode x/y variables
		and check capacity constraints lazily.

		The JSON format matches loadPPDSPInstance() in C++.
		"""
		import json

		data = {
			"lenOfVehicle":  self.lenOfVehicle,
			"lenOfRequest":  self.lenOfRequest,
			"lenOfLocation": self.lenOfLocation,
			"xVarList":      self.xVarList,
			"yVarList":      self.yVarList,
			"requestList":   self.requestList,
			"vehicleList":   self.vehicleList
		}

		with open(filename, "w") as f:
			json.dump(data, f, indent=2)

		print(f"[PPDSP] meta JSON exported to {filename}")

