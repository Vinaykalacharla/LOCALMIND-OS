# LocalMind Vision & Voice Assistant

This document outlines the architecture and roadmap for the LocalMind global background assistant. 
The goal is to provide a 100% offline, privacy-first AI companion that can see your screen, hear your voice, and speak back to you—functioning entirely locally like a private alternative to Microsoft Recall or Apple Intelligence.

## Architecture

The assistant relies on the following local AI stack:
1. **Screen Context (Vision):** `mss` or `Pillow` to capture screenshots, paired with Ollama running a vision model (e.g., `llava` or `qwen-vl`).
2. **Speech-to-Text (Hearing):** `faster-whisper` to accurately transcribe voice offline.
3. **Wake Word Detection:** `openWakeWord` or similar lightweight engine to silently listen for the phrase "Hey LocalMind" using minimal CPU.
4. **Text-to-Speech (Speaking):** `pyttsx3` (for built-in OS voices) or `piper-tts` for high-fidelity offline voice generation.
5. **System Integration:** Global hotkeys via `pynput` or `keyboard`, running as a background thread alongside the FastAPI backend.

## Roadmap

### Phase 1: Global Hotkey & Screen Vision (Current Focus)
- Implement a background listener for a global hotkey (e.g., `Ctrl+Shift+Space`).
- Upon trigger, capture the primary screen.
- Send the image to Ollama with a vision model to analyze the screen.
- Use basic TTS (`pyttsx3`) to speak the result out loud.

### Phase 2: Wake Word & Speech-to-Text
- Replace the hotkey trigger with continuous background microphone polling.
- Integrate a wake-word engine to detect "Hey LocalMind".
- Record the user's audio after the wake word and transcribe it using `faster-whisper`.
- Feed the transcription + the screenshot to the vision model so the user can ask specific questions about what they are looking at.

### Phase 3: High-Fidelity TTS & UI Overlays
- Upgrade the TTS engine to a more human-sounding local model (like Piper).
- Build a Tauri UI overlay (a subtle screen indicator or floating orb) that shows when the AI is listening, thinking, or speaking.
- Optimize the vision model prompts and response times.
