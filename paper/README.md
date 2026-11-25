# Report

`project_report.tex` is the project report in the course template (CS F407, four double-column pages
including references). `project_report.pdf` is the built copy.

- The numbers come from `results/ablation-quick-ollama-qwen2.5-7b/summary.json` (language-model run)
  and from `bb ablate experiments/configs/mock-synthetic.toml` (pipeline check).
- Build: `pdflatex project_report.tex` twice. The references are inline, so no BibTeX step is
  needed.
- Do not change the template's font size, margins, spacing or columns.
