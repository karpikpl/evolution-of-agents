from datetime import date
from dotenv import load_dotenv
from azure.identity.aio import DefaultAzureCredential, AzureDeveloperCliCredential
import os
from semantic_kernel.agents import (
    AzureAIAgent,
    AzureAIAgentSettings,
)
from semantic_kernel.functions.kernel_plugin import KernelPlugin
from azure.ai.agents.models import (
    ToolDefinition,
)
from semantic_kernel.agents import (
    AzureAIAgentThread,
)
from azure.ai.projects.aio import AIProjectClient
from semantic_kernel.contents import FunctionCallContent, FunctionResultContent
from semantic_kernel.contents.chat_message_content import ChatMessageContent

# Load environment variables from the .env file
load_dotenv(override=True)
endpoint = os.environ.get("AZURE_AI_FOUNDRY_CONNECTION_STRING")
deployment_name = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
api_version = os.environ.get("AZURE_OPENAI_API_VERSION", None)
tenant_id = os.environ.get("AZURE_TENANT_ID", None)

ai_agent_settings = AzureAIAgentSettings(
    endpoint=endpoint,
    model_deployment_name=deployment_name,
    api_version=api_version,
)

creds = (
    AzureDeveloperCliCredential(tenant_id=os.environ.get("AZURE_TENANT_ID", None))
    if os.environ.get("USE_AZURE_DEV_CLI") == "true"
    else DefaultAzureCredential()
)


def get_credentials():
    return creds


async def get_project_client() -> AIProjectClient:
    """Get the Azure AI Agent client."""

    # uncomment to test token aquisition
    # token_test  = creds.get_token("https://ai.azure.com")
    # print(f"Token for https://ai.azure.com: {token_test.token[:10]}...")

    client = AzureAIAgent.create_client(
        credential=creds,
        endpoint=ai_agent_settings.endpoint,
        api_version=ai_agent_settings.api_version,
    )

    # List agents
    print("\n --- Agents ---")
    async for agent in client.agents.list_agents():
        print(
            f"Agent ID: {agent.id}, Name: {agent.name}, Description: {agent.description}, Deployment Name: {agent.model}"
        )

    print("\n --- Connections ---")
    # List connections
    async for connection in client.connections.list():
        print(
            f"Connection ID: {connection.id}, Name: {connection.name}, Type: {connection.type} Default: {connection.is_default}"
        )
    return client


async def create_agent(
    agent_name: str,
    agent_instructions: str,
    client: AIProjectClient,
    tools: list[ToolDefinition] = [],
    plugins: list[KernelPlugin] = [],
) -> AzureAIAgent:

    agent_definition = None
    async for agent in client.agents.list_agents():
        if agent.name == agent_name and agent_definition is None:
            agent_definition = agent
            break

    if agent_definition:
        print(
            f"Found existing agent with ID: {agent_definition.id} and name: {agent_definition.name}"
        )
        agent_definition = await client.agents.update_agent(
            agent_id=agent_definition.id,
            instructions=agent_instructions,
            model=ai_agent_settings.model_deployment_name,
            tools=tools,
            temperature=0.2,
        )
        print(
            f"Updated agent with id {agent_definition.id} name: {agent_name} with model {ai_agent_settings.model_deployment_name}"
        )
    else:
        agent_definition = await client.agents.create_agent(
            model=ai_agent_settings.model_deployment_name,
            name=agent_name,
            instructions=agent_instructions,
            tools=tools,
            temperature=0.2,
        )
        print(
            f"Created agent with id {agent_definition.id} name: {agent_name} with model {ai_agent_settings.model_deployment_name}"
        )

    agent = AzureAIAgent(
        client=client,
        definition=agent_definition,
        plugins=plugins,
    )
    return agent


async def on_intermediate_message(agent_response: ChatMessageContent):
    print(f"Intermediate response from Agent: {agent_response}")
    for item in agent_response.items or []:
        if isinstance(item, FunctionResultContent):
            print(f"Function Result:> {item.result} for function: {item.name}")
        elif isinstance(item, FunctionCallContent):
            print(f"Function Call:> {item.name} with arguments: {item.arguments}")
        else:
            print(f"{item}")


async def test_agent(
    client: AIProjectClient,
    agent: AzureAIAgent,
    user_message: str,
    thread: AzureAIAgentThread = None,
):
    try:
        thread = thread or AzureAIAgentThread(client=client)
        async for agent_response in agent.invoke(
            messages=user_message,
            thread=thread,
            additional_instructions="Today is " + date.today().strftime("%Y-%m-%d"),
            on_intermediate_message=on_intermediate_message,
        ):
            print(f"Agent: {agent_response}")
            thread = agent_response.thread
            return thread
    except Exception as e:
        print(f"Agent: {e}")
