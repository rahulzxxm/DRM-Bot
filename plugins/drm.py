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
    filters.incoming & filters.command("drm", prefixes=prefixes)
)
async def drm(bot: ace, m: Message):
    """Bulk DRM video processing."""
    # Ask the user to upload the JSON file
    await m.reply_text("Please upload the JSON file containing video data.")
    file_msg = await bot.listen(m.chat.id)
    
    # Save the uploaded JSON file
    if file_msg.document:
        file_path = f"{Config.DOWNLOAD_LOCATION}/{m.chat.id}/bulk_data.json"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        await file_msg.download(file_path)
    else:
        await m.reply_text("Invalid file format. Please send a valid JSON file.")
        return
    
    # Read the JSON file
    try:
        with open(file_path, "r") as f:
            video_data = json.load(f)
    except Exception as e:
        await m.reply_text(f"Error reading JSON file: {str(e)}")
        return

    # Loop through each video entry in the JSON file
    for index, video in enumerate(video_data, start=1):
        try:
            mpd = video["mpd"]
            raw_name = video["name"]
            Q = video["quality"]
            CP = video["caption"]
            keys = video["keys"]  # Should be a string like "KID:KEY KID:KEY ..."
            
            # Ensure that keys is a string
            if isinstance(keys, list):
                keys = "--key ".join(keys)  # Convert list to space-separated string
            
            name = f"{TgClient.parse_name(raw_name)} ({Q}p)"
            path = f"{Config.DOWNLOAD_LOCATION}/{m.chat.id}/{index}"
            tPath = f"{Config.DOWNLOAD_LOCATION}/THUMB/{m.chat.id}/{index}"
            os.makedirs(path, exist_ok=True)

            BOT = TgClient(bot, m, path)
            Thumb = await BOT.thumb()
            prog = await bot.send_message(
                m.chat.id, f"**Processing Video {index}/{len(video_data)}:** {name}"
            )

            # Step 1: Download the video
            cmd1 = f'yt-dlp -o "{path}/fileName.%(ext)s" -f "bestvideo[height<={int(Q)}]+bestaudio" --allow-unplayable-format --external-downloader aria2c "{mpd}"'
            os.system(cmd1)

            # Step 2: Decrypt the video and audio
            avDir = os.listdir(path)
            for data in avDir:
                if data.endswith("mp4"):
                    decrypt_cmd = [
                        "mp4decrypt", keys, f"{path}/{data}", f"{path}/video.mp4"
                    ]
                    subprocess.run(decrypt_cmd, check=True)
                    os.remove(f"{path}/{data}")
                elif data.endswith("m4a"):
                    decrypt_cmd = [
                        "mp4decrypt", keys, f"{path}/{data}", f"{path}/audio.m4a"
                    ]
                    subprocess.run(decrypt_cmd, check=True)
                    os.remove(f"{path}/{data}")

            # Step 3: Merge video and audio
            cmd4 = f'ffmpeg -i "{path}/video.mp4" -i "{path}/audio.m4a" -c copy "{path}/{name}.mkv"'
            os.system(cmd4)
            os.remove(f"{path}/video.mp4")
            os.remove(f"{path}/audio.m4a")

            filename = f"{path}/{name}.mkv"
            cc = f"{name}.mkv\n\n**Description:-**\n{CP}"

            # Step 4: Upload to Telegram
            UL = Upload_to_Tg(
                bot=bot, m=m, file_path=filename, name=name,
                Thumb=Thumb, path=path, show_msg=prog, caption=cc
            )
            await UL.upload_video()
        except Exception as e:
            await bot.send_message(m.chat.id, f"Error processing video {index}: {str(e)}")
        finally:
            if os.path.exists(tPath):
                shutil.rmtree(tPath)
            shutil.rmtree(path)

    await m.reply_text("Bulk upload completed!")
