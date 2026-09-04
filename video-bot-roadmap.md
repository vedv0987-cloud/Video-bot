# 🎬 Open-Source Automation Bot for Short Health & Fitness Videos

## 🎯 Goal

Build a fully automated pipeline that:

- Researches a given health/fitness topic
- Generates a script (facts, symptoms, prevention, CTA)
- Creates a voiceover using open-source TTS
- Produces motion graphics (animated text, simple shapes, background)
- Adds background music
- Renders a final video (vertical 9:16 for Instagram/Shorts, 16:9 for YouTube)
- Generates SEO metadata (title, description, tags)
- Optionally uploads to platforms via API

All components must be **free, open-source**, and runnable on a local machine or server.

---

## 🧱 Prerequisites

- Python 3.8+ (or Node.js – but Python recommended for ML/audio/video)
- Basic knowledge of command line, Python scripting
- A computer with at least 4GB RAM (8GB recommended for video processing)
- Internet connection for research and optional API calls

---

## 🗺️ High‑Level Pipeline

```
[1] Topic Input / Auto‑Selection
        ↓
[2] Research & Fact Gathering
        ↓
[3] Script Generation (structured)
        ↓
[4] Voiceover Generation (TTS)
        ↓
[5] Motion Graphics Creation
        ↓
[6] Background Music Selection / Generation
        ↓
[7] Video Editing & Assembly
        ↓
[8] Render & Format Conversion
        ↓
[9] Metadata Generation
        ↓
[10] (Optional) Upload via API
```

---

## 🧩 Stage‑by‑Stage Open‑Source Tools & Implementation

### 1️⃣ Topic Input / Auto‑Selection

- **Manual**: Pass topic as command‑line argument.
- **Auto**: Use a list of trending health topics from RSS feeds or APIs (e.g., [NewsAPI](https://newsapi.org/) has a free tier, or scrape Google Trends via `pytrends` – open-source).
- **Tools**: `argparse` (Python), `schedule` for timed runs.

### 2️⃣ Research & Fact Gathering

- **Wikipedia**: Use `wikipedia-api` (`pip install wikipedia-api`) or direct REST API.
- **PubMed**: For scientific abstracts – `biopython` (open-source) or `pymed`.
- **Simple approach**: Use Wikipedia summary and a few facts.

  ```python
  import wikipedia
  summary = wikipedia.summary(topic, sentences=5)
  ```

### 3️⃣ Script Generation

- **Template‑based**: Fill in slots with researched info.
- **LLM (optional, free)**: Use GPT4All (open-source, runs locally) or Llama.cpp to generate natural text.
- Example script structure:

  ```
  Hook:       "Did you know? [startling fact]"
  Facts:      "Here are 3 key facts about [topic]..."
  Symptoms:   "Watch for these symptoms: ..."
  Prevention: "Prevention tips: ..."
  CTA:        "Follow for more health tips!"
  ```

### 4️⃣ Voiceover Generation (TTS)

- **Coqui TTS** (open-source, local):
  - Install: `pip install TTS`
  - Pre‑trained models available (e.g., `tts_models/en/ljspeech/tacotron2-DDC`)
  - Example:

    ```python
    from TTS.api import TTS
    tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False)
    tts.tts_to_file(text=script_text, file_path="voice.wav")
    ```

- **Mozilla TTS** (older, but still works)
- **Piper** (lightweight, fast, good quality) – supports many voices.
- All output can be post‑processed with `pydub` for volume normalization.

### 5️⃣ Motion Graphics Creation

**Goal**: create visually appealing animated text overlays, icons, simple shapes.

- **MoviePy** (`pip install moviepy`) – core video editing library. Can create text clips, animations, composite layers.
- **Pillow (PIL)** – for drawing custom shapes/images frame by frame if needed.
- **CairoSVG / PyCairo** – for vector graphics rendered to PNG.
- **Manim** (open-source, originally by 3Blue1Brown) – powerful for mathematical/educational animations. Can be used for more complex infographics.
- **Blender** (open-source) – overkill for short videos, but can be scripted for high‑end motion graphics. Use only if you need 3D.
- **Practical approach**:
  - Use MoviePy `TextClip` with custom fonts (free fonts from Google Fonts).
  - Animate text (fade in/out, slide, scale) using MoviePy's `crossfadein`, `set_position`, etc.
  - For icon animations: download free SVG icons (e.g., from SVGRepo) and convert to PNG with `cairosvg`, then overlay with transparency.

    ```python
    from moviepy.editor import *
    txt_clip = TextClip("Fact: Hydration boosts energy", fontsize=70, color='white', font='Ubuntu-Bold')
    txt_clip = txt_clip.set_pos('center').set_duration(3).crossfadein(0.5).crossfadeout(0.5)
    ```

  - Background: Use a solid color or simple gradient (generated with Pillow) or a stock video loop (free from Pexels, Pixabay – but they are not open-source, though free to use; for fully open-source, use abstract animations generated with Python or Blender).

### 6️⃣ Background Music

- **Free music libraries**:
  - Free Music Archive (CC licensed)
  - Incompetech (CC BY)
  - YouTube Audio Library (free to use)
- **Generate your own**: Use Sonic Pi (open-source live coding synth) or MuseScore to create simple loops. Export as WAV/MP3.
- **Auto‑selection**: Maintain a folder of royalty‑free tracks, pick one randomly or based on mood.
- **Audio mixing**: Use `pydub` to lower music volume and overlay voiceover.

### 7️⃣ Video Editing & Assembly

- **MoviePy** is the main workhorse:
  - Combine video clips (text, images) with audio (voiceover + music).
  - Add transitions (`crossfadein`, `crossfadeout`, `slide_in`).
  - Overlay logo/watermark if desired.
- Other open-source editors:
  - **FFmpeg** (command line) for post‑processing (e.g., converting to different formats, adding metadata).
  - **Kdenlive** (GUI, but scriptable via its MLT framework).
  - **OpenShot** (Python API available via `openshot` library, but less flexible than MoviePy).

### 8️⃣ Render & Format Conversion

- Render with MoviePy: `final_clip.write_videofile("output.mp4", fps=24, codec='libx264', audio_codec='aac')`
- Use FFmpeg to create different aspect ratios:
  - Vertical (1080x1920) for Instagram/Shorts
  - Square (1080x1080) for feed
  - Horizontal (1920x1080) for YouTube
- FFmpeg command example:

  ```bash
  ffmpeg -i input.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" -c:a copy vertical.mp4
  ```

### 9️⃣ Metadata Generation

- **Title & Description**: Use Python string formatting or simple NLP.
  - Example: `f"{topic} – Facts, Symptoms & Prevention | #Shorts"`
- **Tags/Hashtags**: Generate from topic and related keywords (maybe using `pytrends` to find trending tags).
- Store metadata as JSON for later use.

### 🔟 (Optional) Upload via API

- **YouTube**: Use `google-api-python-client` (free). Requires OAuth2 credentials.
- **Instagram**: Graph API requires a business account and approval; not always accessible. Alternative: use a scheduler like Buffer (free tier) and automate posting via their API (limited). For fully open-source, you may skip direct upload and manually upload or use Zapier/Make (not open-source) to connect.

---

## 🗂️ Suggested Project Structure

```
video-bot/
├── main.py                 # orchestrator
├── config.yaml             # settings (fonts, paths, API keys)
├── research/
│   └── wiki.py
├── script/
│   └── generator.py
├── voiceover/
│   └── tts_engine.py
├── graphics/
│   ├── text_clips.py
│   └── icons.py
├── music/
│   ├── tracks/             # store royalty-free music
│   └── mixer.py
├── render/
│   └── render.py
├── metadata/
│   └── meta.py
├── upload/
│   └── youtube_upload.py
└── output/                 # final videos and metadata
```

---

## 🔁 Automation & Scheduling

- Cron job (Linux/macOS) or Task Scheduler (Windows) to run the bot daily/weekly.
- Use `watchdog` or `schedule` library for periodic execution.
- Example cron entry to run every day at 9 AM:

  ```
  0 9 * * * cd /path/to/video-bot && python main.py --topic "hydration"
  ```

---

## 📦 Full Open‑Source Stack Summary

| Component | Tool(s) | License |
| --- | --- | --- |
| Research | Wikipedia, PyMed, Biopython | Various |
| Script Gen | GPT4All, Llama.cpp (optional) | MIT/Apache |
| TTS | Coqui TTS, Piper, Mozilla TTS | MPL‑2.0, MIT |
| Motion Graphics | MoviePy, Pillow, Manim, cairosvg | MIT/BSD |
| Music | Free Music Archive, Sonic Pi, MuseScore | CC, GPL |
| Video Editing | MoviePy, FFmpeg | MIT, GPL |
| Metadata | Python built‑in, pytrends (optional) | BSD |
| Upload | google‑api‑python‑client (YouTube) | Apache‑2.0 |

All are free to use, modify, and distribute.

---

## ⚠️ Challenges & Solutions

### 1. Natural Voice Quality

- Coqui TTS models like `tts_models/en/ljspeech/tacotron2-DDC` are decent but can sound robotic.
- **Solution**: Use Piper with high‑quality voices (e.g., `en_US-lessac-medium`), or fine‑tune a Coqui model on a health‑specific corpus.

### 2. Motion Graphics Look Professional

- MoviePy text is basic. To improve:
  - Use custom fonts (Google Fonts – open source).
  - Add background shapes (rounded rectangles) behind text for contrast.
  - Animate icons with simple keyframe movements (position, scale, rotation).
  - Consider using Manim for more polished animations.

### 3. Video Length Control

- Keep voiceover under 55 seconds; trim silence with `pydub` `strip_silence`.
- Script should be ~100 words for 60 seconds.

### 4. Resource Usage

- Video rendering can be CPU/GPU heavy. Use `ffmpeg` with hardware acceleration if available.
- Process videos sequentially; do not run multiple renders in parallel on low‑end hardware.

### 5. Copyright of Background Music

- Always use tracks with clear CC0/CC BY licenses. Attribute if required.
- Generate your own music with Sonic Pi to be 100% safe.

### 6. Instagram Upload Limitations

- The Graph API content publishing is only available to approved partners.
- Alternative: Use Zapier or Integromat (now Make) to automatically post from a watched folder – though not open-source, they have free tiers. Or simply save the video and manually upload; the automation can still produce ready‑to‑post files.

---

## 🚀 Next Steps

1. Set up the Python environment and install required packages.
2. Implement research + script generation.
3. Integrate TTS and test output.
4. Build basic motion graphics with MoviePy.
5. Add background music and mixing.
6. Render a vertical and horizontal version.
7. Generate metadata.
8. (Optional) Set up YouTube API and automate upload.
9. Schedule the bot with cron.
10. Iterate: improve voice, graphics, and content based on feedback.

---

## 📚 Resources

- MoviePy Documentation
- Coqui TTS
- Piper TTS
- Manim Community
- FFmpeg
- Free Music Archive
- Google API Python Client

---

**License**: This roadmap is provided under MIT License. Feel free to adapt.
