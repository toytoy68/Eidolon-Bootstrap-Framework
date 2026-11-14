---
library_name: sana, sana-sprint
tags:
- text-to-image
- SANA-Sprint
- 1024px_based_image_size
- BF16
- One-step diffusion
language:
- en
- zh
base_model:
- Efficient-Large-Model/Sana_Sprint_1.6B_1024px
pipeline_tag: text-to-image
license: apache-2.0
---
<p align="center" style="border-radius: 10px">
  <img src="https://nvlabs.github.io/Sana/Sprint/asset/SANA-Sprint.png" width="50%" alt="logo"/>
</p>

<div style="display:flex;justify-content: center">
  <a href="https://huggingface.co/collections/Efficient-Large-Model/sana-sprint-67d6810d65235085b3b17c76"><img src="https://img.shields.io/static/v1?label=Weights&message=Huggingface&color=yellow"></a> &ensp;
  <a href="https://github.com/NVlabs/Sana"><img src="https://img.shields.io/static/v1?label=Code&message=Github&color=blue&logo=github"></a> &ensp;
  <a href="https://nvlabs.github.io/Sana/Sprint/"><img src="https://img.shields.io/static/v1?label=Project&message=Github&color=blue&logo=github-pages"></a> &ensp;
  <!-- <a href="https://hanlab.mit.edu/projects/sana/"><img src="https://img.shields.io/static/v1?label=Page&message=MIT&color=darkred&logo=github-pages"></a> &ensp; -->
  <a href="https://arxiv.org/pdf/2503.09641"><img src="https://img.shields.io/static/v1?label=Arxiv&message=SANA-Sprint&color=red&logo=arxiv"></a> &ensp;
  <a href="https://nv-sana.mit.edu/sprint"><img src="https://img.shields.io/static/v1?label=Demo&message=MIT&color=yellow"></a> &ensp;
  <a href="https://discord.gg/rde6eaE5Ta"><img src="https://img.shields.io/static/v1?label=Discuss&message=Discord&color=purple&logo=discord"></a> &ensp;
</div>

# 🐱 Sana Model Card

## Demos

<div align="center">
  <a href="https://www.youtube.com/watch?v=nI_Ohgf8eOU" target="_blank">
    <img src="https://img.youtube.com/vi/nI_Ohgf8eOU/0.jpg" alt="Demo Video of SANA-Sprint" style="width: 48%; display: block; margin: 0 auto; display: inline-block;">
  </a>
  <a href="https://www.youtube.com/watch?v=OOZzkirgsAc" target="_blank">
    <img src="https://img.youtube.com/vi/OOZzkirgsAc/0.jpg" alt="Demo Video of SANA-Sprint" style="width: 48%; display: block; margin: 0 auto; display: inline-block;">
  </a>
</div>


## Training Pipeline

<p align="center" border-raduis="10px">
  <img src="https://nvlabs.github.io/Sana/Sprint/asset/content/paradigm.png" width="90%" alt="teaser_page1"/>
</p>

## Model Efficiency

<p align="center" border-raduis="10px">
  <img src="https://nvlabs.github.io/Sana/Sprint/asset/content/teaser.png" width="95%" alt="teaser_page1"/>
</p>

SANA-Sprint is an ultra-efficient diffusion model for text-to-image (T2I) generation, reducing inference steps from 20 to 1-4 while achieving state-of-the-art performance. 
Key innovations include: 
(1) A training-free approach for continuous-time consistency distillation (sCM), eliminating costly retraining; 
(2) A unified step-adaptive model for high-quality generation in 1-4 steps; and 
(3) ControlNet integration for real-time interactive image generation. 
SANA-Sprint achieves **7.59 FID and 0.74 GenEval in just 1 step** — outperforming FLUX-schnell (7.94 FID / 0.71 GenEval) while being 10× faster (0.1s vs 1.1s on H100). 
With latencies of **0.1s (T2I) and 0.25s (ControlNet)** for 1024×1024 images on H100, and 0.31s (T2I) on an RTX 4090, SANA-Sprint is ideal for AI-powered consumer applications (AIPC). 


Source code is available at https://github.com/NVlabs/Sana.

### Model Description

- **Developed by:** NVIDIA, Sana
- **Model type:** One-Step Diffusion with Continuous-Time Consistency Distillation
- **Model size:** 1.6B parameters
- **Model precision:** torch.bfloat16 (BF16)
- **Model resolution:** This model is developed to generate 1024px based images with multi-scale heigh and width.
- **License:** [Apache License 2.0](./LICENSE). Additional Information:  [Gemma Terms of Use  |  Google AI for Developers](https://ai.google.dev/gemma/terms) for Gemma-2-2B-IT, [Gemma Prohibited Use Policy  |  Google AI for Developers](https://ai.google.dev/gemma/prohibited_use_policy).
- **Model Description:** This is a model that can be used to generate and modify images based on text prompts. 
It is a Linear Diffusion Transformer that uses one fixed, pretrained text encoders ([Gemma2-2B-IT](https://huggingface.co/google/gemma-2-2b-it))
and one 32x spatial-compressed latent feature encoder ([DC-AE](https://hanlab.mit.edu/projects/dc-ae)).
- **Resources for more information:** Check out our [GitHub Repository](https://github.com/NVlabs/Sana) and the [SANA-Sprint report on arXiv](https://arxiv.org/pdf/2503.09641).


### Model Sources

For research purposes, we recommend our `generative-models` Github repository (https://github.com/NVlabs/Sana), which is more suitable for both training and inference
[MIT Han-Lab](https://nv-sana.mit.edu/sprint) provides free SANA-Sprint inference.
- **Repository:** https://github.com/NVlabs/Sana
- **Demo:** https://nv-sana.mit.edu/sprint
- **Guidance:** https://github.com/NVlabs/Sana/asset/docs/sana_sprint.md


### 🧨 Diffusers 
Under construction [PR](https://github.com/huggingface/diffusers/pull/11074)

```python
from diffusers import SanaSprintPipeline
import torch

pipeline = SanaSprintPipeline.from_pretrained(
    "Efficient-Large-Model/Sana_Sprint_1.6B_1024px_diffusers",
    torch_dtype=torch.bfloat16
)
pipeline.to("cuda:0")

prompt = "a tiny astronaut hatching from an egg on the moon"

image = pipeline(prompt=prompt, num_inference_steps=2).images[0]
image.save("sana_sprint.png")
```


## Uses

### Direct Use

The model is intended for research purposes only. Possible research areas and tasks include

- Generation of artworks and use in design and other artistic processes.
- Applications in educational or creative tools.
- Research on generative models.
- Safe deployment of models which have the potential to generate harmful content.

- Probing and understanding the limitations and biases of generative models.

Excluded uses are described below.

### Out-of-Scope Use

The model was not trained to be factual or true representations of people or events, and therefore using the model to generate such content is out-of-scope for the abilities of this model.

## Limitations and Bias

### Limitations


- The model does not achieve perfect photorealism
- The model cannot render complex legible text
- fingers, .etc in general may not be generated properly.
- The autoencoding part of the model is lossy.

### Bias
While the capabilities of image generation models are impressive, they can also reinforce or exacerbate social biases.