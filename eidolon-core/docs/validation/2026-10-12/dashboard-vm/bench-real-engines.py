# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bench-real-engines.py
# Description : Recette des moteurs avec entrees synthetiques privees
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import sys,pathlib,time,json,tempfile,subprocess,threading,io,wave
sys.path.insert(0,"/home/toytoy/eidolon-worktrees/comm-deploy-20261012/eidolon-core/src")
from eidolon_core.comm_tts import PiperTTS,TextToSpeech,chunks
from eidolon_core.comm_stt import FasterWhisperSTT,SpeechToText
from eidolon_core.comm_vision import OllamaVision,Vision
from PIL import Image,ImageDraw
root=pathlib.Path("/home/toytoy/eidolon-comm")
tts=TextToSpeech(PiperTTS(str(root/"venv/bin/piper"),str(root/"voices")),default_voice="fr_FR-siwis-medium")
stt=SpeechToText(FasterWhisperSTT(str(root/"models/whisper-small"),threads=2),time_budget=180)
measurements=[]
for seconds,text in [(5,"Bonjour. Le serveur fonctionne."),(20,"Bonjour toytoy. Nous testons la mémoire Eidolon, les nombres vingt-quatre et cent dix, puis la caméra et la synthèse vocale. Le serveur fonctionne et les données restent locales.")]:
 start=time.monotonic();out=tts.synthesize("acceptance",text,index=0)
 tts_s=time.monotonic()-start
 pieces=[out["wav"]]
 for index in range(1,len(chunks(text))):pieces.append(tts.synthesize("acceptance",text,index=index)["wav"])
 frames=[];parameters=None
 for piece in pieces:
  with wave.open(io.BytesIO(piece),"rb") as reader:
   parameters=reader.getparams();frames.append(reader.readframes(reader.getnframes()))
 merged=io.BytesIO()
 with wave.open(merged,"wb") as writer:
  writer.setnchannels(parameters.nchannels);writer.setsampwidth(parameters.sampwidth);writer.setframerate(parameters.framerate);writer.writeframes(b"".join(frames))
 out["wav"]=merged.getvalue()
 with tempfile.TemporaryDirectory() as directory:
  source=pathlib.Path(directory)/"input.wav";source.write_bytes(out["wav"]);dest=pathlib.Path(directory)/"test.wav"
  subprocess.run(["ffmpeg","-v","error","-y","-i",str(source),"-af","apad","-t",str(seconds),"-ar","16000","-ac","1",str(dest)],check=True)
  payload=dest.read_bytes()
  start=time.monotonic();answer=stt.transcribe("acceptance",payload);elapsed=time.monotonic()-start
 measurements.append({"audio_s":seconds,"reference":text,"tts_server_chunk_s":tts_s,"stt_s":elapsed,"real_time_factor":elapsed/seconds,"transcript":answer["text"],"synthetic_audio":True})
image=Image.new("RGB",(320,240),"white");ImageDraw.Draw(image).ellipse((80,40,240,200),fill="red");buffer=io.BytesIO();image.save(buffer,format="PNG")
start=time.monotonic()
try:
 raw=OllamaVision("http://127.0.0.1:11435","gemma4:12b").describe(buffer.getvalue(),time.monotonic()+60)
 from eidolon_core.comm_vision import observation
 observed=observation(raw)
 visual={"s":time.monotonic()-start,"result":observed,"synthetic_image":True}
except Exception as e:visual={"error":type(e).__name__+":"+str(e),"synthetic_image":True,"raw_observation":locals().get("raw")}
(root/"acceptance-real-engines.json").write_text(json.dumps({"audio":measurements,"vision":visual},ensure_ascii=False,indent=2))
print("Real engine measurements saved")
