set display verblevel 0
set timing enabled FALSE
read "/home/zha/exp/PPDSP_plus/UWrMaxSat-SCIP-MaxPre/code/scipoptsuite-8.1.0/scip"/check/"instances/MINLP/circle.lp"
optimize
write statistics temp/circle.lp_r1.stats
read "/home/zha/exp/PPDSP_plus/UWrMaxSat-SCIP-MaxPre/code/scipoptsuite-8.1.0/scip"/check/"instances/MINLP/circle.lp"
optimize
write statistics temp/circle.lp_r2.stats
quit
