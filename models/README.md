# Model assets

`face_landmarker.task` (MediaPipe Face Landmarker, float16 v1, Apache-2.0) is **not committed**.

Obtain it with:

```bash
python scripts/download_model.py
```

The script downloads from the pinned Google URL and verifies the SHA-256 recorded in `src/config.py`.
If the file is absent and `BEAUTY_STUDIO_ALLOW_MODEL_DOWNLOAD` is not `0`, the app performs the same verified download on first analysis.
