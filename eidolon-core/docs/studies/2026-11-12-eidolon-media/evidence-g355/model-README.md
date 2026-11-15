---
license: cc-by-nc-nd-4.0
language:
- en
library_name: diffusers
pipeline_tag: text-to-image
base_model: stabilityai/stable-diffusion-xl-base-1.0
extra_gated_prompt: |
  By accessing this model, you agree to the following:
  - You will NOT deploy this model behind a paid API or generative service.
  - You will NOT use this model on a platform that competes with RunDiffusion.com.
  - You will NOT redistribute or rehost the model weights.
  - You agree to receive communications from RunDiffusion (model releases, platform updates, and news). RunDiffusion does not misuse your information.
  Commercial licenses can be obtained by emailing juggernaut@rundiffusion.com.
extra_gated_fields:
  Name: text
  Email: text
  Intended use: text
tags:
- stable-diffusion
- stable-diffusion-xl
- sdxl
- text-to-image
- photorealistic
- photography
- cinematic
- portrait
- juggernaut
- rundiffusion
- kandooai
---

<div align="center">

<a href="https://www.rundiffusion.com/juggernaut?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_v11&utm_content=header_banner">
  <img src="https://huggingface.co/RunDiffusion/Juggernaut-XI-v11/resolve/main/assets/Juggernaut_Banner.webp" alt="Juggernaut — by RunDiffusion" />
</a>

<h1>Juggernaut XI v11 by RunDiffusion</h1>

<p><i>The latest evolution of the Juggernaut SDXL line — sharper aesthetics, better hands, faces, and prompt adherence.</i></p>

<p>
  <a href="https://app.rundiffusion.com/login?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_v11&utm_content=hero_cta"><img alt="Try Juggernaut XI — Free" src="https://img.shields.io/badge/%E2%96%B6%20Try%20Juggernaut%20XI%20%E2%80%94%20Free-7C3AED?style=for-the-badge&labelColor=7C3AED"></a>
</p>

<p>
  <a href="https://www.rundiffusion.com/prompting?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_v11&utm_content=prompting_resource"><img alt="Prompting Guides" src="https://img.shields.io/badge/%F0%9F%93%96%20Prompting%20Guides-1f1f23?style=for-the-badge"></a>&nbsp;<a href="https://www.rundiffusion.com/juggernaut?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_v11&utm_content=lineup_compare"><img alt="Compare the Lineup" src="https://img.shields.io/badge/Compare%20the%20Lineup-1971c2?style=for-the-badge&labelColor=1f1f23"></a>&nbsp;<img alt="Gated" src="https://img.shields.io/badge/Access-Gated-EAB308?style=for-the-badge&labelColor=1f1f23">&nbsp;<img alt="License: CC BY-NC-ND 4.0" src="https://img.shields.io/badge/License-CC%20BY--NC--ND%204.0-2ea44f?style=for-the-badge">
</p>

</div>

> Juggernaut XI is the **latest evolution** of the Juggernaut SDXL line. Like Juggernaut X, it was **trained from the ground up** with **GPT-4 Vision** captioning — but with another pass of dataset cleanup, refined shot-type classification, and improved aesthetic targeting on top. Sharper hands, faces, eyes, and composition; stronger prompt adherence; native text rendering; and the same **RunDiffusion Photo** detail refinement that made earlier versions popular.

## What's Better in XI

- 🎨 **Massively improved aesthetics** — refined lighting, color, and composition vs. v10
- 🖐️ **Better hands, eyes, faces, and overall human anatomy**
- 🎯 **Even stronger prompt adherence** — XI does what you ask with less wrestling than X
- 📸 **Cleaner shot-type classification** — Full Body / Mid Shot / Portrait distinctions are crisper
- 🔤 **Native text rendering** — legible signage, labels, short phrases
- 💬 **Two prompting styles** — Natural language *or* Tagging (use whichever fits)
- 🖼️ **RunDiffusion Photo** refinement for fine detail

---

<div align="center">

<h3>🚀 Skip the gated download. Try Juggernaut XI in your browser.</h3>

<p>No HF gate. No installs. No GPU rental. <b>Just generate.</b></p>

<a href="https://app.rundiffusion.com/login?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_v11&utm_content=midpage_cta"><img alt="Launch on RunDiffusion" src="https://img.shields.io/badge/%E2%96%B6%20Launch%20on%20RunDiffusion-7C3AED?style=for-the-badge&labelColor=7C3AED"></a>

<p><i>Pre-loaded into ComfyUI · Forge · Automatic1111 · Fooocus · InvokeAI · SwarmUI</i></p>

</div>

---

## Two Prompting Styles

| Style | Best for | Example |
| --- | --- | --- |
| **Natural language** | Storytelling, scenes, complex instructions | *"A photographer on a windswept cliff at golden hour, holding a vintage Leica, ocean churning below"* |
| **Tagging** | Quick iteration, established workflows | *`photograph, cliff, golden hour, vintage Leica, ocean, waves, cinematic lighting`* |

📖 **For deeper prompting technique** — see the [**RunDiffusion prompting library**](https://www.rundiffusion.com/prompting?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_v11&utm_content=prompting_inline). Free to read, no signup.

## Recommended Settings

| Parameter | Value |
| --- | --- |
| Resolution | `832 × 1216` (portrait) · `1216 × 832` (landscape) |
| Sampler | `DPM++ 2M Karras` |
| Steps | `30 – 40` |
| CFG scale | `3 – 7` (lower = more realistic) |
| VAE | **Already baked in** — no external VAE required |

For a faster variant, see [**Juggernaut XI Lightning**](https://huggingface.co/RunDiffusion/Juggernaut-XI-Lightning) — same XI base, distilled to 5–7-step inference.

## Two Ways to Run Juggernaut XI

### 🚀 Easiest — Run it on RunDiffusion (recommended)

One-click access inside ComfyUI, Forge, Automatic1111, Fooocus, InvokeAI, or SwarmUI. **No HF gate.** No setup. **Free trial included**, plus access to every other Juggernaut model on the same account.

<div align="center">
  <a href="https://app.rundiffusion.com/login?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_v11&utm_content=quickstart_try"><img alt="Get Started Free" src="https://img.shields.io/badge/Get%20Started%20Free%20%E2%86%92-7C3AED?style=for-the-badge&labelColor=7C3AED"></a>
</div>

### 💻 Or run it locally — Diffusers

> **Note:** XI is a gated model — you must accept the terms above and authenticate with `huggingface-cli login` (or set `HF_TOKEN`) before pulling weights.

```python
import torch
from diffusers import DiffusionPipeline

pipe = DiffusionPipeline.from_pretrained(
    "RunDiffusion/Juggernaut-XI-v11",
    torch_dtype=torch.float16,
    use_safetensors=True,
).to("cuda")

prompt = "A photographer on a windswept cliff at golden hour, holding a vintage Leica, the ocean churning below, cinematic lighting, hyperdetailed photography"

image = pipe(prompt, width=832, height=1216, num_inference_steps=35, guidance_scale=5.0).images[0]
image.save("juggernaut_xi_v11.png")
```

## The Rest of the Family

| Model | Why pick it |
| --- | --- |
| [**Juggernaut XL v9**](https://huggingface.co/RunDiffusion/Juggernaut-XL-v9) | The most popular Juggernaut — proven SDXL workhorse. **6M+ downloads.** |
| [**Juggernaut X v10**](https://huggingface.co/RunDiffusion/Juggernaut-X-v10) | Predecessor of XI — the first ground-up GPT-4V retrain |
| [**Juggernaut XI Lightning**](https://huggingface.co/RunDiffusion/Juggernaut-XI-Lightning) | XI quality at 5–7 steps |
| [**Juggernaut Z**](https://huggingface.co/RunDiffusion/Juggernaut-Z-Image) | Lumina-Image-2 architecture — cinematic, presentation-ready |
| [**Juggernaut Pro Flux**](https://www.rundiffusion.com/juggernaut-pro-flux?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_v11&utm_content=cross_promo_pro_flux) | FLUX.1 backbone — top-tier photo quality |

## License & Commercial Use

Juggernaut XI v11 is released under **[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/)**:

- **BY** — attribute RunDiffusion / KandooAI when sharing output.
- **NC** — **non-commercial use only**. Commercial use requires a license.
- **ND** — **no derivatives**. You may not redistribute modified versions, fine-tunes, or merges.

Additionally, this model **may not be deployed behind paid API services** or hosted on platforms that compete with RunDiffusion.com. For commercial licensing, custom models, or business inquiries, contact **[juggernaut@rundiffusion.com](mailto:juggernaut@rundiffusion.com)**.

## Credits

Juggernaut XI was created by **[KandooAI](https://twitter.com/Juggernaut_AI)** in collaboration with **[RunDiffusion](https://www.rundiffusion.com/?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_v11&utm_content=credits)**. Dataset re-captioned with the **GPT-4 Vision Captioning** tool by **[LEOSAM](https://civitai.com/user/LEOSAM)**. Photographic backbone by the RunDiffusion Photo team.

---

<div align="center">

<h3>Ready to generate?</h3>

<p>Juggernaut XI is one click away on RunDiffusion — no gate, no setup, no GPU rental.</p>

<a href="https://app.rundiffusion.com/login?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_v11&utm_content=footer_cta"><img alt="Try Juggernaut XI — Free" src="https://img.shields.io/badge/%E2%96%B6%20Try%20Juggernaut%20XI%20%E2%80%94%20Free-7C3AED?style=for-the-badge&labelColor=7C3AED"></a>

<p><sub><a href="https://www.rundiffusion.com/juggernaut?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_v11&utm_content=footer_lineup">Compare the full Juggernaut lineup</a> · <a href="https://www.rundiffusion.com/prompting?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_v11&utm_content=footer_prompting">Prompting guides</a> · <a href="mailto:juggernaut@rundiffusion.com">Commercial licensing</a></sub></p>

</div>
