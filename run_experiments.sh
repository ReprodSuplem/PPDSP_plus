#!/bin/bash

# ==============================================================================
# 实验配置区域
# ==============================================================================
# MaxSAT 编码列表 (p1-p6)
# p1: Totalizer + BDD
# p2: Direct + BDD
# p3: Order + BDD
# p4: Order + Lazy
# p5: Direct + Lazy
# p6: Totalizer + Lazy
MAXSAT_ENCS="p1 p2 p3 p4 p5 p6"

# MIP 编码列表
MIP_ENCS="p1"

# 图密度列表 (3=稀疏, 5=中等, 0=完全图) K_LIST="3 5 0"
# 如果只想跑稀疏图，可以改为: K_LIST="3"
K_LIST="3"

# ==============================================================================
# 工具函数
# ==============================================================================

run_cmd() {
    echo "========================================================"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running: $@"
    "$@"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] finished"
}

check_and_run_maxsat() {
    enc=$1; inst=$2; r=$3; v=$4; k=$5
    outfile="${enc}_${inst}_r${r}v${v}k${k}-SBC.wcnf.out"
    if [ -s "$outfile" ]; then
        echo "[SmartSkip] $outfile already exists. Skipping..."
    else
        run_cmd python main.py maxsat $enc $inst $r $v $k
    fi
}

check_and_run_mip() {
    enc=$1; inst=$2; r=$3; v=$4; k=$5
    outfile="${enc}_${inst}_r${r}v${v}k${k}+SBC.lp.out"
    if [ -s "$outfile" ]; then
        echo "[SmartSkip] $outfile already exists. Skipping..."
    else
        run_cmd python main.py mip $enc $inst $r $v $k
    fi
}

run_batch() {
    inst=$1
    # 接收剩余参数作为配对列表，格式为 "r v"
    shift
    pairs=("$@")

    echo ">>> Starting Benchmarks for: $inst"
    
    # 遍历每一个 (r, v) 配对
    for pair in "${pairs[@]}"; do
        # 读取 r and v
        set -- $pair
        r=$1
        v=$2
        
        echo "Processing $inst | Request=$r | Vehicle=$v"
        
        # 遍历 k
        for k in $K_LIST; do
            # 1. Run MaxSAT (p1 - p6)
            for enc in $MAXSAT_ENCS; do
                check_and_run_maxsat $enc $inst $r $v $k
            done
            
            # 2. Run MIP (p1)
            for enc in $MIP_ENCS; do
                check_and_run_mip $enc $inst $r $v $k
            done
        done
    done
    echo ">>> Finished Benchmarks for: $inst"
    echo ""
}

# ==============================================================================
# 主执行逻辑
# ==============================================================================

echo "Starting Experiments..."

# 1. Burma14 Pairs: (7, 2), (10, 2), (13, 3), (16, 3), (19, 4)
# 注意：最后一个是 19, 4 (根据之前修正的文件名逻辑)
#run_batch "burma14" \
#    "7 2" \
#    "10 2" \
#    "13 3" \
#    "16 3" \
#    "19 4"

# 2. Ulysses22 Pairs: (11, 2), (16, 3), (21, 4), (26, 5), (31, 5)
#run_batch "ulysses22" \
#    "11 2" \
#    "16 3" \
#    "21 4" \
#    "26 5" \
#    "31 5"

# 3. Bays29 Pairs: (14, 3), (21, 4), (28, 6), (35, 7), (42, 8)
#run_batch "bays29" \
#    "14 3" \
#    "21 4" \
#    "28 6" \
#    "35 7" \
#    "42 8"

# 4. P-n16-k8 Pairs: (8, 2), (11, 3), (15, 3), (19, 4), (22, 5)
#run_batch "P-n16-k8" \
#    "8 2" \
#    "11 3" \
#    "15 3" \
#    "19 4" \
#    "22 5"

# 5. P-n23-k8 Pairs: (11, 2), (17, 3), (22, 4), (28, 5), (33, 6)
#run_batch "P-n23-k8" \
#    "11 2" \
#    "17 3" \
#    "22 4" \
#    "28 5" \
#    "33 6"

# 6. A-n32-k5 Pairs: (16, 3), (23, 5), (31, 6), (39, 7), (46, 9)
#run_batch "A-n32-k5" \
#    "16 3" \
#    "23 5" \
#    "31 6" \
#    "39 7" \
#    "46 9"

# 1. Burma14 (Only 19 4 active)
run_batch "burma14" "19 4"

# 2. Ulysses22 (21 4, 26 5, 31 5 active)
run_batch "ulysses22" "21 4" "26 5" "31 5"

# 3. Bays29 (21 4, 28 6, 35 7, 42 8 active)
run_batch "bays29" "21 4" "28 6" "35 7" "42 8"

# 4. P-n16-k8 (19 4, 22 5 active)
run_batch "P-n16-k8" "19 4" "22 5"

# 5. P-n23-k8 (22 4, 28 5, 33 6 active)
run_batch "P-n23-k8" "22 4" "28 5" "33 6"

# 6. A-n32-k5 (23 5, 31 6, 39 7, 46 9 active)
run_batch "A-n32-k5" "23 5" "31 6" "39 7" "46 9"

echo "All Experiments Completed Successfully."