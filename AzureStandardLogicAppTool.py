import json
import requests
from typing import Dict, Any
from urllib.parse import urlparse, parse_qs

from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import (
    OpenApiTool,
    OpenApiConnectionAuthDetails,
    OpenApiConnectionSecurityScheme,
)


class AzureStandardLogicAppTool:
    """
    A service that manages multiple Logic Apps by retrieving and storing their callback URLs,
    and then invoking them with an appropriate payload.
    """

    def __init__(self, subscription_id: str, resource_group: str, credential=None):
        if credential is None:
            credential = DefaultAzureCredential()
        self.subscription_id = subscription_id
        self.resource_group = resource_group

        self.callback_urls: Dict[str, str] = {}

        # For REST API calls
        self.credential = credential
        self.base_url = f"https://management.azure.com/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}"

    def get_access_token(self) -> str:
        """
        Get an Azure AD access token for ARM API calls.
        """
        token = self.credential.get_token("https://management.azure.com/.default")
        return token.token

    def list_standard_logic_app_workflows(self, logic_app_name: str) -> Dict[str, Any]:
        """
        List workflows for a Logic App Standard using the ARM REST API.
        """
        url = f"{self.base_url}/providers/Microsoft.Web/sites/{logic_app_name}/hostruntime/runtime/webhooks/workflow/api/management/workflows?api-version=2018-11-01"
        headers = {"Authorization": f"Bearer {self.get_access_token()}"}
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def get_workflow_trigger_definition(
        self, logic_app_name: str, workflow_name: str, trigger_name: str
    ) -> Dict[str, Any]:
        """
        Get the trigger definition for a workflow in Logic App Standard.
        """
        url = f"{self.base_url}/providers/Microsoft.Web/sites/{logic_app_name}/hostruntime/runtime/webhooks/workflow/api/management/workflows/{workflow_name}/triggers/{trigger_name}/schemas/json?api-version=2024-11-01"
        headers = {"Authorization": f"Bearer {self.get_access_token()}"}
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def generate_openapi_spec_from_trigger(
        self, workflow_name: str, trigger_def: Dict[str, Any], server_url: str = None
    ) -> Dict[str, Any]:
        """
        Generate an OpenAPI spec matching the provided Logic App schema example.
        """
        # Extract properties and required fields
        properties = {}
        required = []
        for k, v in trigger_def.get("properties", {}).items():
            prop_schema = {"type": v.get("type", "string")}
            if v.get("description"):
                prop_schema["description"] = v["description"]
            properties[k] = prop_schema
            if v.get("nullable", False) is False:
                required.append(k)

        # Standard Logic App query parameters
        parameters = [
            {
                "name": "api-version",
                "in": "query",
                "description": "`2022-05-01` is the most common generally available version",
                "required": True,
                "schema": {"type": "string", "default": "2022-05-01"},
                "example": "2022-05-01",
            },
            {
                "name": "sv",
                "in": "query",
                "description": "The version number",
                "required": True,
                "schema": {"type": "string", "default": "1.0"},
                "example": "1.0",
            },
            {
                "name": "sp",
                "in": "query",
                "description": "The permissions",
                "required": True,
                "schema": {
                    "type": "string",
                    "default": "%2Ftriggers%2FWhen_a_HTTP_request_is_received%2Frun",
                },
                "example": "%2Ftriggers%2FWhen_a_HTTP_request_is_received%2Frun",
            },
        ]

        # Use /invoke as the path, as in the example
        openapi = {
            "openapi": "3.0.3",
            "info": {
                "version": "1.0.0.0",
                "title": workflow_name.replace("_", "-"),
                "description": workflow_name.replace("_", "-"),
            },
            "servers": [{"url": server_url or "https://your-logic-app-url/paths"}],
            "security": [{"sig": []}],
            "paths": {
                "/invoke": {
                    "post": {
                        "description": workflow_name.replace("_", "-"),
                        "operationId": "When_a_HTTP_request_is_received-invoke",
                        "parameters": parameters,
                        "responses": {
                            "200": {
                                "description": "The Logic App Response.",
                                "content": {
                                    "application/json": {"schema": {"type": "object"}}
                                },
                            },
                            "default": {
                                "description": "The Logic App Response.",
                                "content": {
                                    "application/json": {"schema": {"type": "object"}}
                                },
                            },
                        },
                        "deprecated": False,
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": properties,
                                        **({"required": required} if required else {}),
                                    }
                                }
                            },
                            "required": True,
                        },
                    }
                }
            },
            "components": {
                "securitySchemes": {
                    "sig": {
                        "type": "apiKey",
                        "description": "The SHA 256 hash of the entire request URI with an internal key.",
                        "name": "sig",
                        "in": "query",
                    }
                }
            },
        }
        return openapi

    def get_workflow_callback_url(
        self, logic_app_name: str, workflow_name: str, trigger_name: str
    ) -> str:
        """
        Get the callback URL for a workflow trigger in Logic App Standard.
        """
        url = f"{self.base_url}/providers/Microsoft.Web/sites/{logic_app_name}/hostruntime/runtime/webhooks/workflow/api/management/workflows/{workflow_name}/triggers/{trigger_name}/listCallbackUrl?api-version=2024-11-01"
        headers = {"Authorization": f"Bearer {self.get_access_token()}"}
        resp = requests.post(url, headers=headers)
        resp.raise_for_status()
        return resp.json().get("value", "")


class FoundryTool:
    """
    A service that manages multiple Logic Apps by retrieving and storing their callback URLs,
    and then invoking them with an appropriate payload.
    """

    def __init__(
        self,
        subscription_id: str,
        resource_group: str,
        foundry_name: str,
        project_name: str,
        credential=None,
    ):
        if credential is None:
            credential = DefaultAzureCredential()
        self.credential = credential
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.foundry_name = foundry_name
        self.project_name = project_name

    def get_access_token(self) -> str:
        """
        Get an Azure AD access token for ARM API calls.
        """
        token = self.credential.get_token("https://management.azure.com/.default")
        return token.token

    def create_custom_connection(self, connection_name: str, sig: str) -> str:
        """
        Create a custom connection in the Azure AI Projects service.
        """
        url = f"https://management.azure.com/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}/providers/Microsoft.CognitiveServices/accounts/{self.foundry_name}/projects/{self.project_name}/connections/{connection_name}?api-version=2025-04-01-preview"
        headers = {"Authorization": f"Bearer {self.get_access_token()}"}
        data = {
            "properties": {
                "authType": "CustomKeys",
                "category": "CustomKeys",
                "target": "_",
                "isSharedToAll": True,
                "credentials": {"keys": {"sig": sig}},
                "metadata": {},
            }
        }
        resp = requests.put(url, headers=headers, json=data)
        resp.raise_for_status()
        return resp.json()["id"]


def create_logic_app_tools(
    logic_app_subscription_id: str,
    logic_app_resource_group: str,
    logic_app_name: str,
    foundry_subscription_id: str,
    foundry_resource_group: str,
    foundry_foundry_name: str,
    foundry_project_name: str,
) -> list[OpenApiTool]:
    # Create the tool
    logic_app_tool = AzureStandardLogicAppTool(
        logic_app_subscription_id, logic_app_resource_group
    )

    # 1. List workflows
    workflows = logic_app_tool.list_standard_logic_app_workflows(logic_app_name)
    print("Workflows:", json.dumps(workflows, indent=2))

    # Go through all the workflows and find the first with an HTTP trigger
    if not workflows:
        print("No workflows found.")
        exit(1)

    openapi_tools: list[OpenApiTool] = []

    for wf in workflows:
        workflow_name = wf["name"]
        triggers = wf["triggers"]
        trigger_names = list(triggers.keys())
        print(f"Workflow: {workflow_name}, Triggers: {trigger_names}")
        trigger_name = None

        # find http trigger
        for trigger in triggers:
            if triggers[trigger]["kind"] == "Http":
                trigger_name = trigger
                break
        if not trigger_name:
            print("No HTTP trigger found in the workflow.")
            continue

        print(f"Trigger: {trigger_name}")

        # 3. Get trigger definition
        trigger_def = logic_app_tool.get_workflow_trigger_definition(
            logic_app_name, workflow_name, trigger_name
        )
        # print(
        #     f"Trigger definition for {workflow_name}/{trigger_name}:\n",
        #     json.dumps(trigger_def, indent=2),
        # )

        # 4. Generate OpenAPI spec
        openapi_spec = logic_app_tool.generate_openapi_spec_from_trigger(
            workflow_name, trigger_def
        )
        # print("Generated OpenAPI spec:\n", json.dumps(openapi_spec, indent=2))

        # 5. Get callback URL for the workflow trigger (for invoking)
        callback_url = logic_app_tool.get_workflow_callback_url(
            logic_app_name, workflow_name, trigger_name
        )
        # print(f"Found Callback URL for workflow '{workflow_name}'")

        # parse callback URL to get the base URL
        parsed_callback = urlparse(callback_url)
        query_params = parse_qs(parsed_callback.query)
        sig = query_params.get("sig", [None])[0]

        base_callback_url = (
            f"{parsed_callback.scheme}://{parsed_callback.netloc}{parsed_callback.path}"
        )
        # remove /invoke from path
        if base_callback_url.endswith("/invoke"):
            base_callback_url = base_callback_url[: -len("/invoke")]

        # update openapi spec server URL
        openapi_spec["servers"] = [{"url": base_callback_url}]
        connection_name = f"openapi-logicapp-{logic_app_name}-{workflow_name}"

        # there so SDK for connections - need to use REST API
        foundry_tool = FoundryTool(
            subscription_id=foundry_subscription_id,
            resource_group=foundry_resource_group,
            foundry_name=foundry_foundry_name,
            project_name=foundry_project_name,
        )
        connection_id = foundry_tool.create_custom_connection(
            connection_name=connection_name, sig=sig
        )

        auth = OpenApiConnectionAuthDetails(
            security_scheme=OpenApiConnectionSecurityScheme(
                connection_id=connection_id,
            ),
        )

        # 6. Create OpenAPI tool and invoke
        openapi_tool = OpenApiTool(
            name=workflow_name.replace("-", "_").replace(" ", "_"),
            spec=openapi_spec,
            auth=auth,
            description=f"{workflow_name} OpenAPI tool",
            # allowed_tools=[],  # Optional: specify allowed tools
        )
        openapi_tools.append(openapi_tool)

    return openapi_tools
