#include "PPDSP_utils.h"
#include <iostream>
#include <cassert>
using namespace std;

#include <fstream>

void PPDSP_utils::buildVarIndexMap(PPDSP_Instance* inst)
{
    inst->id2Var.clear();
    // xVars
    for (int t=0; t < inst->lenOfVehicle; t++){
        for (size_t o=0; o < inst->xVarList[t].size(); o++){
            for (size_t d=0; d < inst->xVarList[t][o].size(); d++){
                int vid = inst->xVarList[t][o][d];
                inst->id2Var[vid] = VarInfo('x', t, o, d);
            }
        }
    }
    // yVars
    for (int r=0; r < inst->lenOfRequest; r++){
        for (int t=0; t < inst->lenOfVehicle; t++){
            int vid = inst->yVarList[r][t];
            inst->id2Var[vid] = VarInfo('y', r, t, -1);
        }
    }
}

void PPDSP_utils::extractXYModel(
    PPDSP_Instance* inst,
    const std::vector<int>& fullModel,
    std::vector<int>& xyModel
){
    xyModel.clear();
    int maxY = inst->getLastYVarID();
    for (int lit : fullModel){
        if (lit > 0 && lit <= maxY)
            xyModel.push_back(lit);
    }
}

void PPDSP_utils::decodeModel(
    PPDSP_Instance* inst,
    const std::vector<int>& xyModel,
    std::vector<std::vector<std::pair<int,int>>>& vehRoutes,
    std::vector<std::vector<int>>& vehReqs
){
    vehRoutes.assign(inst->lenOfVehicle, {});
    vehReqs.assign(inst->lenOfVehicle, {});

    if (inst->id2Var.empty())
        buildVarIndexMap(inst);

    // collect edges & reqs
    for (int vid : xyModel){
        std::unordered_map<int,VarInfo>::const_iterator it = inst->id2Var.find(vid);
        if (it == inst->id2Var.end()) continue;

        const VarInfo &info = it->second;

        if (info.type == 'x'){
            int t = info.a;
            int o = info.b;
            int d = info.c;
            if (o != d)
                vehRoutes[t].push_back(std::make_pair(o,d));
        }
        else if (info.type == 'y'){
            int r = info.a;
            int t = info.b;
            vehReqs[t].push_back(r);
        }
    }

    // reconstruct Hamiltonian path starting from depot = lenOfLocation
    int depot = inst->lenOfLocation;
    for (int t=0; t<inst->lenOfVehicle; t++){
        std::vector<std::pair<int,int> > &edges = vehRoutes[t];
        if (edges.empty()) continue;

        std::unordered_map<int,int> nxt;
        for (size_t i = 0; i < edges.size(); i++)
            nxt[edges[i].first] = edges[i].second;

        std::vector<std::pair<int,int> > route;
        int cur = depot;
        while (nxt.count(cur)){
            int d = nxt[cur];
            route.push_back(std::make_pair(cur, d));
            cur = d;
            if (cur == depot) break;
        }
        vehRoutes[t] = route;
    }
}

bool PPDSP_utils::checkOverload(
    PPDSP_Instance* inst,
    int vehID,
    const std::vector<std::pair<int,int>>& route,
    const std::vector<int>& assigned_reqs,
    Minisat::vec<Minisat::Lit>& learnt_clause
){
    if (route.empty()) return false;

    int capacity = inst->vehicleList[vehID][0];
    int load = 0;

    vector<int> req_size(inst->lenOfRequest);
    vector<int> pickup(inst->lenOfRequest);
    vector<int> drop(inst->lenOfRequest);

    for (int r = 0; r < inst->lenOfRequest; r++){
        req_size[r] = inst->requestList[r][1];
        pickup[r]   = inst->requestList[r][2];
        drop[r]     = inst->requestList[r][3];
    }

    vector<bool> onboard(inst->lenOfRequest, false);

    // Iterate route in order
    for (size_t k = 0; k < route.size(); k++){
        int d = route[k].second;

        // Update onboard
        for (int r : assigned_reqs){
            if (d == pickup[r]){
                load += req_size[r];
                onboard[r] = true;
            }
            else if (d == drop[r] && onboard[r]){
                load -= req_size[r];
                onboard[r] = false;
            }
        }

        // ---- Overload found ----
        if (load > capacity){
            learnt_clause.clear();

            // 1. Collect onboard requests
            vector<int> onboard_reqs;
            for (int r : assigned_reqs)
                if (onboard[r])
                    onboard_reqs.push_back(r);

            // 2. Prefix nodes (before or at this step)  --- no depot ---
            vector<int> prefix_nodes;
            for (size_t i = 0; i <= k; i++){
                prefix_nodes.push_back(route[i].first);
            }

            // 3. Build learnt clause
            // yLits (negated y-vars)
            for (int r : onboard_reqs){
                int vid = inst->yVarList[r][vehID];
                learnt_clause.push(~Minisat::mkLit(vid - 1));
            }

            // xLits (only prefix origins → dropNode)
            for (int r : onboard_reqs){
                int dropNode = drop[r];
                for (int o : prefix_nodes){
                    int vid = inst->xVarList[vehID][o][dropNode];
                    learnt_clause.push(Minisat::mkLit(vid - 1));
                }
            }

            return true;
        }
    }

    return false;
}

bool loadPPDSPInstance(const char* filename, PPDSP_Instance& inst)
{
    std::ifstream in(filename);
    if (!in.good()) {
        std::cerr << "[UWrMaxSAT] Cannot open meta file: " << filename << std::endl;
        return false;
    }

    // Read header: lenOfVehicle lenOfRequest lenOfLocation
    in >> inst.lenOfVehicle >> inst.lenOfRequest >> inst.lenOfLocation;

    // Allocate
    inst.xVarList.assign(inst.lenOfVehicle,
                         std::vector<std::vector<int>>(inst.lenOfLocation+1,
                                                       std::vector<int>(inst.lenOfLocation+1, 0)));
    inst.yVarList.assign(inst.lenOfRequest,
                         std::vector<int>(inst.lenOfVehicle, 0));
    inst.requestList.assign(inst.lenOfRequest,
                            std::vector<int>(4, 0));
    inst.vehicleList.assign(inst.lenOfVehicle,
                            std::vector<int>(2, 0));

    std::string tag;
    std::string section = "";

    while (in >> tag)
    {
        // Switch section
        if (tag == "#") {
            in >> section; // e.g. xVarList
            continue;
        }

        // Parse according to current section
        if (section == "xVarList") {
            int t = std::stoi(tag);
            int o, d, vid;
            in >> o >> d >> vid;
            inst.xVarList[t][o][d] = vid;
        }
        else if (section == "yVarList") {
            int r = std::stoi(tag);
            int t, vid;
            in >> t >> vid;
            inst.yVarList[r][t] = vid;
        }
        else if (section == "requestList") {
            int r = std::stoi(tag);
            int w, q, pk, dp;
            in >> w >> q >> pk >> dp;
            inst.requestList[r] = {w, q, pk, dp};
        }
        else if (section == "vehicleList") {
            int t = std::stoi(tag);
            double cap, cost;
            in >> cap >> cost;
            inst.vehicleList[t] = {(int)cap, (int)cost};
        }
    }

    return true;
}
