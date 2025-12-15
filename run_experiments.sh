#!/bin/bash

run_cmd() {
    echo "========================================================"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running: $@"
    "$@"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] finished"
}

# ========================================================
# TSPLIB: Burma14
# Request: 7, 10, 13, 16, 20
# Vehicle: 2, 3, 4
# K: 3, 5, 0
# ========================================================
echo "Starting Burma14 Experiments..."

for r in 7 10 13 16 20; do
    for v in 2 3 4; do
        for k in 3 5 0; do
            # 1. Run MaxSAT (p1, p2, p3, p4)
            for enc in p1 p2 p3 p4; do
                run_cmd python main.py maxsat $enc burma14 $r $v $k
            done
            
            # 2. Run MIP (p1)
            run_cmd python main.py mip p1 burma14 $r $v $k
        done
    done
done


# ========================================================
# TSPLIB: Bayg29
# Request: 14, 21, 28, 35, 42
# Vehicle: 4, 6, 8
# K: 3, 5, 0
# ========================================================
echo "Starting Bayg29 Experiments..."

for r in 14 21 28 35 42; do
    for v in 4 6 8; do
        for k in 3 5 0; do
            # 1. Run MaxSAT (p1, p2, p3, p4)
            for enc in p1 p2 p3 p4; do
                run_cmd python main.py maxsat $enc bayg29 $r $v $k
            done
            
            # 2. Run MIP (p1)
            run_cmd python main.py mip p1 bayg29 $r $v $k
        done
    done
done


# ========================================================
# TSPLIB: Berlin52
# Request: 26, 38, 51, 64, 77
# Vehicle: 7, 10, 14
# K: 3, 5, 0
# ========================================================
echo "Starting Berlin52 Experiments..."

for r in 26 38 51 64 77; do
    for v in 7 10 14; do
        for k in 3 5 0; do
            # 1. Run MaxSAT (p1, p2, p3, p4)
            for enc in p1 p2 p3 p4; do
                run_cmd python main.py maxsat $enc berlin52 $r $v $k
            done
            
            # 2. Run MIP (p1)
            run_cmd python main.py mip p1 berlin52 $r $v $k
        done
    done
done

echo "All experiments completed."