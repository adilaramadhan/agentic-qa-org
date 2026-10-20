"""Agentic QA organization: offline registry, guarded pilot workflow. Python 3.11+."""
import argparse
import hashlib
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEVEL1 = ["QA Manager"]
LEVEL2 = ["SIT & FSD Validation Lead", "QA Lead", "QA Governance & Metrics Agent", "QA Release / Risk Agent"]
LEADS = ["Automation QA Engineer", "Manual QA Engineer", "Performance / Security QA Specialist"]
CHILDREN = {
    "SIT & FSD Validation Lead": ["Document Completeness Validator", "SIT Quality & Coverage Validator", "Test Data & Access Validator", "Technical Traceability & Integration Validator"],
    "Automation QA Engineer": ["Web Automation Worker", "API Automation Worker", "Mobile Automation Worker", "Test Stability Worker"],
    "Manual QA Engineer": ["Functional / SIT Worker", "Exploratory Worker", "Regression Worker", "Retesting Worker"],
    "Performance / Security QA Specialist": ["Performance Worker", "Load / Stress Worker", "Security Worker", "Accessibility Worker"],
    "QA Governance & Metrics Agent": ["Requirement Coverage Agent", "Test Plan Agent", "Test Data Agent", "QA Metrics Agent"],
    "QA Release / Risk Agent": ["Defect Triage Agent", "Severity / Priority Agent", "Release Readiness Agent", "QA Report Agent"],
}
MISSIONS = {
    "QA Manager": "Terima task hanya dari PIC Project; putuskan gate dan keputusan QA akhir berdasarkan bukti.",
    "SIT & FSD Validation Lead": "Gabungkan empat validasi FSD/SIT; keluarkan READY, NEED_REVISION, atau BLOCKED sebelum eksekusi.",
    "QA Lead": "Rencanakan dan koordinasikan eksekusi relevan setelah gate READY; korelasikan konflik.",
    "Automation QA Engineer": "Koordinasikan automation relevan dan jaga hasil asli, trace, serta stabilitas.",
    "Manual QA Engineer": "Koordinasikan SIT manual, eksplorasi, regresi, dan retest berbasis script.",
    "Performance / Security QA Specialist": "Koordinasikan uji non-fungsional dalam scope dan batas approval.",
    "QA Governance & Metrics Agent": "Jaga traceability, rencana, enam kategori data uji, dan metrik dari artifact nyata.",
    "QA Release / Risk Agent": "Kelola triage, severity/priority, rekomendasi readiness dan laporan.",
    "Document Completeness Validator": "Periksa versi, perubahan, scope, behavior, acceptance criteria FSD serta kelengkapan SIT happy/negative.",
    "SIT Quality & Coverage Validator": "Petakan requirement ke test case; cek positive, negative, boundary, empty, kombinasi, dan recovery.",
    "Test Data & Access Validator": "Periksa asal, cara buat, relasi, cleanup data; referensi akun, role, permission tanpa secret.",
    "Technical Traceability & Integration Validator": "Telusuri UI, API, service, database, integrasi; bedakan documented, verified, missing, conflicting.",
    "Web Automation Worker": "Jalankan Web UI SIT pada scope disetujui; simpan screenshot/trace/log.",
    "API Automation Worker": "Jalankan API SIT pada endpoint terdokumentasi; validasi request, respons, auth, error, integrasi.",
    "Mobile Automation Worker": "Jalankan mobile SIT pada device dan izin yang disetujui; simpan log dan screenshot.",
    "Test Stability Worker": "Bandingkan run, locator, timing, data collision; jangan ubah FAIL menjadi PASS karena rerun.",
    "Functional / SIT Worker": "Eksekusi script SIT dari PIC dengan input, role, expected result tetap; catat actual dan evidence.",
    "Exploratory Worker": "Uji edge case dalam charter/scope; catat reproduksi, expected, actual, environment, evidence.",
    "Regression Worker": "Uji fitur terdampak berdasarkan impact analysis; catat backward compatibility dan evidence.",
    "Retesting Worker": "Setelah fix tersedia, ulang defect dan beri VERIFIED/REOPEN/BLOCKED berbasis evidence.",
    "Performance Worker": "Ukur response time, throughput, resource, baseline sesuai scope dan threshold disetujui.",
    "Load / Stress Worker": "Jalankan load/stress/spike/endurance hanya dengan approval traffic dan target eksplisit.",
    "Security Worker": "Uji auth, akses, session, exposure non-destruktif; butuh approval untuk uji destruktif.",
    "Accessibility Worker": "Uji keyboard, fokus, label, semantik, kontras dan error association.",
    "Requirement Coverage Agent": "Petakan requirement sampai acceptance criteria, testcase, teknis, evidence, defect; tandai GAP.",
    "Test Plan Agent": "Susun scope, urutan, dependency, worker, entry/exit, risiko, prioritas, parallelisasi.",
    "Test Data Agent": "Rancang enam kategori Positive, Negative, Boundary, Empty, Combination, Volume tanpa mengarang nilai.",
    "QA Metrics Agent": "Hitung coverage, status, defect, retest, regression dan flaky hanya dari artifact nyata.",
    "Defect Triage Agent": "Bedakan product, test, environment, data, requirement, integration; validasi reproduksi.",
    "Severity / Priority Agent": "Nilai severity berdasar dampak; priority berdasar urgensi; jangan samakan keduanya.",
    "Release Readiness Agent": "Berikan rekomendasi RELEASE/CONDITIONAL_RELEASE/NO_RELEASE dari coverage, defect, risk, evidence.",
    "QA Report Agent": "Susun laporan SIT, retest, regression, risk dan open action dari registry evidence.",
}
VALIDATORS = CHILDREN["SIT & FSD Validation Lead"]
WORKERS = [c for group in CHILDREN.values() for c in group]
ROLES = LEVEL1 + LEVEL2 + LEADS + WORKERS
REQUIRED = {
    "task_metadata": ["project", "module", "feature", "pic_project", "target_release", "target_environment", "risk_level"],
    "documents": ["fsd_reference", "fsd_version", "sit_happy_reference", "sit_happy_version", "sit_negative_reference", "sit_negative_version", "acceptance_criteria", "change_history", "scope_enhancement"],
    "access": ["test_account_reference", "role", "permission"],
    "test_data": ["input_source", "data_creation_method", "cleanup_requirement"],
}
SIX_CATEGORIES = {
    "Positive": ["Normal", "Minimum", "Maximum", "Typical"],
    "Negative": ["Invalid format", "Invalid value", "Unauthorized", "Duplicate"],
    "Boundary": ["Minimum - 1", "Minimum", "Maximum", "Maximum + 1"],
    "Empty": ["Null", "Blank", "Mandatory kosong", "Optional kosong"],
    "Combination": ["Cross-module", "Multiple condition", "Role", "Permission", "Data state"],
    "Volume": ["Small", "Medium", "Large", "Peak"],
}
FORBIDDEN = ["Mengarang requirement, akun, test data, hasil, endpoint, tabel, atau evidence", "Mengubah FSD, acceptance criteria, source, DB, atau environment", "Deploy, merge, menutup defect tanpa retest, release tanpa review", "Menampilkan secret atau PII tak perlu; efek eksternal tanpa approval"]
OUTPUT_KEYS = ["task_id", "parent_task_id", "role_name", "agent_name", "phase", "status", "decision", "input_artifacts", "output_artifacts", "findings", "test_results", "risks", "dependencies", "assumptions", "missing_information", "handoff"]
RESULT_KEYS = ["requirement_id", "test_case_id", "status", "expected_result", "actual_result", "environment", "user_role_reference", "test_data_reference", "evidence_reference", "defect_id"]
FINDING_KEYS = ["finding_id", "category", "severity", "status", "description", "source_reference", "evidence_reference", "required_action", "owner", "exit_criteria"]
DEFECT_KEYS = ["defect_id", "title", "task_id", "requirement_id", "test_case_id", "environment", "user_role_reference", "preconditions", "steps_to_reproduce", "expected_result", "actual_result", "evidence_reference", "severity", "priority", "impact", "frequency", "suspected_component", "category", "owner", "status", "retest_required", "regression_required"]
STATES = {
    "RECEIVED": ["INTAKE_INCOMPLETE", "VALIDATING"],
    "INTAKE_INCOMPLETE": ["VALIDATING", "NEED_REVISION"],
    "VALIDATING": ["NEED_REVISION", "BLOCKED", "READY_FOR_PLANNING"],
    "NEED_REVISION": ["PIC_PROJECT_REVISION"],
    "PIC_PROJECT_REVISION": ["VALIDATING"],
    "BLOCKED": ["DEPENDENCY_RESOLUTION"],
    "DEPENDENCY_RESOLUTION": ["VALIDATING"],
    "READY_FOR_PLANNING": ["READY_FOR_EXECUTION"],
    "READY_FOR_EXECUTION": ["IN_PROGRESS"],
    "IN_PROGRESS": ["EXECUTION_COMPLETE"],
    "EXECUTION_COMPLETE": ["RETEST_REQUIRED", "REGRESSION_REQUIRED", "RELEASE_REVIEW"],
    "RETEST_REQUIRED": ["RETEST_IN_PROGRESS"],
    "RETEST_IN_PROGRESS": ["REGRESSION_REQUIRED", "RELEASE_REVIEW"],
    "REGRESSION_REQUIRED": ["REGRESSION_IN_PROGRESS"],
    "REGRESSION_IN_PROGRESS": ["RELEASE_REVIEW"],
    "RELEASE_REVIEW": ["RELEASE", "CONDITIONAL_RELEASE", "NO_RELEASE", "WAIVED"],
    "WAIVED": ["CLOSED"], "RELEASE": ["CLOSED"], "CONDITIONAL_RELEASE": ["CLOSED"], "NO_RELEASE": ["CLOSED"], "CLOSED": [],
}
SECRET_KEYS = re.compile(r"password|passwd|secret|api.?key|access.?token|cvc|credential", re.I)


def now():
    return datetime.now(timezone.utc).isoformat()


def present(value):
    return value is not None and value != "" and value != [] and value != "MISSING"


def missing_input(packet):
    missing = []
    for section, keys in REQUIRED.items():
        if not isinstance(packet.get(section), dict):
            missing.append(section)
            continue
        for key in keys:
            if not present(packet[section].get(key)):
                missing.append(f"{section}.{key}")
    for key in ("technical_impact", "technical_traceability", "requirement_coverage"):
        if not present(packet.get(key)):
            missing.append(key)
    if "dependencies" not in packet:
        missing.append("dependencies")  # [] boleh untuk tanpa dependency
    if packet.get("environment_status") not in ("AVAILABLE", "UNAVAILABLE"):
        missing.append("environment_status")
    return missing


def check_secrets(obj, path="root"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if SECRET_KEYS.search(k) and present(v):
                raise ValueError(f"Field rahasia dilarang: {path}.{k}; pakai test_account_reference/vault reference")
            check_secrets(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            check_secrets(value, f"{path}[{i}]")


def role_registry():
    out = {}
    for role in ROLES:
        level = 1 if role in LEVEL1 else 2 if role in LEVEL2 else 3
        parent = next((p for p, kids in CHILDREN.items() if role in kids), None)
        if not parent and role in LEADS:
            parent = "QA Lead"
        if not parent and role in LEVEL2:
            parent = "QA Manager"
        child = CHILDREN.get(role, LEADS if role == "QA Lead" else [])
        if role == "QA Manager":
            child = LEVEL2
        read = ["PIC task packet", "artifact registry", "validated state"]
        tools = ["read_file", "search_files", "delegate_task (hanya anak dalam scope)"] if child else ["read_file", "search_files"]
        if role in ["Technical Traceability & Integration Validator", "Requirement Coverage Agent"]:
            tools += ["read-only SELECT bila akses disetujui"]
        if role in ["Web Automation Worker", "API Automation Worker", "Mobile Automation Worker"]:
            tools += ["browser/test runner hanya di environment disetujui"]
        out[role] = {
            "ROLE_NAME": role, "ROLE_LEVEL": level, "PARENT_ROLE": parent, "MISSION": MISSIONS[role],
            "RESPONSIBILITIES": [MISSIONS[role], "Kembalikan output envelope dan referensi source/evidence"],
            "NON_RESPONSIBILITIES": ["Keputusan final QA dan deployment" if role != "QA Manager" else "Eksekusi test dan perubahan source"],
            "ALLOWED_TOOLS": tools, "FORBIDDEN_ACTIONS": FORBIDDEN,
            "REQUIRED_INPUTS": read + (["FSD dan SIT tervalidasi READY"] if role in ["QA Lead"] + LEADS + CHILDREN["Automation QA Engineer"] + CHILDREN["Manual QA Engineer"] + CHILDREN["Performance / Security QA Specialist"] else []),
            "OPTIONAL_INPUTS": ["technical impact", "source snapshot", "baseline", "approved risk waiver"],
            "OUTPUT_SCHEMA": "schemas.json#/$defs/envelope", "DECISION_RULES": {
                "PASS": "Hanya dari hasil uji nyata dan evidence terdaftar; validator: kriteria terpenuhi dan source cukup.",
                "FAIL": "Expected vs actual berbeda, hasil terverifikasi; jangan otomatis PRODUCT_DEFECT.",
                "BLOCKED": "Dependency teknis/akses/environment menghalangi, sebut pemilik dan evidence bila tersedia.",
                "NEED_REVISION": "Dokumen PIC ambigu, tidak lengkap, atau konflik; minta revisi PIC.",
            },
            "HANDOFF_RULES": f"Anak hanya {child}; kembalikan envelope ke {parent or 'PIC Project'}; tanpa delegasi bebas pada level 3.",
            "ESCALATION_RULES": "Konflik, evidence kurang, izin/risiko tinggi: INCONCLUSIVE ke parent lalu QA Manager; jangan voting.",
            "EVIDENCE_REQUIREMENTS": "Setiap klaim: source_reference, artifact ID, evidence ID, status verifikasi. PASS butuh evidence; FAIL butuh reproduksi, expected, actual, environment.",
            "TRAINING_EXAMPLES": ["VALID: MISSING → NEED_REVISION saat role tak disebut.", "INVALID: PASS tanpa evidence atau endpoint rekaan.", "BOUNDARY: NOT_APPLICABLE_WITH_REASON dengan alasan dan source.", "CONFLICT: FSD != source → CONFLICTING, stop gate.", "ESCALATION: hasil rerun beda → INCONCLUSIVE ke parent."],
            "EVALUATION_CHECKLIST": ["Input lengkap dan scope sesuai", "Tidak halusinasi atau secret", "Evidence ID ada di registry", "Status, handoff, keputusan tepat", "Tidak bypass gate/approval"],
        }
    assert len(set(ROLES)) == 32 and len(WORKERS) == 24 and len(LEVEL1 + LEVEL2 + LEADS) == 8
    return out


def build():
    registry = role_registry()
    def dump(name, obj):
        (ROOT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dump("roles.json", registry)
    permissions = {k: {"level": v["ROLE_LEVEL"], "parent": v["PARENT_ROLE"], "children": CHILDREN.get(k, LEADS if k == "QA Lead" else LEVEL2 if k == "QA Manager" else []), "allowed_tools": v["ALLOWED_TOOLS"], "forbidden": FORBIDDEN} for k, v in registry.items()}
    dump("permissions.json", permissions)
    dump("routing.json", {"states": STATES, "validators": VALIDATORS, "activation": "on-demand, relevant scope only", "pilot_web_sit": ["QA Manager", "SIT & FSD Validation Lead", "QA Governance & Metrics Agent", "QA Lead", "Functional / SIT Worker", "Web Automation Worker", "API Automation Worker", "Defect Triage Agent", "Retesting Worker", "Release Readiness Agent", "QA Manager"]})
    obj = lambda keys: {"type": "object", "required": keys, "properties": {k: {"type": "array" if k in ("findings", "test_results", "input_artifacts", "output_artifacts", "risks", "dependencies", "assumptions", "missing_information", "preconditions", "steps_to_reproduce", "evidence_reference") else "string"} for k in keys}}
    envelope_schema = obj(OUTPUT_KEYS)
    envelope_schema["properties"]["handoff"] = {"type": "object", "required": ["next_role", "next_action", "required_input", "blocking_reason"], "properties": {k: {"type": "string"} for k in ("next_role", "next_action", "required_input", "blocking_reason")}}
    envelope_schema["properties"]["findings"] = {"type": "array", "items": {"$ref": "#/$defs/finding"}}
    envelope_schema["properties"]["test_results"] = {"type": "array", "items": {"$ref": "#/$defs/test_result"}}
    defect_schema = obj(DEFECT_KEYS)
    defect_schema["properties"].update({"retest_required": {"type": "boolean"}, "regression_required": {"type": "boolean"}})
    input_schema = {"type": "object", "required": list(REQUIRED) + ["technical_traceability", "requirement_coverage", "technical_impact", "dependencies", "environment_status"], "properties": {section: {"type": "object", "required": keys, "properties": {k: {"type": "array" if k in ("acceptance_criteria", "change_history", "permission") else "string"} for k in keys}} for section, keys in REQUIRED.items()}}
    input_schema["properties"].update({"technical_traceability": {"type": ["object", "string"]}, "requirement_coverage": {"type": "array"}, "technical_impact": {"type": "string"}, "dependencies": {"type": "array"}, "environment_status": {"enum": ["AVAILABLE", "UNAVAILABLE"]}})
    dump("schemas.json", {"$schema": "https://json-schema.org/draft/2020-12/schema", "$defs": {"pic_input": input_schema, "envelope": envelope_schema, "finding": obj(FINDING_KEYS), "test_result": obj(RESULT_KEYS), "defect": defect_schema}, "pic_required": REQUIRED, "test_data_categories": SIX_CATEGORIES})
    prompts = ["# Prompt organisasi Agentic QA", "", "Aturan lintas-role: task hanya dari PIC Project; FSD + SIT happy/negative wajib READY sebelum execution. Jangan mengarang data atau hasil. DB hanya SELECT. Secret/PII tidak boleh ditampilkan. Semua klaim: source, artifact, evidence, verification. Level 3 tidak mendelegasikan. Approval manusia untuk efek eksternal/waiver high-risk/production release. Gunakan schemas.json, routing.json, permissions.json dan shared state sebagai sumber tunggal.", ""]
    for name, spec in registry.items():
        prompts += [f"## {name} — level {spec['ROLE_LEVEL']}", f"SYSTEM: Anda {name}. {spec['MISSION']}", f"SCOPE: {spec['RESPONSIBILITIES'][0]}", f"NON-SCOPE: {spec['NON_RESPONSIBILITIES'][0]}; {'; '.join(FORBIDDEN)}.", f"INPUT: {', '.join(spec['REQUIRED_INPUTS'])}; opsional: {', '.join(spec['OPTIONAL_INPUTS'])}.", f"OUTPUT: {spec['OUTPUT_SCHEMA']}; wajib lengkap termasuk findings, test_results, handoff dan status verifikasi setiap klaim.", f"HANDOFF: {spec['HANDOFF_RULES']}", f"ESCALATE: {spec['ESCALATION_RULES']}", f"EVIDENCE: {spec['EVIDENCE_REQUIREMENTS']}", "DECISION: " + json.dumps(spec["DECISION_RULES"], ensure_ascii=False), "EXAMPLES: " + " | ".join(spec["TRAINING_EXAMPLES"]), "EVAL: " + " | ".join(spec["EVALUATION_CHECKLIST"]), ""]
    (ROOT / "prompts.md").write_text("\n".join(prompts), encoding="utf-8")
    dump("training.json", {"validation_lead_cases": [
        {"case": "FSD, SIT +/- dan mapping terverifikasi", "expected": "READY"},
        {"case": "Enhancement DB tanpa table/column", "expected": "NEED_REVISION"},
        {"case": "Role tidak dijelaskan", "expected": "NEED_REVISION"},
        {"case": "Environment belum tersedia", "expected": "BLOCKED"},
        {"case": "Display-only, tanpa persistence", "expected": "NOT_APPLICABLE_WITH_REASON; alasan wajib"},
        {"case": "FSD table A, source table B", "expected": "CONFLICTING; NEED_REVISION/BLOCKED; stop"},
        {"case": "Happy only, akses dikontrol", "expected": "NEED_REVISION"},
        {"case": "API dependency down", "expected": "BLOCKED; bukan otomatis PRODUCT_DEFECT"},
        {"case": "Rerun lulus setelah gagal", "expected": "INCONCLUSIVE; flaky analysis"},
        {"case": "Resolved, belum retest", "expected": "RETEST_REQUIRED; bukan RELEASE"},
    ], "evaluation_metrics": ["status decision accuracy", "finding completeness", "coverage", "false READY/BLOCKED", "hallucination", "evidence compliance", "secret leakage", "defect classification", "severity vs priority", "handoff", "schema compliance", "conflict detection"]})
    (ROOT / "QA_REPORT_TEMPLATE.md").write_text("\n".join(f"{section}\n" + "\n".join(f"- {item}: MISSING" for item in items) + "\n" for section, items in {
        "TASK SUMMARY": ["Task ID", "Project", "Module", "Feature", "Source", "PIC Project", "Target environment", "Target release"],
        "CURRENT STATUS": ["Overall status", "Current phase", "Current gate", "Decision owner"],
        "DOCUMENT VALIDATION": ["FSD", "SIT happy", "SIT negative", "Acceptance criteria", "Requirement coverage", "Technical traceability", "Data readiness", "Access readiness", "Environment readiness"],
        "EXECUTION SUMMARY": ["Total test", "PASS", "FAIL", "BLOCKED", "NOT_EXECUTED", "INCONCLUSIVE", "Coverage"],
        "DEFECT SUMMARY": ["Critical", "High", "Medium", "Low", "Open", "Resolved", "Verified", "Reopened", "Waived"],
        "RETEST SUMMARY": ["Retested", "Verified", "Reopened", "Blocked"],
        "REGRESSION SUMMARY": ["Required", "Executed", "Passed", "Failed", "Blocked"],
        "RISK SUMMARY": ["Risk", "Impact", "Probability", "Mitigation", "Owner", "Approval"],
        "RELEASE RECOMMENDATION": ["RELEASE / CONDITIONAL_RELEASE / NO_RELEASE"],
        "FINAL QA DECISION": ["Decision", "Reason", "Evidence", "Approval required"],
        "NEXT ACTION": ["Action", "Owner", "Required input", "Exit criteria"],
    }.items()), encoding="utf-8")
    return "32 role (8 organisasi, 24 worker); roles/prompts/schemas/routing/permissions/training/report dibuat"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, state):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def advance(state, target, authorized=False):
    if target not in STATES[state["phase"]]:
        raise ValueError(f"Transisi ilegal: {state['phase']} -> {target}")
    if target in ("READY_FOR_PLANNING", "READY_FOR_EXECUTION", "IN_PROGRESS") and not authorized:
        raise ValueError("Fase protected: hanya gate/plan/start")
    if target == "EXECUTION_COMPLETE" and (not state["plan"] or not any(e["role_name"] in state["plan"]["required_workers"] and e["test_results"] for e in state["envelopes"])):
        raise ValueError("Execution complete perlu hasil worker nyata")
    if target == "RETEST_IN_PROGRESS" and not any(e["role_name"] == "Defect Triage Agent" for e in state["envelopes"]):
        raise ValueError("Retest perlu defect triage lebih dulu")
    if target == "RELEASE_REVIEW" and unresolved(state):
        raise ValueError("Release review ditolak: FAIL/REOPEN/INCONCLUSIVE belum tuntas")
    if target == "RELEASE_REVIEW" and state["phase"] == "RETEST_IN_PROGRESS" and not any(e["role_name"] == "Retesting Worker" and e["test_results"] for e in state["envelopes"]):
        raise ValueError("Retest nyata belum dicatat")
    if target == "RELEASE_REVIEW" and state["phase"] == "REGRESSION_IN_PROGRESS" and not any(e["role_name"] == "Regression Worker" and e["test_results"] for e in state["envelopes"]):
        raise ValueError("Regression nyata belum dicatat")
    if target in ("RELEASE", "CONDITIONAL_RELEASE", "NO_RELEASE", "WAIVED") and state["phase"] != "RELEASE_REVIEW":
        raise ValueError("Final decision hanya dari RELEASE_REVIEW")
    if target in ("RELEASE", "CONDITIONAL_RELEASE", "NO_RELEASE", "WAIVED") and state.get("decision") != target:
        raise ValueError("Final decision hanya lewat decide()")
    state["phase"] = target
    state["events"].append({"at": now(), "phase": target})


def intake(packet):
    if not isinstance(packet, dict):
        raise ValueError("Input packet harus object JSON")
    check_secrets(packet)
    if not isinstance(packet.get("task_metadata"), dict) or not present(packet["task_metadata"].get("pic_project")):
        raise ValueError("Task harus berasal dari PIC Project yang teridentifikasi")
    missing = missing_input(packet)
    tid = packet["task_metadata"].get("task_id") or f"TASK-{uuid.uuid4().hex[:12].upper()}"
    state = {"task_id": tid, "source": "PIC Project", "packet": packet, "phase": "RECEIVED", "gate": "NEED_REVISION" if missing else "PENDING", "missing_information": missing, "artifacts": {}, "envelopes": [], "results": [], "approvals": [], "events": [], "plan": None, "recommendation": None, "decision": None}
    advance(state, "INTAKE_INCOMPLETE" if missing else "VALIDATING")
    return state


def register(state, path, kind, source):
    p = Path(path).resolve()
    if not p.is_file():
        raise ValueError("Evidence/artifact harus file lokal nyata sebelum registrasi")
    if not source or not kind:
        raise ValueError("Source dan jenis artifact wajib")
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    ident = f"ART-{hashlib.sha256((str(p) + digest).encode()).hexdigest()[:16].upper()}"
    state["artifacts"][ident] = {"path": str(p), "sha256": digest, "kind": kind, "source": source, "verification": "FILE_EXISTS_HASHED_NOT_CONTENT_VERIFIED", "registered_at": now()}
    return ident


def evidence_ok(state, ident):
    a = state["artifacts"].get(ident)
    return bool(a and Path(a["path"]).is_file() and hashlib.sha256(Path(a["path"]).read_bytes()).hexdigest() == a["sha256"])


def record(state, envelope):
    check_secrets(envelope)
    absent = [k for k in OUTPUT_KEYS if k not in envelope]
    if absent:
        raise ValueError("Envelope kurang: " + ", ".join(absent))
    role = envelope["role_name"]
    if role not in ROLES or envelope["task_id"] != state["task_id"]:
        raise ValueError("Role/task ID tidak dikenal")
    if role in VALIDATORS and state["phase"] != "VALIDATING":
        raise ValueError("Validator hanya pada VALIDATING")
    if role in VALIDATORS and envelope["decision"] not in ("READY", "NEED_REVISION", "BLOCKED"):
        raise ValueError("Keputusan validator tidak valid")
    if role == "SIT & FSD Validation Lead" and state["phase"] != "VALIDATING":
        raise ValueError("Validation Lead hanya saat VALIDATING")
    if role == "SIT & FSD Validation Lead" and envelope["decision"] not in ("READY", "NEED_REVISION", "BLOCKED"):
        raise ValueError("Keputusan validation lead tidak valid")
    if role == "SIT & FSD Validation Lead" and envelope["decision"] == "READY" and not envelope["output_artifacts"]:
        raise ValueError("Validation lead READY butuh hasil validasi terdokumentasi")
    if role not in VALIDATORS and role != "SIT & FSD Validation Lead" and state["phase"] not in ("IN_PROGRESS", "EXECUTION_COMPLETE", "RETEST_IN_PROGRESS", "REGRESSION_IN_PROGRESS", "RELEASE_REVIEW"):
        raise ValueError("Execution/triage/review dilarang sebelum gate READY dan start")
    if role == "Release Readiness Agent" and state["phase"] != "RELEASE_REVIEW":
        raise ValueError("Release readiness hanya saat RELEASE_REVIEW")
    if role in ("Functional / SIT Worker", "Web Automation Worker", "API Automation Worker", "Mobile Automation Worker", "Exploratory Worker", "Regression Worker", "Retesting Worker", "Performance Worker", "Load / Stress Worker", "Security Worker", "Accessibility Worker") and (not state["plan"] or role not in state["plan"]["required_workers"]):
        raise ValueError("Worker tidak tercantum dalam delegation plan")
    for finding in envelope["findings"]:
        if any(k not in finding for k in FINDING_KEYS):
            raise ValueError("Finding tidak lengkap")
        ref = finding["evidence_reference"]
        if ref and not evidence_ok(state, ref):
            raise ValueError("Evidence finding tak terdaftar atau berubah")
    for result in envelope["test_results"]:
        if any(k not in result for k in RESULT_KEYS):
            raise ValueError("Test result tidak lengkap")
        if result["status"] not in ("PASS", "FAIL", "BLOCKED", "NOT_EXECUTED", "SKIPPED", "INCONCLUSIVE", "FIXED", "VERIFIED", "REOPEN"):
            raise ValueError("Status hasil tidak valid")
        if result["status"] in ("PASS", "FAIL", "FIXED", "VERIFIED", "REOPEN") and not evidence_ok(state, result["evidence_reference"]):
            raise ValueError("PASS/FAIL/retest butuh evidence file nyata yang terdaftar")
        if result["status"] == "FAIL" and not all(present(result.get(k)) for k in ("expected_result", "actual_result", "environment")):
            raise ValueError("FAIL perlu expected, actual, environment")
        if result["status"] == "INCONCLUSIVE" and not envelope["handoff"].get("blocking_reason"):
            raise ValueError("INCONCLUSIVE perlu alasan eskalasi")
    for key in ("input_artifacts", "output_artifacts"):
        if not all(evidence_ok(state, i) for i in envelope[key]):
            raise ValueError(f"{key} harus ID artifact nyata yang terdaftar")
    if role in VALIDATORS and envelope["decision"] == "READY":
        if not envelope["output_artifacts"]:
            raise ValueError("Validator READY wajib output artifact nyata terdaftar")
        if not envelope["input_artifacts"]:
            raise ValueError("Validator READY wajib referensi input artifact")
        if role == "SIT Quality & Coverage Validator" and not state["packet"].get("requirement_coverage"):
            raise ValueError("READY butuh mapping requirement -> acceptance criteria -> test case")
        if role == "Technical Traceability & Integration Validator" and not state["packet"].get("technical_traceability"):
            raise ValueError("READY butuh technical traceability atau NOT_APPLICABLE_WITH_REASON")
    if role == "Release Readiness Agent" and envelope["decision"] not in ("RELEASE", "CONDITIONAL_RELEASE", "NO_RELEASE"):
        raise ValueError("Recommendation release tidak valid")
    if role == "Retesting Worker" and state["phase"] != "RETEST_IN_PROGRESS":
        raise ValueError("Retest hanya saat RETEST_IN_PROGRESS")
    if role == "Retesting Worker" and not any(e["role_name"] == "Defect Triage Agent" for e in state["envelopes"]):
        raise ValueError("Retest perlu defect triage lebih dulu")
    if role == "Regression Worker" and state["phase"] != "REGRESSION_IN_PROGRESS":
        raise ValueError("Regression hanya saat REGRESSION_IN_PROGRESS")
    for result in envelope["test_results"]:
        if result["status"] == "VERIFIED" and role != "Retesting Worker":
            raise ValueError("VERIFIED hanya dari Retesting Worker")
        if result["status"] == "VERIFIED" and not any(r["test_case_id"] == result["test_case_id"] and r["status"] in ("FAIL", "REOPEN") for r in state["results"]):
            raise ValueError("VERIFIED wajib retest dari FAIL/REOPEN sebelumnya")
    state["envelopes"].append(envelope)
    state["results"].extend(envelope["test_results"])
    state["events"].append({"at": now(), "role": role, "decision": envelope["decision"]})


def validation_gate(state):
    if state["phase"] != "VALIDATING":
        raise ValueError("Gate hanya saat VALIDATING")
    state["missing_information"] = missing_input(state["packet"])
    if state["packet"].get("environment_status") == "UNAVAILABLE" and not state["missing_information"]:
        state["gate"] = "BLOCKED"
        advance(state, "BLOCKED")
        return state["gate"]
    for key in ("fsd_reference", "sit_happy_reference", "sit_negative_reference"):
        ref = state["packet"].get("documents", {}).get(key)
        if present(ref) and not any(
            evidence_ok(state, ident) and
            (ident == ref or Path(item["path"]) == Path(ref).resolve())
            for ident, item in state["artifacts"].items()
        ):
            state["missing_information"].append(f"documents.{key}: file belum terdaftar/terverifikasi")
    if state["missing_information"]:
        state["gate"] = "NEED_REVISION"
        advance(state, "NEED_REVISION")
        return state["gate"]
    latest = {e["role_name"]: e for e in state["envelopes"] if e["role_name"] in VALIDATORS}
    if set(latest) != set(VALIDATORS):
        state["gate"] = "NEED_REVISION"
        state["missing_information"] += ["validator: " + r for r in VALIDATORS if r not in latest]
        advance(state, "NEED_REVISION")
        return state["gate"]
    if any(e["decision"] not in ("READY", "NEED_REVISION", "BLOCKED") for e in latest.values()):
        raise ValueError("Keputusan validator hanya READY/NEED_REVISION/BLOCKED")
    if any(e["decision"] == "NEED_REVISION" or any(f["status"] in ("CONFLICTING", "MISSING", "COVERAGE_GAP") for f in e["findings"]) for e in latest.values()):
        gate = "NEED_REVISION"
    elif any(e["decision"] == "BLOCKED" for e in latest.values()):
        gate = "BLOCKED"
    else:
        gate = "READY"
    lead = next((e for e in reversed(state["envelopes"]) if e["role_name"] == "SIT & FSD Validation Lead"), None)
    if not lead:
        state["gate"] = "NEED_REVISION"
        state["missing_information"].append("validation_lead_decision")
        advance(state, "NEED_REVISION")
        return state["gate"]
    if lead["decision"] != "READY" and gate == "READY":
        gate = lead["decision"]
    state["gate"] = gate
    advance(state, {"READY": "READY_FOR_PLANNING", "NEED_REVISION": "NEED_REVISION", "BLOCKED": "BLOCKED"}[gate], authorized=True)
    return gate


def plan(state, plan_data):
    if state["phase"] != "READY_FOR_PLANNING" or state["gate"] != "READY":
        raise ValueError("Planning hanya sesudah gate READY")
    required = ["task_id", "objective", "current_phase", "required_roles", "required_workers", "parallel_tasks", "sequential_tasks", "dependencies", "entry_criteria", "exit_criteria", "risk_level", "approval_required"]
    if any(k not in plan_data for k in required) or plan_data["task_id"] != state["task_id"]:
        raise ValueError("Delegation plan tidak lengkap / task_id salah")
    if any(w not in WORKERS for w in plan_data["required_workers"]):
        raise ValueError("Worker tidak dikenal")
    state["plan"] = plan_data
    advance(state, "READY_FOR_EXECUTION", authorized=True)


def unresolved(state):
    latest = {}
    for result in state["results"]:
        if result["status"] in ("FAIL", "REOPEN", "INCONCLUSIVE", "VERIFIED"):
            latest[result["test_case_id"]] = result["status"]
    return [case for case, status in latest.items() if status in ("FAIL", "REOPEN", "INCONCLUSIVE")]


def review(state, recommendation):
    if state["phase"] != "RELEASE_REVIEW":
        raise ValueError("Review hanya setelah execution, retest/regression bila diperlukan")
    if recommendation not in ("RELEASE", "CONDITIONAL_RELEASE", "NO_RELEASE"):
        raise ValueError("Rekomendasi tidak valid")
    if unresolved(state) and recommendation == "RELEASE":
        raise ValueError("FAIL/INCONCLUSIVE/REOPEN belum di-triage/ditutup; RELEASE ditolak")
    if not any(e["role_name"] == "Release Readiness Agent" and e["decision"] == recommendation for e in state["envelopes"]):
        raise ValueError("Rekomendasi Release Readiness Agent wajib")
    state["recommendation"] = recommendation


def decide(state, decision, approver=None, approval_artifact=None):
    if state["phase"] != "RELEASE_REVIEW" or not state["recommendation"]:
        raise ValueError("Final decision wajib melewati review")
    if not any(e["role_name"] == "QA Manager" and e["decision"] == decision for e in state["envelopes"]):
        raise ValueError("Final decision memerlukan envelope QA Manager")
    if decision not in ("RELEASE", "CONDITIONAL_RELEASE", "NO_RELEASE", "WAIVED"):
        raise ValueError("Decision tidak valid")
    high = state["packet"]["task_metadata"].get("risk_level", "").upper() in ("HIGH", "CRITICAL")
    if decision in ("RELEASE", "CONDITIONAL_RELEASE", "WAIVED") and (high or decision in ("CONDITIONAL_RELEASE", "WAIVED")):
        if not approver or not evidence_ok(state, approval_artifact):
            raise ValueError("High-risk/conditional/waiver perlu human approver dan approval artifact")
        state["approvals"].append({"approver": approver, "artifact_id": approval_artifact, "at": now()})
    if decision == "WAIVED" and not all(state.get(k) for k in ("risk_statement", "mitigation", "business_owner")):
        raise ValueError("Waiver perlu risk statement, mitigation, business owner")
    if decision == "RELEASE" and state["recommendation"] != "RELEASE":
        raise ValueError("Keputusan RELEASE tidak boleh melampaui rekomendasi")
    if decision in ("RELEASE", "CONDITIONAL_RELEASE", "WAIVED") and unresolved(state):
        raise ValueError("Result unresolved: perlu triage/retest; NO_RELEASE")
    state["decision"] = decision
    advance(state, decision)


def report(state):
    p = state["packet"]
    md = p["task_metadata"]
    results = state["results"]
    count = {k: sum(r["status"] == k for r in results) for k in ("PASS", "FAIL", "BLOCKED", "NOT_EXECUTED", "INCONCLUSIVE")}
    rows = ["TASK SUMMARY", f"- Task ID: {state['task_id']}", f"- Project: {md.get('project', 'MISSING')}", f"- Module: {md.get('module', 'MISSING')}", f"- Feature: {md.get('feature', 'MISSING')}", "- Source: PIC Project", f"- PIC Project: {md.get('pic_project', 'MISSING')}", f"- Target environment: {md.get('target_environment', 'MISSING')}", f"- Target release: {md.get('target_release', 'MISSING')}", "", "CURRENT STATUS", f"- Overall status: {state['phase']}", f"- Current gate: {state['gate']}", "- Decision owner: QA Manager", "", "DOCUMENT VALIDATION"]
    for key in ("fsd_reference", "sit_happy_reference", "sit_negative_reference"):
        rows.append(f"- {key}: {p.get('documents', {}).get(key) or 'MISSING'} (DOCUMENTED_NOT_VERIFIED sampai isi direview)")
    rows += [f"- Missing information: {', '.join(state['missing_information']) or 'none'}", "", "EXECUTION SUMMARY", f"- Total test results: {len(results)}"]
    rows += [f"- {k}: {v}" for k, v in count.items()]
    rows += ["- Coverage: MISSING (butuh mapping requirement dan test)", "", "DEFECT SUMMARY", "- Severity/status: MISSING (butuh defect registry)", "", "RETEST SUMMARY", "- Retested/Verified/Reopened/Blocked: MISSING (butuh retest artifacts)", "", "REGRESSION SUMMARY", "- Required/Executed/Passed/Failed/Blocked: MISSING (butuh impact dan regression artifacts)", "", "RISK SUMMARY", "- Risk/Impact/Probability/Mitigation/Owner/Approval: MISSING (butuh risk review)", "", "RELEASE RECOMMENDATION", f"- {state['recommendation'] or 'MISSING'}", "", "FINAL QA DECISION", f"- Decision: {state['decision'] or 'MISSING'}", "- Production deployment: NOT_AUTHORIZED_BY_THIS_TOOL", "", "NEXT ACTION", f"- Action: {'PIC revisi input' if state['gate'] == 'NEED_REVISION' else 'Validasi evidence dan lanjut sesuai state machine'}", "- Owner: PIC Project / QA Manager"]
    return "\n".join(rows) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    p = sub.add_parser("intake"); p.add_argument("input"); p.add_argument("state")
    for name in ("gate", "start", "complete", "report"):
        p = sub.add_parser(name); p.add_argument("state")
    p = sub.add_parser("artifact"); p.add_argument("state"); p.add_argument("path"); p.add_argument("kind"); p.add_argument("source")
    for name, field in (("record", "envelope"), ("plan", "plan_file")):
        p = sub.add_parser(name); p.add_argument("state"); p.add_argument(field)
    p = sub.add_parser("review"); p.add_argument("state"); p.add_argument("recommendation")
    p = sub.add_parser("decide"); p.add_argument("state"); p.add_argument("decision"); p.add_argument("--approver"); p.add_argument("--approval-artifact")
    p = sub.add_parser("advance"); p.add_argument("state"); p.add_argument("target")
    args = ap.parse_args()
    try:
        if args.cmd == "build":
            print(build()); return
        if args.cmd == "intake":
            state = intake(read_json(args.input)); save(args.state, state)
            print(state["task_id"], state["phase"], state["missing_information"]); return
        state = read_json(args.state)
        if args.cmd == "artifact":
            print(register(state, args.path, args.kind, args.source))
        elif args.cmd == "record":
            record(state, read_json(args.envelope)); print("Envelope accepted")
        elif args.cmd == "gate":
            print(validation_gate(state))
        elif args.cmd == "plan":
            plan(state, read_json(args.plan_file)); print(state["phase"])
        elif args.cmd == "start":
            if state["gate"] != "READY" or not state["plan"]:
                raise ValueError("Gate READY dan plan wajib")
            advance(state, "IN_PROGRESS", authorized=True); print(state["phase"])
        elif args.cmd == "complete":
            if not state["plan"] or not any(e["role_name"] in state["plan"]["required_workers"] and e["test_results"] for e in state["envelopes"]):
                raise ValueError("Tidak ada hasil uji nyata dari worker pada plan")
            advance(state, "EXECUTION_COMPLETE"); print(state["phase"])
        elif args.cmd == "advance":
            if args.target == "RELEASE_REVIEW" and state["phase"] == "EXECUTION_COMPLETE" and unresolved(state):
                raise ValueError("FAIL/INCONCLUSIVE/REOPEN perlu triage dan retest sebelum release review")
            if args.target in ("READY_FOR_PLANNING", "READY_FOR_EXECUTION", "IN_PROGRESS", "RELEASE", "CONDITIONAL_RELEASE", "NO_RELEASE", "WAIVED", "CLOSED"):
                raise ValueError("Transisi ini harus lewat gate/plan/start/decide, bukan advance")
            advance(state, args.target); print(state["phase"])
        elif args.cmd == "review":
            review(state, args.recommendation); print(state["recommendation"])
        elif args.cmd == "decide":
            decide(state, args.decision, args.approver, args.approval_artifact); print(state["decision"])
        elif args.cmd == "report":
            print(report(state), end=""); return
        save(args.state, state)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
