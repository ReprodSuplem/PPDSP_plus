set display verblevel 0
set timing enabled FALSE
read "/home/zha/exp/PPDSP_plus/UWrMaxSat-SCIP-MaxPre/code/scipoptsuite-8.1.0/scip"/check/"instances/SAT/bart10.shuffled.cnf"
optimize
write statistics temp/bart10.shuffled.cnf_r1.stats
read "/home/zha/exp/PPDSP_plus/UWrMaxSat-SCIP-MaxPre/code/scipoptsuite-8.1.0/scip"/check/"instances/SAT/bart10.shuffled.cnf"
optimize
write statistics temp/bart10.shuffled.cnf_r2.stats
quit
