set heur emph off
read "/home/zha/exp/PPDSP_plus/UWrMaxSat-SCIP-MaxPre/code/scipoptsuite-8.1.0/scip"/check/"instances/MIP/blend2.mps"
write problem temp/blend2.mps.lp
presolve
write transproblem temp/blend2.mps_trans.lp
set heur emph def
read temp/blend2.mps_trans.lp
optimize
validatesolve "7.598985" "7.598985"
read temp/blend2.mps.lp
optimize
validatesolve "7.598985" "7.598985"
quit
