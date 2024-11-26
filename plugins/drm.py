import os
import subprocess
import shutil
import json
import logging
from pyrogram import filters, Client as ace
from pyrogram.types import Message
from main import Config, LOGGER, prefixes
from handlers.uploader import Upload_to_Tg
from handlers.tg import TgClient

logging.basicConfig(level=logging.INFO)  # Configure logging

@ace.on_message(
    (filters.chat(Config.GROUPS) | filters.chat(Config.AUTH_USERS)) & 
    filters.incoming & filters.command("drm", prefixes=prefixes)
)
async def drm(bot: ace, m: Message):
    await m.reply_text("Please upload the JSON file containing video details.")
    response = await bot.listen(m.chat.id, filters.document, timeout=300)
    
    json_file_path = f"{Config.DOWNLOAD_LOCATION}/{response.document.file_name}"
    await response.download(file_name=json_file_path)

    try:
        with open(json_file_path, 'r') as f:
            video_data = json.load(f)
    except Exception as e:
        logging.error(f"Error reading JSON file: {e}")
        await m.reply_text(f"Error reading JSON file: {e}")
        return

    for video in video_data:
        try:
            mpd = video.get("mpd")
            raw_name = video.get("name")
            Q = video.get("quality", "720")
            caption = video.get("caption", "")
            keys = video.get("keys", [])

            if not mpd or not raw_name or not keys:
                await m.reply_text(f"Skipping entry due to missing details: {video}")
                continue

            name = f"{TgClient.parse_name(raw_name)} ({Q}p)"
            path = f"{Config.DOWNLOAD_LOCATION}/{m.chat.id}/{name}"
            os.makedirs(path, exist_ok=True)

            key_string = " ".join(keys)

            BOT = TgClient(bot, m, path)
            Thumb = await BOT.thumb()
            prog = await bot.send_message(m.chat.id, f"**Downloading DRM Video!** - [{name}]({mpd})")

            # Use yt-dlp directly via Python API
            ydl_opts = {
                'outtmpl': f'{path}/fileName.%(ext)s',
                'format': f'bestvideo[height<={int(Q)}]+bestaudio',
                'external_downloader': 'aria2c',  # External downloader (aria2c)
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([mpd])

            # Decryption steps (with checks)
            avDir = os.listdir(path)
            mp4_file = next((f for f in avDir if f.endswith(".mp4")), None)
            m4a_file = next((f for f in avDir if f.endswith(".m4a")), None)

            if mp4_file and m4a_file:
                cmd2 = f'mp4decrypt {key_string} --show-progress "{path}/{mp4_file}" "{path}/video.mp4"'
                subprocess.run(cmd2, shell=True, check=True)
                os.remove(f'{path}/{mp4_file}')

                cmd3 = f'mp4decrypt {key_string} --show-progress "{path}/{m4a_file}" "{path}/audio.m4a"'
                subprocess.run(cmd3, shell=True, check=True)
                os.remove(f'{path}/{m4a_file}')
            else:
                await m.reply_text(f"Error: Missing .mp4 or .m4a files for decryption.")
                continue

            # Merging with ffmpeg
            cmd4 = f'ffmpeg -i "{path}/video.mp4" -i "{path}/audio.m4a" -c copy "{path}/{name}.mkv"'
            subprocess.run(cmd4, shell=True, check=True)
            os.remove(f"{path}/video.mp4")
            os.remove(f"{path}/audio.m4a")

            # Uploading to Telegram
            filename = f"{path}/{name}.mkv"
            cc = f"{name}.mkv\n\n**Description:-**\n{caption}"
            UL = Upload_to_Tg(bot=bot, m=m, file_path=filename, name=name, Thumb=Thumb, path=path, show_msg=prog, caption=cc)
            await UL.upload_video()
            logging.info(f"Processed and uploaded: {name}")
        except Exception as e:
            logging.error(f"Error while processing {video.get('name', 'Unknown')}: {e}")
            await prog.delete(True)
            await m.reply_text(f"Error processing {video.get('name', 'Unknown')}:\n\n{e}")
        finally:
            if os.path.exists(path):
                shutil.rmtree(path)
            await m.reply_text(f"Finished processing: {raw_name}")

    if os.path.exists(json_file_path):
        os.remove(json_file_path)
    
    await m.reply_text("All videos processed successfully.")
