# bot/app.py
# Entry-point for the Teams bot application (Flask web service).
# Sets up the Bot Framework adapter with Teams credentials and defines the message route.

import os
import asyncio
from flask import Flask, request, Response, jsonify, make_response, render_template
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.schema import Activity
from dotenv import load_dotenv
from bot.teams_bot import TeamsBot
import logging

#from botbuilder.integration.flask import FlaskAdapter


from bot.teams_bot import TeamsBot
from flask import send_from_directory

# Load environment variables from .env (Teams app ID and password, etc.)
load_dotenv()
APP_ID = os.getenv("BOT_APP_ID", "")
APP_PW = os.getenv("BOT_APP_PASSWORD", "")

logging.basicConfig(
    filename='bot.log',
    format='%(asctime)s %(levelname)s:%(name)s:%(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize the Bot Framework adapter with the Microsoft Teams bot credentials.
adapter_settings = BotFrameworkAdapterSettings(APP_ID, APP_PW)
adapter = BotFrameworkAdapter(adapter_settings)

# Create the Teams bot instance (defined in teams_bot.py).
from bot.teams_bot import TeamsBot
bot = TeamsBot()

# Create Flask application
app = Flask(__name__)

@app.route('/static/<path:filename>')
def download_static(filename):
    return send_from_directory('static', filename, as_attachment=True)

# Error handler for the adapter (optional: logs errors and sends trace messages if needed)
async def on_error(context, error):
    print(f"Bot error: {error}")
    await context.send_activity("Sorry, something went wrong processing your request.")

adapter.on_turn_error = on_error

@app.route("/api/messages", methods=["POST"])
async def messages():
    if "application/json" in request.headers.get("Content-Type", ""):
        body = request.json
    else:
        return Response(status=415)

    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    async def turn_logic(turn_context):
        await bot.on_turn(turn_context)

    try:
        # Route the activity to the bot's OnTurn handler
        response = await adapter.process_activity(activity, auth_header, bot.on_turn)
        if response:
            return jsonify(response.body), response.status
        return Response(status=201)
    except Exception as e:
        logger.exception(f"Error processing activity: {e}")
        return jsonify({"error": str(e)}), 500
    
from flask import make_response


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

    # GET request
    html = render_template("upload.html")
    return wrap_html(html)






if __name__ == "__main__":
    print("🚀 Flask bot is running on http://localhost:3978")
    app.run(host="0.0.0.0", port=3978, debug=True)
