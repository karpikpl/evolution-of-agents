from dotenv import load_dotenv
from azure.ai.inference.aio import ChatCompletionsClient
from azure.identity.aio import DefaultAzureCredential, AzureDeveloperCliCredential

import os
# Load environment variables from the .env file
load_dotenv(override=True)

creds = (
    AzureDeveloperCliCredential(tenant_id=os.environ.get("AZURE_TENANT_ID", None))
    if os.environ.get("USE_AZURE_DEV_CLI") == "true"
    else DefaultAzureCredential()
)

def get_credentials():
    return creds
