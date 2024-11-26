import json
import os
import shutil
import subprocess
from pyrogram import filters, Client as ace
from pyrogram.types import Message
from handlers.uploader import Upload_to_Tg
from handlers.tg import TgClient
from main import Config, prefixes


@ace.on_message(
    (filters.chat(Config.GROUPS) | filters.chat(Config.AUTH_USERS)) &
    filters.incoming & filters.command("bulkdrm", prefixes=prefixes)
)
async def bulk_drm(bot: ace, m: Message):
    """Bulk DRM video processing."""
    await m.reply_text("Please upload the JSON file containing video data.")
    
    # Listen for the file sent by the user
    file_msg = await bot.listen(m.chat.id)

    # Validate that a file has been sent
    if not file_msg.document:
        await m.reply_text("Invalid file format. Please send a valid JSON file.")
        return

    # Define file path and ensure the directory exists
    file_path = f"{Config.DOWNLOAD_LOCATION}/{m.chat.id}/bulk_data.json"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Download the file to the specified location
    await file_msg.download(file_path)

    # Read the JSON file
    try:
        with open(file_path, "r") as f:
            video_data = json.load(f)
            if not isinstance(video_data, list):
                raise ValueError("Invalid JSON structure. Expected a list of video objects.")
    except Exception as e:
        await m.reply_text(f"Error reading JSON file: {str(e)}")
        return

    # Process each video entry in the JSON file
    for video in video_data:
        mpd = video.get("mpd")
        raw_name = video.get("name")
        quality = video.get("quality")
        caption = video.get("caption")
        keys = video.get("keys", [])

        # Prepare paths and other variables
        path = f"{Config.DOWNLOAD_LOCATION}/{m.chat.id}"
        os.makedirs(path, exist_ok=True)

        name = f"{TgClient.parse_name(raw_name)} ({quality}p)"
        keys_str = " ".join(keys)

        print(mpd, name, quality)

        BOT = TgClient(bot, m, path)
        Thumb = await BOT.thumb()
        prog = await bot.send_message(m.chat.id, f"**Downloading Drm Video!** - [{name}]({mpd})")

        # Download the video using yt-dlp
        cmd1 = f'yt-dlp -o "{path}/fileName.%(ext)s" -f "bestvideo[height<={int(quality)}]+bestaudio" --allow-unplayable-format --external-downloader aria2c "{mpd}"'
        os.system(cmd1)
        
        avDir = os.listdir(path)
        print(avDir)
        print("Decrypting")

        try:
            video_file = None
            audio_file = None
            for data in avDir:
                if data.endswith("mp4"):
                    video_file = data
                elif data.endswith("m4a"):
                    audio_file = data

            if video_file and audio_file:
                cmd2 = f'mp4decrypt {keys_str} --show-progress "{path}/{video_file}" "{path}/video.mp4"'
                os.system(cmd2)
                os.remove(f'{path}/{video_file}')
                
                cmd3 = f'mp4decrypt {keys_str} --show-progress "{path}/{audio_file}" "{path}/audio.m4a"'
                os.system(cmd3)
                os.remove(f'{path}/{audio_file}')

                # Combine video and audio using ffmpeg
                if os.path.exists(f"{path}/video.mp4") and os.path.exists(f"{path}/audio.m4a"):
                    cmd4 = f'ffmpeg -i "{path}/video.mp4" -i "{path}/audio.m4a" -c copy "{path}/{name}.mkv"'
                    os.system(cmd4)

                    os.remove(f"{path}/video.mp4")
                    os.remove(f"{path}/audio.m4a")
                    filename = f"{path}/{name}.mkv"
                    cc = f"{name}.mkv\n\n**Description:-**\n{caption}"

                    # Upload video to Telegram
                    UL = Upload_to_Tg(bot=bot, m=m, file_path=filename, name=name, Thumb=Thumb, path=path, show_msg=prog, caption=cc)
                    await UL.upload_video()
                    print("Done")
                else:
                    raise FileNotFoundError("Video or audio file not found after decryption.")
            else:
                raise FileNotFoundError("Video or audio files not found in the downloaded directory.")
        except Exception as e:
            await prog.delete(True)
            await m.reply_text(f"**Error**\n\n`{str(e)}`\n\nOr Maybe Video not Available in {quality}")
        finally:
            if os.path.exists(path):
                shutil.rmtree(path)

    await m.reply_text("Bulk processing complete.")
