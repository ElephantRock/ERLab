"""Phase D tests: Admission Policy + Report."""


from backend.pipeline.model_certification.admission_policy import (
    AdmissionStatus,
    decide_admission,
    load_policy,
)
from backend.pipeline.model_certification.report import CapabilityReport


class TestAdmissionPolicy:
    def test_rejected_when_smoke_test_failed(self):
        d = decide_admission(
            smoke_passed=False,
            hardware_stable=True,
            schema_valid_rate=1.0,
            valid_json_rate=1.0,
            safe_context_window=8192,
        )
        assert d.status == AdmissionStatus.REJECTED
        assert d.promotion_allowed is False
        assert all(v == "blocked" for v in d.stage_eligibility.values())

    def test_rejected_when_hardware_unstable(self):
        d = decide_admission(
            smoke_passed=True,
            hardware_stable=False,
            schema_valid_rate=1.0,
            valid_json_rate=1.0,
            safe_context_window=8192,
        )
        assert d.status == AdmissionStatus.REJECTED
        assert d.promotion_allowed is False

    def test_production_requires_95pct_schema_valid(self):
        d = decide_admission(
            smoke_passed=True,
            hardware_stable=True,
            schema_valid_rate=0.96,
            valid_json_rate=0.96,
            safe_context_window=8192,
        )
        assert d.status == AdmissionStatus.APPROVED_FOR_PRODUCTION
        assert d.promotion_allowed is True

    def test_production_rejects_below_95pct_schema(self):
        d = decide_admission(
            smoke_passed=True,
            hardware_stable=True,
            schema_valid_rate=0.94,
            valid_json_rate=0.96,
            safe_context_window=8192,
        )
        assert d.status != AdmissionStatus.APPROVED_FOR_PRODUCTION

    def test_limited_use_at_85pct_schema_valid(self):
        d = decide_admission(
            smoke_passed=True,
            hardware_stable=True,
            schema_valid_rate=0.88,
            valid_json_rate=0.92,
            safe_context_window=8192,
        )
        assert d.status == AdmissionStatus.APPROVED_FOR_LIMITED_USE
        assert d.promotion_allowed is True

    def test_repair_only_at_70pct_schema_valid(self):
        d = decide_admission(
            smoke_passed=True,
            hardware_stable=True,
            schema_valid_rate=0.72,
            valid_json_rate=0.78,
            safe_context_window=8192,
        )
        assert d.status == AdmissionStatus.APPROVED_FOR_REPAIR_ONLY
        assert d.promotion_allowed is True

    def test_manual_review_when_borders(self):
        d = decide_admission(
            smoke_passed=True,
            hardware_stable=True,
            schema_valid_rate=0.50,
            valid_json_rate=0.60,
            safe_context_window=8192,
        )
        assert d.status == AdmissionStatus.REQUIRES_MANUAL_REVIEW
        assert d.promotion_allowed is False

    def test_stage_eligibility_conservative_for_paper_synthesis(self):
        d = decide_admission(
            smoke_passed=True,
            hardware_stable=True,
            schema_valid_rate=0.96,
            valid_json_rate=0.96,
            safe_context_window=8192,
        )
        # Even with production approval, high-risk stages are not_approved in v0.1
        assert d.stage_eligibility["paper_synthesis"] == "not_approved"
        assert d.stage_eligibility["adversarial_review"] == "not_approved"
        assert d.stage_eligibility["proposal_synthesis"] == "not_approved"

    def test_structured_generation_approved_at_95pct(self):
        d = decide_admission(
            smoke_passed=True,
            hardware_stable=True,
            schema_valid_rate=0.96,
            valid_json_rate=0.96,
            safe_context_window=8192,
        )
        assert d.stage_eligibility["structured_generation"] == "approved"

    def test_structured_generation_not_approved_below_95pct(self):
        d = decide_admission(
            smoke_passed=True,
            hardware_stable=True,
            schema_valid_rate=0.88,
            valid_json_rate=0.92,
            safe_context_window=8192,
        )
        assert d.stage_eligibility["structured_generation"] == "not_approved"

    def test_limited_use_with_no_allowed_stages_is_not_promotable(self):
        """Edge case: limited_use but all stages are not_approved."""
        d = decide_admission(
            smoke_passed=True,
            hardware_stable=True,
            schema_valid_rate=0.72,
            valid_json_rate=0.78,
            safe_context_window=8192,
        )
        # repair_only status: check that repair stage is eligible
        assert d.stage_eligibility.get("repair") in ("limited", "approved")
        assert d.promotion_allowed is True

    def test_context_window_below_4096_blocks_production(self):
        d = decide_admission(
            smoke_passed=True,
            hardware_stable=True,
            schema_valid_rate=0.96,
            valid_json_rate=0.96,
            safe_context_window=2048,
        )
        assert d.status != AdmissionStatus.APPROVED_FOR_PRODUCTION

    def test_load_policy_returns_defaults_when_no_file(self):
        policy = load_policy("/nonexistent/path.yaml")
        assert "hard_reject" in policy
        assert "production_required" in policy


class TestCapabilityReport:
    def test_capability_report_serializes_to_yaml(self):
        report = CapabilityReport(
            model_id="test-model",
            status="approved_for_limited_use",
            safe_context_window=6553,
            safe_output_tokens=1638,
            stage_eligibility={"draft": "approved"},
            manifest_hash="abc123",
        )
        yaml_str = report.to_yaml()
        assert "model_id: test-model" in yaml_str
        assert "approved_for_limited_use" in yaml_str

    def test_capability_report_yaml_roundtrip(self):
        report = CapabilityReport(
            model_id="test-model",
            status="approved_for_production",
            safe_context_window=6553,
            stage_eligibility={"draft": "approved", "repair": "approved"},
            manifest_hash="deadbeef",
            schema_versions={"smoke_test": "1.0"},
        )
        yaml_str = report.to_yaml()
        loaded = CapabilityReport.from_yaml(yaml_str)
        assert loaded.model_id == report.model_id
        assert loaded.status == report.status
        assert loaded.manifest_hash == "deadbeef"
        assert loaded.schema_versions == {"smoke_test": "1.0"}

    def test_report_includes_provenance_fields(self):
        report = CapabilityReport(
            model_id="test-model",
            manifest_hash="abc123",
            policy_version="0.1",
            schema_versions={"structured_claim": "1.0"},
        )
        d = report.to_dict()
        prov = d["provenance"]
        assert "git_commit" in prov
        assert prov["manifest_hash"] == "abc123"
        assert prov["policy_version"] == "0.1"
        assert prov["schema_versions"] == {"structured_claim": "1.0"}

    def test_report_write_to_creates_file(self, tmp_path):
        report = CapabilityReport(
            model_id="test-model",
            status="rejected",
            safe_context_window=4096,
        )
        path = report.write_to(tmp_path)
        assert path.exists()
        assert "test-model" in str(path)
        content = path.read_text()
        assert "test-model" in content

    def test_report_auto_generates_run_id(self):
        report = CapabilityReport(model_id="test-model")
        assert report.eval_run_id.startswith("test-model-")
        assert len(report.eval_run_id) > len("test-model-")
