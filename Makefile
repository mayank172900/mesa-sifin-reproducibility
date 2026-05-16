PYTHON ?= python3
JOBS ?= 8
LOBSTER_DEPTH_LEVELS ?= 10
BINANCE_DATES ?= 2024-01-15 2024-04-15 2024-07-15
M_SERIES_WORKERS ?= 16
PYTHONPATH := src

export PYTHONPATH
export VECLIB_MAXIMUM_THREADS ?= 1
export OMP_NUM_THREADS ?= 1
export OPENBLAS_NUM_THREADS ?= 1
export NUMEXPR_NUM_THREADS ?= 1

.PHONY: install test quick full data hawkes hawkes-size replay deepest-replay reconstruct benchmark siam-source paper validate bundle reproduce full-reproduce

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest -q

quick:
	$(PYTHON) scripts/run_all.py --quick --jobs $(JOBS)

full:
	$(PYTHON) scripts/run_all.py --jobs $(JOBS)

data:
	$(PYTHON) scripts/fetch_lobster_sample.py --ticker AAPL --levels 1
	$(PYTHON) scripts/fetch_lobster_sample.py --ticker AMZN --levels 1
	$(PYTHON) scripts/fetch_lobster_sample.py --ticker GOOG --levels 1
	$(PYTHON) scripts/fetch_lobster_sample.py --ticker INTC --levels 1
	$(PYTHON) scripts/fetch_lobster_sample.py --ticker MSFT --levels 1
	$(PYTHON) scripts/fetch_lobster_sample.py --ticker AAPL --levels $(LOBSTER_DEPTH_LEVELS)
	$(PYTHON) scripts/fetch_lobster_sample.py --ticker AMZN --levels $(LOBSTER_DEPTH_LEVELS)
	$(PYTHON) scripts/fetch_lobster_sample.py --ticker GOOG --levels $(LOBSTER_DEPTH_LEVELS)
	$(PYTHON) scripts/fetch_lobster_sample.py --ticker INTC --levels $(LOBSTER_DEPTH_LEVELS)
	$(PYTHON) scripts/fetch_lobster_sample.py --ticker MSFT --levels $(LOBSTER_DEPTH_LEVELS)
	$(PYTHON) scripts/fetch_crypto_depth.py --symbols BTC ETH SOL
	$(PYTHON) scripts/fetch_binance_aggtrades.py --symbols BTCUSDT ETHUSDT SOLUSDT --dates $(BINANCE_DATES)

hawkes:
	$(PYTHON) scripts/fit_lobster_hawkes.py --skip-panel --validate-estimator
	$(PYTHON) scripts/fit_lobster_hawkes.py --skip-panel --diagnostic-max-events 30000 --diagnostics
	$(PYTHON) scripts/fit_binance_hawkes.py --symbols BTCUSDT ETHUSDT SOLUSDT --dates $(BINANCE_DATES) --max-events 60000

hawkes-size:
	$(PYTHON) scripts/fit_lobster_hawkes.py --skip-panel --diagnostic-max-events 15000 --diagnostics --size-side-robustness

replay:
	$(PYTHON) scripts/replay_lobster_top_of_book.py --mode both --levels 1 --max-events 80000
	$(PYTHON) scripts/replay_lobster_top_of_book.py --mode depth-quote --levels $(LOBSTER_DEPTH_LEVELS) --max-events 80000
	$(PYTHON) scripts/replay_lobster_top_of_book.py --mode depth-priority --levels $(LOBSTER_DEPTH_LEVELS) --max-events 80000
	$(PYTHON) scripts/replay_lobster_top_of_book.py --mode depth-priority-sensitivity --levels $(LOBSTER_DEPTH_LEVELS) --max-events 80000

deepest-replay:
	$(PYTHON) scripts/fetch_lobster_sample.py --ticker AAPL --levels 50
	$(PYTHON) scripts/fetch_lobster_sample.py --ticker MSFT --levels 50
	$(PYTHON) scripts/replay_lobster_deepest_public.py --levels 50 --max-events 200000

reconstruct:
	$(PYTHON) scripts/audit_lobster_orderbook_reconstruction.py --levels $(LOBSTER_DEPTH_LEVELS) --max-events 80000 --compare-every 10 --reanchor-every-events 100

benchmark:
	$(PYTHON) scripts/benchmark_m_series.py --max-workers $(M_SERIES_WORKERS)

siam-source:
	$(PYTHON) scripts/build_siam_source.py

paper: siam-source
	@if command -v tectonic >/dev/null 2>&1; then \
		tectonic --keep-logs --outdir paper paper/mesa_sifin_manuscript.tex; \
		tectonic --keep-logs --outdir paper paper/mesa_scalar_theory_appendix.tex; \
		tectonic --keep-logs --outdir paper paper/siam_jfm_cover_letter.tex; \
	elif command -v pdflatex >/dev/null 2>&1; then \
		pdflatex -interaction=nonstopmode -halt-on-error -output-directory=paper paper/mesa_sifin_manuscript.tex; \
		pdflatex -interaction=nonstopmode -halt-on-error -output-directory=paper paper/mesa_scalar_theory_appendix.tex; \
		pdflatex -interaction=nonstopmode -halt-on-error -output-directory=paper paper/siam_jfm_cover_letter.tex; \
	else \
		echo "Install tectonic or pdflatex, or use the Codex latex-to-pdf helper documented in README_REPRODUCE.md"; \
		exit 1; \
	fi

validate:
	$(PYTHON) scripts/validate_submission_package.py --strict

bundle: validate
	$(PYTHON) scripts/build_submission_bundle.py

reproduce: test data quick hawkes replay reconstruct benchmark paper validate

full-reproduce: test data full hawkes replay deepest-replay reconstruct benchmark paper validate
