import io
import os
import glob
import datetime
import pydub
from pydub.silence import detect_nonsilent
import discord
from discord.ext import commands
from discord.sinks import MP3Sink
import google.generativeai as genai
import whisper
from enum import Enum
from tqdm import tqdm
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
DISCORD_API_KEY = os.environ.get("DISCORD_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')
whisper_model = whisper.load_model("medium")
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(intents=intents)
memberlist = []
recList = []

class GeminiVersion(Enum):
    gemin_10_pro = "gemini-1.0-pro"
    gemin_15_pro_lst = "gemini-1.5-pro-latest"
    gemin_flash_15_lst = "gemini-1.5-flash-latest"

def user_name(user_id: str):
    name = "fullrecord"
    global memberlist
    if user_id != "fullRecord":
        userinfo = next(x for x in memberlist if x.id == user_id)
        name = userinfo.nick
        if name == None:
            name = userinfo.name
    
    return name 

def seconds_to_hms(seconds):
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

async def finished_callback(sink: MP3Sink, ctx: discord.ApplicationContext):
    channel = ctx.channel
    global memberlist
    if (memberlist == None):
        memberlist = ctx.guild.members
        
    mention_strs = []
    audio_segs: list[pydub.AudioSegment] = []
    files: list[discord.File] = []
    longest = pydub.AudioSegment.empty()   

    for user_id, audio in sink.audio_data.items():
        name = user_name(user_id)
        mention_strs.append(f"<@{user_id}> : {user_id}\n")
        temp = io.BytesIO(audio.file.getvalue())
        seg = pydub.AudioSegment.from_file(temp,format("mp3"))
        
        # Determine the longest audio segment
        if len(seg) > len(longest):
            audio_segs.append(longest)
            longest = seg
        else:
            audio_segs.append(seg)
        
        file_name = f"{name}.{sink.encoding}"
        file_name = file_name.encode('utf-8').decode('utf-8')
        audio.file.seek(0)
        files.append(discord.File(audio.file, f"{file_name}"))
        audio_copy = io.BytesIO(audio.file.getvalue())
        recList.append((user_id , audio_copy))

    for seg in audio_segs:
        longest = longest.overlay(seg)

    with io.BytesIO() as f:
        longest.export(f, format="mp3")
        audio_copy = io.BytesIO(f.getvalue())
        recList.append(("fullRecord" , audio_copy))
        
        await channel.send(
            f"Finished! Recorded audio for \n {' '.join(mention_strs)}",
            files=files + [discord.File(f, filename="fullRecord.mp3")],
        )

@bot.slash_command()
async def join(ctx: discord.ApplicationContext):
    """Join the voice channel!"""
    voice = ctx.author.voice
    global memberlist
    memberlist = ctx.guild.members
    if not voice:
        return await ctx.respond("You're not in a vc right now")

    await voice.channel.connect()

    await ctx.respond("Joined!")

@bot.slash_command()
async def start(ctx: discord.ApplicationContext):
    """Record the voice channel!"""
    voice = ctx.author.voice

    if not voice:
        return await ctx.respond("You're not in a vc right now")

    vc: discord.VoiceClient = ctx.voice_client

    if not vc:
        return await ctx.respond(
            "I'm not in a vc right now. Use `/join` to make me join!"
        )

    vc.start_recording(
        MP3Sink(),
        finished_callback,
        ctx,
        sync_start=True,
    )

    await ctx.respond("The recording has started!")

@bot.slash_command()
async def stop(ctx: discord.ApplicationContext):
    vc: discord.VoiceClient = ctx.voice_client
    
    if not vc:
        return await ctx.respond("There's no recording going on right now")

    vc.stop_recording()

    await ctx.respond("The recording has stopped!")

@bot.slash_command()
async def leave(ctx: discord.ApplicationContext):
    """Leave the voice channel!"""
    vc: discord.VoiceClient = ctx.voice_client

    if not vc:
        return await ctx.respond("I'm not in a vc right now")

    # remove tempdata
    temp_file = glob.glob('temp/*')
    for t in temp_file:
        try:
            os.remove(t)
        except OSError as e:
            print('Delete Problem: ', e)
            
    temp_audio = glob.glob('*.mp3') 
    for t in temp_audio:
        try:
            os.remove(t)
        except OSError as e:
            print('Delete Problem: ', e)     
    
    recList.clear()
            
    await vc.disconnect()

    await ctx.respond("Left!")

@bot.slash_command()
async def totext(ctx: discord.ApplicationContext):    
    if recList.count == 0:
        return await ctx.respond(
            "no file can transcribe"
        )
    temp_folder = "temp"  

    try:
        os.makedirs(temp_folder)    
    except FileExistsError:
        print("暫存資料夾已存在")
    
    for user_id, audio in tqdm(recList):    
        name = user_name(user_id)
        file_path = f"{user_id}_audio"        
        with open(f"{file_path}.mp3", "wb") as audio_file:
            audio.seek(0)
            audio_file.write(audio.read())
        
        result = f"{name}:\n{transcribe(name, file_path, temp_folder)}"
        txt_path =f"{temp_folder}/{user_id}.txt" 
        with open(txt_path, "w", encoding= "utf-8") as file:
            file.write(result)
        
        with open(txt_path, "rb") as file: 
            file_name = f"{name}.txt"
            file_name = file_name.encode('utf-8').decode('utf-8')
            await ctx.channel.send(
                    f"<@{user_id}> transcribe result:"
                     ,files= [discord.File(fp=file, filename=file_name)]
                )
      
    recList.clear()

    await ctx.channel.send(
        f"speech to text Finished!"
    )
    
def transcribe(name:str, file_path:str, temp_folder:str):
    audio = pydub.AudioSegment.from_file(f"{file_path}.mp3")

    # 檢測非沉默部分
    nonsilent_chunks = detect_nonsilent(
        audio,
        min_silence_len=1500,
        silence_thresh=-100
    )
    result = ""
    # 輸出非沉默部分
    for start_ms, end_ms in tqdm(nonsilent_chunks):
        temp_file = f"{temp_folder}/{file_path}_{start_ms}_{end_ms}.mp3"
        non_silent_segment = audio[start_ms:end_ms]
        non_silent_segment.export(temp_file, format="mp3")
        buffer = whisper_model.transcribe(temp_file, 
                                        language="zh", 
                                        verbose=False, 
                                        logprob_threshold = None,
                                        temperature=0)
        result = result + f"{segment(buffer, (start_ms / 1000))}"

    all_temp_audio = glob.glob('temp/*.mp3')
    for t in all_temp_audio:
        try:
            os.remove(t)
        except OSError as e:
            print('Delete Problem: ', e)  
            
    print(result)
    return result  

def segment( input: dict[str, list], create_time):
    result = ""
    for i, segment in enumerate(input["segments"]):
        text = segment["text"]
        start_seconds = datetime.timedelta(seconds=segment["start"]).total_seconds()
        end_seconds = datetime.timedelta(seconds=segment["end"]).total_seconds()
        total_seconds = end_seconds - start_seconds
        start_time = create_time + start_seconds
        end_time = start_time + total_seconds
        result = result + f"[{seconds_to_hms(start_time)}]-[{seconds_to_hms(end_time)}] {text}\n"
                  
    return result

@bot.slash_command()
async def gemini(ctx: discord.ApplicationContext, version: GeminiVersion, content:str):
    model = genai.GenerativeModel(version.value)
    response = model.generate_content(content)    
    await ctx.channel.send(response.text)

@bot.slash_command()
async def auto_gemini(ctx: discord.ApplicationContext, version: GeminiVersion):
    all_txt_file = glob.glob('temp/*.txt')
    content1 = ""
    content2 = ""
    for txt_file in all_txt_file:
        try:
            if txt_file.find("fullRecord") > 0 :
                with open(txt_file, "r", encoding="utf-8") as file: 
                    next(file)
                    for line in file:
                        content2 = content2 + line
            else :
                with open(txt_file, "r", encoding="utf-8") as file: 
                     content2 = content2 + file.read()
        except OSError as e:
            print('Delete Problem: ', e)              
    
    prompt = f""" !!!角色說明
                  你的角色為Scrum敏捷式開發的每日Stand up meeting 會議記錄人員
                  你需要將每個人員的文字做整理
                  不確定的字詞要保留
                  去除重複的冗詞贅字
                  整理出昨日處理狀況、昨日遇到的問題、今日預計處理的項目。
                  
                  以下提供範例，僅作為格式參考: 
                  範例一:                
                  [原文] nobody1: 
                         [0]-[251]
                             好 那就那我們開始吧
                             呃，好吧，我今天要先處理我現在在處理mailgun
                             然後晚點把文件補齊部署到我的主機上面
                             然後給就是把整個highdumps給視覺他們測看看
                             然後確定一下有什麼問題之類的。
                             好的
                             然後今天應該除了這些事情以外
                             應該會繼續處理剩下的全線部分。
                  [回覆] nobody1:
                         今日: 處理mailgun，準備文件部署到主機，交付視覺團隊測試highdumps，繼續處理權限部分。
                               遇到的問題: 暫無提及特定問題。
                  範例二:
                  [原文] nobody2:
                         [255]-[615] 
                         那再來就是我了對呃
                         昨天早在處理
                         內政部那個公情某些特定狀況下
                         不會合法釋出的問題
                         然後昨天上班8小時在處理
                         下班8小時在處理。
                         呃，好可憐，差不多了好可憐。
                         然後今天應該這會處理那個收尾因為今天早差不多了然後再來就是改他回來的修改這樣。
                    [回覆] nobody2:
                           昨日: 處理內政部公情某些狀況下不合法釋出的問題，昨天全天處理此事。
                           今日: 收尾昨日的工作，並進行必要的修改。
                           遇到的問題: 工作量大，需長時間處理。 
                                          
                經過上述的範例後
                你已了解回覆的格式
                整理文字"不要"參考範例的原文。
                
                !!!正式開始
                接下來你將得到兩段語音辨識的文字訊息
                第一段為各人員分別的語音紀錄
                第二段為混音後的該會議室的語音紀錄
                請根據這兩段的文字記錄及註記的時間軸
                將會議記錄整理出來。
                
                第一段:
                請整理接下來這些文字，這些文字為各個人員分別的語音辨識的結果，你將會得到時間軸與對話紀錄: 
                {content1}
                
                第二段:
                請整理接下來這些文字，這些文字為會議室所有人員的錄音，你將會得到時間軸與對話紀錄: 
                {content2}                
                """
    model = genai.GenerativeModel(version.value)
    response = model.generate_content(prompt)    
    await ctx.channel.send(response.text)  
      
    for file in all_txt_file:
        try:
            os.remove(file)
        except OSError as e:
            print('Delete Problem: ', e)  
            
bot.run(DISCORD_API_KEY)  