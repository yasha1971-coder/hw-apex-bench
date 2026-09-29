# GPU evidence contract

GPU measurements are a separate device-resident path. They are never inferred
from CPU results and are not silently compared with a CPU codec operation.

## Current measured open-profile evidence

The current ACEAPEX GPU presentation is **measured — external runner: Colab**.
hw-apex-bench did not rerun a GPU. Source logs and the source summary table are
copied byte-for-byte from `yasha1971-coder/aceapex/results` into
`evidence/aceapex-gpu-open-20260929/source/`.

[Measured table →](RESULTS/GPU_OPEN_20260929.md)

| GPU | corpus | on-device GB/s | +H2D GB/s | check |
|---|---|---:|---:|---|
| Tesla T4 | chr1 | 12.38 | 9.79 | bit-perfect |
| NVIDIA L4 | chr1 | 25.04 | 16.31 | bit-perfect |
| NVIDIA A100-SXM4-40GB | chr1 | 41.15 | 21.91 | bit-perfect |
| NVIDIA A100-SXM4-80GB | chr1 | 41.69 | 22.06 | bit-perfect |
| RTX PRO 6000 Blackwell Server Edition | chr1 | 68.29 | 51.86 | bit-perfect |
| NVIDIA A100-SXM4-80GB | T2T-CHM13v2.0 | 60.37 | 25.66 | bit-perfect |
| RTX PRO 6000 Blackwell Server Edition | T2T-CHM13v2.0 | 118.15 | 75.02 | bit-perfect |

The retained Blackwell T2T session also measures the automatic eight-batch stream
pipeline at **94.63 GB/s delivered**.

Every row retains the source GPU identity, VRAM, compute capability, driver,
CUDA build, libzstd, nvCOMP version, ACEAPEX commit, corpus identity, archive
bytes and explicit bit-perfect verdict. The imported sessions report driver
580.82.07 and CUDA 12.8.

GPU region seek is **n/a — not measured by these imported Colab open-profile logs**.
T4, L4, A100-40GB and the first Blackwell session did not have T2T available;
no missing GPU/corpus pair is synthesized.

## Historical declared evidence

The older `gpu-results.declared.json` observations remain historical evidence only.
They were supplied without raw pod logs and are not relabelled as measured. The current
Pages/report GPU table uses the measured Colab evidence above instead.
