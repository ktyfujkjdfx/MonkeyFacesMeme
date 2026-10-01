# MonkeyFacesMeme

**English** · [Русский](README_RU.md)

A Windows camera app that recognizes gestures and turns them into smooth,
full-screen monkey reactions. It includes a clean 720×720 output for Telegram
video messages through OBS Virtual Camera.

Everything runs locally. Camera frames are not uploaded anywhere.

## Features

- captures an integrated or USB camera at 1280×720 and 30 FPS;
- recognizes the body, face, and both hands with MediaPipe Holistic;
- shows a reaction only after the gesture is confirmed;
- fills the square output smoothly without inner frames or black bars;
- sends a clean 720×720 feed to OBS Virtual Camera;
- saves PNG screenshots, MP4 recordings, and recent frame sequences;
- prevents a blocked `capture.read()` from freezing the interface forever;
- closes cleanly with `Q`, the window close button, or `Ctrl+C`.

## Gestures

| Reaction | Gesture |
|---|---|
| Thinking | Hold a finger near your chin |
| Pointing | Raise your index finger above your head |
| Shocked | Open your mouth wide |
| Snide | Join your hands, smile, and slightly furrow your brows |
| Mid finger | Raise your middle finger |
| Love | Make a heart with your thumbs and index fingers |
| Power | Clench both fists |

The live camera stays visible when no gesture is active.

## Quick start on Windows 10/11

Install these first:

- Python 3.11;
- OBS Studio;
- Telegram Desktop if you want to record Telegram video messages.

After downloading or extracting the project, run this once:

```text
Setup.cmd
```

The setup script creates `.venv`, installs the pinned package versions, and
prepares the OBS profile. Start the app with:

```text
Start.cmd
```

The first window shows all controls without opening the camera. Press `Enter`
when you are ready. Press `T` after the camera starts to toggle the clean
Telegram/OBS output.

The main window starts fullscreen. `F` switches between fullscreen and a
resizable window. Telegram mode uses a separate fixed 720×720 output window,
so resizing the main interface cannot change the OBS frame.

Manual start without OBS:

```powershell
.\.venv\Scripts\python.exe main.py
```

Manual start with the square output and OBS:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start_telegram.ps1
```

Select **OBS Virtual Camera** in Telegram.

## Controls

| Key | Action |
|---|---|
| `Q` | Close the app |
| `T` | Toggle the clean square output |
| `S` | Save a PNG to `screenshots` |
| `R` | Start or stop an MP4 recording in `recordings` |
| `G` | Save the recent frames as an image sequence |
| `P` | Pause |
| `C` | Switch camera |
| `H` | Show help |
| `N` | Toggle smooth transitions |
| `F` | Toggle fullscreen |

File names include the date, time, and milliseconds, so existing recordings
are never overwritten.

Hotkeys also work with Caps Lock and the Russian keyboard layout. Saved files
always go to the `screenshots` and `recordings` folders next to `main.py`.

## Camera reliability

The app checks camera indices `0`, `1`, and `2`, trying DSHOW before MSMF for
each index. A camera is accepted only after it returns a real nonempty image.
Capture runs in a separate process, so a blocked driver can be stopped after a
timeout without freezing the interface.

MediaPipe receives a smaller analysis frame while the app and OBS keep the
original display pixels. Reaction images are prepared once and cached in
memory, keeping transitions responsive.

See [TELEGRAM_SETUP.md](TELEGRAM_SETUP.md) for OBS setup and black-screen
troubleshooting.

## Project structure

```text
main.py                  small application launcher
monkeyfacesmeme/         camera, gestures, media, UI, controls, and lifecycle
memes/                   reaction images
obs_setup/               ready-to-use OBS profile
tests/                   automated checks
```

## Validation

```powershell
.\.venv\Scripts\python.exe -m compileall -q main.py monkeyfacesmeme
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -c "import cv2, mediapipe, numpy; print('Imports OK')"
```

The working package versions are pinned in `requirements.txt`:

```text
numpy==1.26.4
mediapipe==0.10.9
opencv-contrib-python==4.11.0.86
```

## Privacy

The app does not use a server, analytics, telemetry, accounts, or network APIs.
Camera frames stay on the computer unless the user saves or streams them.

## License

The source code is available under the MIT License. Reaction images are not
covered by that license; see [ASSET_NOTICE.md](ASSET_NOTICE.md).
