import os
import json
import shutil
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
    # Step 1: Ask for the JSON file
    await m.reply_text("Please upload the JSON file containing video details.")
    response = await bot.listen(m.chat.id, filters.document, timeout=300)  # Wait for JSON file upload
    
    json_file_path = f"{Config.DOWNLOAD_LOCATION}/{response.document.file_name}"
    await response.download(file_name=json_file_path)
    
    try:
        with open(json_file_path, 'r') as f:
            video_data = json.load(f)  # Load all video data
    except Exception as e:
        await m.reply_text(f"Error reading JSON file: {e}")
        return

    total_links = len(video_data)
    await m.reply_text(f"JSON file loaded successfully. Total links: {total_links}")

    # Step 2: Ask from which index to start downloading
    await m.reply_text(f"From which index would you like to start downloading? (1 to {total_links})")
    start_response = await bot.listen(m.chat.id, filters.text, timeout=300)
    try:
        start_index = int(start_response.text.strip())
        if start_index < 1 or start_index > total_links:
            raise ValueError("Index out of range.")
    except ValueError as e:
        await m.reply_text(f"Invalid index provided: {e}")
        return

    # Step 3: Ask for the Batch Name
    await m.reply_text("Please provide the Batch Name:")
    batch_name_response = await bot.listen(m.chat.id, filters.text, timeout=300)
    batch_name = batch_name_response.text.strip()

    # Step 4: Ask for the Download By
    await m.reply_text("Please provide the Download By:")
    download_by_response = await bot.listen(m.chat.id, filters.text, timeout=300)
    download_by = download_by_response.text.strip()

    # Automatically capture the username as Download By
    download_by = f"**[{m.from_user.first_name}](tg://user?id={m.from_user.id})**"

    await m.reply_text(f"Batch Name: {batch_name}\nDownload By: {download_by}")

    # Ask for the thumbnail only once before processing any videos
    tPath = f"{Config.DOWNLOAD_LOCATION}/THUMB/{m.chat.id}"
    os.makedirs(tPath, exist_ok=True)
    BOT = TgClient(bot, m, tPath)
    Thumb = await BOT.thumb()  # Get the thumbnail once

    # Adjust the range for processing videos based on start_index
    for index, video in enumerate(video_data[start_index - 1:], start=start_index):
        try:
            mpd = video.get("mpd")
            raw_name = video.get("name")
            Q = video.get("quality", "720")
            keys = video.get("keys", [])

            if not mpd or not raw_name or not keys:
                await m.reply_text(f"Skipping entry due to missing details: {video}")
                continue

            # Index the video with three-digit padding
            name = f"**{index:03}.** {TgClient.parse_name(raw_name)} ({Q}p)"
            path = f"{Config.DOWNLOAD_LOCATION}/{m.chat.id}/{name}"
            os.makedirs(path, exist_ok=True)

            prog = await bot.send_message(m.chat.id, f"**Downloading DRM Video!** - [{name}]({mpd})")

            # Downloading the encrypted video
            download_cmd = (
                f'yt-dlp -o "{path}/fileName.%(ext)s" '
                f'-f "bestvideo[height<={int(Q)}]+bestaudio" --allow-unplayable-format '
                f'--external-downloader aria2c "{mpd}"'
            )
            os.system(download_cmd)

            av_files = os.listdir(path)
            for data in av_files:
                if data.endswith("mp4"):
                    # Decrypt video
                    decrypt_video_cmd = (
                        f'mp4decrypt {" ".join([f"--key {key}" for key in keys])} '
                        f'"{path}/{data}" "{path}/video.mp4"'
                    )
                    os.system(decrypt_video_cmd)
                    os.remove(f'{path}/{data}')
                elif data.endswith("m4a"):
                    # Decrypt audio
                    decrypt_audio_cmd = (
                        f'mp4decrypt {" ".join([f"--key {key}" for key in keys])} '
                        f'"{path}/{data}" "{path}/audio.m4a"'
                    )
                    os.system(decrypt_audio_cmd)
                    os.remove(f'{path}/{data}')

            # Merge video and audio into .mkv format
            merge_cmd = f'ffmpeg -i "{path}/video.mp4" -i "{path}/audio.m4a" -c copy "{path}/{name}.mkv"'
            os.system(merge_cmd)

            # Ensure the file is correctly named with .mkv extension
            filename = f"{path}/{name}.mkv"

            # Remove the raw video and audio files after merging
            os.remove(f"{path}/video.mp4")
            os.remove(f"{path}/audio.m4a")

            # Format caption with bold text for index, Batch Name, and Download By
            cc = f"**{index:03}.** {TgClient.parse_name(raw_name)} ({Q}p)\n\n" \
                 f"**Batch Name :** {batch_name}\n\n" \
                 f"**Download By :** {download_by}"

            # Upload to Telegram with .mkv extension
            UL = Upload_to_Tg(bot=bot, m=m, file_path=filename, name=f"{name}.mkv",  # Name includes .mkv
                              Thumb=Thumb, path=path, show_msg=prog, caption=cc)
            await UL.upload_video()
            print(f"Processed and uploaded: {name}.mkv")  # Log with .mkv extension
        except Exception as e:
            await prog.delete(True)
            await m.reply_text(f"**Error while processing {video.get('name', 'Unknown')}**\n\n{str(e)}")
        finally:
            shutil.rmtree(path)  # Cleanup the video files after processing

    # Remove the JSON file after processing all videos
    if os.path.exists(json_file_path):
        os.remove(json_file_path)
    
    await m.reply_text("All videos processed and uploaded successfully.")
