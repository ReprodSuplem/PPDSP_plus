set heur emph off
read "/home/zha/exp/PPDSP_plus/UWrMaxSat-SCIP-MaxPre/code/scipoptsuite-8.1.0/scip"/check/"instances/MIP/stein27_inf.lp"
write problem temp/stein27_inf.lp.mps
presolve
write transproblem temp/stein27_inf.lp_trans.mps
set heur emph def
read temp/stein27_inf.lp_trans.mps
optimize
validatesolve "+infinity" "+infinity"
read temp/stein27_inf.lp.mps
optimize
validatesolve "+infinity" "+infinity"
quit
