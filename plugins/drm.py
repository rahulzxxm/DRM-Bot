import json
import os
import shutil
import subprocess
from pyrogram import filters, Client as ace
from pyrogram.types import Message
from handlers.uploader import Upload_to_Tg
from handlers.tg import TgClient
from main import Config, LOGGER, prefixes


async def process_video(bot, m, mpd, raw_name, quality, caption, keys):
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
        await m.reply_text(f"**Error**\n\n`{str(e)}`\n\nOr May be Video not Available in {quality}")
    finally:
        if os.path.exists(path):
            shutil.rmtree(path)
        await m.reply_text("Done")


@ace.on_message(
    (filters.chat(Config.GROUPS) | filters.chat(Config.AUTH_USERS)) &
    filters.incoming & filters.command("drm_bulk", prefixes=prefixes)
)
async def drm_bulk(bot: ace, m: Message):
    # Load the JSON data
    try:
        file_path = f"{Config.DOWNLOAD_LOCATION}/videos.json"  # Path to the JSON file
        with open(file_path, "r") as json_file:
            videos_data = json.load(json_file)
    except FileNotFoundError:
        await m.reply_text("**Error**: JSON file not found!")
        return
    except json.JSONDecodeError:
        await m.reply_text("**Error**: Invalid JSON format!")
        return

    # Process each video entry in the JSON file
    for video in videos_data:
        mpd = video.get("mpd")
        raw_name = video.get("name")
        quality = video.get("quality")
        caption = video.get("caption")
        keys = video.get("keys", [])

        # Process each video
        await process_video(bot, m, mpd, raw_name, quality, caption, keys)


