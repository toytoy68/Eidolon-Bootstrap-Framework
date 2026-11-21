# Eidolon Core Technologies (ECT) - synthetic visual perception qualification
from pathlib import Path
import json,sys,time,os,re,traceback,hashlib
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P/'wevis-source'))
import torch,numpy as np
from PIL import Image,ImageDraw,ImageFont
from wevisone_vl import WeVisOneVL
out=P/'wevis-results';out.mkdir(exist_ok=False)
torch.set_num_threads(8);torch.manual_seed(1234)
image=Image.new('RGB',(512,384),'white');d=ImageDraw.Draw(image)
d.rectangle((40,60,140,160),fill='red');d.rectangle((220,60,320,160),fill='red');d.ellipse((370,70,460,160),fill='blue')
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',44)
d.text((120,260),'STOP 42',font=font,fill='black')
image.save(out/'scene.png')
tasks=[('count','count_point','red squares'),('locate','referring','the blue circle'),('absent','referring','a green triangle'),('ocr','ocr',''),('mask','segmentation','the blue circle'),('count-repeat','count_point','red squares')]
(out/'protocol.json').write_text(json.dumps(dict(tasks=tasks,known=dict(red_squares=2,blue_circle_box=[370/512,70/384,460/512,160/384],green_triangle_absent=True,text='STOP 42'),criteria='count exact; absent None; box IoU >=0.5; OCR exact text; mask IoU>=0.5; repeat identical',source_commit='9a6bcd85404505df0d05cfb5d97512ccacf35dee',precision='float16',torch=torch.__version__,transformers=__import__('transformers').__version__,runtime_differs_vendor_pins=True),indent=2))
try:
 t=time.time();m=WeVisOneVL(str(P/'wevis-model'),device='cuda:0',dtype='float16',attention_implementation='sdpa',max_pixels=512*512,decoder_batch_size=1)
 rows=[];load=time.time()-t
 for ident,task,query in tasks:
  t=time.time()
  result=m.predict(image,task=task,query=query,max_new_tokens=512,temperature=0)
  torch.cuda.synchronize()
  row=dict(id=ident,task=task,query=query,response=result.response,boxes=result.boxes,mask_count=len(result.masks),seconds=time.time()-t,peak_vram_mib=torch.cuda.max_memory_allocated()/1048576)
  for i,mask in enumerate(result.masks):
   np.save(out/(ident+'-mask-'+str(i)+'.npy'),mask)
   Image.fromarray(np.uint8(np.clip(mask,0,1)*255)).save(out/(ident+'-mask-'+str(i)+'.png'))
  rows.append(row);(out/'results.json').write_text(json.dumps(dict(load_seconds=load,rows=rows),indent=2))
 (out/'status.json').write_text(json.dumps(dict(finished=True)))
except BaseException as e:
 (out/'status.json').write_text(json.dumps(dict(finished=False,error=repr(e),traceback=traceback.format_exc()),indent=2));raise
