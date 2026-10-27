# G296 — Natural pronunciation experiment (operator voice reference)

The operator supplied a private 20.20-second M4A containing approximately ten
human repetitions, heard as "É-do-lon" / "È-do-lon" rather than the intended
"Eille-do-lon". **Do not commit the voice recording, derived waveforms, or voice
embeddings to this public repository.**

The new experimental recipe `eidolon-training-natural-experiment.yml` keeps
the other C199 positive spellings but replaces synthetic `Eilledolon` with
`Édolon` and `Èdolon` to investigate the shorter human-like pronunciation.
This is a *candidate*, not a phoneme-validated replacement. It requires a
Piper/espeak phonemization and audio spot-check prior to GPU training. Check
confusability with `et dolent`, `et Dolan`, and other held-out negatives.

The supplied user audio was converted offline to mono 16 kHz PCM WAV with
a SHA-256 manifest and retained only in a private conversation artifact.
**It has not been transferred to VM100 or ingested by wakeword-generator.**
The standard generator does not expose a verified, audited custom human-positive
ingestion path in the current G296 kit. Adding the actual recording into training
would require a private local input workflow and tests to prevent holdout leakage.

Avoid pretending that a single speaker's ten repetitions measure recall in a
household. A fresh separately captured human test set remains required.
No model should be activated based on this experiment. C199 v3a, using the v2
clips unchanged, remains a separate experiment for controlled comparison.
