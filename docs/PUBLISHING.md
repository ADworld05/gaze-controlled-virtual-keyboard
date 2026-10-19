# GitHub publishing checklist

Target: https://github.com/ADworld05/gaze-controlled-virtual-keyboard

## What to upload

- `app/`: the current working yellow-tinted interface and all application modules.
- `assets/sounds/`: local tones and optional prerecorded voice clips.
- `tools/`: asset setup and verification utilities.
- `tests/`: control/geometry/calibration tests.
- `docs/`: documentation, screenshots, this guide and the exact upload manifest.
- `LICENSE`, `README.md`, `requirements.txt`, `requirements-lock.txt`, `.gitignore`.

`upload-manifest.txt` lists the individual files selected by Git's ignore rules. Git does not upload empty folders. The model directory is created by setup after cloning.

## What stays on your laptop

`.venv/`, caches, generated model/checksum, `work/`, local UI backups in `ui_redesign/`, and editor metadata are ignored. The earlier interface backup has not been deleted. Personal settings and calibration normally live under LOCALAPPDATA, outside this project. No camera recordings are needed.

## Review before publishing

Open PowerShell and run:

```powershell
Set-Location 'E:\study\Projecrts\gaze detctions\gaze_keyboard_v2'
git status --short
git add .gitignore LICENSE README.md requirements.txt requirements-lock.txt app assets/sounds tools tests docs
git diff --cached --stat
git diff --cached --name-only
```

These commands stage files locally; they do not publish anything. Check the names against `docs/upload-manifest.txt`. Do not include `.venv`, the old UI backup or a downloaded `.task` file. To unstage a file before the first commit, use `git rm --cached -- path/to/file`; it keeps the local file.

After you have reviewed the file list:

```powershell
git commit -m "Add gaze-controlled virtual keyboard"
git branch -M main
git remote add origin https://github.com/ADworld05/gaze-controlled-virtual-keyboard.git
git remote -v
```

If origin already exists, inspect it with `git remote -v`; use `git remote set-url origin https://github.com/ADworld05/gaze-controlled-virtual-keyboard.git` only if it needs changing.

The next command publishes the commit. Run it only when you are ready:

```powershell
git push -u origin main
```

Sign into GitHub if prompted. These instructions assume an empty remote repository. If GitHub already contains a README or another commit, stop on a rejected push and reconcile that history; do not force-push.

## Cloning check for another user

The public README contains the clone, Python 3.12 environment, dependency installation, asset setup and launch commands. After publication, try those commands in a different folder to verify the download/install path independently of the development environment. The entry point is `python -m app`, run from the repository root.

## Review results — 2026-10-20

- 44 unit tests passed. The sandbox's default temporary directory was unwritable; rerunning with TEMP/TMP pointed to the ignored project `work/temp` folder passed.
- Installed environment: Python 3.12.14, NumPy 1.26.4, OpenCV 4.11.0, MediaPipe 0.10.21, PySide6 6.10.2.
- `pip check` passed.
- Offscreen UI/control integration and all 38 local MP3 decoding checks passed. Screenshots were regenerated and inspected.
- Local model load/blank-frame inference and simulated camera error/release checks passed.
- No real webcam accuracy study, fresh network install or remote clone was performed in this review. Other operating systems are not verified.
- No source-code behavior was changed during repository preparation.
- The original project code now uses the MIT License (copyright 2026 ADworld05); third-party assets retain their own terms. Known voice-clip provenance is documented in `model.md`; redistribution rights have not been independently established.
- No files were staged, committed or pushed by the assistant.

