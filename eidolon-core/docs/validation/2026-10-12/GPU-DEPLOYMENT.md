# GPU deployment acceptance — 2026-10-12

Core uses Gemma4 12B through a restricted loopback SSH tunnel to VM101 (192.168.1.135). Memory is served by VM110. Qwen3.5 9B remains an alternative profile; the previous CPU profile is retained.

Two downloaded candidates occupy 14,572,444,491 bytes combined. Remaining disk space after downloads was 110,379,413,504 bytes (102.80 GiB). Original models were retained; no candidate was invalidated or purged.

| Candidate | Download bytes | Observed NVIDIA VRAM at context 4096 | Warm full HTTP mean |
| --- | ---: | ---: | ---: |
| Gemma4 12B | 8,021,618,941 | 8,913 MiB | 6.61 s |
| Qwen3.5 9B | 6,550,825,550 | 6,697 MiB | 5.70 s |

Four models passed five limited qualitative API probes each. The broader isolated HTTP acceptance used fourteen cases per candidate, including absent facts, planned hardware, citations, memory outage, and a diagnostic request. Both produced thirteen answers and one clarification or proposal, without executing a mission. No unsupported claimed citation was detected. On eleven positive factual cases, Gemma cited exact source references in nine, Qwen in four. This is a small acceptance set, not a general accuracy estimate.

The final active Core HTTP smoke returned an answer in 7.8 seconds using Gemma4, five memory records, an exact supported citation, and the UNVERIFIED status. Core API and both SSH tunnels were active.

The validated source tree passed 1,460 Core tests with six skips. Private detailed transcripts and tokens remain outside Git. VM101 existing experimental installations were backed up and preserved; its role here is inference.
