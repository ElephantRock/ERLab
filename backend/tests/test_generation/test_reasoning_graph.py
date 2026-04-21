"""Tests for reasoning graph, scratch space, and strategy tracker."""


from backend.pipeline.generation.borda import borda_rank_graph_nodes
from backend.pipeline.generation.reasoning_graph import (
    GraphOfOperations,
    ReasoningGraph,
    ThoughtNode,
    ThoughtState,
)
from backend.pipeline.generation.strategies import (
    CriticStrategy,
    StrategyOutcome,
    StrategyTracker,
)
from backend.pipeline.reasoning.scratch_space import (
    ScratchSpace,
)

# --- Reasoning Graph ---


class TestThoughtNode:
    def test_create(self):
        node = ThoughtNode(content="Test hypothesis")
        assert node.state == ThoughtState.PROPOSED
        assert node.score == 0.0
        assert len(node.id) == 12

    def test_add_child_parent(self):
        parent = ThoughtNode(content="root")
        child = ThoughtNode(content="leaf", parent_ids=[parent.id])
        parent.add_child(child.id)
        assert child.id in parent.child_ids
        assert parent.id in child.parent_ids


class TestReasoningGraph:
    def test_add_node_and_root(self):
        g = ReasoningGraph()
        root = ThoughtNode(content="root")
        g.add_node(root, root=True)
        assert g.node_count == 1
        assert root.id in g.root_ids

    def test_add_edge(self):
        g = ReasoningGraph()
        a = ThoughtNode(content="a")
        b = ThoughtNode(content="b")
        g.add_node(a)
        g.add_node(b)
        g.add_edge(a.id, b.id)
        children = g.get_children(a.id)
        assert len(children) == 1
        assert children[0].id == b.id

    def test_leaves(self):
        g = ReasoningGraph()
        root = ThoughtNode(content="root")
        leaf = ThoughtNode(content="leaf", parent_ids=[root.id])
        g.add_node(root, root=True)
        g.add_node(leaf)
        g.add_edge(root.id, leaf.id)
        leaves = g.get_leaves()
        assert len(leaves) == 1
        assert leaves[0].content == "leaf"

    def test_prune(self):
        g = ReasoningGraph()
        node = ThoughtNode(content="bad idea")
        g.add_node(node)
        g.prune(node.id)
        assert node.state == ThoughtState.PRUNED
        assert g.active_count == 0

    def test_get_by_state(self):
        g = ReasoningGraph()
        a = ThoughtNode(content="a", state=ThoughtState.SCORED, score=0.5)
        b = ThoughtNode(content="b", state=ThoughtState.PROPOSED)
        g.add_node(a)
        g.add_node(b)
        scored = g.get_by_state(ThoughtState.SCORED)
        assert len(scored) == 1


class TestGraphOfOperations:
    def _make_graph(self):
        g = ReasoningGraph()
        root = ThoughtNode(content="Research gap: RAG retrieval")
        g.add_node(root, root=True)
        return g, root

    def test_generate(self):
        g, root = self._make_graph()
        ops = GraphOfOperations(g, beam_width=3)

        def gen(content, n=1, **kw):
            return [f"Branch {i} of {content}" for i in range(n)]

        ids = ops.generate([root.id], gen, n_branches=2)
        assert len(ids) == 2
        children = g.get_children(root.id)
        assert len(children) == 2

    def test_score(self):
        g, root = self._make_graph()
        ops = GraphOfOperations(g)
        ids = ops.generate(
            [root.id], lambda c, n=1, **kw: [f"h{i}" for i in range(n)], n_branches=1
        )
        scored = ops.score(ids, lambda c, **kw: 0.8)
        assert len(scored) == 1
        assert g.nodes[ids[0]].score == 0.8
        assert g.nodes[ids[0]].state == ThoughtState.SCORED

    def test_keep_best_n(self):
        g, root = self._make_graph()
        ops = GraphOfOperations(g, beam_width=2)

        def gen(content, n=1, **kw):
            return [f"idea_{i}" for i in range(n)]

        def scorer(content, **kw):
            scores = {"idea_0": 0.9, "idea_1": 0.3, "idea_2": 0.7, "idea_3": 0.1}
            return scores.get(content, 0.5)

        ids = ops.generate([root.id], gen, n_branches=4)
        ops.score(ids, scorer)
        kept = ops.keep_best_n(ids, n=2)
        assert len(kept) == 2
        assert g.nodes[kept[0]].score >= g.nodes[kept[1]].score

    def test_aggregate(self):
        g, root = self._make_graph()
        ops = GraphOfOperations(g)
        ids = ops.generate(
            [root.id], lambda c, n=1, **kw: [f"part{i}" for i in range(n)], n_branches=2
        )
        agg_id = ops.aggregate(ids, lambda parts, **kw: " + ".join(parts))
        assert agg_id is not None
        assert g.nodes[agg_id].metadata["aggregated_from"] == 2

    def test_validate(self):
        g, root = self._make_graph()
        ops = GraphOfOperations(g)
        ids = ops.generate([root.id], lambda c, n=1, **kw: ["idea"], n_branches=1)
        ops.score(ids, lambda c, **kw: 0.95)
        validated = ops.validate(ids, lambda c, s, **kw: s >= 0.9)
        assert len(validated) == 1
        assert g.nodes[ids[0]].state == ThoughtState.SOLVED

    def test_beam_search(self):
        g = ReasoningGraph()
        root = ThoughtNode(content="gap: efficient attention")
        g.add_node(root, root=True)
        ops = GraphOfOperations(g, beam_width=2)

        call_count = [0]

        def gen(content, n=1, **kw):
            call_count[0] += 1
            return [f"thought_{call_count[0]}_{i}" for i in range(n)]

        def scorer(content, **kw):
            return 0.5 + hash(content) % 50 / 100

        def validator(content, score, **kw):
            return score >= 0.85

        results = ops.beam_search(
            [root.id],
            gen,
            scorer,
            validator,
            max_depth=2,
            n_branches=3,
        )
        assert len(results) >= 1
        assert all(r.state in (ThoughtState.SOLVED, ThoughtState.VALIDATED) for r in results)


# --- Scratch Space ---


class TestScratchSpace:
    def test_write_read_commit(self):
        space = ScratchSpace()
        tx = space.begin()
        space.write(tx, "hypothesis", "RAG improves recall")
        assert space.read(tx, "hypothesis") == "RAG improves recall"
        assert space.global_count == 0

        space.commit(tx)
        assert space.global_count == 1
        assert space.read_global("hypothesis") == "RAG improves recall"

    def test_rollback(self):
        space = ScratchSpace()
        tx = space.begin()
        space.write(tx, "bad_idea", "This is wrong")
        space.rollback(tx)
        assert space.global_count == 0
        assert space.read_global("bad_idea") is None

    def test_isolation(self):
        space = ScratchSpace()
        tx_a = space.begin()
        tx_b = space.begin()

        space.write(tx_a, "a_key", "from_a")
        space.write(tx_b, "b_key", "from_b")

        assert space.read(tx_a, "b_key") is None
        assert space.read(tx_b, "a_key") is None

    def test_read_all(self):
        space = ScratchSpace()
        tx = space.begin()
        space.write(tx, "k1", "v1")
        space.write(tx, "k2", "v2")
        all_data = space.read_all(tx)
        assert all_data == {"k1": "v1", "k2": "v2"}

    def test_commit_promotes_to_global(self):
        space = ScratchSpace()
        tx1 = space.begin()
        space.write(tx1, "base", "value")
        space.commit(tx1)

        tx2 = space.begin()
        assert space.read(tx2, "base") == "value"
        space.write(tx2, "new", "addition")
        space.commit(tx2)

        assert space.read_global("base") == "value"
        assert space.read_global("new") == "addition"

    def test_cannot_use_committed_tx(self):
        space = ScratchSpace()
        tx = space.begin()
        space.commit(tx)
        try:
            space.write(tx, "x", "y")
            assert False, "Should have raised"
        except ValueError:
            pass

    def test_delete_global(self):
        space = ScratchSpace()
        tx = space.begin()
        space.write(tx, "temp", "data")
        space.commit(tx)
        assert space.delete_global("temp")
        assert space.global_count == 0


# --- Strategy Tracker ---


class TestStrategyTracker:
    def test_falls_back_to_rules(self):
        tracker = StrategyTracker()
        strategy = tracker.recommend(round_num=1, total_rounds=3)
        assert strategy == CriticStrategy.SHALLOW_REVIEW

    def test_data_driven_selection(self):
        tracker = StrategyTracker()
        for _ in range(3):
            tracker.record(
                StrategyOutcome(
                    strategy=CriticStrategy.DEEP_DIAGNOSIS,
                    round_num=2,
                    idea_count=5,
                    avg_score=0.9,
                )
            )
        for _ in range(3):
            tracker.record(
                StrategyOutcome(
                    strategy=CriticStrategy.SHALLOW_REVIEW,
                    round_num=2,
                    idea_count=5,
                    avg_score=0.5,
                )
            )
        best = tracker.recommend(round_num=2, total_rounds=6)
        assert best == CriticStrategy.DEEP_DIAGNOSIS

    def test_record_count(self):
        tracker = StrategyTracker()
        tracker.record(
            StrategyOutcome(
                strategy=CriticStrategy.SHALLOW_REVIEW,
                round_num=1,
                idea_count=3,
                avg_score=0.6,
            )
        )
        assert tracker.record_count == 1


# --- Borda Graph Nodes ---


class TestBordaGraphNodes:
    def test_single_node(self):
        winner, scores = borda_rank_graph_nodes({"a": [0.8, 0.7]})
        assert winner == "a"

    def test_multi_node_multi_dim(self):
        winner, scores = borda_rank_graph_nodes(
            {
                "a": [0.9, 0.3],
                "b": [0.5, 0.8],
                "c": [0.7, 0.6],
            }
        )
        assert winner in ("a", "b", "c")
        assert all(nid in scores for nid in ("a", "b", "c"))

    def test_empty(self):
        winner, scores = borda_rank_graph_nodes({})
        assert winner == ""
        assert scores == {}
