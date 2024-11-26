import os
import subprocess
import shutil
import json
from pyrogram import filters, Client as ace
from pyrogram.types import Message
from main import Config, LOGGER, prefixes
from handlers.uploader import Upload_to_Tg
from handlers.tg import TgClient


@ace.on_message(
    (filters.chat(Config.GROUPS) | filters.chat(Config.AUTH_USERS)) &
    filters.incoming & filters.command("drm", prefixes=prefixes)
)
async def drm(bot: ace, m: Message):
    await m.reply_text("Please upload the JSON file containing video details.")
    response = await bot.listen(m.chat.id, filters.document, timeout=300)  # Wait for JSON file upload
    
    json_file_path = f"{Config.DOWNLOAD_LOCATION}/{response.document.file_name}"
    await response.download(file_name=json_file_path)
    
    try:
        with open(json_file_path, 'r') as f:
            video_data = json.load(f)
    except Exception as e:
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
            tPath = f"{Config.DOWNLOAD_LOCATION}/THUMB/{m.chat.id}"
            os.makedirs(path, exist_ok=True)

            key_string = " ".join(keys)

            BOT = TgClient(bot, m, path)
            Thumb = await BOT.thumb()
            prog = await bot.send_message(m.chat.id, f"**Downloading DRM Video!** - [{name}]({mpd})")

            cmd1 = f'yt-dlp -o "{path}/fileName.%(ext)s" -f "bestvideo[height<={int(Q)}]+bestaudio" --allow-unplayable-format --external-downloader aria2c "{mpd}"'
            os.system(cmd1)

            avDir = os.listdir(path)
            print(avDir)
            print("Decrypting")

            for data in avDir:
                if data.endswith("mp4"):
                    cmd2 = f'mp4decrypt {key_string} --show-progress "{path}/{data}" "{path}/video.mp4"'
                    os.system(cmd2)
                    os.remove(f'{path}/{data}')
                elif data.endswith("m4a"):
                    cmd3 = f'mp4decrypt {key_string} --show-progress "{path}/{data}" "{path}/audio.m4a"'
                    os.system(cmd3)
                    os.remove(f'{path}/{data}')

            cmd4 = f'ffmpeg -i "{path}/video.mp4" -i "{path}/audio.m4a" -c copy "{path}/{name}.mkv"'
            os.system(cmd4)
            os.remove(f"{path}/video.mp4")
            os.remove(f"{path}/audio.m4a")
            filename = f"{path}/{name}.mkv"
            cc = f"{name}.mkv\n\n**Description:-**\n{caption}"

            UL = Upload_to_Tg(bot=bot, m=m, file_path=filename, name=name,
                              Thumb=Thumb, path=path, show_msg=prog, caption=cc)
            await UL.upload_video()
            print(f"Processed and uploaded: {name}")
        except Exception as e:
            await prog.delete(True)
            await m.reply_text(f"**Error while processing {video.get('name', 'Unknown')}**\n\n`{str(e)}`")
        finally:
            if os.path.exists(tPath):
                shutil.rmtree(tPath)
            shutil.rmtree(path)
            await m.reply_text(f"Finished processing: {raw_name}")

    if os.path.exists(json_file_path):
        os.remove(json_file_path)
    await m.reply_text("All videos processed successfully.")
