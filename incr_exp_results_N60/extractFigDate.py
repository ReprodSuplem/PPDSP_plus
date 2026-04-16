import pandas as pd
import numpy as np
import re
import os

# 1. 提取 N=60 增量数据与全局最优值 (BKB_N)
df = pd.read_csv('incr_exp_results_N60.csv')
BKB_N = df[df['config'] == 'Mono-SAT']['objective'].max()

def calc_gap(obj):
    if obj <= 0: return None
    gap = (BKB_N - obj) / obj * 100
    return max(gap, 0.01) # 限制最小值为0.01，防止对数坐标轴崩溃

configs = ['PhG-Cpx', 'PhG-Uni', 'Asm-Cpx', 'Asm-Uni', 'MIP-Cpx', 'MIP-Uni']
data = {}

for cfg in configs:
    sub = df[df['config'] == cfg].sort_values('stage')
    cum_time = 0.0
    t_list, g_list = [], []
    
    for _, row in sub.iterrows():
        cum_time += float(row['consumed']) if pd.notna(row['consumed']) else 0.0
        gap_str = str(row['gap_N']).replace('%', '')
        gap = float(gap_str) if gap_str.strip() != 'nan' else 0.0
        
        t_list.append(round(cum_time, 2))
        g_list.append(max(gap, 0.01))
    
    safe_cfg = cfg.replace('-', '')
    data[f'time_{safe_cfg}'] = t_list
    data[f'gap_{safe_cfg}'] = g_list

# 2. 智能解析 Mono-SAT
if os.path.exists('Mono-SAT.log'):
    with open('Mono-SAT.log', 'r') as f:
        sat_content = f.read()

    offset_match = re.search(r'Found solution:\s*(\d+)', sat_content)
    offset = int(offset_match.group(1)) if offset_match else 0

    sat_pts = []
    matches = re.finditer(r'\[Elapsed time\]\s*([\d\.]+)\s*s.*?\n.*?Found solution:\s*(\d+)', sat_content)
    for m in matches:
        t = float(m.group(1))
        obj = offset - int(m.group(2))
        g = calc_gap(obj)
        if g is not None: sat_pts.append((t, g))

    cpu_time_match = re.search(r'CPU time\s*:\s*([\d\.]+)\s*s', sat_content)
    sat_final_time = float(cpu_time_match.group(1)) if cpu_time_match else 3600.0

    if sat_pts: sat_pts.append((sat_final_time, sat_pts[-1][1]))
    data['time_MonoSAT'] = [p[0] for p in sat_pts]
    data['gap_MonoSAT'] = [p[1] for p in sat_pts]

# 3. 智能解析 Mono-MIP
if os.path.exists('Mono-MIP.log'):
    with open('Mono-MIP.log', 'r') as f:
        mip_content = f.read()

    mip_pts = []
    lines = mip_content.split('\n')
    last_time = 0.0

    for line in lines:
        m_time = re.search(r'Elapsed time =\s*([\d\.]+)\s*sec', line)
        if m_time: last_time = float(m_time.group(1))
        
        m_inc = re.search(r'after\s*([\d\.]+)\s*sec', line)
        if m_inc: last_time = float(m_inc.group(1))
        
        m_star = re.search(r'^\s*\*\s*\d+\+?\s*\d+\s+([\d\.]+)', line)
        if m_star:
            val = float(m_star.group(1))
            g = calc_gap(val)
            if g is not None: mip_pts.append((last_time, g))
            continue
        
        m_found = re.search(r'Found incumbent of value ([\d\.]+) after ([\d\.]+) sec', line)
        if m_found:
            val = float(m_found.group(1))
            t = float(m_found.group(2))
            g = calc_gap(val)
            if g is not None: mip_pts.append((t, g))
            last_time = t

    mip_time_match = re.search(r'Solution time =\s*([\d\.]+)\s*sec', mip_content)
    mip_final_time = float(mip_time_match.group(1)) if mip_time_match else 3600.0
    if mip_pts: mip_pts.append((mip_final_time, mip_pts[-1][1]))

    data['time_MonoMIP'] = [p[0] for p in mip_pts]
    data['gap_MonoMIP'] = [p[1] for p in mip_pts]

# 4. 对齐并输出 LaTeX 可读格式 (用 nan 填充空白)
max_len = max(len(v) for v in data.values())
for k in data.keys():
    while len(data[k]) < max_len:
        data[k].append(np.nan)

out_df = pd.DataFrame(data)
out_file = 'cactus_plot_data.txt'
out_df.to_csv(out_file, sep='\t', index=False, na_rep='nan')
print(f"成功生成供 TikZ 使用的数据文件：{out_file}")