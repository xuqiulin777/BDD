package com.huawei.divista.remap.service.impl;

import com.huawei.afcj.web.enums.ResponseCodeEnum;
import com.huawei.afcj.web.exception.AppException;
import com.huawei.divista.remap.service.BddReliabilityService;
import com.huawei.divista.remap.vo.McsTopoGraphVo;
import com.huawei.divista.remap.vo.McsTopoGraphVo.Constraints;
import com.huawei.divista.remap.vo.McsTopoGraphVo.McsTopoEdge;
import com.huawei.divista.remap.vo.McsTopoGraphVo.McsTopoNode;
import net.sf.javabdd.BDD;
import net.sf.javabdd.BDDFactory;
import org.apache.commons.collections4.CollectionUtils;
import org.apache.commons.lang3.StringUtils;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.stream.Collectors;

/**
 * 基于BDD的拓扑图可靠度计算实现
 */
@Service
public class BddReliabilityServiceImpl implements BddReliabilityService {

    private static final int BDD_NODE_NUM = 200000;
    private static final int BDD_CACHE_SIZE = 20000;
    private static final int DEFAULT_TIMEOUT_SECONDS = 180;

    @Override
    public Double calculateReliability(McsTopoGraphVo topoGraph, AtomicBoolean cancelled) {
        if (topoGraph == null || CollectionUtils.isEmpty(topoGraph.getNodes())
                || CollectionUtils.isEmpty(topoGraph.getEdges())) {
            return 0.0;
        }
        List<McsTopoNode> nodes = topoGraph.getNodes();
        List<McsTopoEdge> edges = topoGraph.getEdges();
        Constraints constraints = topoGraph.getConstraints();

        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(DEFAULT_TIMEOUT_SECONDS);
        BDDFactory factory = BDDFactory.init("java", BDD_NODE_NUM, BDD_CACHE_SIZE);
        BDD csubset = null;
        BDD cglobal = null;
        BDD fconn = null;
        BDD f = null;
        try {
            if (cancelled != null && cancelled.get()) {
                return 0.0;
            }
            VarMap vm = buildVarMap(nodes, edges, deadline, cancelled);
            factory.setVarNum(vm.nVars());
            factory.autoReorder(BDDFactory.REORDER_SIFT);

            csubset = buildSubsetConstraintBDD(factory, vm, constraints, deadline, cancelled);
            cglobal = buildGlobalNodeFailureBDD(factory, nodes, vm, constraints, deadline, cancelled);
            fconn = buildConnectivityBDDAllPairsAliveOnly(factory, nodes, edges, vm, constraints, deadline, cancelled);

            BDD tmp = csubset.and(cglobal);
            f = tmp.and(fconn);
            tmp.free();

            return weightedProb(f, vm.pUp, deadline, cancelled);
        } finally {
            safeFree(csubset);
            safeFree(cglobal);
            safeFree(fconn);
            safeFree(f);
            factory.done();
        }
    }

    private static class VarMap {
        Map<String, Integer> nodeVar = new LinkedHashMap<>();
        Map<String, Integer> edgeVar = new LinkedHashMap<>();
        double[] pUp;

        int nVars() {
            return pUp.length;
        }
    }

    private VarMap buildVarMap(List<McsTopoNode> nodes, List<McsTopoEdge> edges, long deadline, AtomicBoolean cancelled) {
        checkTimeout(deadline, cancelled);
        VarMap vm = new VarMap();
        int idx = 0;
        for (McsTopoNode node : nodes) {
            checkTimeout(deadline, cancelled);
            vm.nodeVar.put(node.getId(), idx++);
        }
        for (McsTopoEdge edge : edges) {
            checkTimeout(deadline, cancelled);
            vm.edgeVar.put(edge.getId(), idx++);
        }

        vm.pUp = new double[idx];
        for (McsTopoNode node : nodes) {
            vm.pUp[vm.nodeVar.get(node.getId())] = parseProbability(node.getReliability());
        }
        for (McsTopoEdge edge : edges) {
            vm.pUp[vm.edgeVar.get(edge.getId())] = parseProbability(edge.getReliability());
        }
        return vm;
    }

    private BDD buildSubsetConstraintBDD(BDDFactory f, VarMap vm, Constraints cons, long deadline, AtomicBoolean cancelled) {
        checkTimeout(deadline, cancelled);
        if (cons == null || CollectionUtils.isEmpty(cons.getSubSetNodes()) || cons.getSubsetMaxFail() == null) {
            return f.one();
        }
        Set<String> subsetIds = cons.getSubSetNodes().stream().map(McsTopoNode::getId).collect(Collectors.toSet());
        List<Integer> subsetVars = new ArrayList<>();
        for (String nid : subsetIds) {
            Integer varIdx = vm.nodeVar.get(nid);
            if (varIdx != null) {
                subsetVars.add(varIdx);
            }
        }
        if (subsetVars.isEmpty()) {
            return f.one();
        }
        return atMostKFailuresOnNodes(f, subsetVars, cons.getSubsetMaxFail(), deadline, cancelled);
    }

    private BDD buildGlobalNodeFailureBDD(BDDFactory f, List<McsTopoNode> nodes, VarMap vm,
            Constraints cons, long deadline, AtomicBoolean cancelled) {
        int globalMaxFailed = (cons != null && cons.getMaxFailNodes() != null) ? cons.getMaxFailNodes() : nodes.size();
        if (globalMaxFailed >= nodes.size()) {
            return f.one();
        }
        List<Integer> allNodeVars = new ArrayList<>();
        for (McsTopoNode node : nodes) {
            Integer varIdx = vm.nodeVar.get(node.getId());
            if (varIdx != null) {
                allNodeVars.add(varIdx);
            }
        }
        return atMostKFailuresOnNodes(f, allNodeVars, globalMaxFailed, deadline, cancelled);
    }

    private BDD atMostKFailuresOnNodes(BDDFactory f, List<Integer> nodeVarIdx, int k, long deadline, AtomicBoolean cancelled) {
        checkTimeout(deadline, cancelled);
        if (k < 0) {
            return f.zero();
        }
        if (nodeVarIdx.isEmpty()) {
            return f.one();
        }

        BDD[] eq = new BDD[k + 1];
        for (int j = 0; j <= k; j++) {
            eq[j] = f.zero();
        }
        eq[0].free();
        eq[0] = f.one();

        for (int var : nodeVarIdx) {
            checkTimeout(deadline, cancelled);
            BDD x = f.ithVar(var);
            BDD fail = x.not();
            BDD[] next = new BDD[k + 1];
            next[0] = eq[0].and(x);
            for (int j = 1; j <= k; j++) {
                BDD term1 = eq[j].and(x);
                BDD term2 = eq[j - 1].and(fail);
                next[j] = term1.or(term2);
                term1.free();
                term2.free();
            }
            for (BDD b : eq) {
                b.free();
            }
            x.free();
            fail.free();
            eq = next;
        }

        BDD res = f.zero();
        for (BDD b : eq) {
            BDD next = res.or(b);
            res.free();
            res = next;
            b.free();
        }
        return res;
    }

    private BDD buildConnectivityBDDAllPairsAliveOnly(BDDFactory f, List<McsTopoNode> nodes,
            List<McsTopoEdge> edges, VarMap vm, Constraints cons, long deadline, AtomicBoolean cancelled) {
        int n = nodes.size();
        Map<String, Integer> nodeIndex = indexOfNodes(nodes);
        BDD[][] adj = new BDD[n][n];
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                adj[i][j] = f.zero();
            }
        }

        for (McsTopoEdge edge : edges) {
            checkTimeout(deadline, cancelled);
            Integer uIdx = nodeIndex.get(edge.getSource());
            Integer vIdx = nodeIndex.get(edge.getTarget());
            if (uIdx == null || vIdx == null) {
                continue;
            }
            BDD xu = f.ithVar(vm.nodeVar.get(edge.getSource()));
            BDD xv = f.ithVar(vm.nodeVar.get(edge.getTarget()));
            BDD ye = f.ithVar(vm.edgeVar.get(edge.getId()));
            BDD a = ye.and(xu).and(xv);
            adj[uIdx][vIdx] = replaceOr(adj[uIdx][vIdx], a);
            adj[vIdx][uIdx] = replaceOr(adj[vIdx][uIdx], a);
            xu.free();
            xv.free();
            ye.free();
            a.free();
        }

        int h = (cons != null && cons.getNodesMaxHops() != null) ? cons.getNodesMaxHops() : n;
        h = Math.min(Math.max(h, 1), n);
        BDD[][] reach = boundedReach(adj, f, h, deadline, cancelled);

        BDD fconn = f.one();
        for (int u = 0; u < n; u++) {
            for (int v = u + 1; v < n; v++) {
                checkTimeout(deadline, cancelled);
                BDD xu = f.ithVar(vm.nodeVar.get(nodes.get(u).getId()));
                BDD xv = f.ithVar(vm.nodeVar.get(nodes.get(v).getId()));
                BDD imp = xu.not().or(xv.not()).or(reach[u][v]);
                fconn = replaceAnd(fconn, imp);
                xu.free();
                xv.free();
                imp.free();
            }
        }

        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                adj[i][j].free();
                reach[i][j].free();
            }
        }
        return fconn;
    }

    private BDD[][] boundedReach(BDD[][] adj, BDDFactory f, int h, long deadline, AtomicBoolean cancelled) {
        int n = adj.length;
        BDD[][] reach = new BDD[n][n];
        BDD[][] rPrev = new BDD[n][n];
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                reach[i][j] = adj[i][j].id();
                rPrev[i][j] = adj[i][j].id();
            }
        }

        for (int l = 2; l <= h; l++) {
            checkTimeout(deadline, cancelled);
            BDD[][] rCur = new BDD[n][n];
            for (int u = 0; u < n; u++) {
                for (int v = 0; v < n; v++) {
                    BDD acc = f.zero();
                    for (int w = 0; w < n; w++) {
                        BDD term = rPrev[u][w].and(adj[w][v]);
                        BDD next = acc.or(term);
                        acc.free();
                        acc = next;
                        term.free();
                    }
                    rCur[u][v] = acc;
                    reach[u][v] = replaceOr(reach[u][v], acc);
                }
            }
            freeMatrix(rPrev);
            rPrev = rCur;
        }
        freeMatrix(rPrev);
        return reach;
    }

    private double weightedProb(BDD root, double[] pUp, long deadline, AtomicBoolean cancelled) {
        Map<Integer, Double> memo = new HashMap<>();
        return probDfs(root, pUp, memo, deadline, cancelled);
    }

    private double probDfs(BDD b, double[] pUp, Map<Integer, Double> memo, long deadline, AtomicBoolean cancelled) {
        checkTimeout(deadline, cancelled);
        if (b.isOne()) {
            return 1.0;
        }
        if (b.isZero()) {
            return 0.0;
        }
        int key = b.hashCode();
        Double cached = memo.get(key);
        if (cached != null) {
            return cached;
        }
        int varIdx = b.var();
        BDD hi = b.high();
        BDD lo = b.low();
        double p = pUp[varIdx];
        double ans = p * probDfs(hi, pUp, memo, deadline, cancelled)
                + (1.0 - p) * probDfs(lo, pUp, memo, deadline, cancelled);
        memo.put(key, ans);
        hi.free();
        lo.free();
        return ans;
    }

    private Map<String, Integer> indexOfNodes(List<McsTopoNode> nodes) {
        Map<String, Integer> index = new HashMap<>();
        for (int i = 0; i < nodes.size(); i++) {
            index.put(nodes.get(i).getId(), i);
        }
        return index;
    }

    private void checkTimeout(long deadline, AtomicBoolean cancelled) {
        if (cancelled != null && cancelled.get()) {
            throw new AppException("BDD computation cancelled", ResponseCodeEnum.BAD_REQUEST.getValue());
        }
        if (System.nanoTime() > deadline) {
            throw new RuntimeException("BDD computation timeout");
        }
    }

    private double parseProbability(String prob) {
        if (StringUtils.isEmpty(prob)) {
            return 1.0;
        }
        double value = Double.parseDouble(prob);
        return value > 1.0 ? value / 100.0 : value;
    }

    private void safeFree(BDD bdd) {
        if (bdd != null) {
            bdd.free();
        }
    }

    private void freeMatrix(BDD[][] matrix) {
        for (BDD[] row : matrix) {
            for (BDD b : row) {
                b.free();
            }
        }
    }

    private BDD replaceOr(BDD oldBdd, BDD add) {
        BDD next = oldBdd.or(add);
        oldBdd.free();
        return next;
    }

    private BDD replaceAnd(BDD oldBdd, BDD add) {
        BDD next = oldBdd.and(add);
        oldBdd.free();
        return next;
    }
}
