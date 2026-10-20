"""Offline smoke and gate regression; run: python test_organization.py"""
import json
import tempfile
from pathlib import Path

import organization as q


def rejects(fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError("Expected ValueError")


def packet(tmp):
    return {
        "task_metadata": {"project": "Pilot", "module": "Web", "feature": "Sample", "pic_project": "PIC-REF", "target_release": "R-REF", "target_environment": "QA", "risk_level": "HIGH"},
        "documents": {"fsd_reference": "MISSING", "fsd_version": "MISSING", "sit_happy_reference": "MISSING", "sit_happy_version": "MISSING", "sit_negative_reference": "MISSING", "sit_negative_version": "MISSING", "acceptance_criteria": [], "change_history": [], "scope_enhancement": "MISSING"},
        "access": {"test_account_reference": "MISSING", "role": "MISSING", "permission": []},
        "test_data": {"input_source": "MISSING", "data_creation_method": "MISSING", "cleanup_requirement": "MISSING"},
        "dependencies": [], "environment_status": "AVAILABLE", "technical_impact": "NOT_APPLICABLE_WITH_REASON: belum ditentukan", "technical_traceability": {"screen": "NOT_APPLICABLE_WITH_REASON: mock"}, "requirement_coverage": [{"requirement_id": "AC-1", "test_case_id": "TC-1"}],
    }


def envelope(state, role, decision, artifact_id):
    return {**{k: [] for k in ("input_artifacts", "output_artifacts", "findings", "test_results", "risks", "dependencies", "assumptions", "missing_information")},
            "task_id": state["task_id"], "parent_task_id": state["task_id"], "role_name": role, "agent_name": role,
            "phase": state["phase"], "status": decision, "decision": decision,
            "output_artifacts": [artifact_id], "handoff": {"next_role": "SIT & FSD Validation Lead", "next_action": "correlate", "required_input": "", "blocking_reason": ""}}


def main():
    assert len(q.role_registry()) == 32 and len(q.WORKERS) == 24
    assert set(q.SIX_CATEGORIES) == {"Positive", "Negative", "Boundary", "Empty", "Combination", "Volume"}
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        p = packet(tmp)
        state = q.intake(p)
        assert state["phase"] == "INTAKE_INCOMPLETE"
        rejects(lambda: q.advance(state, "IN_PROGRESS"))
        rejects(lambda: q.plan(state, {}))
        rejects(lambda: q.record(state, {"role_name": "Web Automation Worker"}))
        assert state["results"] == []
        rejects(lambda: q.intake({"task_metadata": {"pic_project": "Dev"}, "password": "x"}))
        rejects(lambda: q.intake({"task_metadata": {}}))
        for key in ("fsd_reference", "sit_happy_reference", "sit_negative_reference"):
            path = tmp / (key + ".txt")
            path.write_text("Contoh dokumen uji; bukan hasil eksekusi", encoding="utf-8")
            p["documents"][key] = str(path)
        p["documents"].update(fsd_version="1", sit_happy_version="1", sit_negative_version="1", acceptance_criteria=["AC-1"], change_history=["v1"], scope_enhancement="display")
        p["access"].update(test_account_reference="vault:REF", role="tester", permission=["view"])
        p["test_data"].update(input_source="fixture", data_creation_method="UI", cleanup_requirement="manual")
        state = q.intake(p)
        assert state["phase"] == "VALIDATING"
        assert q.validation_gate(state) == "NEED_REVISION"  # file ref belum registry
        assert state["phase"] == "NEED_REVISION"
        state = q.intake(p)
        for key in ("fsd_reference", "sit_happy_reference", "sit_negative_reference"):
            q.register(state, p["documents"][key], "document", "PIC Project")
        assert q.validation_gate(state) == "NEED_REVISION"  # validator belum ada
        state = q.intake(p)
        ids = [q.register(state, p["documents"][key], "document", "PIC Project") for key in ("fsd_reference", "sit_happy_reference", "sit_negative_reference")]
        output = tmp / "validator-output.json"
        output.write_text('{"note":"mock validator output"}', encoding="utf-8")
        output_id = q.register(state, output, "validation", "mock validator")
        for role in q.VALIDATORS:
            e = envelope(state, role, "READY", output_id)
            e["input_artifacts"] = ids
            q.record(state, e)
        q.record(state, envelope(state, "SIT & FSD Validation Lead", "READY", output_id))
        assert q.validation_gate(state) == "READY"
        rejects(lambda: q.advance(state, "IN_PROGRESS"))
        plan = dict(task_id=state["task_id"], objective="Pilot", current_phase="PLANNING", required_roles=["QA Lead"], required_workers=["Functional / SIT Worker"], parallel_tasks=[], sequential_tasks=["SIT"], dependencies=[], entry_criteria=["READY"], exit_criteria=["results"], risk_level="HIGH", approval_required=True)
        q.plan(state, plan)
        rejects(lambda: q.advance(state, "IN_PROGRESS"))
        q.advance(state, "IN_PROGRESS", authorized=True)
        result = {k: "" for k in q.RESULT_KEYS}
        result.update(requirement_id="AC-1", test_case_id="TC-1", status="PASS", expected_result="visible", actual_result="visible", environment="QA", user_role_reference="tester", test_data_reference="fixture", evidence_reference="NO-EVIDENCE")
        e = envelope(state, "Functional / SIT Worker", "PASS", ids[0]); e["test_results"] = [result]
        rejects(lambda: q.record(state, e))  # PASS tanpa evidence
        assert not state["results"]
        result["evidence_reference"] = ids[0]
        q.record(state, e)
        assert len(state["results"]) == 1
        q.advance(state, "EXECUTION_COMPLETE")
        q.advance(state, "RELEASE_REVIEW")
        rejects(lambda: q.review(state, "RELEASE"))
        q.record(state, envelope(state, "Release Readiness Agent", "RELEASE", ids[0]))
        q.review(state, "RELEASE")
        q.record(state, envelope(state, "QA Manager", "RELEASE", ids[0]))
        rejects(lambda: q.decide(state, "RELEASE"))  # HIGH: human approval
        q.decide(state, "RELEASE", approver="HUMAN-REF", approval_artifact=ids[0])
        assert state["phase"] == "RELEASE"
        assert "PASS: 1" in q.report(state)
        # Pilihan role dan artifact ini data mock untuk menguji guard, bukan keputusan QA nyata.
        conflict = q.intake(p)
        for key in ("fsd_reference", "sit_happy_reference", "sit_negative_reference"):
            ident = q.register(conflict, p["documents"][key], "document", "PIC Project")
        for role in q.VALIDATORS:
            e = envelope(conflict, role, "READY", ident)
            e["input_artifacts"] = [ident]
            if role == q.VALIDATORS[-1]:
                e["findings"] = [{k: "" for k in q.FINDING_KEYS} | {"status": "CONFLICTING"}]
            q.record(conflict, e)
        q.record(conflict, envelope(conflict, "SIT & FSD Validation Lead", "READY", ident))
        assert q.validation_gate(conflict) == "NEED_REVISION"
    print("OK: 32 role, 24 worker; intake, secret, gate, evidence, conflict, approval, report")


if __name__ == "__main__":
    main()
