Agentic QA Organization — pilot offline (stdlib Python)

Struktur: 8 role organisasi (QA Manager, 4 coordinator, 3 domain lead); 24 worker on-demand. Sumber kebenaran task: state JSON per task. Tidak membuat agent permanen atau menjalankan test terhadap sistem target. Template training/mock dalam test_organization.py bukan hasil QA riil.

File:
- organization.py: registry generator, CLI, guarded state machine, artifact registry SHA-256, gate, approval, report.
- roles.json, prompts.md: kontrak dan system prompt per 32 node; role level 3 tidak bebas delegasi.
- permissions.json, routing.json: parent/child, tool permission, state transitions, jalur pilot.
- schemas.json: PIC input, envelope, finding, test result, defect dan enam kategori test data.
- training.json: 10 skenario Validation Lead + evaluasi.
- QA_REPORT_TEMPLATE.md: laporan dengan placeholder MISSING.
- pic_input.example.json: bentuk input PIC; semua placeholder MISSING bukan data nyata.
- test_organization.py: smoke offline dengan fixture palsu; bukan test execution riil.

Cara pakai (dari folder ini):
  python organization.py build
  python test_organization.py
  python organization.py intake <paket-PIC-riil.json> state.json
  python organization.py report state.json

Template pic_input.example.json memang ditolak sampai pic_project terisi identitas PIC; jangan isi placeholder hanya demi melewati gate.

Untuk task PIC riil: salin pic_input.example.json ke lokasi task dan isi referensi dokumen, target environment, role, test data, mapping requirement, technical impact dan dependency dari PIC. Isi pic_project wajib identitas PIC riil (bukan MISSING). Jaga file state/task di lokasi aman; tidak menyimpan password/token/PII. Field dokumen bisa path file lokal atau ID artifact yang sudah diregistrasikan.

  python organization.py artifact state.json <path-FSD> document "PIC Project"
  python organization.py artifact state.json <path-SIT-happy> document "PIC Project"
  python organization.py artifact state.json <path-SIT-negative> document "PIC Project"
  python organization.py artifact state.json <path-validasi> validation "Document Completeness Validator"
  python organization.py record state.json <envelope-validator.json>
  python organization.py gate state.json

Panggil record untuk 4 validator lalu Validation Lead, masing-masing output_artifacts berisi ID hasil artifact register, input_artifacts ID dokumen PIC. Gate READY hanya setelah input lengkap, FSD/SIT terdaftar, keempat validator dan Validation Lead READY serta tidak ada MISSING/CONFLICTING/COVERAGE_GAP. Semua referensi teknis yang hanya tertulis di FSD tetap DOCUMENTED_NOT_VERIFIED. Validasi isi dokumen, traceability source, test data, role dan evidence dilakukan manusia/worker; hash file hanya membuktikan integritas file, bukan kebenaran isinya. Test negative authorization wajib bila fitur punya access control. Environment unavailable mengubah gate BLOCKED jika input dokumen lengkap; ketidaklengkapan dokumen = NEED_REVISION.

Setelah READY:
  python organization.py plan state.json <delegation-plan.json>
  python organization.py start state.json
  python organization.py artifact state.json <hasil-nyata> evidence "Functional / SIT Worker"
  python organization.py record state.json <envelope-execution.json>
  python organization.py complete state.json
  python organization.py advance state.json RELEASE_REVIEW
  python organization.py record state.json <envelope-release-readiness.json>
  python organization.py review state.json NO_RELEASE
  python organization.py record state.json <envelope-qa-manager.json>
  python organization.py decide state.json NO_RELEASE
  python organization.py report state.json

Jalur lain dari EXECUTION_COMPLETE: advance RETEST_REQUIRED → RETEST_IN_PROGRESS → RELEASE_REVIEW, atau REGRESSION_REQUIRED → REGRESSION_IN_PROGRESS → RELEASE_REVIEW. Panggil record untuk worker relevan dan simpan evidence riil. FAIL, INCONCLUSIVE, REOPEN tidak bisa menuju review langsung. FIXED dan RESOLVED tidak sama dengan VERIFIED; retest nyata wajib. Gunakan WAIVED hanya dengan human approval artifact dan risk statement, business owner, mitigation. CONDITIONAL_RELEASE/high-risk RELEASE memerlukan approval artifact. Production deployment/merge bukan fungsi tool ini.

Schema envelope mengacu schemas.json#/$defs/envelope; input_artifacts/output_artifacts berupa ID ART-... dari registry; evidence_reference pada PASS/FAIL/retest harus ID terdaftar. Simpan langkah reproduksi FAIL pada finding/defect artifact. Value kosong dan MISSING tidak boleh diganti dengan angka atau evidence dugaan. Uji load/security destruktif dan semua efek eksternal memerlukan approval sebelum worker berjalan, tidak cukup hanya field plan.

Known limitation: CLI ini kerangka koordinasi offline, bukan runner Playwright/API/mobile dan bukan engine LLM multi-agent otomatis. Prompt/permission dalam file bersifat instruksi, bukan sandbox keamanan OS; execution guard hanya memvalidasi struktur/status dan hash, bukan memverifikasi isi sumber. JSON state belum punya locking transaksi/ACL untuk multi-process; jalankan single-writer. Tidak gunakan pada production tanpa service dengan otorisasi, audit, secret vault, human approval terotentikasi, validasi source dan penyimpanan immutable.

Pilot Web SIT: isi paket PIC asli, daftarkan FSD + SIT happy/negative, jalankan 4 validator, cek gate, pilih Functional/SIT + Web/API hanya bila scope memuat keduanya; triage/retest/review sesuai temuan. Jangan aktifkan Mobile/Performance/Security/Load/Accessibility tanpa scope. Tidak ada task PIC riil terlampir pada request ini, jadi tidak ada eksekusi atau keputusan release nyata.
