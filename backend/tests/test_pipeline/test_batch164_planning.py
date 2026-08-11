"""BATCH-164: Planning Agent & Adaptive Pipeline."""



class TestPlanningAgent:

    def test_01_plan_deep_research(self):
        from backend.pipeline.planning.agent import PlanningAgent
        agent = PlanningAgent()
        plan = agent.plan(domain="AI/NLP", strategy="deep_research")
        assert len(plan.stages) > 0
        assert plan.total_estimated_time_s > 0

    def test_02_plan_fast_scan_faster(self):
        from backend.pipeline.planning.agent import PlanningAgent
        agent = PlanningAgent()
        deep = agent.plan(strategy="deep_research")
        fast = agent.plan(strategy="fast_scan", disabled_stages=["adversarial_review", "paper_synthesis"])
        assert fast.total_estimated_time_s < deep.total_estimated_time_s

    def test_03_blocker_detection_no_domain(self):
        from backend.pipeline.planning.agent import PlanningAgent
        agent = PlanningAgent()
        plan = agent.plan(domain="")
        assert any("domain" in b.lower() or "No domain" in b for b in plan.blockers)

    def test_04_to_dict_serializable(self):
        import json

        from backend.pipeline.planning.agent import PlanningAgent
        agent = PlanningAgent()
        plan = agent.plan(domain="AI")
        d = plan.to_dict()
        json.dumps(d)  # Must not raise
        assert "stages" in d
        assert "total_estimated_time_s" in d

    def test_05_plan_api_endpoint(self):
        from backend.api.routes.pipeline import router
        routes = [r.path for r in router.routes]
        assert any("plan" in r for r in routes)

    def test_06_plan_api_returns_data(self):
        from fastapi.testclient import TestClient

        from backend.api.app import app
        client = TestClient(app)
        response = client.get("/api/v1/pipeline/plan?strategy=deep_research&domain=AI")
        assert response.status_code == 200
        data = response.json()
        assert "stages" in data
        assert len(data["stages"]) > 0

    def test_07_disabled_stages_show_in_plan(self):
        from backend.pipeline.planning.agent import PlanningAgent
        agent = PlanningAgent()
        plan = agent.plan(strategy="fast_scan", disabled_stages=["proposal_synthesis"])
        synthesis_stage = [s for s in plan.stages if s.stage_name == "proposal_synthesis"]
        if synthesis_stage:
            assert not synthesis_stage[0].enabled

    def test_08_has_blockers_property(self):
        from backend.pipeline.planning.agent import PlanningAgent
        agent = PlanningAgent()
        plan_with = agent.plan(domain="")
        plan_without = agent.plan(domain="AI")
        assert plan_with.has_blockers is True
        # plan_without may or may not have blockers depending on defaults
        assert isinstance(plan_without.has_blockers, bool)

    def test_09_stage_plan_dataclass(self):
        from backend.pipeline.planning.agent import StagePlan
        sp = StagePlan(stage_name="test", enabled=True, estimated_time_s=10, estimated_tokens=100)
        assert sp.stage_name == "test"
        assert sp.dependencies == []

    def test_10_execution_plan_dataclass(self):
        from backend.pipeline.planning.agent import ExecutionPlan
        ep = ExecutionPlan()
        assert ep.stages == []
        assert ep.blockers == []
        assert ep.strategy == "deep_research"
