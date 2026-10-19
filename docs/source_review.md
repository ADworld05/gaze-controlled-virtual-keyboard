# Source review

Reference inspected read-only: `E:\study\Projecrts\gaze detctions\my_code`.

All nine Python files were read. No requirements file or packaged entry point was present.

- `Gaze detection/Main_Program/Gaze_controlled_keyboard.py` is the integrated main program. It opens two Tk sensitivity wizards, starts legacy `mp.solutions.face_mesh.FaceMesh(refine_landmarks=True)`, initializes pygame, then runs a capture thread beside Tk. OpenCV, MediaPipe, NumPy, Tkinter and pygame are required. Launching previously required a working directory containing `sounds/`.
- Iris rings 469–472 and 474–477 and centers 468/473 are used. Eye-name constants are inconsistent across modules. Input is mirrored before inference. Horizontal commands use ratios of distances to corners; denominators have no zero guard. “High” sensitivity raises the movement threshold, making movement harder.
- Vertical gaze uses a left-eye lid position and eye height captured once at startup. It mixes those stale positions with subsequent iris measurements. Startup without a face leaves `eye_height`, `left_eye_top` and `blink_threshold` undefined; the first capture is also converted without checking success.
- Blink selection increments a counter while a lid gap remains below a threshold. It does not require reopening. A long closure can count twice. Navigation and blinking share `previous_time` and reset the same counter; normal single blinks can accumulate indefinitely. There are no duration bounds, target binding, or deliberate-gesture interval.
- Main keyboard rows are alphabetical with unequal lengths. Downward movement sometimes refuses a valid transition rather than choosing a nearby key. The GUI is fixed-size and text is a one-line Entry. There is no pause, calibration workflow, settings persistence, dwell mode, case switch, clipboard, or clear confirmation.
- Tk `root.after` is called by the camera thread; there is no bounded mailbox, stop event, thread join, or coordinated shutdown. Camera failure calls `root.quit()` from that thread. Closing the window can leave camera cleanup dependent on process exit.
- `Resources/pupil_keyboard.py` is a second integrated prototype with an initial face-wait loop that cannot terminate on camera failure, stale calibration geometry, similar gesture problems, and a 2000 ms `cv2.waitKey` delay.
- `Resources/virtual_keyboard/virtual_keyboard.py` builds QWERTY mouse buttons but never appends letter rows to `key_buttons`; only Space/Backspace are navigable. Its row-navigation code therefore does not implement the displayed letter grid.
- `Resources/cordinate_plot.py` is an exploratory video/plot script using a missing relative `samplevideo.mp4`, growing histories and reversed subject eye labels. It is not the main application.
- `Resources/Pop_up_wizard/{sensitivity,value_input}.py` duplicate sensitivity dialogs. Closing the main wizards without submission leaves unset values; float input is subsequently converted with `int()`.
- `Resources/sound_genration/play_sound.py` is a fragment depending on undefined globals and missing `os`. `sound_generator.py` uses online gTTS to generate MP3 speech. `voice_keyboard.py` imports pyttsx3/keyboard but contains no actual input loop; its synchronous speaking helper would block if used.

There are 38 MP3 files in each of two sound folders (letters, digits, Space, Backspace). Their filename/size sets and hashes were inspected; matching filenames do not all have matching content. V2 consistently uses the top-level `my_code/sounds` set. Qt decoding inspection is recorded in verification.md. They are local spoken-key assets, unsuitable as constant navigation feedback. V2 reuses copies only for optional selected-key speech and generates original short WAV tones locally. Neither reference folder is modified. Speech is off by default; no online TTS is used by V2.

V2 replaces the control loop and interface rather than importing these scripts, which execute side effects at import time. Source review describes behavior verified from code, not measured webcam performance.
