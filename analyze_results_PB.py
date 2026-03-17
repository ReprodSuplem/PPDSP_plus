import re
import pandas as pd
import numpy as np
import glob
import os

def load_wcnf_stats():
    stats_map = {}
    files = glob.glob("*.wcnf")
    if not files: return stats_map
    pattern = re.compile(r"^([a-z0-9\-]+)_([a-zA-Z0-9\-]+)_r(\d+)v(\d+)k\d+_([A-Z]+)\.wcnf$")
    for fname in files:
        match = pattern.match(fname)
        if match:
            instance, R, T, enc = match.group(2), int(match.group(3)), int(match.group(4)), match.group(5)
            if enc == 'BA': enc = 'AN'
            try:
                with open(fname, 'r') as f:
                    header = f.readline().strip()
                    if header.startswith('p wcnf'):
                        parts = header.split()
                        if len(parts) >= 4:
                            stats_map[(instance, R, T, enc)] = (int(parts[2]), int(parts[3]))
            except: pass
    return stats_map

def parse_logs():
    data = {}
    mip_bounds = {}
    
    # MaxSAT patterns
    vars_pat = re.compile(r"c \|\s+Number of variables:\s+(\d+)")
    cl_pat = re.compile(r"c \|\s+Number of clauses:\s+(\d+)")
    ms_sol_pat = re.compile(r"c Found solution: (\d+)")
    ms_time_pat = re.compile(r"c \[Elapsed time\] ([\d\.]+) s")
    ms_obj_pat = re.compile(r"Objective = ([\d\.-]+)")
    ms_conflicts_pat = re.compile(r"c\s+conflicts\s*:\s+(\d+)")
    ms_up_pat = re.compile(r"c\s+propagations\s*:\s+(\d+)")
    
    # MIP patterns
    mip_elapsed_pat = re.compile(r"Elapsed time\s*=\s*([\d\.]+)\s*sec")
    mip_star_pat = re.compile(r"^\s*\*")
    mip_inc_pat = re.compile(r"Found incumbent of value ([\d\.]+) after ([\d\.]+) sec")
    mip_fobj_pat = re.compile(r"\[CPLEX\] OPTIMAL OBJ:\s*([\d\.\-]+)")
    mip_fobj_alt = re.compile(r"Objective = ([\d\.-]+)")
    mip_ftime_pat = re.compile(r"\[CPLEX\] Runtime:\s*([\d\.]+)")

    log_files = glob.glob("full_experiment_*.log")
    if os.path.exists("full_experiment.log"): 
        if "full_experiment.log" not in log_files: 
            log_files.append("full_experiment.log")
    
    wcnf_map = load_wcnf_stats()

    for log_file in log_files:
        enc_match = re.search(r'full_experiment_([A-Z]+)\.log', log_file)
        current_log_enc = enc_match.group(1) if enc_match else None
        if current_log_enc == 'BA': current_log_enc = 'AN'
        
        with open(log_file, 'r') as f: lines = f.readlines()
            
        current_run = None
        ms_true_obj = None; ms_to = False; ms_tmp_time = 0.0
        mip_last_el = 0.0; mip_to = False; mip_temp_bound = None
        mip_used_sbc = False 
        
        def save_run():
            nonlocal current_run, ms_true_obj, ms_to, mip_to, mip_temp_bound, mip_used_sbc
            if not current_run or not current_run.get('method'): return
            m = current_run['method']
            
            if m == 'maxsat':
                if current_log_enc is None: return 
                current_run['config'] = current_log_enc
                k_wcnf = (current_run['instance'], current_run['R'], current_run['T'], current_log_enc)
                if k_wcnf in wcnf_map:
                    current_run['variables'], current_run['clauses'] = wcnf_map[k_wcnf]
                
                if ms_true_obj is not None:
                    current_run['objective'] = ms_true_obj
                    current_run['status'] = 'Optimal' if not ms_to else 'Feasible'
                else:
                    current_run['objective'] = np.nan
                    current_run['status'] = 'Unsolved'
                current_run['timeout'] = 'Yes' if ms_to else 'No'
                
            elif m == 'mip':
                if mip_used_sbc:
                    return 
                    
                current_run['config'] = 'MIP'
                if ms_true_obj is not None:
                    current_run['objective'] = ms_true_obj
                    current_run['status'] = 'Optimal' if not mip_to else 'Feasible'
                elif pd.notnull(current_run.get('objective')):
                    current_run['status'] = 'Optimal' if not mip_to else 'Feasible'
                else:
                    current_run['objective'] = np.nan
                    current_run['status'] = 'Unsolved'
                current_run['timeout'] = 'Yes' if mip_to else 'No'
                
                if mip_temp_bound is not None:
                    mip_bounds[(current_run['instance'], current_run['R'], current_run['T'])] = mip_temp_bound
                elif pd.notnull(current_run.get('objective')) and not mip_to:
                    mip_bounds[(current_run['instance'], current_run['R'], current_run['T'])] = current_run['objective']
                
            key = (current_run['instance'], current_run['R'], current_run['T'], current_run['config'])
            data[key] = current_run.copy()

        for line in lines:
            line = line.strip()
            if "Running: python main.py" in line:
                save_run()
                current_run = {'method': None, 'instance': None, 'R': None, 'T': None, 'variables': np.nan, 'clauses': np.nan, 'time': np.nan, 'objective': np.nan, 'status': 'Unknown', 'timeout': '?', 'up': np.nan, 'conflicts': np.nan}
                ms_true_obj = None; ms_to = False; ms_tmp_time = 0.0
                mip_last_el = 0.0; mip_to = False; mip_temp_bound = None
                mip_used_sbc = False 
                
                parts = line.split("main.py")[1].strip().split()
                if len(parts) >= 5:
                    if parts[0] == 'mip':
                        current_run['method'] = 'mip'; current_run['instance'] = parts[2]; current_run['R'] = int(parts[3]); current_run['T'] = int(parts[4])
                    else:
                        current_run['method'] = 'maxsat'; current_run['instance'] = parts[2]; current_run['R'] = int(parts[3]); current_run['T'] = int(parts[4])
                continue
            
            if not current_run or not current_run.get('method'): continue
            
            if current_run['method'] == 'maxsat':
                if "Number of variables:" in line:
                    m1 = vars_pat.search(line)
                    if m1: current_run['variables'] = int(m1.group(1))
                if "Number of clauses:" in line:
                    m2 = cl_pat.search(line)
                    if m2: current_run['clauses'] = int(m2.group(1))
                
                if "conflicts" in line:
                    m_conf = ms_conflicts_pat.search(line)
                    if m_conf: current_run['conflicts'] = int(m_conf.group(1))
                if "propagations" in line:
                    m_up = ms_up_pat.search(line)
                    if m_up: current_run['up'] = float(m_up.group(1))
                    
                m3 = ms_time_pat.search(line)
                if m3: ms_tmp_time = float(m3.group(1))
                if "Found solution:" in line: current_run['time'] = ms_tmp_time
                if "Objective =" in line and "PPDSP" not in line:
                    m4 = ms_obj_pat.search(line)
                    if m4: ms_true_obj = float(m4.group(1))
                if "Timeout reached" in line:
                    ms_to = True
                    if pd.isnull(current_run['time']): current_run['time'] = 3600.0
                    
            elif current_run['method'] == 'mip':
                if "[CPLEX] Added" in line and "SBC inequalities." in line:
                    mip_used_sbc = True
                    
                m5 = mip_elapsed_pat.search(line)
                if m5: mip_last_el = float(m5.group(1))
                if mip_star_pat.match(line): current_run['time'] = mip_last_el
                m6 = mip_inc_pat.search(line)
                if m6: current_run['time'] = float(m6.group(2))
                m7 = mip_fobj_pat.search(line)
                if m7: current_run['objective'] = float(m7.group(1))
                m8 = mip_fobj_alt.search(line)
                if m8 and "PPDSP" not in line: ms_true_obj = float(m8.group(1))
                m9 = mip_ftime_pat.search(line)
                if m9:
                    rt = float(m9.group(1))
                    current_run['time'] = rt
                    if rt >= 3599.0: mip_to = True
                if "Timeout reached" in line or "Time limit exceeded" in line:
                    mip_to = True
                    if pd.isnull(current_run['time']): current_run['time'] = 3600.0
                
                if line.endswith('%'):
                    parts = line.split()
                    try:
                        if '.' in parts[-2]: mip_temp_bound = float(parts[-2])
                        elif '.' in parts[-3]: mip_temp_bound = float(parts[-3])
                    except: pass
                    
        save_run() 
        
    return pd.DataFrame(list(data.values())), mip_bounds

if __name__ == "__main__":
    print(">>> Loading SMC Experiment Data...\n")
    df, mip_bounds = parse_logs()
    
    df['objective'] = pd.to_numeric(df['objective'], errors='coerce')
    df['time'] = pd.to_numeric(df['time'], errors='coerce')
    
    w_t, w_o = [], []
    for name, group in df.groupby(['instance', 'R', 'T']):
        v = group.dropna(subset=['objective'])
        if v.empty: continue
        max_obj = v['objective'].max()
        best_cands = v[v['objective'] == max_obj]
        
        if len(best_cands) == 1:
            w_o.extend(best_cands.index.tolist())
        else:
            min_time = best_cands['time'].min()
            winners = best_cands[best_cands['time'] == min_time]
            w_t.extend(winners.index.tolist())

    df['is_winner'] = False
    df.loc[w_t, 'is_winner'] = True
    df.loc[w_o, 'is_winner'] = True

    df['gap'] = np.nan
    for name, group in df.groupby(['instance', 'R', 'T']):
        inst_key = name
        proven_opts = group[group['timeout'] == 'No'].dropna(subset=['objective'])
        if not proven_opts.empty:
            BKB = proven_opts['objective'].max()
        else:
            BKB = mip_bounds.get(inst_key, np.nan)
            
            if pd.isnull(BKB):
                valid_objs = group.dropna(subset=['objective'])
                if not valid_objs.empty: BKB = valid_objs['objective'].max()
        
        if pd.notnull(BKB):
            for idx in group.index:
                obj = df.at[idx, 'objective']
                if pd.notnull(obj) and obj > 0:
                    gap = ((BKB - obj) / obj) * 100.0
                    df.at[idx, 'gap'] = max(0.0, gap) 

    print("\n[Optimal Solutions (Out of 30)]")
    for c in sorted(df['config'].unique()): print(f" - {c:<5}: {len(df[(df['config']==c) & (df['timeout']=='No')])}")
        
    print("\n[Total Wins (Best Objective or Fastest Time)]")
    for c in sorted(df['config'].unique()): print(f" - {c:<5}: {len(df[(df['config']==c) & (df['is_winner']==True)])}")
    
    print("\n[Average Formula Size Across Instances]")
    size_df = df[df['config'] != 'MIP'].groupby('config')[['variables', 'clauses']].mean().reset_index()
    for _, row in size_df.iterrows():
        if pd.notnull(row['variables']):
            print(f" - {row['config']:<5} -> Variables: {int(row['variables']):<8} | Clauses: {int(row['clauses'])}")

    print("\n[Average Propagation Efficiency Across Instances]")
    uc_df = df[df['config'] != 'MIP'].groupby('config')[['up', 'conflicts']].mean().reset_index()
    for _, row in uc_df.iterrows():
        if pd.notnull(row['up']) and pd.notnull(row['conflicts']):
            # up的数字较大，所以给15位占位符以确保对齐美观
            print(f" - {row['config']:<5} -> UP: {int(row['up']):<15} | Conflicts: {int(row['conflicts'])}")

    df['time'] = df['time'].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "")
    df['gap'] = df['gap'].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "")
    df['objective'] = df['objective'].apply(lambda x: f"{int(x)}" if pd.notnull(x) else "")
    df['up'] = df['up'].apply(lambda x: f"{int(x)}" if pd.notnull(x) else "")
    df['conflicts'] = df['conflicts'].apply(lambda x: f"{int(x)}" if pd.notnull(x) else "")
    
    for i in w_t: df.at[i, 'time'] = str(df.at[i, 'time']) + "*"
    for i in w_o: df.at[i, 'objective'] = str(df.at[i, 'objective']) + "*"

    df.rename(columns={'R': '|R|', 'T': '|T|'}, inplace=True)
    instance_order = ['burma14', 'ulysses22', 'bays29', 'P-n16-k8', 'P-n23-k8', 'A-n32-k5']
    df['instance'] = pd.Categorical(df['instance'], categories=instance_order, ordered=True)
    df = df.sort_values(by=['instance', '|R|', '|T|', 'config'])
    
    final_cols = ['instance', '|R|', '|T|', 'method', 'config', 'variables', 'clauses', 'timeout', 'status', 'objective', 'time', 'up', 'conflicts', 'gap']
    df = df[final_cols]
    
    csv_name = 'experiment_results_PB.csv'
    df.to_csv(csv_name, index=False)
    print(f"\n[Success] Output formatted strictly to requirements and saved to {csv_name}")