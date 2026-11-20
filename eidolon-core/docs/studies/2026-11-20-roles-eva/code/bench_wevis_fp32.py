# Eidolon Core Technologies (ECT) - controlled FP32 mask decoder diagnostic
from pathlib import Path
import json,sys,time,inspect,textwrap,types
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P/'wevis-source'))
import torch,numpy as np
from PIL import Image,ImageDraw
from wevisone_vl import WeVisOneVL
import wevisone_vl.engine as engine
out=P/'wevis-fp32-decoder';out.mkdir(exist_ok=False)
torch.set_num_threads(8);torch.manual_seed(1234)
try:
 model=WeVisOneVL(str(P/'wevis-model'),device='cuda:0',dtype='float16',attention_implementation='sdpa',max_pixels=512*512,decoder_batch_size=1)
 model.mask_decoder.float()
 state=torch.load(P/'wevis-model/mask_decoder.pt',map_location='cpu',weights_only=True)
 model.mask_decoder.load_state_dict(state['state_dict'],strict=True);del state
 source=textwrap.dedent(inspect.getsource(WeVisOneVL.decode_masks)).replace('dtype=self.dtype','dtype=torch.float32')
 source=source.replace('count = min(len(boxes), int(t_seg.shape[0]))','assert all(torch.isfinite(f).all() for f in visual_maps) and torch.isfinite(t_seg).all(), "Nonfinite backbone features"\n    count = min(len(boxes), int(t_seg.shape[0]))')
 ns=dict(engine.__dict__);exec(compile(source,'fp32-decode-masks','exec'),ns)
 model.decode_masks=types.MethodType(ns['decode_masks'],model)
 (out/'decode_masks.py').write_text(source)
 results=[]
 for ident,box in [('original',(370,70,460,160)),('shifted',(60,200,150,290)),('original-repeat',(370,70,460,160))]:
  if ident.startswith('original'):image=Image.open(P/'wevis-results/scene.png')
  else:
   image=Image.new('RGB',(512,384),'white');d=ImageDraw.Draw(image);d.ellipse(box,fill='blue');d.rectangle((260,60,360,160),fill='red')
  image.save(out/(ident+'.png'));t=time.time()
  result=model.predict(image,task='segmentation',query='the blue circle',max_new_tokens=512,temperature=0)
  mask=result.masks[0] if result.masks else np.zeros((384,512))
  finite=bool(np.isfinite(mask).all());gold=Image.new('L',(512,384),0);ImageDraw.Draw(gold).ellipse(box,fill=255);g=np.asarray(gold)>0;b=mask>=.5
  iou=float((b&g).sum()/(b|g).sum()) if finite else None
  np.save(out/(ident+'-mask.npy'),mask)
  if finite:Image.fromarray(np.uint8(np.clip(mask,0,1)*255)).save(out/(ident+'-mask.png'))
  results.append(dict(id=ident,response=result.response,boxes=result.boxes,masks=len(result.masks),finite=finite,iou=iou,seconds=time.time()-t,peak_vram_mib=torch.cuda.max_memory_allocated()/1048576))
  (out/'results.json').write_text(json.dumps(results,indent=2))
 (out/'status.json').write_text(json.dumps(dict(finished=True,passed=all(x['finite'] and x['iou']>=.5 for x in results),same_initial_mask=np.array_equal(np.load(out/'original-mask.npy'),np.load(out/'original-repeat-mask.npy')))))
except BaseException as e:
 import traceback
 (out/'status.json').write_text(json.dumps(dict(finished=False,error=repr(e),traceback=traceback.format_exc()),indent=2));raise
