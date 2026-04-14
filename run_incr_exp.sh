#!/bin/bash

# ==============================================================================
# PPDSP Experimental Batch Script
# 包含：Monolithic Baselines, MIP/PhG Incremental, 和 Asm Incremental
# chmod +x run_incr_exp.sh
# tmux new -s ppdsp_exp
# ./run_incr_exp.sh
# tmux attach -t ppdsp_exp (see logs in real-time)
# ==============================================================================

# 1. 全局配置
INSTANCE="A-n32-k5"
# 完整的 Stage 序列 (60个 stages)
SEQ="4,2,2 5,2,2 6,2,2 7,2,2 8,2,2 9,2,2 10,2,2 11,2,2 11,3,2 12,3,2 13,3,2 14,3,2 15,3,2 16,3,2 17,3,2 18,3,2 18,4,2 19,4,2 20,4,2 21,4,2 22,4,2 23,4,2 24,4,2 24,5,2 24,5,3 25,5,3 26,5,3 27,5,3 28,5,3 29,5,3 30,5,3 30,6,3 31,6,3 32,6,3 33,6,3 34,6,3 35,6,3 36,6,3 36,7,3 37,7,3 38,7,3 39,7,3 40,7,3 41,7,3 42,7,3 42,8,3 43,8,3 44,8,3 45,8,3 46,8,3 47,8,3 48,8,3 48,9,3 49,9,3 50,9,3 51,9,3 52,9,3 53,9,3 53,9,4 54,9,4"

# 最终阶段的参数 (用于 Mono Baselines)
FINAL_R=54
FINAL_V=9
FINAL_K=4

# 创建日志文件夹
LOG_DIR="logs_experiment"
mkdir -p $LOG_DIR

echo "======================================================================"
echo "  [Phase 1] 开始执行 Baseline 和 Phase-Guided 实验"
echo "======================================================================"

# 1. Mono-MIP (直接解最终状态)
echo ">>> Running Mono-MIP ..."
python main.py mip p1 $INSTANCE $FINAL_R $FINAL_V $FINAL_K 2>&1 | tee $LOG_DIR/Mono-MIP.log

# 2. Mono-SAT (直接解最终状态)
echo ">>> Running Mono-SAT ..."
python main.py maxsat p4 $INSTANCE $FINAL_R $FINAL_V $FINAL_K 2>&1 | tee $LOG_DIR/Mono-SAT.log

# 3. MIP-Uni
echo ">>> Running MIP-Uni ..."
python incr.py mip p1 $INSTANCE uni $SEQ 2>&1 | tee $LOG_DIR/MIP-Uni.log

# 4. PhG-Uni (Phase-Guided, 使用现在的 MsSolver.cc setPolarity 编译版本)
echo ">>> Running PhG-Uni ..."
python incr.py maxsat p4 $INSTANCE uni $SEQ 2>&1 | tee $LOG_DIR/PhG-Uni.log

# 5. MIP-Cpx
echo ">>> Running MIP-Cpx ..."
python incr.py mip p1 $INSTANCE cpx $SEQ 2>&1 | tee $LOG_DIR/MIP-Cpx.log

# 6. PhG-Cpx (Phase-Guided)
echo ">>> Running PhG-Cpx ..."
python incr.py maxsat p4 $INSTANCE cpx $SEQ 2>&1 | tee $LOG_DIR/PhG-Cpx.log

echo ""
echo "======================================================================"
echo "  [PAUSE] Phase 1 已经全部完成！"
echo "======================================================================"
echo "警告: 接下来的实验是 Asm-Uni 和 Asm-Cpx。"
echo "请打开另一个终端窗口，完成以下操作："
echo "  1. 把 UWrMaxSAT 的 MsSolver.cc 恢复成旧的 Assumption (Hard Lock) 代码："
echo "     即使用 assump_ps.push(ppdsp_assumps[i])"
echo "  2. 重新 make 编译 UWrMaxSAT 并确保生效。"
echo "======================================================================"

# 暂停脚本，等待用户按回车键
read -p "如果您已经重新编译完成了 UWrMaxSAT，请按 [Enter] 键继续执行 Phase 2..."

echo ""
echo "======================================================================"
echo "  [Phase 2] 开始执行 Assumption-Based (Hard Lock) 实验"
echo "======================================================================"

# 7. Asm-Uni
echo ">>> Running Asm-Uni ..."
python incr.py maxsat p4 $INSTANCE uni $SEQ 2>&1 | tee $LOG_DIR/Asm-Uni.log

# 8. Asm-Cpx
echo ">>> Running Asm-Cpx ..."
python incr.py maxsat p4 $INSTANCE cpx $SEQ 2>&1 | tee $LOG_DIR/Asm-Cpx.log

echo "======================================================================"
echo "  所有 8 组实验已全部运行完毕！日志已保存在 $LOG_DIR/ 目录下。"
echo "======================================================================"