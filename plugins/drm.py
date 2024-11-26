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
    filters.incoming & filters.command("bulk_drm", prefixes=prefixes)
)
async def bulk_drm(bot: ace, m: Message):
    # Check if the user uploaded a file
    if not m.document:
        await m.reply_text("**Error**: Please upload a JSON file containing video details.")
        return

    # Download the uploaded file
    file_id = m.document.file_id
    file_name = f"{Config.DOWNLOAD_LOCATION}/uploaded_videos.json"
    downloaded_file = await bot.download_media(file_id, file_name)

    # Try to open and parse the uploaded JSON file
    try:
        with open(downloaded_file, "r") as json_file:
            videos_data = json.load(json_file)
    except json.JSONDecodeError:
        await m.reply_text("**Error**: Invalid JSON format!")
        return
    except FileNotFoundError:
        await m.reply_text("**Error**: File not found!")
        return

    # Process each video entry in the JSON file
    for video in videos_data:
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
            for data in avDir:
                if data.endswith("mp4"):
                    cmd2 = f'mp4decrypt {keys_str} --show-progress "{path}/{data}" "{path}/video.mp4"'
                    os.system(cmd2)
                    os.remove(f'{path}/{data}')
                elif data.endswith("m4a"):
                    cmd3 = f'mp4decrypt {keys_str} --show-progress "{path}/{data}" "{path}/audio.m4a"'
                    os.system(cmd3)
                    os.remove(f'{path}/{data}')

            # Combine video and audio using ffmpeg
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
        except Exception as e:
            await prog.delete(True)
            await m.reply_text(f"**Error**\n\n`{str(e)}`\n\nOr Maybe Video not Available in {quality}")
        finally:
            if os.path.exists(path):
                shutil.rmtree(path)

    await m.reply_text("Bulk processing complete.")
