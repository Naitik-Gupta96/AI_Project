# Paper

`main.tex` is the report skeleton.
- **Already written:** the protocol, architecture and counterfactual sections, which describe
  the implementation.
- **Filled in from the runs:** the results.

1. Run the ablation on the GPU machine ([../scripts/gpu_runbook.md](../scripts/gpu_runbook.md)).
2. `bb report runs/experiments/ablation-qwen2.5-7b`
3. Copy that run's `figures/` and `tables/` into this directory.
4. Build: `latexmk -pdf main.tex`. Until step 3 is done, missing results show up as a boxed note.

`references.bib` gives the full author list for every entry, from each paper's arXiv page.
