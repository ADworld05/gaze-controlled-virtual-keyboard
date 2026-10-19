# Model, landmarks and offline assets

The bundled model is Google's Face Landmarker float16 version 1:

https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task

Official setup/API reference:
https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python

Official landmark connection definitions:
https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/python/solutions/face_mesh_connections.py

The Tasks model returns 478 points. V2 verifies the count and rejects missing or non-finite landmarks. The subject's right eye uses corners 33/133, lids 159/145 and iris ring 469–472. The subject's left uses corners 362/263, lids 386/374 and iris ring 474–477. Ring averages avoid relying on center-point naming. Coordinates are scaled to pixel aspect ratio, projected onto an eye-local corner axis and its perpendicular, then divided by eye width. Eye openness is lid distance / eye width; vertical gaze never divides by a closing lid gap.

Inference uses the unmirrored frame. Only the preview is mirrored. Calibration learns signed axes from explicit LEFT/RIGHT and UP/DOWN looks; it does not assume that increasing image-x means looking right. Synthetic mirrored-profile tests check that the mapping survives an x-axis inversion. Live direction mapping still requires the webcam checklist; this is directional control, not exact screen-point gaze estimation.

`tools/setup_assets.py` downloads the model atomically if absent, records its SHA256 in `assets/models/SHA256.txt`, and generates two original envelope-shaped sine-tone WAV files (selection 85 ms, navigation 35 ms). It is the only application setup script using the network. It preserves existing model and tone files. Google assets retain their source terms; the original project's speech copies retain their original provenance (generated with gTTS per its source). No third-party sound license is asserted.

Application startup uses the model and sound files relative to the package directory. It makes no network calls and does not save camera images/video. A missing model produces an actionable camera status. Missing speech is silently skipped. Missing/unavailable audio never disables typing. Speech playback replaces the previous utterance instead of creating a queue.

Dependency choice: the initial 0.10.35 trial successfully ran local inference but emitted a Clearcut uploader network-attempt error. V2 therefore pins the compatible Python 3.12 Windows Tasks release **0.10.21** and NumPy 1.26.4/OpenCV contrib 4.11.0.86. Google's maintainer confirms that newer binary releases include telemetry and expose no official disable API: https://github.com/google-ai-edge/mediapipe/issues/6291. The final package was rechecked with local model inference under restricted network access; no Clearcut log appeared. This is an observed offline run, not a packet-capture audit or a guarantee about every third-party binary. Application code has no runtime network request path.
