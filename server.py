from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from PIL import Image
import io

app = Flask(__name__)
CORS(app)  # Allows your desktop app to securely talk to this server

# --- PUT YOUR SECURE API KEY HERE ---
# Now it lives safely on the server, not in the user's .exe!
API_KEY = "AIzaSy..."
client = genai.Client(api_key=API_KEY)


@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        # 1. Grab the image and the prompt sent by your desktop app
        if 'image' not in request.files:
            return jsonify({"error": "No image provided"}), 400

        file = request.files['image']
        prompt = request.form.get('prompt', '')

        # 2. Convert it into a format Gemini understands
        pil_img = Image.open(file.stream)

        # 3. Ask Gemini
        print("✨ Received a scan! Asking Gemini...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, pil_img]
        )
        print("✅ Gemini answered successfully!")

        # 4. Send the text answer back down to the user's app
        return jsonify({"result": response.text})

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # This runs the server locally on port 5000
    print("🚀 Proxy Server is running on http://127.0.0.1:5000")
    app.run(port=5000, debug=True)