.PHONY: run run-app stop model eval test

MODEL_FILE := models/apertus-v1.5-8b-text-q4_k_m.gguf
MODEL_URL  ?= https://huggingface.co/Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF/resolve/main/apertus-v1.5-8b-text-q4_k_m.gguf

# Start Riserbo and the Apertus model server in Docker, then open http://localhost:8080
# The model (~5 GB) is downloaded once; after that nothing needs the internet.
run: model
	docker compose up --build -d
	@echo "Riserbo is starting on http://localhost:$${RISERBO_PORT:-8080} (the model needs ~1-3 minutes to load on CPU)"
	docker compose logs -f app

# Only the app, against an OpenAI-compatible endpoint you already run (e.g. LM Studio, vLLM):
#   LLM_BASE_URL=http://host.docker.internal:1234/v1 make run-app
run-app:
	docker compose up --build --no-deps app

stop:
	docker compose down

model: $(MODEL_FILE)

$(MODEL_FILE):
	mkdir -p models
	curl -L --fail --retry 5 -C - -o $@.part "$(MODEL_URL)"
	mv $@.part $@

# Reproduce the evaluation table (uses the running model server).
eval:
	docker compose run --rm -v "$(CURDIR)/data/eval:/app/data/eval" app python -m riserbo.eval.run

test:
	docker compose run --rm --no-deps app python -m pytest -q
