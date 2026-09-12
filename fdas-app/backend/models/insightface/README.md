# InsightFace model provisioning

FDAS Phase 10.7A uses the InsightFace `buffalo_l` model pack as a local,
CPU-only research/demo component. The model files are intentionally ignored by
Git because the extracted pack is approximately 325 MiB.

Provision from `backend/` with the verified Python 3.11 environment:

```powershell
.\.venv\Scripts\python.exe scripts\provision_insightface_model.py
```

The provisioning command downloads the official release archive, verifies its
known SHA-256 and each required model file, then extracts to:

```text
backend/models/insightface/buffalo_l/
```

Application runtime never downloads the model. It loads this explicit local
directory using ONNX Runtime `CPUExecutionProvider` and fails closed when files
are missing or invalid.

InsightFace library code is MIT licensed. InsightFace-supplied pretrained model
packs, including `buffalo_l`, carry research/non-commercial restrictions unless
separately licensed. FDAS uses the pack only as a Final Year Project research
and demonstration component and does not claim unrestricted commercial rights.
