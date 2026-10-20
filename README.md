# Agentic QA Organization

Kerangka pilot offline untuk mengatur alur QA berbasis role, dari task PIC Project sampai validasi dokumen, pencatatan hasil uji, retest/regression, dan keputusan QA. Ditulis dengan Python 3.11+ dan standard library. Repo ini **bukan** sistem multi-agent yang berjalan otomatis: role adalah kontrak/prompt, bukan proses yang langsung bisa dipanggil dari CLI. Tidak ada eksekusi Playwright, API, mobile, SIT nyata, atau deployment otomatis.

## Fungsi dan fitur

| Fitur | Fungsi |
| --- | --- |
| Registry 32 role | 8 role organisasi (1 QA Manager, 4 koordinator, 3 domain lead) dan 24 worker on-demand. `roles.json` memuat mission, tanggung jawab, input/output, batas tindakan, handoff, dan evaluasi; `prompts.md` memuat prompt per role. |
| Intake PIC Project | Membaca paket JSON berisi identitas PIC, FSD, SIT happy/negative, acceptance criteria, akses, data uji, impact, dan environment. Input kurang diberi status `INTAKE_INCOMPLETE`/`NEED_REVISION`; nilai `MISSING` tidak dianggap data valid. |
| Gate validasi sebelum eksekusi | Empat validator memeriksa kelengkapan dokumen, coverage SIT, kesiapan data/akses, dan traceability teknis. Validation Lead menggabungkan hasil menjadi `READY`, `NEED_REVISION`, atau `BLOCKED`. Eksekusi tidak bisa dimulai sebelum gate `READY` dan delegation plan ada. |
| Routing dan status task | State machine mengatur intake, validasi, planning, execution, retest, regression, release review, dan keputusan akhir. Jalur yang tidak sah ditolak. |
| Artifact dan evidence | File FSD, SIT, validasi, dan hasil uji didaftarkan sebagai `ART-...` dengan SHA-256. Referensi PASS/FAIL/retest harus menunjuk file terdaftar yang belum berubah. Hash membuktikan integritas file, **bukan** kebenaran isi atau kualitas uji. |
| Pencatatan hasil role | `record` menerima envelope sesuai `schemas.json`: temuan, hasil uji, referensi source/evidence, risiko, informasi kurang, dan handoff. `record` **mencatat**, bukan menjalankan role. |
| Perencanaan data uji | Enam kategori: Positive, Negative, Boundary, Empty, Combination, Volume. Kategori adalah panduan; nilai aktual harus berasal dari kebutuhan dan data riil. |
| Review dan keputusan | Release Readiness Agent memberi rekomendasi; QA Manager mencatat keputusan. Hasil FAIL/REOPEN/INCONCLUSIVE yang belum tuntas menghalangi release. Retest VERIFIED wajib dari Retesting Worker dan hasil sebelumnya. High-risk release, conditional release, dan waiver memerlukan referensi persetujuan manusia. |
| Laporan | `report` merangkum status task dan jumlah hasil uji yang tercatat; bagian tanpa data tetap `MISSING`, tidak diisi angka rekaan. |
| Guard keamanan dasar | Field rahasia pada paket/envelope ditolak; instruksi role melarang perubahan DB (hanya SELECT bila diizinkan), deploy/merge, dan efek eksternal tanpa persetujuan. Ini **bukan** sandbox atau autentikasi kuat. |

### Susunan role

- QA Manager: menerima task PIC dan memutuskan QA akhir.
- SIT & FSD Validation Lead: memimpin Document Completeness, SIT Quality & Coverage, Test Data & Access, serta Technical Traceability & Integration Validator.
- QA Lead: mengoordinasikan Automation QA Engineer, Manual QA Engineer, dan Performance / Security QA Specialist beserta worker-nya.
- QA Governance & Metrics Agent: coverage, test plan, test data, metrik.
- QA Release / Risk Agent: defect triage, severity/priority, release readiness, laporan.

Daftar lengkap dan batas masing-masing role: [roles.json](roles.json). Alur status: [routing.json](routing.json). Hak akses/hierarki: [permissions.json](permissions.json).

## Isi repo

| File | Isi |
| --- | --- |
| `organization.py` | Sumber definisi role, generator file turunan, dan CLI workflow offline. |
| `roles.json`, `prompts.md`, `permissions.json`, `routing.json`, `schemas.json`, `training.json`, `QA_REPORT_TEMPLATE.md` | File hasil `python organization.py build`; **jangan edit langsung** untuk perubahan permanen karena akan tertimpa. |
| `pic_input.example.json` | Template paket input; nilai `MISSING` harus diganti dari dokumen PIC. |
| `test_organization.py` | Smoke test offline memakai data mock, bukan hasil QA target. |
| `README.txt` | Panduan CLI terperinci, termasuk jalur retest dan keterbatasan. |

## Cara menjalankan pilot

Jalankan dari root repo:

    python organization.py build
    python test_organization.py
    python organization.py intake paket-PIC-riil.json state.json

Jangan jalankan `intake` terhadap template mentah: `pic_project` masih `MISSING`, sehingga sengaja ditolak. Setelah paket valid, daftarkan masing-masing FSD, SIT happy, SIT negative, dan output validasi sebagai artifact. Isi envelope hasil kerja empat validator dan Validation Lead dengan ID `ART-...`, lalu catat dan cek gate:

    python organization.py artifact state.json path/to/FSD.pdf document "PIC Project"
    python organization.py artifact state.json path/to/hasil-validasi.json validation "Document Completeness Validator"
    python organization.py record state.json path/to/envelope-validator.json
    python organization.py gate state.json
    python organization.py report state.json

Ulangi `artifact` untuk SIT happy/negative dan `record` untuk semua validator serta Validation Lead. Struktur input/output ada di [schemas.json](schemas.json). Jika gate `READY`, buat delegation plan, mulai eksekusi sesuai scope, daftarkan evidence hasil uji **nyata**, dan catat envelope worker. Urutan CLI lengkap ada di [README.txt](README.txt). `state.json` berisi data task dan diabaikan Git; simpan di lokasi aman, jangan masukkan password/token/PII.

## Mengubah role

Edit mission, relasi parent–child, atau guard di `organization.py`; lalu jalankan `python organization.py build` dan `python test_organization.py`. Perubahan generated JSON/prompt ikut dikomit. Mengubah `roles.json` atau `prompts.md` saja tidak bertahan setelah build.

## Batas versi v1.0.0

Tag `v1.0.0` menandai pilot awal. Belum ada agent runtime/dispatcher yang memanggil role secara otomatis, adapter Playwright/API/mobile, validasi semantik isi dokumen, penyimpanan state transaksional, otorisasi multi-user, atau persetujuan manusia yang terautentikasi. JSON state dirancang single-writer. Jangan perlakukan `READY` atau `RELEASE` dari demo/mock sebagai keputusan QA riil.
