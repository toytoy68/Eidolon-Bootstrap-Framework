# Limite d'inférence observée dans VM Core — 12/10/2026

Observations directes pendant la recette :
- 8 vCPU, nom exposé : QEMU Virtual CPU version 2.5+.
- Les flags visibles ne contiennent ni AVX ni AVX2.
- Ollama rapporte size_vram=0 pour gemma3:4b.
- nvidia-smi ne communique pas avec un pilote dans cette VM.
- Un prompt mémoire de 2911 tokens est traité à environ 13–15 tokens/s.

Cela explique une première échéance à 110 secondes insuffisante.
Le profil CPU expérimental utilise désormais 300 secondes et 256 tokens
de génération, contexte 4096. Ce réglage vérifie un parcours lent ; il ne
qualifie pas le modèle final ni les performances attendues avec les V100.

Le CPU physique, le type CPU exact configuré sur Proxmox et le passthrough
GPU ne sont pas audités depuis l'hyperviseur. Aucun réglage matériel,
redémarrage de VM ou changement de pilote effectué.

Qwen3 0.6B est téléchargé comme candidat CPU supplémentaire, sans activation
comme modèle de dialogue et sans qualification de sa qualité.
