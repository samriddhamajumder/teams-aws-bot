# bot/app.py
import os
import asyncio
import logging
import threading
import time
from flask import Flask, request, Response, jsonify, make_response, render_template, send_from_directory
from dotenv import load_dotenv
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.schema import Activity
from bot.teams_bot import TeamsBot
from bot.knowledge_base import load_knowledge_base

# =================================================
# ✅ ONLY ONE app = Flask(__name__) AT THE TOP
app = Flask(__name__)
# =================================================

# Load env variables
load_dotenv()
APP_ID = os.getenv("BOT_APP_ID", "")
APP_PW = os.getenv("BOT_APP_PASSWORD", "")

# Logging
logging.basicConfig(filename='bot.log',
                    format='%(asctime)s %(levelname)s:%(name)s:%(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot adapter
adapter_settings = BotFrameworkAdapterSettings(APP_ID, APP_PW)
adapter = BotFrameworkAdapter(adapter_settings)
bot = TeamsBot()

# Error handler
async def on_error(context, error):
    print(f"Bot error: {error}")
    await context.send_activity("❌ I faced an unexpected error. Please try again later or contact support.")

adapter.on_turn_error = on_error

# ================= ROUTES =======================

@app.route("/")
def index():
    return "✅ TikoGen bot backend is running."

@app.route('/static/<path:filename>')
def download_static(filename):
    return send_from_directory('static', filename, as_attachment=True)

@app.route("/api/messages", methods=["POST"])
def messages():
    if "application/json" in request.headers.get("Content-Type", ""):
        body = request.json
    else:
        return Response(status=415)

    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        response = loop.run_until_complete(
            adapter.process_activity(activity, auth_header, bot.on_turn)
        )
        if response:
            return jsonify(response.body), response.status
        return Response(status=201)
    except Exception as e:
        logger.exception(f"Error processing activity: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        loop.close()

@app.route("/upload", methods=["GET", "POST"])
def upload_page():
    from aws_crew_tools.s3 import upload_file_to_s3

    def wrap_html(html):
        response = make_response(html)
        response.headers['Content-Security-Policy'] = (
            "frame-ancestors 'self' teams.microsoft.com *.teams.microsoft.com *.skype.com *.skypeforbusiness.com *.cloud.microsoft"
        )
        response.headers['X-Frame-Options'] = "ALLOW-FROM https://teams.microsoft.com"
        return response

    if request.method == "POST":
        file = request.files.get("file")
        bucket = request.form.get("bucket_name")
        prefix = request.form.get("prefix", "")
        acl = request.form.get("acl", "private")
        storage_class = request.form.get("storage_class", "STANDARD")

        success, message = upload_file_to_s3(bucket, file.read(), file.filename, prefix, acl, storage_class)

        if success:
            html_success = f"""
            <html>
              <head>
                <script src="https://statics.teams.cdn.office.net/sdk/v2.19.0/js/MicrosoftTeams.min.js"></script>
                <script>
                  microsoftTeams.app.initialize();
                  setTimeout(() => {{
                    microsoftTeams.dialog.submit();
                  }}, 1500);
                </script>
                <style>
                  body {{
                    font-family: 'Segoe UI';
                    background-color: #e0ffe0;
                    padding: 20px;
                    border: 1px solid green;
                    border-radius: 8px;
                  }}
                </style>
              </head>
              <body>
                ✅ File <strong>{file.filename}</strong> uploaded to <strong>{bucket}</strong>.<br>
                Task module will close automatically...
              </body>
            </html>
            """
            return wrap_html(html_success)
        else:
            html_error = f"""
            <html>
              <head>
                <style>
                  body {{
                    font-family: 'Segoe UI';
                    background-color: #ffe0e0;
                    padding: 20px;
                    border: 1px solid red;
                    border-radius: 8px;
                  }}
                </style>
              </head>
              <body>
                ❌ Upload Failed: {message}<br><br>
                <a href="/upload">🔁 Try Again</a>
              </body>
            </html>
            """
            return wrap_html(html_error)

    html = render_template("upload.html")
    return wrap_html(html)

# ================= UTILITIES =====================

def cleanup_pem_files():
    pem_folder = "./static/"
    while True:
        for file in os.listdir(pem_folder):
            if file.endswith(".pem"):
                file_path = os.path.join(pem_folder, file)
                file_age = time.time() - os.path.getmtime(file_path)
                if file_age > 600:
                    os.remove(file_path)
        time.sleep(300)

# Start background cleanup
threading.Thread(target=cleanup_pem_files, daemon=True).start()
