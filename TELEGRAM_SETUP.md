# Telegram and OBS

**English** · [Русский](TELEGRAM_SETUP_RU.md)

## Normal start

Close any unfinished Telegram video-message preview, then run:

```text
Start.cmd
```

The controls screen opens first and the physical camera stays closed. Press
`Enter` in that window when you are ready to continue.

The launcher automatically:

1. releases the physical camera before startup;
2. waits for a real camera frame;
3. opens the **MonkeyFacesMeme** OBS profile;
4. starts OBS Virtual Camera;
5. provides a clean 720×720 feed at 30 FPS.

Select **OBS Virtual Camera** in Telegram.

## OBS settings

- Base Resolution: `720×720`;
- Output Resolution: `720×720`;
- FPS: `30`;
- scene: `MonkeyFacesMeme`;
- source: `MonkeyFacesMeme Feed`;
- window: `MonkeyFacesMeme Output`;
- Capture Method: `BitBlt`;
- Capture Cursor: disabled;
- Scale Filtering: `Lanczos`;
- Color Space: `Rec.709`;
- Color Range: `Partial`.

The main application window is fullscreen. The square output is a fixed-size
OBS utility window and intentionally cannot be maximized.

BitBlt is intentional. On some Windows versions, WGC detects an OpenCV window
but sends a completely black surface to OBS.

## What appears in the circle

The live camera stays visible until a gesture is confirmed. The movement is
shown first, then the reaction image smoothly fills the complete circle. There
are no inner cards, black bars, or blurred backgrounds.

The reaction appears in `0.12` seconds, stays visible for at least `0.95`
seconds, and then fades smoothly back to the camera.

## If the circle is black

1. Check the `MonkeyFacesMeme Output` window.
2. Open the `MonkeyFacesMeme` scene preview in OBS.
3. Confirm that the source uses BitBlt.
4. Click **Start Virtual Camera** if the OBS camera is stopped.
5. Select OBS Virtual Camera again in Telegram and start a new recording.

If the app output is already black, close other programs using the physical
camera and restart the app.

The launcher prints the current log paths in the console. Logs are stored in:

```text
%LOCALAPPDATA%\MonkeyFacesMeme\logs
```

## Saved files

- `S` creates `screenshots/shot_YYYYMMDD_HHMMSS_mmm.png`;
- `R` creates `recordings/camera_YYYYMMDD_HHMMSS_mmm_720x720.mp4`;
- `G` creates `screenshots/sequence_...` with the recent frames.
