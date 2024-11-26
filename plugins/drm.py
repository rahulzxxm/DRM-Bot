import json
import os
import shutil
from pyrogram import filters, Client as ace
from pyrogram.types import Message
from handlers.uploader import Upload_to_Tg
from handlers.tg import TgClient
from main import Config


@ace.on_message(
    (filters.chat(Config.GROUPS) | filters.chat(Config.AUTH_USERS)) & 
    filters.incoming & filters.command("bulk_drm", prefixes=Config.prefixes)
)
async def bulk_drm(bot: ace, m: Message):
    """Bulk DRM video processing."""
    await m.reply_text("Please upload the JSON file containing video data.")
    
    # Listen for the uploaded file
    file_msg = await bot.listen(m.chat.id)

    # Check if the uploaded file is a JSON file
    if not file_msg.document or not file_msg.document.file_name.endswith('.json'):
        await m.reply_text("Invalid file format. Please send a valid JSON file.")
        return

    # Save the uploaded file to disk
    json_file_path = f"{Config.DOWNLOAD_LOCATION}/{m.chat.id}/video_data.json"
    await file_msg.download(file_name=json_file_path)
    
    # Now, process the JSON file
    try:
        with open(json_file_path, 'r') as file:
            video_data = json.load(file)

        # Process each video entry in the JSON
        for video in video_data:
            mpd = video.get("mpd")
            name = video.get("name")
            quality = video.get("quality")
            caption = video.get("caption")
            keys = video.get("keys", [])

            # Ask the user to provide keys
            inputKeys = await bot.ask(m.chat.id, "**Send Kid:Key**")
            keysData = inputKeys.text.split("\n")
            for k in keysData:
                key = f"{k} "
                keys.append(key)

            print(mpd, name, quality, keys)

            # Initialize the TgClient
            BOT = TgClient(bot, m, Config.DOWNLOAD_LOCATION)
            Thumb = await BOT.thumb()
            prog = await bot.send_message(m.chat.id, f"**Downloading Drm Video!** - [{name}]({mpd})")

            # Download and decrypt video
            cmd1 = f'yt-dlp -o "{Config.DOWNLOAD_LOCATION}/{m.chat.id}/fileName.%(ext)s" -f "bestvideo[height<={int(quality)}]+bestaudio" --allow-unplayable-format --external-downloader aria2c "{mpd}"'
            os.system(cmd1)

            avDir = os.listdir(f"{Config.DOWNLOAD_LOCATION}/{m.chat.id}")
            print(avDir)
            print("Decrypting")

            try:
                for data in avDir:
                    if data.endswith("mp4"):
                        cmd2 = f'mp4decrypt {" ".join(keys)} --show-progress "{Config.DOWNLOAD_LOCATION}/{m.chat.id}/{data}" "{Config.DOWNLOAD_LOCATION}/{m.chat.id}/video.mp4"'
                        os.system(cmd2)
                        os.remove(f'{Config.DOWNLOAD_LOCATION}/{m.chat.id}/{data}')
                    elif data.endswith("m4a"):
                        cmd3 = f'mp4decrypt {" ".join(keys)} --show-progress "{Config.DOWNLOAD_LOCATION}/{m.chat.id}/{data}" "{Config.DOWNLOAD_LOCATION}/{m.chat.id}/audio.m4a"'
                        os.system(cmd3)
                        os.remove(f'{Config.DOWNLOAD_LOCATION}/{m.chat.id}/{data}')

                # Combine video and audio
                cmd4 = f'ffmpeg -i "{Config.DOWNLOAD_LOCATION}/{m.chat.id}/video.mp4" -i "{Config.DOWNLOAD_LOCATION}/{m.chat.id}/audio.m4a" -c copy "{Config.DOWNLOAD_LOCATION}/{m.chat.id}/{name}.mkv"'
                os.system(cmd4)

                # Clean up intermediate files
                os.remove(f"{Config.DOWNLOAD_LOCATION}/{m.chat.id}/video.mp4")
                os.remove(f"{Config.DOWNLOAD_LOCATION}/{m.chat.id}/audio.m4a")
                filename = f"{Config.DOWNLOAD_LOCATION}/{m.chat.id}/{name}.mkv"
                cc = f"{name}.mkv\n\n**Description:-**\n{caption}"

                # Upload video
                UL = Upload_to_Tg(bot=bot, m=m, file_path=filename, name=name, Thumb=Thumb, path=Config.DOWNLOAD_LOCATION, show_msg=prog, caption=cc)
                await UL.upload_video()
                print(f"Uploaded {name}")
            except Exception as e:
                await prog.delete(True)
                await m.reply_text(f"**Error**\n\n`{str(e)}`\n\nOr May be Video not Available in {quality}")
            finally:
                # Cleanup
                if os.path.exists(f"{Config.DOWNLOAD_LOCATION}/THUMB/{m.chat.id}"):
                    shutil.rmtree(f"{Config.DOWNLOAD_LOCATION}/THUMB/{m.chat.id}")
                shutil.rmtree(f"{Config.DOWNLOAD_LOCATION}/{m.chat.id}")
                print(f"Completed processing for {name}")

    except Exception as e:
        await m.reply_text(f"Error processing the JSON file: {str(e)}")
        print(f"Error loading JSON file: {e}")
