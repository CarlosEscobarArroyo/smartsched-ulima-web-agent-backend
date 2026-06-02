# Makefile — backend SmartSched (Cloud Run).
PROJECT  ?= ulima-agent
REGION   ?= us-east1
SERVICE  := smartsched-backend
ENV_FILE := backend.env.yaml

.PHONY: deploy migrate url logs

deploy:
	@test -f $(ENV_FILE) || { echo "Falta $(ENV_FILE): copia backend.env.yaml.example y rellenalo."; exit 1; }
	gcloud run deploy $(SERVICE) \
	  --source . \
	  --region $(REGION) --project $(PROJECT) \
	  --allow-unauthenticated \
	  --memory 1Gi --cpu 1 \
	  --env-vars-file $(ENV_FILE)

migrate:
	uv run alembic upgrade head

url:
	@gcloud run services describe $(SERVICE) --region $(REGION) --project $(PROJECT) --format='value(status.url)'

logs:
	gcloud run services logs read $(SERVICE) --region $(REGION) --project $(PROJECT)
