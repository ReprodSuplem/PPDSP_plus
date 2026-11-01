import os
import glob
import re
import pandas as pd

def get_reach_time(block, method, fallback_time):
    """
    核心黑科技：提取到达最优解时的真实收敛时间，忽略后面的停滞浪费时间。
    """
    reach_time = None
    if method == 'maxsat':
        # 1. 优先提取最后一个 [Elapsed time]
        times = re.findall(r'\[Elapsed time\]\s*([\d\.]+)\s*s', block)
        if times:
            reach_time = float(times[-1])
        else:
            # 2. 兜底抓取 MaxSAT 的 CPU time
            cpu_times = re.findall(r'CPU time\s*:\s*([\d\.]+)\s*s', block)
            if cpu_times:
                reach_time = float(cpu_times[-1])
                
    elif method == 'mip':
        # CPLEX: 匹配行首可选空白后紧跟 '*' 的行（忽略星号后是否有空格）
        last_star_matches = list(re.finditer(r'^\s*\*', block, re.MULTILINE))
        
        # 统一匹配 CPLEX 打印时间的两种格式: 'Elapsed time = XXX sec' 或 'after XXX sec'
        time_pattern = r'(?:Elapsed time =|after)\s*([\d\.]+)\s*sec'
        
        if last_star_matches:
            last_pos = last_star_matches[-1].start()
            # 在最后一个星号行之前寻找最近的时间打印
            time_matches = list(re.finditer(time_pattern, block[:last_pos]))
            if time_matches:
                reach_time = float(time_matches[-1].group(1))
        else:
            # 如果压根没有 * 行，直接找全文最后一个时间
            time_matches = list(re.finditer(time_pattern, block))
            if time_matches:
                reach_time = float(time_matches[-1].group(1))
                
    return reach_time if reach_time is not None else fallback_time

def parse_mono_log(filepath):
    filename = os.path.basename(filepath)
    config = filename.replace('.log', '')
    method = 'mip' if 'MIP' in config else 'maxsat'
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    obj = None
    dual_bound = None
    total_cpu_time = None
    timeout = "No"
    status = "Unsolved"
    restarts = ""
    conflicts = ""

    obj_match = re.search(r'======== PPDSP OBJECTIVE ========.*?Objective\s*=\s*(\d+)', content, re.DOTALL)
    if obj_match:
        obj = int(obj_match.group(1))
        status = "Feasible"

    if method == 'mip':
        time_match = re.search(r'Solution time =\s*([\d\.]+)\s*sec', content)
        if time_match:
            total_cpu_time = float(time_match.group(1))
            
        if "Time limit exceeded" in content or (total_cpu_time and total_cpu_time >= 3599):
            timeout = "Yes"
        else:
            status = "Optimal" if obj else "Unsolved"
            
        bound_match = re.search(r'(?:best bound|Best bound)\s*=\s*([\d\.]+)', content, re.IGNORECASE)
        if bound_match:
            dual_bound = float(bound_match.group(1))
        elif status == "Optimal" and obj is not None:
            dual_bound = float(obj)
            
    else: # maxsat
        if re.search(r'Optimal solution:', content):
            status = "Optimal"
            dual_bound = float(obj) if obj else None
        elif obj:
            dual_bound = float(obj)
                
        time_match = re.search(r'CPU time\s*:\s*([\d\.]+)\s*s', content)
        if time_match:
            total_cpu_time = float(time_match.group(1))
            
        if "Timeout reached" in content or (total_cpu_time and total_cpu_time >= 3599):
            timeout = "Yes"
            
        res_matches = re.findall(r'c restarts\s*:\s*(\d+)', content, re.IGNORECASE)
        if res_matches: restarts = int(res_matches[-1])
        
        conf_matches = re.findall(r'c conflicts\s*:\s*(\d+)', content, re.IGNORECASE)
        if conf_matches: conflicts = int(conf_matches[-1])
        
    reach_time = get_reach_time(content, method, total_cpu_time)
            
    return {
        'stage': 'Final',
        '(|R|,|T|,|k|)': None,
        'method': method,
        'config': config,
        'tLimit': 3600.0,
        'consumed': round(total_cpu_time, 2) if total_cpu_time else None,
        'timeout': timeout,
        'status': status,
        'objective': obj,
        'dual_bound': dual_bound,
        'time': round(reach_time, 2) if reach_time else None,
        'restarts': restarts,
        'conflicts': conflicts
    }

def parse_incremental_log(filepath):
    filename = os.path.basename(filepath)
    config = filename.replace('.log', '')
    method = 'mip' if 'MIP' in config else 'maxsat'
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    maxsat_cpp_blocks = {}
    if method == 'maxsat':
        meta_pattern = re.compile(r'\[UWrMaxSAT\] meta file: .*?_r(\d+)v(\d+)k(\d+)\.meta')
        meta_matches = list(meta_pattern.finditer(content))
        for i in range(len(meta_matches)):
            m = meta_matches[i]
            r, v, k = int(m.group(1)), int(m.group(2)), int(m.group(3))
            start_pos = m.start()
            end_pos = meta_matches[i+1].start() if i+1 < len(meta_matches) else len(content)
            maxsat_cpp_blocks[(r, v, k)] = content[start_pos:end_pos]

    rows = []
    stage_pattern = re.compile(r'^\[(\d+)/\d+\] Building & Solving: R=(\d+), V=(\d+), K=(\d+)', re.MULTILINE)
    py_matches = list(stage_pattern.finditer(content))
    
    for i in range(len(py_matches)):
        match = py_matches[i]
        stage_idx = int(match.group(1))
        r, v, k = int(match.group(2)), int(match.group(3)), int(match.group(4))
        
        start_pos = match.start()
        end_pos = py_matches[i+1].start() if i+1 < len(py_matches) else len(content)
        py_block = content[start_pos:end_pos]
        
        budget_match = re.search(r'Recalibrated Budget for this step:\s*([\d\.]+)s', py_block)
        budget = float(budget_match.group(1)) if budget_match else None
        
        time_match = re.search(r'Step \d+ consumed ([\d\.]+)s', py_block)
        total_cpu_time = float(time_match.group(1)) if time_match else None
        
        timeout = "No"
        status = "Unsolved"
        obj = None
        dual_bound = None
        restarts = ""
        conflicts = ""
        
        obj_match = re.search(r'======== PPDSP OBJECTIVE ========.*?Objective\s*=\s*(\d+)', py_block, re.DOTALL)
        if obj_match:
            obj = int(obj_match.group(1))
            status = "Feasible"
            
        cpp_block = maxsat_cpp_blocks.get((r, v, k), "") if method == 'maxsat' else ""
        
        # 如果外层没抓到时间，使用底层作为备用
        if total_cpu_time is None:
            if method == 'maxsat':
                cpu_match = re.findall(r'CPU time\s*:\s*([\d\.]+)\s*s', cpp_block)
                if cpu_match: total_cpu_time = float(cpu_match[-1])
            elif method == 'mip':
                sol_match = re.findall(r'Solution time =\s*([\d\.]+)\s*sec', py_block)
                if sol_match: total_cpu_time = float(sol_match[-1])
        
        if method == 'mip':
            if "Time limit exceeded" in py_block or (total_cpu_time and budget and total_cpu_time >= budget - 0.5):
                timeout = "Yes"
            else:
                status = "Optimal" if obj else "Unsolved"
                
            bound_match = re.search(r'(?:best bound|Best bound)\s*=\s*([\d\.]+)', py_block, re.IGNORECASE)
            if bound_match:
                dual_bound = float(bound_match.group(1))
            elif status == "Optimal" and obj is not None:
                dual_bound = float(obj)
                
            reach_time = get_reach_time(py_block, method, total_cpu_time)
                
        else: # maxsat
            if re.search(r'Optimal solution:', cpp_block) or re.search(r'Optimal solution:', py_block):
                status = "Optimal"
                dual_bound = float(obj) if obj else None
            elif obj:
                dual_bound = float(obj)
                    
            if "Timeout reached" in cpp_block or "Timeout reached" in py_block or (total_cpu_time and budget and total_cpu_time >= budget - 0.5):
                timeout = "Yes"
                
            res_matches = re.findall(r'c restarts\s*:\s*(\d+)', cpp_block, re.IGNORECASE)
            if res_matches: restarts = int(res_matches[-1])
            
            conf_matches = re.findall(r'c conflicts\s*:\s*(\d+)', cpp_block, re.IGNORECASE)
            if conf_matches: conflicts = int(conf_matches[-1])
                
            reach_time = get_reach_time(cpp_block, method, total_cpu_time)
                
        if "Extraction failed" in py_block:
            status = "Failed"

        rows.append({
            'stage': stage_idx,
            '(|R|,|T|,|k|)': f"({r},{v},{k})",
            'method': method,
            'config': config,
            'tLimit': round(budget, 2) if budget else None,
            'consumed': round(total_cpu_time, 2) if total_cpu_time else None,
            'timeout': timeout,
            'status': status,
            'objective': obj,
            'dual_bound': dual_bound,
            'time': round(reach_time, 2) if reach_time else None,
            'restarts': restarts,
            'conflicts': conflicts 
        })
                
    return rows

if __name__ == "__main__":
    log_dir = "incr_exp_results_N6" 
    if not os.path.exists(log_dir):
        log_dir = "."
        
    all_data = []
    log_files = glob.glob(os.path.join(log_dir, "*.log"))
    
    for filepath in log_files:
        if "Mono" in filepath:
            row = parse_mono_log(filepath)
            all_data.append(row)
        else: 
            rows = parse_incremental_log(filepath)
            all_data.extend(rows)

    if not all_data:
        print(f"未找到任何有效日志文件，请确保执行路径包含 {log_dir} 文件夹。")
        exit(1)

    df = pd.DataFrame(all_data)
    
    max_stage = df[df['stage'] != 'Final']['stage'].max()
    
    final_stage_rtk = ""
    target_rows = df[df['stage'] == max_stage]
    if not target_rows.empty:
        final_stage_rtk = target_rows.iloc[0]['(|R|,|T|,|k|)']
    
    df.loc[df['stage'] == 'Final', '(|R|,|T|,|k|)'] = final_stage_rtk

    df['stage_num'] = df['stage'].apply(lambda x: max_stage if x == 'Final' else x)
    df['stage'] = df['stage_num'].astype(int)
    
    stage_bkb = {}
    for stage_val in df['stage_num'].unique():
        sub_df = df[df['stage_num'] == stage_val]
        has_optimal = (sub_df['status'] == 'Optimal').any()
        
        max_obj = sub_df['objective'].max()
        max_bound = sub_df['dual_bound'].max()
        
        if has_optimal:
            bkb = max_obj
        else:
            bkb = max(max_obj if pd.notna(max_obj) else 0, max_bound if pd.notna(max_bound) else 0)
            if bkb == 0: bkb = None
            
        stage_bkb[stage_val] = bkb
    
    bkb_N = stage_bkb.get(max_stage, None)
    
    def calc_gap(row_obj, bkb):
        if pd.isna(row_obj) or bkb is None or row_obj == 0: return ""
        gap = (bkb - float(row_obj)) / float(row_obj) * 100
        return f"{max(0, gap):.2f}%"

    df['gap'] = df.apply(lambda r: calc_gap(r['objective'], stage_bkb.get(r['stage_num'])), axis=1)
    df['gap_N'] = df.apply(lambda r: calc_gap(r['objective'], bkb_N), axis=1)

    df.sort_values(by=['stage_num', 'config'], inplace=True)
    
    columns_order = [
        'stage', '(|R|,|T|,|k|)', 'method', 'config', 
        'tLimit', 'consumed', 'timeout', 'status', 'objective', 
        'time', 'restarts', 'conflicts', 'gap', 'gap_N'
    ]
    
    df_out = df[columns_order]
    
    output_csv = "incr_exp_results_N6.csv"
    df_out.to_csv(output_csv, index=False)
    print(f"数据提取与分析完成！结果已保存至: {output_csv}")