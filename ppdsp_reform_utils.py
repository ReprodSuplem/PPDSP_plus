# ppdsp_reform_utils.py

from z3 import *

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
	# Get Z3 BoolRef from varID
	# ----------------------------
	@staticmethod
	def get_z3_var(solver_instance, vid):
		"""
		Given an integer varID, return the corresponding Z3 BoolRef object.
		Returns None if not found or not an x/y variable.
		"""
		# Ensure mapping exists
		if solver_instance.id2Var is None:
			PPDSP_utils.buildVarIndexMap(solver_instance)
			
		abs_id = abs(vid)
		if abs_id not in solver_instance.id2Var:
			return None
			
		info = solver_instance.id2Var[abs_id]
		v_type = info[0]
		
		if v_type == 'x':
			t, o, d = info[1], info[2], info[3]
			return solver_instance.smt2x[t][o][d]
		elif v_type == 'y':
			r, t = info[1], info[2]
			return solver_instance.smt2y[r][t]
			
		return None

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
		# Iterate over all registered variables
		for vid in self.id2Var.keys():
			# Reuse the helper function
			z3v = PPDSP_utils.get_z3_var(self, vid)
			if z3v is not None:
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
	# Grouping homogeneous vehicles
	# ----------------------------
	@staticmethod
	def get_sbc_groups(vehicleList):
		"""
		Group vehicles by Capacity and Cost Factor.
		Returns: dict {(capacity, cost): [v1, v2, v3...]}
		"""
		groups = {}
		for t, veh in enumerate(vehicleList):
			cap = int(veh[0])
			cost = float(f"{veh[1]:.4f}")
			key = (cap, cost)
			
			if key not in groups:
				groups[key] = []
			groups[key].append(t)
			
		# Filter groups with < 2 vehicles (no symmetry to break)
		return {k: v for k, v in groups.items() if len(v) >= 2}

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
			# Update load status
			for r in assigned_reqs:
				if d == pickup_node[r]:
					load += req_size[r]
					onboard.add(r)
				elif d == drop_node[r] and r in onboard:
					load -= req_size[r]
					onboard.remove(r)

			if load > capacity:
				violated = True

				# ---- 1. Collect and Sort (Descending by size) ----
				# Convert set to list for sorting
				onboard_reqs = list(onboard)
				# Sort logic: largest request first
				onboard_reqs.sort(key=lambda r: req_size[r], reverse=True)

				# ---- 2. Greedy Reduction: Find minimal conflict core ----
				minimal_conflict = []
				current_subset_load = 0
				for r in onboard_reqs:
					current_subset_load += req_size[r]
					minimal_conflict.append(r)
					if current_subset_load > capacity:
						break # Found the minimal set that exceeds capacity

				# ---- 3. Build learnt clause based on Minimal Conflict ----
				# yLits: Negate Y vars ONLY for the minimal conflict set
				yLits = [-self.yVarList[r][vehID] for r in minimal_conflict]
				# xLits: Build prefix nodes origins
				prefix_origins = [route[i][0] for i in range(k + 1)]

				xLits = []
				# Only generate path negation for the minimal conflict set
				for r in minimal_conflict:
					dp = drop_node[r]
					for p in prefix_origins:
						xLits.append(self.xVarList[vehID][p][dp])

				# Reason: The minimal subset of onboard requests implies overload on this path
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
			z3_var = PPDSP_utils.get_z3_var(self, abs(lit))
			if z3_var is not None:
				if lit > 0:
					z3_clause.append(z3_var)
				else:
					z3_clause.append(Not(z3_var))
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

			# vehicleGroups
			f.write("# vehicleGroups\n")
			groups = PPDSP_utils.get_sbc_groups(self.vehicleList)
			gid = 0
			for key, vehs in groups.items():
				line = f"{gid} {len(vehs)} " + " ".join(map(str, vehs))
				f.write(line + "\n")
				gid += 1

			print(f"[UWrMaxSAT] meta exported to {filename}")

	# ----------------------------
	# Run UWrMaxSAT with real-time stdout logging and write to log file
	# ----------------------------
	@staticmethod
	def run_uwrmaxsat(cmd, log_file, time_limit=None):
		"""
		Run UWrMaxSAT with:
		- real-time stdout echo to terminal
		- real-time write to log_file
		- time limit (seconds)
		- clean kill on timeout
		"""
		import subprocess, shlex, time

		print(f"[UWrMaxSAT] Running command:\n  {cmd}")

		with open(log_file, "w", buffering=1) as log_f:
			proc = subprocess.Popen(
				shlex.split(cmd),
				stdout=subprocess.PIPE,
				stderr=subprocess.STDOUT,
				text=True,
				bufsize=1
			)
			start_time = time.time()
			timeout_hit = False
			try:
				for line in proc.stdout:
					print(line, end="")
					log_f.write(line)
					log_f.flush()
					if time_limit is not None and (time.time() - start_time) > time_limit:
						print(f"\n[UWrMaxSAT] Time limit {time_limit} s reached. Killing process...", flush=True)
						timeout_hit = True
						proc.terminate()
						try:
							proc.wait(timeout=3)
						except subprocess.TimeoutExpired:
							proc.kill()
						break
			finally:
				if proc.stdout:
					proc.stdout.close()
				try:
					proc.wait(timeout=3)
				except subprocess.TimeoutExpired:
					proc.kill()
			if timeout_hit:
				print(f"[UWrMaxSAT] Process stopped due to time limit. returncode = {proc.returncode}")
			else:
				print(f"[UWrMaxSAT] Process finished. returncode = {proc.returncode}")

			return timeout_hit

	# ----------------------------
	# Z3 Solver with Threaded Interrupt (Hard Timeout)
	# ----------------------------
	@staticmethod
	def solve_z3_with_interrupt(z3_optimizer, time_limit):
		"""
		Run Z3 check() with a separate timer thread to force interrupt.
		This is stronger than z3_optimizer.set("timeout", ...)
		"""
		import threading
		
		# Define the container to hold the result
		result_container = {'status': None}
		
		def target():
			result_container['status'] = z3_optimizer.check()

		# Create a thread to run the solver
		solve_thread = threading.Thread(target=target)
		solve_thread.start()
		
		# Wait for the thread to finish or timeout
		solve_thread.join(timeout=time_limit)
		
		if solve_thread.is_alive():
			print(f"[Z3] Time limit {time_limit}s reached. Sending interrupt signal...")
			# Force Z3 to stop
			z3_optimizer.ctx.interrupt()
			
			# Give it a moment to clean up
			solve_thread.join(timeout=2) 
			
			if solve_thread.is_alive():
				print("[Z3] Warning: Z3 is struggling to stop even after interrupt.")
			
			return None # Treat as timeout/unknown
			
		return result_container['status']

	# ----------------------------
	# Assumption literals reader
	# ----------------------------
	@staticmethod
	def read_assumption_literals(filename):
		"""
		Read assumption literals from a file.
		File format: space separated integers (e.g., "1 -2 3 ...")
		Returns: set of integer literals
		"""
		lits = set()
		try:
			with open(filename, 'r') as f:
				content = f.read()
				tokens = content.replace('\n', ' ').split()
				for t in tokens:
					try:
						lit = int(t)
						if lit != 0: lits.add(lit) # Add non-zero literals only
					except ValueError:
						pass # Ignore non-integer content (e.g., 'v')
		except FileNotFoundError:
			print(f"[Utils] Assumption file not found: {filename}")
		return lits
