# ppdsp_reform_utils.py

from z3 import is_true

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

	@staticmethod
	def extractXYModel_z3(self, model):
		if self.id2Var is None:
			PPDSP_utils.buildVarIndexMap(self)
		xy_model = []
		for vid, info in self.id2Var.items():
			vtype = info[0]
			if vtype == 'x':
				_, t, o, d = info
				z3v = self.smt2x[t][o][d]
			elif vtype == 'y':
				_, r, t = info
				z3v = self.smt2y[r][t]
			else:
				continue
			val = model.evaluate(z3v, model_completion=True)
			if is_true(val):
				xy_model.append(vid)
		xy_model.sort()
		return xy_model

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
		req_size    = {r: self.requestList[r][1] for r in range(self.lenOfRequest)}
		pickup_node = {r: self.requestList[r][2] for r in range(self.lenOfRequest)}
		drop_node   = {r: self.requestList[r][3] for r in range(self.lenOfRequest)}

		violated = False
		learnt_clause = []

		for k, (o, d) in enumerate(route):
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

				# ---- Build prefix nodes origins (exclude depot) ----
				prefix_origins = [route[i][0] for i in range(k + 1)]
				xLits = []
				for r in onboard:
					dp = drop_node[r]
					for p in prefix_origins:
						if p != depot:
							xLits.append(self.xVarList[vehID][p][dp])

				# Reason: if onboard_reqs overload, then at least one of them should be dropped earlier
				learnt_clause = yLits + xLits
				break

		return violated, learnt_clause

	# ----------------------------
	# Learnt clause → z3 literals
	# ----------------------------
	@staticmethod
	def learntClause_z3(self, learnt_clause):
		z3_clause = []
		for lit in learnt_clause:
			vid = abs(lit)
			vtype = self.id2Var[vid][0]
			if lit > 0:
				if vtype == 'x':
					z3_clause.append(Bool(f"x{vid}"))
				else:
					z3_clause.append(Bool(f"y{vid}"))
			else:
				if vtype == 'x':
					z3_clause.append(Not(Bool(f"x{vid}")))
				else:
					z3_clause.append(Not(Bool(f"y{vid}")))
		return z3_clause

	# ----------------------------
	# Print each vehicle's route and request
	# ----------------------------
	@staticmethod
	def printVehRoutes(self, filtered_model):
		vehRoutes = PPDSP_utils.decodeModel(self, filtered_model)
		depot = self.lenOfLocation
		for vehID, info in vehRoutes.items():
			route = info['route']
			reqs  = info['requests']
			if not route:
				# No route → only depot
				print(f"Vehicle {vehID}: d, (requests = {reqs})")
				continue
			# Convert route to a node sequence directly
			node_seq = [route[0][0]] + [d for (_, d) in route]
			# Replace depot index with 'd'
			node_seq_str = ["d" if n == depot else str(n) for n in node_seq]
			# Pretty print
			pretty_route = " → ".join(node_seq_str)
			print(f"Vehicle {vehID}: {pretty_route}, (requests = {reqs})")

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
	# Export meta file for UWrMaxSAT
	# ----------------------------
	@staticmethod
	def export_meta(self, filename):
		"""
		Export all necessary PPDSP meta information into a text file
		so that the modified UWrMaxSAT solver can decode x/y variables
		and check capacity constraints lazily.

		The text format matches loadPPDSPInstance() in C++.
		"""
		with open(filename, "w") as f:
			f.write(f"{self.lenOfVehicle} {self.lenOfRequest} {self.lenOfLocation}\n")

			# xVarList
			f.write("# xVarList\n")
			for t in range(self.lenOfVehicle):
				for o in range(len(self.xVarList[t])):
					for d in range(len(self.xVarList[t][o])):
						vid = self.xVarList[t][o][d]
						f.write(f"{t} {o} {d} {vid}\n")

			# yVarList
			f.write("# yVarList\n")
			for r in range(self.lenOfRequest):
				for t in range(self.lenOfVehicle):
					vid = self.yVarList[r][t]
					f.write(f"{r} {t} {vid}\n")

			# requestList
			f.write("# requestList\n")
			for r in range(self.lenOfRequest):
				w, q, pk, dp = self.requestList[r]
				f.write(f"{r} {w} {q} {pk} {dp}\n")

			# vehicleList
			f.write("# vehicleList\n")
			for t in range(self.lenOfVehicle):
				cap, cost = self.vehicleList[t]
				f.write(f"{t} {cap} {cost}\n")

			print(f"[UWrMaxSAT] meta exported to {filename}")

