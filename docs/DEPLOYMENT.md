# Deployment Guide — The Beauty Studio

> **Status:** not deployed. Deployment requires the repository owner's GitHub and Streamlit Community Cloud accounts.

## 1. Requirements
- Python **3.11** (verified locally with 3.11.9).
- `requirements.txt` (pinned), `packages.txt` (system libraries for OpenCV pulled in by MediaPipe).
- Outbound HTTPS to `storage.googleapis.com` on first analysis **or** a pre-provisioned model file.
- No secrets or environment variables are required.

## 2. Pre-deployment checklist
1. `python -m pytest -q` passes.
2. `python -m ruff check .` and `python scripts/validate_data.py` pass.
3. `git status` shows no `.env`, `.venv/`, `models/*.task`, images or caches staged.
4. All paths are project-relative (`src/config.py` resolves from the repository root).
5. App starts from a clean virtual environment: `streamlit run app.py`.

## 3. Streamlit Community Cloud (recommended, free)
1. Create a GitHub repository and push this project (the owner must do this or explicitly authorise it).
2. Sign in at <https://share.streamlit.io> with GitHub → **Create app** → select the repository, branch `main`, main file `app.py`.
3. **Advanced settings → Python version: 3.11.**
4. Deploy. The platform installs `packages.txt` (apt) and `requirements.txt` (pip).
   *Unverified until the first deployment:* `packages.txt` lists `libgl1` and `libglib2.0-0`, which OpenCV's non-headless build (a MediaPipe dependency) typically needs on Debian. If the build log reports an unknown package (newer Debian releases renamed `libglib2.0-0` to `libglib2.0-0t64`), adjust that line. If the app logs `ImportError: libGL.so.1`, `libgl1` is missing.
5. On the first analysis the app downloads `face_landmarker.task` from the pinned Google URL and verifies its SHA-256 before use. To disable network fetches set `BEAUTY_STUDIO_ALLOW_MODEL_DOWNLOAD=0` in *Secrets/Environment* and commit the model instead (Apache-2.0; ~3.7 MB; keep the license notice).
6. Open the public URL and run the manual checklist in `TEST_PLAN.md §4`.

## 4. Docker / any Linux VM (alternative)
```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python scripts/download_model.py
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
```
Serve behind HTTPS (camera capture requires a secure context).

## 5. Model asset
| Item | Value |
|---|---|
| File | `models/face_landmarker.task` |
| Source | `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task` |
| SHA-256 | `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff` |
| Size | 3 758 596 bytes |
| License | Apache License 2.0 (MediaPipe models); see the Face Landmarker model card |

## 6. Post-deployment verification
Record in `TEST_PLAN.md §5`: URL opens; all pages render; a face photo analyzes; Shade Finder and Routine work; camera prompt appears over HTTPS.
