# LaunchPad project-level Makefile.
# Currently scoped narrowly to dependency-locking for the Python plugin
# runtime + Layer 3 lint tools. The TS workspace uses pnpm/turbo directly
# (see CLAUDE.md "Development Commands"); this Makefile does NOT wrap those.

.PHONY: lock-deps help

PYTHON ?= python3
REQ_DIR := plugins/launchpad/scripts
REQ_IN  := $(REQ_DIR)/requirements.in
REQ_TXT := $(REQ_DIR)/requirements.txt

help: ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

lock-deps: ## Regenerate $(REQ_TXT) from $(REQ_IN) via pip-compile.
	@echo "Locking $(REQ_IN) -> $(REQ_TXT) (pip-compile --generate-hashes)..."
	@$(PYTHON) -m pip install --quiet pip-tools
	@$(PYTHON) -m piptools compile --generate-hashes --resolver=backtracking \
		--output-file=$(REQ_TXT).tmp $(REQ_IN)
	@# Preserve the curated header (lines until the first blank line of the .txt
	@# match the v2.1.1 R1-T1-16 supply-chain framing). Keep the existing header,
	@# replace only the auto-generated body.
	@awk '/^$$/{found=1} !found' $(REQ_TXT) > $(REQ_TXT).header
	@tail -n +7 $(REQ_TXT).tmp > $(REQ_TXT).body
	@cat $(REQ_TXT).header > $(REQ_TXT)
	@echo "" >> $(REQ_TXT)
	@cat $(REQ_TXT).body >> $(REQ_TXT)
	@rm -f $(REQ_TXT).tmp $(REQ_TXT).header $(REQ_TXT).body
	@echo "Done. Review the diff and commit $(REQ_IN) + $(REQ_TXT) together."
