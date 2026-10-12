# Interactive video editing update

User requests source time-range trim, draggable/resizable logo/text watermark, eight crop handles and playback inside the existing app. Preserve Native implementation, commit/report workflow and self-contained Windows EXE. Preview placement and exported geometry must agree.

Trim source interval before speed; UI accepts minutes:seconds (also hours:minutes:seconds), plain decimal minutes. Defaults whole video. Require finite 0 <= start < end <= source duration; output duration=(end-start)/speed. Audio retains source synchronization including delayed/early streams. Intro starts at the new output start. Preview timeline is output time.

Paused canvas supports move by interior drag and resize at eight corners/edges. Crop stays within source-after-flip bounds, even coordinates/dimensions. Logo gets optional independent height (old width-only constructors still preserve aspect). Text resizing changes font size proportionally; text still rendered with Pillow/Unicode. Placement modes omit the selected layer but draw its image/text as a manipulable canvas item. Numeric controls remain optional fallback; all actual transforms use the model.

Playback remains in Tk canvas. Generate an edited proxy in background through the shared pipeline, downscale only after effects, fast H264 encoding. Display FFmpeg-decoded frames with bounded queues; optional audio through bundled ffplay with no separate window. Play/pause and seek via output timeline; changing effects pauses playback and invalidates edited proxy. Paused editing restores full-resolution static frame. Progress/cancel and close must stop rendering/decoding/audio processes and remove temporary user-directory files. No new end-user dependencies or package installs at app startup. Bundle ffplay from the already verified FFmpeg archive.

Controls remain responsive during preparation; export never uses reduced-quality proxy. Proxy may require preparation after edits, with visible progress. Windows CI exercises bundled playback and source interval export; public release remains draft until FFmpeg matching source supplied.
