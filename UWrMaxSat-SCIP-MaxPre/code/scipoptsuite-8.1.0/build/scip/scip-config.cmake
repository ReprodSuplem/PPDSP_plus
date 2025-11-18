if(NOT TARGET libscip)
  include("${CMAKE_CURRENT_LIST_DIR}/scip-targets.cmake")
endif()

if()
   set(ZIMPL_DIR "")
   find_package(ZIMPL QUIET CONFIG)
endif()

if(1)
   set(SOPLEX_DIR "/home/zha/exp/PPDSP_plus/UWrMaxSat-SCIP-MaxPre/code/scipoptsuite-8.1.0/build")
   find_package(SOPLEX QUIET CONFIG)
endif()

set(SCIP_LIBRARIES libscip)
set(SCIP_INCLUDE_DIRS "/home/zha/exp/PPDSP_plus/UWrMaxSat-SCIP-MaxPre/code/scipoptsuite-8.1.0/scip/src;/home/zha/exp/PPDSP_plus/UWrMaxSat-SCIP-MaxPre/code/scipoptsuite-8.1.0/build/scip")
set(SCIP_FOUND TRUE)
