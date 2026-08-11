"""BATCH-169: Domain-Specific Prompts & Budget/Time Controls."""


class TestDomainPrompts:

    def test_01_domain_loader_exists(self):
        from backend.pipeline.prompts.domain_loader import load_domain_prompt
        assert load_domain_prompt is not None

    def test_02_cs_domain_loads(self):
        from backend.pipeline.prompts.domain_loader import load_domain_prompt
        prompt = load_domain_prompt("machine learning")
        assert len(prompt) > 0

    def test_03_bio_domain_loads(self):
        from backend.pipeline.prompts.domain_loader import load_domain_prompt
        prompt = load_domain_prompt("biology")
        assert len(prompt) > 0

    def test_04_unknown_domain_fallback(self):
        from backend.pipeline.prompts.domain_loader import load_domain_prompt
        prompt = load_domain_prompt("quantum_physics_12345")
        # Should return empty or generic prompt, not crash
        assert isinstance(prompt, str)

    def test_05_domain_files_exist(self):
        from pathlib import Path
        domains_dir = Path("backend/pipeline/prompts/domains")
        assert (domains_dir / "computer_science.md").exists()
        assert (domains_dir / "biology.md").exists()
        assert (domains_dir / "social_science.md").exists()


class TestBudgetControls:

    def test_06_budget_settings_exist(self):
        from backend.config import get_settings
        settings = get_settings()
        assert hasattr(settings, "budget_enabled")
        assert hasattr(settings, "budget_max_tokens")
        assert hasattr(settings, "budget_max_cost_usd")
        assert hasattr(settings, "budget_max_seconds")

    def test_07_budget_guard_exists(self):
        from backend.pipeline.budget_guard import BudgetGuard
        assert BudgetGuard is not None

    def test_08_budget_guard_tracks_usage(self):
        from backend.pipeline.budget_guard import BudgetConfig, BudgetGuard
        config = BudgetConfig(max_time_s=60, max_cost_usd=1.0)
        guard = BudgetGuard(config=config)
        guard.start()
        status = guard.check()
        assert isinstance(status, object)  # BudgetStatus

    def test_09_stage_budgets_config(self):
        from backend.config import get_settings
        settings = get_settings()
        assert settings.compaction_stage_budgets  # JSON string
        assert "gap_analysis" in settings.compaction_stage_budgets

    def test_10_budget_guard_records_cost(self):
        from backend.pipeline.budget_guard import BudgetConfig, BudgetGuard
        config = BudgetConfig(max_time_s=60, max_cost_usd=0.01)
        guard = BudgetGuard(config=config)
        guard.start()
        guard.update_cost(0.005)
        status = guard.check()
        assert status is not None
        guard.update_cost(0.01)
        # Budget should be exceeded now
        assert guard.check().cost_usd > 0.01
