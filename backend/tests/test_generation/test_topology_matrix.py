"""Tests for adjacency matrix property on ExecutionDAG."""

from backend.pipeline.generation.topology import (
    DAGNode,
    ExecutionDAG,
    NodeType,
    build_default_dag,
)


class TestAdjMatrix:
    def test_default_dag_has_edges(self):
        dag = build_default_dag()
        matrix = dag.adj_matrix
        assert len(matrix) == len(dag.nodes)
        # Verify it's square
        for row in matrix:
            assert len(row) == len(dag.nodes)

    def test_edge_count_matches(self):
        dag = build_default_dag()
        matrix = dag.adj_matrix
        total_edges = sum(sum(row) for row in matrix)
        assert total_edges == len(dag.edges)

    def test_known_edge(self):
        dag = build_default_dag()
        node_ids = [n.id for n in dag.nodes]
        idx = {nid: i for i, nid in enumerate(node_ids)}
        matrix = dag.adj_matrix
        # entry -> route should have an edge
        assert matrix[idx["entry"]][idx["route"]] == 1

    def test_no_self_loops(self):
        dag = build_default_dag()
        matrix = dag.adj_matrix
        n = len(matrix)
        for i in range(n):
            assert matrix[i][i] == 0

    def test_empty_dag(self):
        dag = ExecutionDAG(nodes=[], edges=[])
        assert dag.adj_matrix == []

    def test_single_node_no_edges(self):
        dag = ExecutionDAG(
            nodes=[DAGNode(id="a", node_type=NodeType.GATE)],
            edges=[],
        )
        assert dag.adj_matrix == [[0]]
