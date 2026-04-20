import os
import io
import time
from dotenv import load_dotenv
from PIL import Image
from PyQt6.QtCore import QThread, pyqtSignal, QByteArray, QBuffer, QIODevice
from google import genai
from google.genai import types

# Load the hidden API key from the .env file
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")


class AIWorker(QThread):
    finished = pyqtSignal(str)
    image_finished = pyqtSignal(QByteArray)
    error = pyqtSignal(str)

    def __init__(self, qimage, mode="Solve", history="", new_question="", is_imagine=False):
        super().__init__()
        self.qimage = qimage
        self.mode = mode
        self.history = history
        self.new_question = new_question
        self.is_imagine = is_imagine

    def run(self):
        max_retries = 3

        for attempt in range(max_retries):
            try:
                client = genai.Client(api_key=API_KEY)

                # --- STABLE IMAGE GENERATION WATERFALL ---
                if self.is_imagine:
                    try:
                        # ATTEMPT 1: The ultra-fast, stable 2.5 Flash Image model
                        response = client.models.generate_content(
                            model='gemini-2.5-flash-image',
                            contents=self.new_question,
                            config=types.GenerateContentConfig(
                                response_modalities=["IMAGE"]
                            )
                        )

                        if response.parts:
                            for part in response.parts:
                                if part.inline_data:
                                    img_bytes = part.inline_data.data
                                    self.image_finished.emit(QByteArray(img_bytes))
                                    return  # Success! Exit the thread.
                        raise ValueError("No image data returned by 2.5 Flash.")

                    except Exception as e1:
                        try:
                            # ATTEMPT 2: Legacy Imagen endpoint (Works for paid/Vertex keys)
                            result = client.models.generate_images(
                                model='imagen-3.0-generate-001',
                                prompt=self.new_question,
                                config=types.GenerateImagesConfig(
                                    number_of_images=1,
                                    aspect_ratio="1:1",
                                    output_mime_type="image/jpeg"
                                )
                            )

                            if not result.generated_images:
                                raise ValueError("Blocked by safety filters.")

                            img_bytes = result.generated_images[0].image.image_bytes
                            self.image_finished.emit(QByteArray(img_bytes))
                            return  # Success! Exit the thread.

                        except Exception as e2:
                            error_string = str(e1)

                            # 1. Check if it's a 503 Traffic Jam (trigger the retry loop)
                            if "503" in error_string or "503" in str(e2):
                                raise Exception("503 UNAVAILABLE")

                            # 2. Intercept the ugly 429 Quota/Free Tier Error
                            elif "429" in error_string or "quota" in error_string.lower():
                                self.error.emit(
                                    "🔒 Image Generation is restricted. Your API key has either reached its daily limit, or you need to enable billing in Google AI Studio to unlock the /imagine command.")
                                return

                            # 3. Clean Generic Error (usually Safety Filters)
                            else:
                                self.error.emit(
                                    "⚠️ Image Generation failed. Your prompt may have triggered Google's safety filters, or the image model is currently unavailable.")
                                return

                # --- EXISTING TEXT / VISION LOGIC ---
                else:
                    ba = QByteArray()
                    buff = QBuffer(ba)
                    buff.open(QIODevice.OpenModeFlag.WriteOnly)
                    self.qimage.save(buff, "PNG")
                    pil_img = Image.open(io.BytesIO(ba.data()))

                    if self.mode == "Tutor":
                        base_prompt = "You are an expert high school tutor. Guide the student step-by-step. Point out where they might be stuck. NEVER just give the final answer directly."
                    elif self.mode == "Debug":
                        base_prompt = "You are a senior software engineer. Analyze the code or errors in this image. Identify the bug, explain why it's failing, and provide the corrected code snippet."
                    else:
                        base_prompt = "You are an expert AI assistant. Solve the math equation or explain the concept perfectly and directly."

                    if self.new_question:
                        prompt = f"{base_prompt}\n\nHere is our conversation history:\n{self.history}\n\nUser's follow-up question: {self.new_question}\n\nAnswer the new question based on the image and our history."
                    else:
                        prompt = f"{base_prompt}\n\nAnalyze the attached screenshot from a transparent overlay. Focus on any hand-drawn ink."

                    # Already using the stable 2.5 Flash model for text/vision!
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[prompt, pil_img]
                    )

                    self.finished.emit(response.text)
                    return  # Success! Exit the loop and thread.

            except Exception as e:
                error_msg = str(e)

                # --- UPGRADED: Exponential Backoff Retry Logic ---
                if "503" in error_msg:
                    if attempt < max_retries - 1:
                        # We still have retries left. Wait and loop again.
                        wait_time = 2 ** (attempt + 1)
                        self.error.emit(
                            f"Google's servers are experiencing high demand. Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        # We ran out of retries. Show a clean final error.
                        self.error.emit(
                            "⚠️ Google's servers are currently overloaded and could not process the request. Please wait a few minutes and try again.")
                        return

                # --- NEW: Intercept 429 Rate Limits & Quotas ---
                elif "429" in error_msg or "quota" in error_msg.lower():
                    self.error.emit(
                        "🛑 Rate Limit Reached: You are sending requests too quickly or have hit your daily limit. Please wait a moment and try again.")
                    return

                else:
                    # Catch-all for any other unexpected errors
                    self.error.emit(f"AI Error: {error_msg}")
                    return