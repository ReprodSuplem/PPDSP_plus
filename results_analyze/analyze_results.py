import re
import pandas as pd
import numpy as np
import glob
import os

def parse_log(filename):
    data = []
    current_run = {}
    
    # Run-specific state
    maxsat_last_raw_sol = None
    maxsat_true_final_obj = None
    maxsat_hit_timeout_msg = False
    maxsat_temp_time = 0.0
    
    mip_last_elapsed_buffer = 0.0
    mip_hit_timeout_threshold = False
    mip_temp_bound = None 
    
    # Flags to detect tags in the log for the CURRENT run
    found_maxsat_no_sbc_tag = False
    found_mip_sbc_tag = False
    
    # 1. Pre-load WCNF stats
    wcnf_stats_map = load_real_wcnf_stats()
    
    # Global MIP bounds map
    mip_log_bounds_map = {} 

    # --- Regex ---
    run_pattern = re.compile(r"Running: python main\.py (\w+) (\S+) (\S+) (\d+) (\d+)")
    
    # MaxSAT Patterns
    vars_pattern = re.compile(r"c \|\s+Number of variables:\s+(\d+)")
    clauses_pattern = re.compile(r"c \|\s+Number of clauses:\s+(\d+)\s*\(incl")
    maxsat_sol_pattern = re.compile(r"c Found solution: (\d+)")
    maxsat_time_pattern = re.compile(r"c \[Elapsed time\] ([\d\.]+) s")
    maxsat_true_obj_pattern = re.compile(r"Objective = ([\d\.-]+)")
    maxsat_timeout_str_1 = "Timeout reached inside slice loop"
    maxsat_timeout_str_2 = "Timeout reached"
    
    # Tag detection patterns
    maxsat_no_sbc_pattern = re.compile(r"Generating instance:.*-SBC\.wcnf")
    mip_sbc_pattern = re.compile(r"\[CPLEX\] Added \d+ SBC inequalities")
    
    # MIP Patterns
    mip_elapsed_pattern = re.compile(r"Elapsed time\s*=\s*([\d\.]+)\s*sec")
    mip_star_line_pattern = re.compile(r"^\s*\*")
    mip_incumbent_pattern = re.compile(r"Found incumbent of value ([\d\.]+) after ([\d\.]+) sec")
    mip_final_obj_pattern = re.compile(r"\[CPLEX\] OPTIMAL OBJ:\s*([\d\.\-]+)")
    mip_final_time_pattern = re.compile(r"\[CPLEX\] Runtime:\s*([\d\.]+)")

    # Config Base Map
    config_base_map = {
        'p1': 'TE+BDD', 'p2': 'DE+BDD', 'p3': 'OE+BDD',
        'p4': 'OE+LCG', 'p5': 'DE+LCG', 'p6': 'TE+LCG',
        'default': 'MIP'
    }

    def save_run(run_data, last_raw, true_obj, ms_timeout, mp_timeout, m_bound, found_ms_no_sbc, found_mp_sbc):
        if not run_data or not run_data.get('method'): return
        
        raw_cfg = run_data.get('raw_config')
        method = run_data['method']
        base_label = config_base_map.get(raw_cfg, raw_cfg)
        
        # --- Apply User's SBC Logic Here ---
        T = run_data.get('K', 0)
        final_is_sbc = False # Default
        
        if method == 'maxsat':
            # MaxSAT Rules:
            # 1. Has "-SBC" (found_ms_no_sbc=True) AND T>=4 -> No-SBC (False)
            # 2. No "-SBC" (found_ms_no_sbc=False) AND T<4  -> No-SBC (False)
            # 3. No "-SBC" (found_ms_no_sbc=False) AND T>=4 -> +SBC  (True)
            
            if found_ms_no_sbc and T >= 4:
                final_is_sbc = False
            elif not found_ms_no_sbc and T < 4:
                final_is_sbc = False
            elif not found_ms_no_sbc and T >= 4:
                final_is_sbc = True
            
        elif method == 'mip':
            # MIP Rules:
            # 1. Has "Added SBC" (found_mp_sbc=True) AND T>=4 -> +SBC (True)
            # 2. No "Added SBC" -> No-SBC (False)
            
            if found_mp_sbc and T >= 4:
                final_is_sbc = True
            else:
                final_is_sbc = False
        
        # Construct Config Label
        final_label = base_label
        if final_is_sbc:
            final_label += "+SBC"
            
        run_data['config'] = final_label
        
        # WCNF Stats Lookup (MaxSAT only)
        if method == 'maxsat':
            # Key: (instance, R, V, raw_config, is_sbc)
            lookup_key = (
                run_data.get('instance'), 
                run_data.get('N'), 
                run_data.get('K'), 
                raw_cfg, 
                final_is_sbc
            )
            if lookup_key in wcnf_stats_map:
                real_vars, real_clauses = wcnf_stats_map[lookup_key]
                run_data['variables'] = real_vars
                run_data['clauses'] = real_clauses
        
        # Determine Status/Objective
        if method == 'maxsat':
            if true_obj is not None and last_raw is not None:
                run_data['objective'] = true_obj
                run_data['status'] = 'Feasible'
            else:
                run_data['objective'] = np.nan
                run_data['status'] = 'Unsolved'
            
            if ms_timeout:
                run_data['Timeout'] = 'Yes'
            else:
                run_data['Timeout'] = 'No'
                if run_data['status'] == 'Feasible':
                    run_data['status'] = 'Optimal'
                    
        elif method == 'mip':
            if run_data.get('objective') is not None:
                run_data['status'] = 'Feasible'
            if mp_timeout:
                run_data['Timeout'] = 'Yes'
            else:
                run_data['Timeout'] = 'No'
                if run_data['status'] == 'Feasible':
                    run_data['status'] = 'Optimal'
            
            if m_bound is not None:
                k = (run_data['instance'], run_data['N'], run_data['K'])
                mip_log_bounds_map[k] = m_bound
        
        data.append(run_data)

    with open(filename, 'r') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        
        # New Run Detection
        if "Running: python main.py" in line:
            # Save previous run
            save_run(current_run, maxsat_last_raw_sol, maxsat_true_final_obj, 
                     maxsat_hit_timeout_msg, mip_hit_timeout_threshold, mip_temp_bound,
                     found_maxsat_no_sbc_tag, found_mip_sbc_tag)
            
            # Reset
            current_run = {
                'instance': None, 'method': None, 'raw_config': None,
                'N': None, 'K': None,
                'variables': np.nan, 'clauses': np.nan, 
                'time': np.nan, 'objective': np.nan, 
                'status': 'Unknown', 'Timeout': '?'
            }
            maxsat_last_raw_sol = None
            maxsat_true_final_obj = None
            maxsat_hit_timeout_msg = False
            maxsat_temp_time = 0.0
            mip_last_elapsed_buffer = 0.0
            mip_hit_timeout_threshold = False
            mip_temp_bound = None
            
            # Reset Tags
            found_maxsat_no_sbc_tag = False
            found_mip_sbc_tag = False
            
            try:
                parts = line.split("main.py")[1].strip().split()
                if len(parts) >= 5:
                    method = parts[0]
                    current_run['method'] = method
                    current_run['raw_config'] = parts[1] if method == 'maxsat' else 'default'
                    current_run['instance'] = parts[2]
                    current_run['N'] = int(parts[3])
                    current_run['K'] = int(parts[4])
            except:
                pass
            continue
            
        if not current_run.get('method'): continue
        
        # Check Tags (Applicable to any run line)
        if maxsat_no_sbc_pattern.search(line):
            found_maxsat_no_sbc_tag = True
        if mip_sbc_pattern.search(line):
            found_mip_sbc_tag = True
        
        if current_run['method'] == 'maxsat':
            if "Number of variables:" in line:
                m = vars_pattern.search(line)
                if m: current_run['variables'] = int(m.group(1))
            if "Number of clauses:" in line:
                m = clauses_pattern.search(line)
                if m: current_run['clauses'] = int(m.group(1))
            m_time = maxsat_time_pattern.search(line)
            if m_time: maxsat_temp_time = float(m_time.group(1))
            if "Found solution:" in line:
                m_sol = maxsat_sol_pattern.search(line)
                if m_sol:
                    maxsat_last_raw_sol = float(m_sol.group(1))
                    current_run['time'] = maxsat_temp_time
            if "Objective =" in line and "PPDSP" not in line:
                m_obj = maxsat_true_obj_pattern.search(line)
                if m_obj: maxsat_true_final_obj = float(m_obj.group(1))
            if maxsat_timeout_str_1 in line or maxsat_timeout_str_2 in line:
                maxsat_hit_timeout_msg = True
        
        elif current_run['method'] == 'mip':
            m_elapsed = mip_elapsed_pattern.search(line)
            if m_elapsed: mip_last_elapsed_buffer = float(m_elapsed.group(1))
            if mip_star_line_pattern.match(line): current_run['time'] = mip_last_elapsed_buffer
            m_inc = mip_incumbent_pattern.search(line)
            if m_inc:
                time_val = float(m_inc.group(2))
                current_run['time'] = time_val
            m_final_obj = mip_final_obj_pattern.search(line)
            if m_final_obj: current_run['objective'] = float(m_final_obj.group(1))
            m_final_time = mip_final_time_pattern.search(line)
            if m_final_time:
                runtime = float(m_final_time.group(1))
                if runtime >= 3599.0: mip_hit_timeout_threshold = True
            if line.endswith('%'):
                parts = line.split()
                def is_bound_value(s):
                    try: 
                        float(s); return '.' in s
                    except: return False
                if len(parts) >= 2:
                    if is_bound_value(parts[-2]): mip_temp_bound = float(parts[-2])
                    elif len(parts) >= 3 and is_bound_value(parts[-3]): mip_temp_bound = float(parts[-3])

    # Save last run
    save_run(current_run, maxsat_last_raw_sol, maxsat_true_final_obj, 
             maxsat_hit_timeout_msg, mip_hit_timeout_threshold, mip_temp_bound,
             found_maxsat_no_sbc_tag, found_mip_sbc_tag)
    
    df = pd.DataFrame(data)
    df = df.drop(columns=['raw_config'])
    df = df.rename(columns={'N': '|R|', 'K': '|T|', 'Timeout': 'timeout'})
    
    # --- Analysis Logic ---
    analyze_pairwise_sbc(df)
    analyze_sbc_effectiveness(df)
    analyze_size_comparison(df)
    
    # Gap Calculation
    group_best_bound_map = {}
    if not df.empty:
        df['objective'] = pd.to_numeric(df['objective'], errors='coerce')
        groups = df.groupby(['instance', '|R|', '|T|'])
        for name, group in groups:
            optimals = group[group['timeout'] == 'No']
            if not optimals.empty: best_known = optimals['objective'].max()
            else: best_known = mip_log_bounds_map.get(name)
            group_best_bound_map[name] = best_known

    def calc_gap(row):
        key = (row['instance'], row['|R|'], row['|T|'])
        best_known = group_best_bound_map.get(key)
        obj = row['objective']
        if best_known is None or pd.isna(obj) or obj == 0: return ""
        try:
            gap_val = (best_known - obj) / abs(obj)
            return f"{gap_val * 100:.2f}%"
        except: return ""

    df['gap'] = df.apply(calc_gap, axis=1)
    
    # Winners Logic
    winner_time_indices = []
    winner_obj_indices = []
    
    if not df.empty:
        df['time'] = pd.to_numeric(df['time'], errors='coerce')
        groups = df.groupby(['instance', '|R|', '|T|'])
        for name, group in groups:
            valid_obj = group.dropna(subset=['objective'])
            if valid_obj.empty: continue
            max_obj = valid_obj['objective'].max()
            best_obj_candidates = valid_obj[valid_obj['objective'] == max_obj]
            
            if len(best_obj_candidates) == 1:
                winner_obj_indices.extend(best_obj_candidates.index.tolist())
            else:
                optimal_candidates = best_obj_candidates[best_obj_candidates['timeout'] == 'No']
                pool = optimal_candidates if not optimal_candidates.empty else best_obj_candidates
                min_time = pool['time'].min()
                winners = pool[pool['time'] == min_time]
                winner_time_indices.extend(winners.index.tolist())

    df['is_winner'] = False
    df.loc[winner_time_indices, 'is_winner'] = True
    df.loc[winner_obj_indices, 'is_winner'] = True

    # Formatting
    df['time'] = df['time'].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "")
    df['objective'] = df['objective'].apply(lambda x: f"{int(x)}" if pd.notnull(x) else "")
    
    for idx in winner_time_indices:
        df.at[idx, 'time'] = str(df.at[idx, 'time']) + "*"
    for idx in winner_obj_indices:
        df.at[idx, 'objective'] = str(df.at[idx, 'objective']) + "*"

    instance_order = ['burma14', 'ulysses22', 'bays29', 'P-n16-k8', 'P-n23-k8', 'A-n32-k5']
    df['instance'] = pd.Categorical(df['instance'], categories=instance_order, ordered=True)
    df = df.sort_values(by=['instance', '|R|', '|T|', 'method', 'config'])
    
    final_cols = ['instance', '|R|', '|T|', 'method', 'config', 'variables', 'clauses', 'timeout', 'status', 'objective', 'time', 'gap', 'is_winner']
    final_cols = [c for c in final_cols if c in df.columns]
    df = df[final_cols]
    
    return df

def load_real_wcnf_stats():
    stats_map = {}
    files = glob.glob("*.wcnf")
    if not files:
        print("[Warning] No .wcnf files found in current directory. Using log stats.")
        return stats_map
        
    print(f"Found {len(files)} .wcnf files. Parsing headers for real encoding sizes...")
    filename_pattern = re.compile(r"^([a-z0-9]+)_(.+)_r(\d+)v(\d+)k\d+(-SBC)?\.wcnf$")
    
    for fname in files:
        match = filename_pattern.match(fname)
        if match:
            raw_cfg = match.group(1)
            instance = match.group(2)
            R = int(match.group(3))
            V = int(match.group(4))
            sbc_tag = match.group(5)
            
            # WCNF Lookup Logic needs to align with user's logic:
            # 1. Filename has -SBC -> is_sbc=False
            # 2. Filename no -SBC -> if V < 4 then is_sbc=False else is_sbc=True
            
            if sbc_tag is not None:
                is_sbc = False
            else:
                if V < 4:
                    is_sbc = False
                else:
                    is_sbc = True
            
            try:
                with open(fname, 'r') as f:
                    header = f.readline().strip()
                    if header.startswith('p wcnf'):
                        parts = header.split()
                        if len(parts) >= 4:
                            real_vars = int(parts[2])
                            real_clauses = int(parts[3])
                            key = (instance, R, V, raw_cfg, is_sbc)
                            stats_map[key] = (real_vars, real_clauses)
            except Exception as e:
                print(f"[Error] Failed to read {fname}: {e}")
                
    print(f"Loaded stats for {len(stats_map)} instances.")
    return stats_map

def get_base_cfg(cfg):
    if cfg.endswith('+SBC'): return cfg.replace('+SBC', ''), True
    return cfg, False

def analyze_pairwise_sbc(df):
    if df.empty: return
    pairwise_stats = {}
    df_anl = df.copy()
    df_anl[['base_config', 'has_sbc']] = df_anl['config'].apply(lambda x: pd.Series(get_base_cfg(x)))
    groups = df_anl.groupby(['instance', '|R|', '|T|', 'method', 'base_config'])
    for name, group in groups:
        if len(group) != 2: continue
        row_sbc = group[group['has_sbc'] == True]
        row_no = group[group['has_sbc'] == False]
        if row_sbc.empty or row_no.empty: continue
        
        base_cfg = name[4]
        if base_cfg not in pairwise_stats: pairwise_stats[base_cfg] = {'sbc': 0, 'no_sbc': 0, 'tie': 0}
        
        obj_sbc = row_sbc['objective'].values[0]
        obj_no = row_no['objective'].values[0]
        if pd.isna(obj_sbc): obj_sbc = -1
        if pd.isna(obj_no): obj_no = -1
        winner = 'tie'
        if obj_sbc > obj_no: winner = 'sbc'
        elif obj_no > obj_sbc: winner = 'no_sbc'
        else:
            t_sbc = row_sbc['time'].values[0]
            t_no = row_no['time'].values[0]
            if pd.isna(t_sbc): t_sbc = float('inf')
            if pd.isna(t_no): t_no = float('inf')
            if t_sbc < t_no: winner = 'sbc'
            elif t_no < t_sbc: winner = 'no_sbc'
            else: winner = 'tie'
        pairwise_stats[base_cfg][winner] += 1
        
    print("\n" + "="*70)
    print(">>> PAIRWISE HEAD-TO-HEAD ANALYSIS (No-SBC vs. With-SBC)")
    print("="*70)
    print(f"{'Base Config':<15} | {'No-SBC Wins':<12} : {'SBC Wins':<10} | {'Tie':<5} | {'Verdict'}")
    print("-" * 70)
    for cfg in sorted(pairwise_stats.keys()):
        no_wins = pairwise_stats[cfg]['no_sbc']
        sbc_wins = pairwise_stats[cfg]['sbc']
        ties = pairwise_stats[cfg]['tie']
        verdict = ""
        if sbc_wins > no_wins: verdict = "SBC Better"
        elif no_wins > sbc_wins: verdict = "No-SBC Better"
        else: verdict = "Neutral"
        print(f"{cfg:<15} | {no_wins:<12} : {sbc_wins:<10} | {ties:<5} | {verdict}")

def analyze_sbc_effectiveness(df):
    if df.empty: return
    df_anl = df.copy()
    df_anl[['base_config', 'has_sbc']] = df_anl['config'].apply(lambda x: pd.Series(get_base_cfg(x)))
    stats = {'maxsat': {}, 'mip': {}}
    groups = df_anl.groupby(['instance', '|R|', '|T|', 'method', 'base_config'])
    for name, group in groups:
        instance, R, T, method, base_config = name
        if len(group) != 2: continue
        row_sbc = group[group['has_sbc'] == True]
        row_no = group[group['has_sbc'] == False]
        if row_sbc.empty or row_no.empty: continue
        
        obj_sbc = row_sbc['objective'].values[0]
        obj_no = row_no['objective'].values[0]
        if pd.isna(obj_sbc): obj_sbc = -1
        if pd.isna(obj_no): obj_no = -1
        
        winner = 'tie'
        if obj_sbc > obj_no: winner = 'sbc'
        elif obj_no > obj_sbc: winner = 'no_sbc'
        else:
            t_sbc = row_sbc['time'].values[0]
            t_no = row_no['time'].values[0]
            if pd.isna(t_sbc): t_sbc = float('inf')
            if pd.isna(t_no): t_no = float('inf')
            if t_sbc < t_no: winner = 'sbc'
            elif t_no < t_sbc: winner = 'no_sbc'
        
        if T not in stats[method]: stats[method][T] = {'sbc': 0, 'no_sbc': 0, 'tie': 0}
        stats[method][T][winner] += 1

    print("\n" + "="*70)
    print(">>> SBC EFFECTIVENESS BY VEHICLE COUNT (|T|)")
    print("="*70)
    for method in ['maxsat', 'mip']:
        print(f"\nMethod: {method.upper()}")
        print(f"{'|T|':<5} | {'SBC Wins':<10} | {'No-SBC Wins':<12} | {'Tie':<5} | {'Conclusion'}")
        print("-" * 60)
        sorted_T = sorted(stats[method].keys())
        for T in sorted_T:
            s = stats[method][T]
            sbc_w = s['sbc']
            no_w = s['no_sbc']
            tie = s['tie']
            if sbc_w > no_w: conc = "SBC Helps"
            elif no_w > sbc_w: conc = "SBC Hurts"
            else: conc = "Neutral"
            print(f"{T:<5} | {sbc_w:<10} | {no_w:<12} | {tie:<5} | {conc}")

def analyze_size_comparison(df):
    if df.empty: return
    df_ms = df[df['method'] == 'maxsat'].copy()
    if df_ms.empty: return
    
    def get_enc_type(cfg):
        if 'BDD' in cfg: return 'BDD'
        if 'LCG' in cfg: return 'LCG'
        return 'Other'
        
    df_ms['Enc_Type'] = df_ms['config'].apply(get_enc_type)
    df_target = df_ms[df_ms['Enc_Type'].isin(['BDD', 'LCG'])]
    if df_target.empty: return
    
    df_target['variables'] = pd.to_numeric(df_target['variables'], errors='coerce')
    df_target['clauses'] = pd.to_numeric(df_target['clauses'], errors='coerce')
    
    target_order = ['burma14', 'P-n16-k8', 'ulysses22', 'P-n23-k8', 'bays29', 'A-n32-k5']
    
    print("\n" + "="*60)
    print(">>> SIZE COMPARISON BY INSTANCE")
    print("="*60)
    print(f"{'Instance':<12} | {'Type':<5} | {'Variables':<12} | {'Clauses':<12}")
    print("-" * 60)

    grouped = df_target.groupby(['instance', 'Enc_Type'])[['variables', 'clauses']].mean()
    
    for inst in target_order:
        if inst not in df_target['instance'].values: continue
        try:
            if (inst, 'BDD') in grouped.index:
                bdd_vars = grouped.loc[(inst, 'BDD'), 'variables']
                bdd_cls  = grouped.loc[(inst, 'BDD'), 'clauses']
            else: bdd_vars, bdd_cls = np.nan, np.nan
            
            if (inst, 'LCG') in grouped.index:
                lcg_vars = grouped.loc[(inst, 'LCG'), 'variables']
                lcg_cls  = grouped.loc[(inst, 'LCG'), 'clauses']
            else: lcg_vars, lcg_cls = np.nan, np.nan
            
            print(f"{inst:<12} | {'BDD':<5} | {int(bdd_vars) if pd.notnull(bdd_vars) else '-':<12} | {int(bdd_cls) if pd.notnull(bdd_cls) else '-':<12}")
            print(f"{'':<12} | {'LCG':<5} | {int(lcg_vars) if pd.notnull(lcg_vars) else '-':<12} | {int(lcg_cls) if pd.notnull(lcg_cls) else '-':<12}")
            
            r_var_str, r_cls_str = "", ""
            if pd.notnull(bdd_vars) and pd.notnull(lcg_vars) and lcg_vars > 0:
                r_var_str = f"Vars: {bdd_vars / lcg_vars:.1f}x"
            if pd.notnull(bdd_cls) and pd.notnull(lcg_cls) and lcg_cls > 0:
                r_cls_str = f"Cls:  {bdd_cls / lcg_cls:.1f}x"
            
            print(f"{'':<12} | {'Ratio':<5} | {r_var_str:<12} | {r_cls_str:<12}")
            print("-" * 60)
        except Exception as e: print(f"Error processing {inst}: {e}")

if __name__ == "__main__":
    log_file = 'full_experiment.log' 
    output_csv = 'experiment_results.csv'
    
    print(f"Parsing {log_file}...")
    df = parse_log(log_file)
    
    print("\n" + "="*70)
    print(">>> CONSOLIDATED WIN COUNTS (Total Wins across all configs)")
    print("="*70)
    
    win_stats = {} 
    all_configs = sorted(df['config'].unique())
    for cfg in all_configs:
        base, _ = get_base_cfg(cfg)
        if base not in win_stats: win_stats[base] = {'total': 0, 'sbc_wins': 0}
            
    for index, row in df.iterrows():
        if row['is_winner']:
            cfg = row['config']
            base, is_sbc = get_base_cfg(cfg)
            if base in win_stats:
                win_stats[base]['total'] += 1
                if is_sbc: win_stats[base]['sbc_wins'] += 1
    
    for base in sorted(win_stats.keys()):
        total = win_stats[base]['total']
        sbc = win_stats[base]['sbc_wins']
        print(f"{base:<15}: {total} ({sbc})")
        
    df = df.drop(columns=['is_winner'])
    df.to_csv(output_csv, index=False)
    print(f"\nDone. Saved to {output_csv}")