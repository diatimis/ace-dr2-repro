# ACE Cosmology: MCMC Analysis Pipeline

**Companion code repository for:**

> Nikoo Eslami, *An H² Tracking Vacuum Sector from Causal Coarse Graining*  
> Preprint DOI: 10.5281/zenodo.16938680  
> ORCID: 0009-0007-7399-9301

---

## Overview

This repository contains the YAML configuration files, chain outputs, and diagnostic scripts used to produce the MCMC results, tables, and figures in the paper.

The ACE (Adaptive Cosmological Evolution) model implements the H² tracker relation

```
rho_Lambda = alpha_DE * M_Pl^2 * H^2
```

with the CPL ridge constraint `w_a = -q(1 + w_0)` reducing the effective parameter count to a single observable `w_0`.

---

## What is included and what is not

Included in this repository:
- Cobaya YAML configurations for all runs
- Cobaya outputs for each run (chains, covmat, progress, checkpoint, and related files)
- Diagnostic scripts used for tables and checks (for example `qfit_dr2_global.py`, `get_neff.py`)
- Figure generation script used in the paper (`generate_fig4_fig5_from_chains.py`)
- Shell diagnostic helpers (`.bash_aliases`)

Not included in this repository:
- CLASS source code and builds
- External likelihood packages and data (Planck 2018 clik, PantheonPlus, DESI DR2 BAO, SH0ES, etc.)

To support reproducibility, an environment snapshot is provided under:
- `tools/env/`

This snapshot records Python version, Cobaya version, pip freeze, Cobaya CLI path, Cobaya config location, and a deterministic CLASS source fingerprint (SHA256 of key files) when CLASS is present as a source tree but not a git checkout.

---

## Dependencies

Core requirements:
- Cobaya (MCMC sampler)
- CLASS (Boltzmann solver), typically used by Cobaya as an external code under a Cobaya `packages_path`

Python:
- Python 3.8+ (the original environment used for the paper is captured in `tools/env/`)
- NumPy, pandas (see `tools/env/pip-freeze.txt`)

Utilities:
- gawk (GNU awk), required for `check_ace`
- MPI runtime (for example OpenMPI) if launching multiple chains with `mpirun -n 4`

Likelihood data (external, not shipped here):
- Planck 2018 likelihoods (via clik)
- PantheonPlus likelihood
- DESI DR2 BAO likelihood
- SH0ES likelihood (for tension suite runs)

Important note on `classy`: some environments install the Python module `classy` for CLASS. In the environment used here, CLASS is recorded as a source directory under a Cobaya packages path and `import classy` may not work standalone. This does not prevent Cobaya from running CLASS from source.

---

## Repository Structure

Each run is a self-contained folder. Every folder contains:

```
<run_prefix>/
├── <run_prefix>.yaml            # Input config used to launch the run
├── <run_prefix>.input.yaml      # Cobaya-recorded input at run time
├── <run_prefix>.updated.yaml    # Cobaya-updated yaml after run
├── <run_prefix>.1.txt           # Chain 1 (post-burn samples)
├── <run_prefix>.2.txt           # Chain 2
├── <run_prefix>.3.txt           # Chain 3
├── <run_prefix>.4.txt           # Chain 4
├── <run_prefix>.checkpoint      # Cobaya checkpoint (resume state)
├── <run_prefix>.covmat          # Proposal covariance matrix
├── <run_prefix>.paramnames      # Parameter names file (most runs)
└── <run_prefix>.progress        # Sampler progress log
```

**Note:** `ace_global_fixed_q3_desiDR2` additionally contains `.A.txt` and `.B.txt` sub-chains from a resumed run.

### Additional scripts (inside specific run folders)

| File | Location | Purpose |
|---|---|---|
| `qfit_dr2_global.py` | `ace_cpl_global_diag_desiDR2/` | CPL ridge slope fit for the DR2 global free-CPL diagnostic |
| `get_neff.py` | `lcdm_shoes_baseline_desiDR2/` | Computes effective number of data points Neff for BIC calculation |

---

## Run Map (Table 3 of paper)

| Run ID | Folder / Chain prefix | Suite | Command |
|---|---|---|---|
| Run 0 DR2 | `lcdm_baseline_desiDR2` | Global | `check_lcdm_dr2` |
| Run 4 DR2 | `ace_cpl_global_diag_desiDR2` | Global | `check_desi` |
| Run 1 DR2 | `ace_global_desiDR2` | Global | `check_ace_global_dr2` |
| Run 1b DR2 | `ace_global_fixed_desiDR2` | Global | `check_ace_fixed_dr2` |
| Run 1bC DR2 | `ace_global_curved_fixed_desiDR2` | Global | `check_ace_curved_fixed_dr2` |
| Run 1b q=3 DR2 | `ace_global_fixed_q3_desiDR2` | Global | `check_ace_fixed_q3_dr2` |
| Run 0S DR2 | `lcdm_shoes_baseline_desiDR2` | Tension | `check_lcdm_shoes_baseline_dr2` |
| Run 2 DR2 | `ace_shoes_diag_desiDR2` | Tension | `check_shoes_diag_dr2` |
| Run 3 DR2 | `ace_shoes_constrained_desiDR2` | Tension | `check_ace_shoes_constrained_dr2` |
| Run 3b DR2 | `ace_shoes_fixed_desiDR2` | Tension | `check_ace_shoes_fixed_dr2` |
| Run 3bC DR2 | `ace_shoes_curved_fixed_desiDR2` | Tension | `check_ace_shoes_curved_fixed_dr2` |
| Run 3c DR2 | `ace_shoes_strong_fixed_desiDR2` | Tension | `check_ace_shoes_strong_fixed_dr2` |
| Run 3cC DR2 | `ace_shoes_strong_curved_fixed_desiDR2` | Tension | `check_ace_shoes_strong_curved_fixed_dr2` |

---

## Environment Activation

The original workflow uses a Python venv activated via:

```bash
source ~/cobaya_env/bin/activate
```

The exact environment fingerprint used to generate the paper results is saved under `tools/env/`.

---

## Running a Chain

Chains are launched with 4 MPI processes from inside the run folder. The number of chains is passed at runtime. For example:

```bash
cd lcdm_shoes_baseline_desiDR2
mpirun -n 4 cobaya-run lcdm_shoes_baseline_desiDR2.yaml -f
```

The `-f` flag forces a fresh run, overwriting any existing output. Replace the folder name and YAML filename with any run in this repository.

---

## Figure Reproduction

Figures 4 and 5 in the paper are generated from the chains using:

```bash
python3 generate_fig4_fig5_from_chains.py \
  --tracker-dir ~/ace_global_fixed_desiDR2 \
  --lcdm-dir ~/lcdm_baseline_desiDR2 \
  --output-dir ~/paper_plots
```

---

## Bash Aliases (Diagnostics)

This workflow relies on helper aliases and functions in the provided `.bash_aliases` to summarize runs.

1) Copy the provided `.bash_aliases` into your home directory (or merge with your existing one):

```bash
cp .bash_aliases ~/.bash_aliases
```

2) Load it in your current shell:

```bash
source ~/.bash_aliases
```

3) Ensure your shell loads it automatically in future sessions (typically in `~/.bashrc`):

```bash
# in ~/.bashrc
[ -f ~/.bash_aliases ] && . ~/.bash_aliases
```

---

### `check_here` — Universal command

`check_here` is the general-purpose diagnostic. Run it from inside any chain folder:

```bash
cd ace_global_fixed_desiDR2
check_here
```

It auto-detects the chain prefix from `.txt` files in the current directory, applies a 30% burn-in by default, and outputs:

- Per-chain file listing with raw and post-burn sample counts
- Best-fit point (minimum χ²) with all common parameters
- Component χ² contributions (BAO, CMB, SN, SH0ES where present)
- Weighted posterior summary (median and 68% CL) for H0, w0, wa, q_ace, q_eff

**Optional arguments:**

```bash
check_here                                      # auto-detect prefix, burn = 0.30
check_here 0.20                                 # custom burn fraction
check_here ace_global_fixed_desiDR2             # explicit prefix
check_here ace_global_fixed_desiDR2 0.25        # explicit prefix and burn
```

---

### `check_ace` — gawk-based diagnostic

`check_ace` is a fast gawk-based alternative. Run from inside a chain folder with an optional file pattern:

```bash
cd ace_cpl_global_diag_desiDR2
check_ace
check_ace "ace_cpl_global_diag_desiDR2.*.txt"
```

Outputs best-fit χ², posterior medians, weighted ridge slope fit `q_ridge_fit`, and weighted correlation `corr(w0, wa)`.

---

### Per-run aliases

Each run has a dedicated alias that reads from its specific folder prefix and applies the correct burn-in and parameter set. These reproduce the exact values in Tables 1 and 2 of the paper. Run each alias from the corresponding chain folder:

```bash
cd lcdm_baseline_desiDR2 && check_lcdm_dr2
cd ace_global_fixed_desiDR2 && check_ace_fixed_dr2
cd lcdm_shoes_baseline_desiDR2 && check_lcdm_shoes_baseline_dr2
```

See the run map above for the full list.

---

## Sampler Settings

All runs use the following Cobaya MCMC settings unless otherwise specified in the individual YAML:

| Setting | Value |
|---|---|
| Sampler | `mcmc` |
| Chains per run | 4 (passed via `mpirun -n 4`) |
| `drag` | enabled |
| `oversample_power` | 0.4 |
| `proposal_scale` | 1.4 |
| `Rminus1_stop` | 0.03 |
| `max_tries` | 5000 |
| Burn-in fraction | 0.30 |

---

## Key Results

| Comparison | Δχ² | ΔAIC | ΔBIC |
|---|---|---|---|
| Run 1b DR2 vs Run 0 DR2 (Global) | −6.07 | −4.07 | +1.71 |
| Run 3b DR2 vs Run 0S DR2 (Tension) | −2.22 | −0.22 | +5.56 |

BIC uses conservative Neff = 2393. See Section 7.3 of the paper for full discussion.

---

## Packaging for GitHub Release

A helper script can stage a minimal, publishable subset of runs and tools for upload. Example:

```bash
python3 package_github_upload.py \
  --base "$HOME" \
  --out "$HOME/ace_repo_staging" \
  --runs ace_global_fixed_desiDR2 lcdm_baseline_desiDR2 \
  --force --zip --env-snapshot \
  --venv-activate ~/cobaya_env/bin/activate
```

To stage all runs, either pass a full list to `--runs`, or use `--auto-detect-runs` (only detects run folders directly under `--base`).

---

## License

CC BY 4.0 — see [LICENSE](LICENSE)

---

## Citation

```bibtex
@misc{eslami2026ace,
  author       = {Nikoo Eslami},
  title        = {An H² Tracking Vacuum Sector from Causal Coarse Graining},
  year         = {2026},
  doi          = {10.5281/zenodo.16938680},
  orcid        = {0009-0007-7399-9301}
}
```
