#!/bin/bash

# 定义运行函数
run_cmd() {
    echo "========================================================"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running: $@"
    "$@"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] finished"
}

# ==============================================================================
# 智能检测函数
# 检查结果文件是否存在，如果存在则跳过，否则运行
# ==============================================================================

# 检查并运行 MaxSAT
check_and_run_maxsat() {
    enc=$1; inst=$2; r=$3; v=$4; k=$5
    
    # 构建预期的输出文件名
    # 例如: p1_bayg29_r21v4k5.wcnf.out
    # 注意：这里假设 main.py 生成的文件名格式与你展示的 ls 结果一致
    outfile="${enc}_${inst}_r${r}v${v}k${k}.wcnf.out"
    
    # [ -s file ] 检查文件是否存在且大小大于0
    if [ -s "$outfile" ]; then
        echo "[SmartSkip] $outfile already exists. Skipping..."
    else
        run_cmd python main.py maxsat $enc $inst $r $v $k
    fi
}

# 检查并运行 MIP
check_and_run_mip() {
    enc=$1; inst=$2; r=$3; v=$4; k=$5
    
    # 构建预期的输出文件名
    # 例如: p1_bayg29_r21v4k5.lp.out
    outfile="${enc}_${inst}_r${r}v${v}k${k}.lp.out"
    
    if [ -s "$outfile" ]; then
        echo "[SmartSkip] $outfile already exists. Skipping..."
    else
        run_cmd python main.py mip $enc $inst $r $v $k
    fi
}

# ==============================================================================
# 0. 强制清理崩溃点 (Bayg29, r=21, v=4, k=3, MIP)
# ==============================================================================
echo "Cleaning up crash point..."
# 强制删除这个特定的 .out 文件，确保它一定会被重跑
rm -f p1_bayg29_r21v4k3.lp.out
echo "Removed p1_bayg29_r21v4k3.lp.out (if existed) to force re-run."


# ==============================================================================
# 1. 恢复 Bayg29 (从 r=21 开始扫描)
#    注意：r=14 已经完全跑完，所以这里循环从 21 开始
# ==============================================================================
echo "Scanning Bayg29 Experiments..."

# Request: 21, 28, 35, 42
for r in 21 28 35 42; do
    # Vehicle: 4, 6, 8
    for v in 4 6 8; do
        # K: 3, 5, 0
        for k in 3 5 0; do
            
            # 1. Check & Run MaxSAT (p1-p4)
            for enc in p1 p2 p3 p4; do
                check_and_run_maxsat $enc bayg29 $r $v $k
            done
            
            # 2. Check & Run MIP (p1)
            check_and_run_mip p1 bayg29 $r $v $k
            
        done
    done
done


# ==============================================================================
# 2. 运行 Berlin52 (全部扫描)
# ==============================================================================
echo "Scanning Berlin52 Experiments..."

# Request: 26, 38, 51, 64, 77
for r in 26 38 51 64 77; do
    # Vehicle: 7, 10, 14
    for v in 7 10 14; do
        # K: 3, 5, 0
        for k in 3 5 0; do
            
            # 1. Check & Run MaxSAT
            for enc in p1 p2 p3 p4; do
                check_and_run_maxsat $enc berlin52 $r $v $k
            done
            
            # 2. Check & Run MIP
            check_and_run_mip p1 berlin52 $r $v $k
            
        done
    done
done

echo "All Smart Resumed Experiments Completed."