# incr.py

import re
import os
import sys
import time
import pandas as pd
from ppdsp_reform_utils import GlobalVariableRegistry, PPDSP_utils
from ppdsp_reform_p1_cplex import PPDSP_MIP
from ppdsp_reform_p1_rc2 import PPDSP_MaxSAT_p1
from ppdsp_reform_p2_rc2 import PPDSP_MaxSAT_p2
from ppdsp_reform_p3_rc2 import PPDSP_MaxSAT_p3
from ppdsp_reform_p4_rc2 import PPDSP_MaxSAT_p4
from ppdsp_reform_p5_rc2 import PPDSP_MaxSAT_p5
from ppdsp_reform_p6_rc2 import PPDSP_MaxSAT_p6

def auto_slice_csvs(tsplib, max_r, max_v, curr_r, curr_v):
    """
    Automatic Dynamic Slicing: Slice the curr_r / curr_v rows from the Master CSV.
    """
    # 1. Slice Request
    curr_req_file = f'requestInfo{curr_r}_{tsplib}.csv'
    if not os.path.exists(curr_req_file):
        master_req_file = f'requestInfo{max_r}_{tsplib}.csv'
        if not os.path.exists(master_req_file):
            print(f"  [Fatal] Master request file {master_req_file} missing! Please generate it first.")
            sys.exit(1)
        df_req = pd.read_csv(master_req_file, header=None)
        df_req.head(int(curr_r)).to_csv(curr_req_file, header=False, index=False)
        print(f"  [Auto-Slice] Created {curr_req_file} from Master ({max_r}).")

    # 2. Slice Vehicle
    curr_veh_file = f'vehicleCap{curr_v}_{tsplib}.csv'
    if not os.path.exists(curr_veh_file):
        master_veh_file = f'vehicleCap{max_v}_{tsplib}.csv'
        if not os.path.exists(master_veh_file):
            print(f"  [Fatal] Master vehicle file {master_veh_file} missing! Please generate it first.")
            sys.exit(1)
        df_veh = pd.read_csv(master_veh_file, header=None)
        df_veh.head(int(curr_v)).to_csv(curr_veh_file, header=False, index=False)
        print(f"  [Auto-Slice] Created {curr_veh_file} from Master ({max_v}).")

if __name__ == "__main__":
    # Usage example: 
    # python incr.py maxsat p4 burma14 uni 5,2,3 10,2,3 15,3,3 19,3,3 19,4,3
    if len(sys.argv) < 6:
        print("Usage: python incr.py <mode> <method> <tsplib> <strategy> <R,V,K> <R,V,K> ...")
        print("  <strategy>: 'uni' for Uniform Rollover, 'cpx' for Complexity-Aware Time Bank")
        print("Example: python incr.py mip p1 A-n32-k5 cpx")
        print("4,2,2 5,2,2 6,2,2 7,2,2 8,2,2 9,2,2 10,2,2 11,2,2 11,3,2 12,3,2")
        print("13,3,2 14,3,2 15,3,2 16,3,2 17,3,2 18,3,2 18,4,2 19,4,2 20,4,2 21,4,2")
        print("22,4,2 23,4,2 24,4,2 24,5,2 24,5,3 25,5,3 26,5,3 27,5,3 28,5,3 29,5,3")
        print("30,5,3 30,6,3 31,6,3 32,6,3 33,6,3 34,6,3 35,6,3 36,6,3 36,7,3 37,7,3")
        print("38,7,3 39,7,3 40,7,3 41,7,3 42,7,3 42,8,3 43,8,3 44,8,3 45,8,3 46,8,3")
        print("47,8,3 48,8,3 48,9,3 49,9,3 50,9,3 51,9,3 52,9,3 53,9,3 53,9,4 54,9,4")
        sys.exit(1)

    mode = sys.argv[1]       # mip / maxsat
    method = sys.argv[2]     # p1 / p2 / ...
    tsplib = sys.argv[3]
    strategy = sys.argv[4].lower() # 提取 strategy 参数并转为小写 (uni 或 cpx)
    raw_sequence = sys.argv[5:]

    # Parse R,V,K sequence
    sequence = []
    max_r, max_v = 0, 0
    for seq_str in raw_sequence:
        parts = seq_str.split(',')
        if len(parts) != 3:
            print(f"Error: Sequence format must be R,V,K (got {seq_str})")
            sys.exit(1)
        r, v, k = parts[0], parts[1], parts[2]
        sequence.append((r, v, k))
        max_r = max(max_r, int(r))
        max_v = max(max_v, int(v))

    print("="*70)
    print(f">>> MULTI-DIMENSIONAL ROLLING HORIZON ({mode.upper()}) <<<")
    print(f"Instance: {tsplib} | Method: {method} | Strategy: {strategy.upper()}")
    print(f"Master Bounds Required -> Requests: {max_r}, Vehicles: {max_v}")
    print(f"Incremental Sequence (R,V,K): {sequence}")
    print("="*70)

    # ==========================================
    # [NEW] Dynamic Recalibration Time Manager
    # ==========================================
    TOTAL_TIME_BUDGET = 3600.0
    num_steps = len(sequence)
    
    # 获取真实的节点数 |V|
    node_file = f'2DNode_{tsplib}.csv'
    if not os.path.exists(node_file):
        print(f"  [Fatal] Node file {node_file} missing! Cannot determine |V|.")
        sys.exit(1)
        
    with open(node_file, 'r') as f:
        V_nodes = sum(1 for line in f if line.strip())
    
    # 根据传入的 strategy 参数静态分配阶段权重 W_i
    if strategy == "uni":
        print("  [Time Manager] Strategy: Uniform Recalibration (-Uni)")
        weights = [1.0 for _ in sequence]
        
    elif strategy == "cpx":
        print("  [Time Manager] Strategy: Complexity-Aware Time Bank (-Cpx)")
        # W_i = |T_i| * (|V| * k_i + |R_i|)
        weights = [float(int(v) * (V_nodes * int(k) + int(r))) for (r, v, k) in sequence]
        
    else:
        print(f"  [Fatal] Unknown strategy: '{strategy}'. Please use 'uni' or 'cpx'.")
        sys.exit(1)
    
    # 新机制：不再追踪“存下的时间”，而是追踪“已消耗的总时间”
    total_consumed_time = 0.0
    
    print(f"  [Time Manager] Global Budget: {TOTAL_TIME_BUDGET}s | Steps: {num_steps} | Map Nodes |V|: {V_nodes}")

    global_registry = GlobalVariableRegistry()
    previous_assumption_file = None

    for idx, (curr_r, curr_v, curr_k) in enumerate(sequence):
        print(f"\n[{idx+1}/{len(sequence)}] Building & Solving: R={curr_r}, V={curr_v}, K={curr_k}")
        
        # ==========================================
        # 1. Auto-slice CSVs for the current sub-problem
        # ==========================================
        auto_slice_csvs(tsplib, max_r, max_v, curr_r, curr_v)
        
        if not os.path.exists(f'adjMatrx{curr_k}_{tsplib}.csv'):
            print(f"  [Fatal] adjMatrx{curr_k}_{tsplib}.csv not found! Please run ins_arg.py to generate it.")
            sys.exit(1)

        # ==========================================
        # 2. Initialize Solver and Generate Formulation
        # ==========================================
        if mode == "mip":
            solver = PPDSP_MIP(tsplib, curr_r, curr_v, curr_k, increment=global_registry)
            print("  [Info] Generating MIP Formulation...")
            solver.genMipFormular()
            solver.writeLpFile()
            log_file = solver.insName + ".lp.out"
            
        elif mode == "maxsat":
            if method == "p1":
                solver = PPDSP_MaxSAT_p1(tsplib, curr_r, curr_v, curr_k, increment=global_registry)
            elif method == "p2":
                solver = PPDSP_MaxSAT_p2(tsplib, curr_r, curr_v, curr_k, increment=global_registry)
            elif method == "p3":
                solver = PPDSP_MaxSAT_p3(tsplib, curr_r, curr_v, curr_k, increment=global_registry)
            elif method == "p4":
                solver = PPDSP_MaxSAT_p4(tsplib, curr_r, curr_v, curr_k, increment=global_registry)
            elif method == "p5":
                solver = PPDSP_MaxSAT_p5(tsplib, curr_r, curr_v, curr_k, increment=global_registry)
            elif method == "p6":
                solver = PPDSP_MaxSAT_p6(tsplib, curr_r, curr_v, curr_k, increment=global_registry)
            else:
                print(f"Unknown maxsat method: {method}")
                sys.exit(1)
            print("  [Info] Generating MaxSAT Formulation...")
            solver.genMaxsatFormular()
            log_file = solver.insName + ".wcnf.out"
        else:
            print(f"Mode {mode} not fully supported in this script yet.")
            sys.exit(1)

        # ==========================================
        # 3. Solve the current sub-problem with Dynamic Recalibration
        # ==========================================
        # 1. 计算全局剩余预算 (B_global - sum(tau_j))
        # 使用 max(1.0, ...) 防止由于系统时间误差导致预算为负，至少给1秒
        remaining_budget = max(1.0, TOTAL_TIME_BUDGET - total_consumed_time)
        
        # 2. 计算从当前阶段到最后阶段的总权重 (sum_{j=i}^N W_j)
        remaining_weight = sum(weights[idx:])
        
        # 3. 动态计算本阶段的限时 L_i
        current_time_limit = remaining_budget * (weights[idx] / remaining_weight)
        
        print(f"  [Time Manager] Global Remaining Budget: {remaining_budget:.2f}s | Future Weight Sum: {remaining_weight}")
        print(f"  [Time Manager] Recalibrated Budget for this step: {current_time_limit:.2f}s")
        
        start_time = time.time()
        
        # Solve the current sub-problem
        solver.solve(time_limit=int(current_time_limit), assumption_file=previous_assumption_file)
        
        # 记录真实消耗的时间 (tau_i)
        elapsed_time = time.time() - start_time
        
        # 累计已消耗的总时间 (\sum tau_j)
        total_consumed_time += elapsed_time
        print(f"  [Time Manager] Step {idx+1} consumed {elapsed_time:.2f}s. Total Consumed: {total_consumed_time:.2f}s.")

        # ==========================================
        # 4. Parse the solver's log to extract the new assumption for the next round
        # ==========================================
        if mode == "mip":
            next_assumption_file = solver.insName + ".lp.asm"
        elif mode == "maxsat":
            next_assumption_file = solver.insName + ".wcnf.asm"
        else:
            print(f"Mode {mode} not fully supported in this script yet.")
            sys.exit(1)
        
        success = PPDSP_utils.parse_and_save_assumption(
            log_file, 
            next_assumption_file, 
            solver.getLastYVarID(), 
            mode
        )
        
        if success:
            previous_assumption_file = next_assumption_file
        else:
            print("  [Warning] Extraction failed. Stopping rolling horizon.")
            break

    print("\n>>> ROLLING HORIZON COMPLETED SUCCESSFULLY <<<")