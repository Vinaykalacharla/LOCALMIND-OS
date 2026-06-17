import threading
import time
import io
import base64
import requests
import json
import os
import sys
import urllib.request
import zipfile
import subprocess
from typing import Optional

try:
    import keyboard
    from PIL import ImageGrab
    import pyttsx3
    import sounddevice as sd
    from vosk import Model, KaldiRecognizer
    import queue
except ImportError:
    keyboard = None
    ImageGrab = None
    pyttsx3 = None
    sd = None
    Model = None
    KaldiRecognizer = None
    queue = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "..", "models")
VOICE_MODEL_DIR = os.path.join(MODELS_DIR, "voice", "vosk-model-small-en-us")
VOSK_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"

class AssistantService:
    def __init__(self):
        self.enabled = False
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.hotkey = "ctrl+shift+space"
        self.processing = False
        self.ollama_url = "http://127.0.0.1:11434/api/generate"
        self.ollama_chat_url = "http://127.0.0.1:11434/api/chat"
        self.tts_engine = None
        self.q = None
        self.wake_words = ["localmind", "computer", "gemini"]

    def _init_tts(self):
        if pyttsx3 and not self.tts_engine:
            try:
                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty('rate', 160)
            except Exception as e:
                print(f"TTS Init Error: {e}")

    def speak(self, text: str):
        if not self.tts_engine:
            self._init_tts()
        if self.tts_engine:
            print(f"Assistant speaks: {text}")
            try:
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            except Exception as e:
                print(f"Speak Error: {e}")
        else:
            print(f"Assistant: {text}")

    def _ensure_vosk_model(self):
        if not os.path.exists(VOICE_MODEL_DIR):
            print("Downloading Vosk offline voice model (~40MB)...")
            os.makedirs(os.path.dirname(VOICE_MODEL_DIR), exist_ok=True)
            zip_path = VOICE_MODEL_DIR + ".zip"
            urllib.request.urlretrieve(VOSK_URL, zip_path)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(os.path.dirname(VOICE_MODEL_DIR))
            os.remove(zip_path)
            extracted = os.path.join(os.path.dirname(VOICE_MODEL_DIR), "vosk-model-small-en-us-0.15")
            if os.path.exists(extracted):
                os.rename(extracted, VOICE_MODEL_DIR)

    def _capture_screen(self) -> str:
        if not ImageGrab:
            raise RuntimeError("Pillow is not installed")
        img = ImageGrab.grab()
        img.thumbnail((1280, 720))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=80)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _ask_ollama_vision(self, image_b64: str, prompt: str) -> str:
        payload = {
            "model": "llava",
            "prompt": prompt,
            "images": [image_b64],
            "stream": False
        }
        try:
            resp = requests.post(self.ollama_url, json=payload, timeout=60)
            resp.raise_for_status()
            return resp.json().get("response", "")
        except Exception as e:
            print(f"Vision error: {e}")
            return "I'm having trouble seeing the screen right now."

    def _run_react_agent(self, prompt: str) -> str:
        """
        Runs a ReAct loop. Uses a text model (like llama3, qwen2.5, or whatever is default in Ollama).
        If specific tool calls are outputted, it executes them.
        """
        system_prompt = """You are LocalMind OS, a fully autonomous offline coding agent.
You have access to the following actions:
[ExecuteCommand]: Run a terminal command. Provide the command after this tag.
[ReadFile]: Read a file. Provide the path after this tag.
[WriteFile]: Write to a file. Provide path::content after this tag.
[FinalAnswer]: Provide the final answer to the user.

Example:
Thought: I need to check the python version.
[ExecuteCommand] python --version
Observation: Python 3.12.0
Thought: I know the answer.
[FinalAnswer] You are running Python 3.12.0.

Always use [FinalAnswer] to speak back to the user. Keep your spoken answers very concise.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        max_turns = 5
        # We try to use a strong default model, or fallback to llama3/qwen2.5
        model_name = "qwen2.5:1.5b" # a safe fast offline model
        
        for i in range(max_turns):
            payload = {
                "model": model_name,
                "messages": messages,
                "stream": False,
                "options": { "temperature": 0.2 }
            }
            try:
                resp = requests.post(self.ollama_chat_url, json=payload, timeout=60)
                resp.raise_for_status()
                response_content = resp.json().get("message", {}).get("content", "")
                print(f"Agent Action:\n{response_content}")
                
                if "[FinalAnswer]" in response_content:
                    answer = response_content.split("[FinalAnswer]")[1].strip()
                    return answer
                
                # Parse Tools
                observation = "No tool recognized. Use [FinalAnswer], [ExecuteCommand], [ReadFile], or [WriteFile]."
                if "[ExecuteCommand]" in response_content:
                    cmd = response_content.split("[ExecuteCommand]")[1].split("\n")[0].strip()
                    try:
                        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                        observation = f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
                    except Exception as e:
                        observation = f"Error executing: {e}"
                elif "[ReadFile]" in response_content:
                    path = response_content.split("[ReadFile]")[1].split("\n")[0].strip()
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            observation = f.read()[:2000] # truncate
                    except Exception as e:
                        observation = f"Error reading: {e}"
                elif "[WriteFile]" in response_content:
                    parts = response_content.split("[WriteFile]")[1].strip().split("::", 1)
                    if len(parts) == 2:
                        path, content = parts[0].strip(), parts[1].strip()
                        try:
                            with open(path, "w", encoding="utf-8") as f:
                                f.write(content)
                            observation = f"Successfully wrote to {path}"
                        except Exception as e:
                            observation = f"Error writing: {e}"

                messages.append({"role": "assistant", "content": response_content})
                messages.append({"role": "user", "content": f"Observation: {observation}"})
            except Exception as e:
                print(f"Agent LLM error: {e}")
                return "I encountered an error while thinking."
                
        return "I couldn't complete the task in time."

    def _handle_voice_prompt(self, text: str):
        self.processing = True
        try:
            print(f"Handling voice prompt: {text}")
            # If screen intent
            if any(w in text for w in ["screen", "see", "meet", "chrome", "looking at"]):
                self.speak("Let me look at your screen.")
                b64_image = self._capture_screen()
                prompt = text if len(text) > 20 else "Describe what is on my screen."
                answer = self._ask_ollama_vision(b64_image, prompt)
                self.speak(answer)
            else:
                # Coding / General Agent intent
                self.speak("Thinking...")
                answer = self._run_react_agent(text)
                self.speak(answer)
        except Exception as e:
            print(f"Assistant handler error: {e}")
            self.speak("I encountered an error.")
        finally:
            self.processing = False

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            pass # ignore
        if self.q:
            self.q.put(bytes(indata))

    def _listen_loop(self):
        self._ensure_vosk_model()
        model = Model(VOICE_MODEL_DIR)
        rec = KaldiRecognizer(model, 16000)
        self.q = queue.Queue()

        print("🎤 Wake Word Listener Active. Say 'hey localmind' or 'computer'...")
        with sd.RawInputStream(samplerate=16000, blocksize=8000, device=None, dtype='int16',
                               channels=1, callback=self._audio_callback):
            while self.running and self.enabled:
                data = self.q.get()
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    text = res.get("text", "")
                    if text:
                        print(f"[Heard]: {text}")
                        for wake in self.wake_words:
                            if wake in text and not self.processing:
                                # Extract prompt after wake word
                                prompt = text.split(wake, 1)[1].strip()
                                if prompt:
                                    self._handle_voice_prompt(prompt)
                                else:
                                    self.speak("Yes? I am listening.")
                                break
                else:
                    pass

    def _on_hotkey(self):
        if not self.enabled or self.processing:
            return
        self._handle_voice_prompt("look at my screen and summarize")

    def toggle(self, enabled: bool):
        self.enabled = enabled
        print(f"Background assistant enabled: {self.enabled}")
        if self.enabled and not self.running:
            self.start()

    def start(self):
        if not keyboard or not sd or not Model:
            print("Required modules (keyboard, sounddevice, vosk) not fully installed. Voice Assistant disabled.")
            return
        if self.running:
            return
        self.running = True
        
        def listener():
            keyboard.add_hotkey(self.hotkey, self._on_hotkey)
            self._listen_loop()
            
        self.thread = threading.Thread(target=listener, daemon=True)
        self.thread.start()
        print("Assistant background listener started.")

assistant_service = AssistantService()
