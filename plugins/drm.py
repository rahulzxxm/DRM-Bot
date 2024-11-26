import os
import subprocess
import json
import re
import time
import signal
from pyrogram import Client, filters
from pyrogram.types import Message

# Initialize the bot
logging.basicConfig(level=logging.INFO)  # Configure logging

@ace.on_message(
    (filters.chat(Config.GROUPS) | filters.chat(Config.AUTH_USERS)) & 
    filters.incoming & filters.command("drm", prefixes=prefixes)
)
def progress(current, total):
    print("\rUpload Progress: {:.1f}%".format(current * 100 / total), end='')

# Sanitize the filename to avoid any special characters that can cause issues
def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

# Function to download video using the N_m3u8DL-RE tool
def download_video(entry, temp_dir):
    mpd = entry["mpd"]
    name = sanitize_filename(entry["name"])
    keys = entry["keys"]

    command = [
        "./N_m3u8DL-RE",
        mpd,
        "-M", "format=mp4",
        "--save-name", name,
        "--thread-count", "64",
        "--append-url-params",
        "-mt",
        "--auto-select"
    ]

    # Add keys to the command if provided
    for key in keys:
        command.extend(["--key", key])

    os.makedirs(temp_dir, exist_ok=True)
    command.extend(["--save-dir", temp_dir])

    try:
        subprocess.run(command, check=True)
        return os.path.join(temp_dir, f"{name}.mp4")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Download failed: {str(e)}")

# Command to handle /drm and upload a JSON file
@bot.on_message(filters.private & filters.document)
def handle_json_file(client, message: Message):
    try:
        # Check if the uploaded file is a JSON file
        if not message.document.file_name.endswith(".json"):
            message.reply_text("Please send a valid .json file.")
            return

        # Download the file and process it
        file_path = message.download()
        message.reply_text("JSON file received. Processing...")

        with open(file_path, "r") as f:
            data = json.load(f)

        temp_dir = "downloads"

        for entry in data:
            name = sanitize_filename(entry["name"])
            message.reply_text(f"Starting download for: {name}")

            try:
                # Download the video
                video_path = download_video(entry, temp_dir)

                if not os.path.exists(video_path):
                    message.reply_text(f"Download failed for {name}: File not found")
                    continue

                message.reply_text(f"Download complete. Starting upload for: {name}")

                # Upload the video with a progress bar
                start_time = time.time()

                client.send_video(
                    chat_id=message.chat.id,
                    video=video_path,
                    caption=f"Uploaded: {name}",
                    progress=progress,
                    width=1920,
                    height=1080
                )

                end_time = time.time()
                time_taken = end_time - start_time
                message.reply_text(f"Upload complete for {name}. Time taken: {time_taken:.2f} seconds")

                # Clean up downloaded video
                if os.path.exists(video_path):
                    os.remove(video_path)

            except Exception as e:
                message.reply_text(f"Error processing {name}: {str(e)}")
                continue

        message.reply_text("All videos processed successfully!")

    except Exception as e:
        message.reply_text(f"An error occurred: {str(e)}")

# Command to restart the bot
@bot.on_message(filters.private & filters.command("restart"))
def restart(client, message: Message):
    try:
        message.reply_text("Restarting the bot...")
        os.kill(os.getpid(), signal.SIGINT)  # This will stop the bot and trigger a restart if supervised (like with systemd or pm2)
    except Exception as e:
        message.reply_text(f"Error restarting the bot: {str(e)}")

# Command to handle /drm and ask for the JSON file upload
@bot.on_message(filters.private & filters.command("drm"))
async def drm(client, message: Message):
    await message.reply_text("Please upload the .json file to process.")

# Start the bot
bot.run()
