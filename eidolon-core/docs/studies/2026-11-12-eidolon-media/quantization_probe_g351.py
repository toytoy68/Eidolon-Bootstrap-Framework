# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : quantization_probe_g351.py
# Description : Vérification limitée de déquantification Q8 sur Volta
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
from collections import Counter
import json,numpy as np,torch,gguf
from diffusers.quantizers.gguf.utils import GGUFParameter,dequantize_gguf_tensor
w=Path('/srv/eidolon/workspaces/media-20261112/flux-q8-g351')
reader=gguf.GGUFReader('/srv/eidolon/data/media-models-20261113/flux-schnell-q8/flux1-schnell-Q8_0.gguf')
t=next(t for t in reader.tensors if t.tensor_type==gguf.GGMLQuantizationType.Q8_0)
data=t.data.reshape(-1,34)[:16].copy()
expected=gguf.quants.dequantize(data,gguf.GGMLQuantizationType.Q8_0)
p=GGUFParameter(torch.from_numpy(data).cuda(),quant_type=gguf.GGMLQuantizationType.Q8_0)
actual=dequantize_gguf_tensor(p).float().cpu().numpy();error=float(np.max(np.abs(actual-expected)))
assert np.isfinite(actual).all() and np.allclose(actual,expected,rtol=.001,atol=.00001)
report={'tensor_count':len(reader.tensors),'tensor_types':dict(Counter(t.tensor_type.name for t in reader.tensors)),'sample_tensor':t.name,'sample_blocks':16,'max_abs_error_vs_numpy':error,'cuda_capability':torch.cuda.get_device_capability(),'torch':torch.__version__,'diffusers':__import__('diffusers').__version__,'gguf':'0.17.1','proof_scope':'16 blocks only, GPU dequantization versus numpy; not a full conversion audit'}
(w/'quantization-probe.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
