#!/bin/bash
# Deploy FastAPI backend to Cloud Run (us-east1)

set -e

PROJECT_ID="${GCP_PROJECT_ID:-clawdbot-config}"
SERVICE_NAME="clawdbot-api"
REGION="us-east1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "Building Docker image..."
gcloud builds submit --tag "${IMAGE_NAME}" --project "${PROJECT_ID}"

echo "Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_NAME}" \
  --platform managed \
  --region "${REGION}" \
  --allow-unauthenticated \
  --memory 256Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --timeout 300 \
  --set-env-vars "API_KEY=${API_KEY},POLYCLAW_AGENT_API_KEY=${POLYCLAW_AGENT_API_KEY}" \
  --project "${PROJECT_ID}"

echo "Deployment complete!"
echo "Service URL: $(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)' --project ${PROJECT_ID})"
