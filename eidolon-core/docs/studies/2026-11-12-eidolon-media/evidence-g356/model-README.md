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
- sdxl-lightning
- text-to-image
- photorealistic
- fast
- low-step
- juggernaut
- rundiffusion
- kandooai
---

<div align="center">

<a href="https://www.rundiffusion.com/juggernaut?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_lightning&utm_content=header_banner">
  <img src="https://huggingface.co/RunDiffusion/Juggernaut-XI-Lightning/resolve/main/assets/Juggernaut_Banner.webp" alt="Juggernaut — by RunDiffusion" />
</a>

<h1>Juggernaut XI Lightning by RunDiffusion</h1>

<p><i>The latest XI quality at SDXL Lightning speed — 5–7 steps, photo-grade output.</i></p>

<p>
  <a href="https://app.rundiffusion.com/login?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_lightning&utm_content=hero_cta"><img alt="Try Juggernaut XI Lightning — Free" src="https://img.shields.io/badge/%E2%96%B6%20Try%20Juggernaut%20XI%20Lightning%20%E2%80%94%20Free-7C3AED?style=for-the-badge&labelColor=7C3AED"></a>
</p>

<p>
  <a href="https://www.rundiffusion.com/prompting?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_lightning&utm_content=prompting_resource"><img alt="Prompting Guides" src="https://img.shields.io/badge/%F0%9F%93%96%20Prompting%20Guides-1f1f23?style=for-the-badge"></a>&nbsp;<a href="https://www.rundiffusion.com/juggernaut?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_lightning&utm_content=lineup_compare"><img alt="Compare the Lineup" src="https://img.shields.io/badge/Compare%20the%20Lineup-1971c2?style=for-the-badge&labelColor=1f1f23"></a>&nbsp;<img alt="5-7 steps" src="https://img.shields.io/badge/Inference-5%E2%80%937%20steps-EAB308?style=for-the-badge&labelColor=1f1f23">&nbsp;<img alt="License: CC BY-NC-ND 4.0" src="https://img.shields.io/badge/License-CC%20BY--NC--ND%204.0-2ea44f?style=for-the-badge">
</p>

</div>

> Juggernaut XI Lightning is the **speed-optimized** variant of [**Juggernaut XI v11**](https://huggingface.co/RunDiffusion/Juggernaut-XI-v11) — distilled with **SDXL Lightning** for 5–7-step inference. All of XI's improvements (sharper hands, faces, better prompt adherence, native text rendering) at ~5× the speed of standard XI.

## Inherited from XI v11

- 🎨 Massively improved aesthetics over X / earlier versions
- 🖐️ Better hands, eyes, faces, and overall human anatomy
- 🎯 Stronger prompt adherence
- 🔤 Native text rendering for signage, labels, short phrases
- 💬 Two prompting styles: Natural language *or* Tagging
- 🖼️ RunDiffusion Photo refinement

## What Lightning Adds

- ⚡ **5–7-step inference** — generate in a fraction of standard SDXL inference time
- 🔁 **Real-time iteration** — preview prompt changes in seconds
- 💻 **Lower VRAM pressure** during inference

If you need the very best per-image quality, use the [**standard XI v11**](https://huggingface.co/RunDiffusion/Juggernaut-XI-v11) instead.

---

<div align="center">

<h3>⚡ Skip the gated download. Try XI Lightning in your browser.</h3>

<p>No HF gate. No installs. No GPU rental. <b>Just generate at speed.</b></p>

<a href="https://app.rundiffusion.com/login?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_lightning&utm_content=midpage_cta"><img alt="Launch on RunDiffusion" src="https://img.shields.io/badge/%E2%96%B6%20Launch%20on%20RunDiffusion-7C3AED?style=for-the-badge&labelColor=7C3AED"></a>

<p><i>Pre-loaded into ComfyUI · Forge · Automatic1111 · Fooocus · InvokeAI · SwarmUI</i></p>

</div>

---

## Recommended Settings

> Lightning needs different settings from standard XI. Steps low, CFG very low.

| Parameter | Value |
| --- | --- |
| Sampler | `DPM++ SDE` or `DPM++ SDE Karras` |
| Steps | `5 – 7` |
| CFG scale | `1.5 – 2.0` |
| Resolution | `≥ 1024 × 1024` (use SDXL-native sizes) |
| VAE | **Already baked in** — no external VAE required |

Standard XI prompts work as-is. Just adjust the sampler, steps, and CFG.

📖 [**Prompting library**](https://www.rundiffusion.com/prompting?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_lightning&utm_content=prompting_inline) — free to read.

## The Rest of the Family

| Model | Best for |
| --- | --- |
| [**Juggernaut XI v11**](https://huggingface.co/RunDiffusion/Juggernaut-XI-v11) | Standard XI — full-step, maximum detail |
| [**Juggernaut XL v9**](https://huggingface.co/RunDiffusion/Juggernaut-XL-v9) | The flagship SDXL — **6M+ downloads** |
| [**Juggernaut XL Lightning**](https://huggingface.co/RunDiffusion/Juggernaut-XL-Lightning) | v9-base speed variant |
| [**Juggernaut Z**](https://huggingface.co/RunDiffusion/Juggernaut-Z-Image) | Lumina-Image-2 — cinematic, presentation-ready |
| [**Juggernaut Pro Flux**](https://www.rundiffusion.com/juggernaut-pro-flux?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_lightning&utm_content=cross_promo_pro_flux) | FLUX.1 — top-tier photo quality |

## License & Commercial Use

Juggernaut XI Lightning is released under **[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/)**:

- **BY** — attribute RunDiffusion / KandooAI when sharing output.
- **NC** — **non-commercial use only**. Commercial use requires a license.
- **ND** — **no derivatives**. You may not redistribute modified versions, fine-tunes, or merges.

This model **may not be deployed behind paid API services** or hosted on platforms that compete with RunDiffusion.com. For commercial licensing, contact **[juggernaut@rundiffusion.com](mailto:juggernaut@rundiffusion.com)**.

## Credits

Juggernaut XI Lightning was created by **[KandooAI](https://twitter.com/Juggernaut_AI)** in collaboration with **[RunDiffusion](https://www.rundiffusion.com/?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_lightning&utm_content=credits)**, distilled with **[SDXL Lightning](https://huggingface.co/ByteDance/SDXL-Lightning)**. Photographic backbone by the RunDiffusion Photo team.

---

<div align="center">

<h3>Ready to generate at speed?</h3>

<p>Juggernaut XI Lightning — one click away on RunDiffusion. No gate, no setup.</p>

<a href="https://app.rundiffusion.com/login?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_lightning&utm_content=footer_cta"><img alt="Try Juggernaut XI Lightning — Free" src="https://img.shields.io/badge/%E2%96%B6%20Try%20Juggernaut%20XI%20Lightning%20%E2%80%94%20Free-7C3AED?style=for-the-badge&labelColor=7C3AED"></a>

<p><sub><a href="https://www.rundiffusion.com/juggernaut?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_lightning&utm_content=footer_lineup">Compare the full Juggernaut lineup</a> · <a href="https://www.rundiffusion.com/prompting?utm_source=huggingface&utm_medium=model_card&utm_campaign=juggernaut_xi_lightning&utm_content=footer_prompting">Prompting guides</a> · <a href="mailto:juggernaut@rundiffusion.com">Commercial licensing</a></sub></p>

</div>
