# Eidolon Core Technologies (ECT)
# Projet : Eidolon Core
# Fichier : embeddinggemma-probe.py
# Description : Sonde isolee de validation du backlog
# Standard : Eidolon Presentation Standard v1
from pathlib import Path
import os,time,json,traceback
b=Path('/srv/eidolon/ssd/work/backlog-20261120')
os.environ.update(HF_HOME=str(b/'hf-cache'),HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1',TOKENIZERS_PARALLELISM='false')
result={'revision':'f9972ac22e696a105c482202646979e33e4b5a1e','device':'cuda:0','dtype':'float32','scope':'synthetic text/image smoke test only'}
try:
 from huggingface_hub import snapshot_download
 p=snapshot_download('google/embeddinggemma-2',revision=result['revision'],ignore_patterns=['*.onnx','*.tflite','*.gguf'])
 os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
 import torch,numpy as np
 from sentence_transformers import SentenceTransformer
 from PIL import Image,ImageDraw
 torch.set_num_threads(4);start=time.monotonic()
 model=SentenceTransformer(p,device='cuda:0',model_kwargs={'torch_dtype':torch.float32},config_kwargs={'audio_config':None},local_files_only=True)
 result['load_seconds']=time.monotonic()-start
 docs=['La pompe à chaleur chauffe la maison en hiver.','La carte graphique calcule des images avec sa mémoire vidéo.','Le camion transporte des marchandises sur une autoroute.']
 queries=['Quel appareil chauffe le logement ?','Quel composant utilise de la VRAM ?','Quel véhicule assure le transport routier ?']
 start=time.monotonic()
 d=model.encode(docs,prompt_name='Document',normalize_embeddings=True);q=model.encode(queries,prompt_name='SearchQuery',normalize_embeddings=True)
 result['text_seconds']=time.monotonic()-start;result['text_shape']=list(d.shape);result['text_finite']=bool(np.isfinite(d).all() and np.isfinite(q).all());result['text_top1']=(q@d.T).argmax(1).tolist();result['text_scores']=(q@d.T).tolist()
 images=[]
 for color,shape in [('red','circle'),('blue','square'),('green','triangle')]:
  im=Image.new('RGB',(224,224),'white');draw=ImageDraw.Draw(im)
  if shape=='circle':draw.ellipse((35,35,190,190),fill=color)
  elif shape=='square':draw.rectangle((35,35,190,190),fill=color)
  else:draw.polygon([(112,25),(25,190),(200,190)],fill=color)
  images.append({'image':im})
 start=time.monotonic();v=model.encode(images,normalize_embeddings=True)
 iq=model.encode(['A red circle on a white background','A blue square on a white background','A green triangle on a white background'],prompt_name='SearchQuery',normalize_embeddings=True)
 result['image_seconds']=time.monotonic()-start;result['image_shape']=list(v.shape);result['image_finite']=bool(np.isfinite(v).all());result['image_top1']=(iq@v.T).argmax(1).tolist();result['image_scores']=(iq@v.T).tolist()
 result['peak_gpu_allocated_bytes']=torch.cuda.max_memory_allocated();result['status']='completed'
except Exception as e:result['status']='failed';result['error']=repr(e);traceback.print_exc()
(b/'embeddinggemma-results.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
