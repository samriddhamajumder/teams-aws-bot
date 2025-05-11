# crew_handler.py
# Orchestrates request handling using CrewAI agents and direct boto3 calls.
# Decides when to prompt the user for more info via Adaptive Cards vs. executing an AWS operation.
from crewai import Agent, Task, Crew, LLM
from aws_crew_tools import ec2, s3, iam, vpc  # import our AWS boto3 modules
from bot import adaptive_cards

# Initialize the CrewAI LLM to use the local Ollama LLaMA3 model.
# The model and endpoint are read from environment variables (or default values).
import os
os.environ.setdefault("OLLAMA_API_BASE", "http://192.168.0.177:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "ollama/llama3:7b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://192.168.0.177:11434")
aws_llm = LLM(model=OLLAMA_MODEL, base_url=OLLAMA_URL)

# Define a single agent that can handle AWS requests using provided tools.
aws_agent = Agent(
    role="AWS Assistant",
    goal="Help the user manage AWS resources via natural language commands",
    backstory=("You are an AWS assistant agent. You can create and manage cloud resources (EC2 instances, S3 buckets, IAM users, VPCs) "
               "on behalf of the user. You have access to tools that perform AWS actions. Use them as needed to fulfill the user's request."),
    llm=aws_llm,
    # Assign the AWS action tools to this agent (the agent can choose among these when reasoning).
    tools=[
        ec2.CreateEC2Tool(), ec2.ListEC2Tool(), ec2.TerminateEC2Tool(),
        s3.CreateBucketTool(), s3.ListS3BucketsTool(),
        vpc.CreateVPCTool(), vpc.ListVPCsTool(),
        # IAM (Full Set)
        iam.CreateIAMUserTool(),
        iam.CreateIAMGroupTool(),
        iam.AttachUserToGroupTool(),
        iam.AttachPolicyTool(),
        iam.DetachPolicyTool(),
        iam.CreateInlinePolicyTool(),
        iam.CreateIAMRoleTool(),
        iam.DeleteIAMUserTool(),
        iam.DeleteIAMGroupTool(),
        iam.DeleteIAMRoleTool(),
        iam.EnableMfaTool(),
        iam.AuditIAMTool(),
    ],
    verbose=False  # set True to debug agent reasoning if needed
)

def process_user_message(user_message: str):
    """
    Process a user's message and determine an appropriate response.
    - If additional input is required, return an Adaptive Card (as dict) to collect info.
    - If it is a straightforward request, perform it directly or via CrewAI and return the result.
    """
    message_lower = user_message.lower()

    # 1. Check if the message is a known simple command that requires more info via Adaptive Card.
    if any(kw in message_lower for kw in ["create ec2", "launch ec2", "launch instance", "new ec2", "spin up ec2"]):
        return adaptive_cards.ec2_launch_card()
    if "create bucket" in message_lower or "create s3" in message_lower:
        return adaptive_cards.s3_create_bucket_card()
    if "create user" in message_lower or "new user" in message_lower:
        return adaptive_cards.iam_user_creation_card()
    if any(kw in message_lower for kw in ["create vpc", "new vpc", "provision vpc", "build vpc", "setup vpc"]):
        return adaptive_cards.vpc_full_creation_card()

    # 2. Check for direct simple queries/commands that we can handle with a single boto3 call (no LLM needed).
    if message_lower.startswith("list"):
        # List resources command
        if "instances" in message_lower or "ec2" in message_lower:
            # List EC2 instances
            result = ec2.list_instances()
            return f"**EC2 Instances:**\n{result}"
        if "buckets" in message_lower or "s3" in message_lower:
            result = s3.list_s3_buckets()
            return f"**S3 Buckets:**\n{result}"
        if "users" in message_lower or "iam" in message_lower:
            result = iam.list_users()
            return f"**IAM Users:**\n{result}"
        if "vpcs" in message_lower or "vpc" in message_lower:
            result = vpc.list_vpcs()
            return f"**VPCs:**\n{result}"
    if message_lower.startswith("terminate") or message_lower.startswith("delete"):
        # Terminate an EC2 instance or delete other resource (requires an identifier).
        # For simplicity, handle EC2 instance termination; other deletions can be added similarly.
        if "instance" in message_lower:
            # Expect an instance ID in the message (e.g., "terminate instance i-123abc")
            parts = user_message.split()
            # Find something that looks like an instance ID (starts with i-)
            instance_id = None
            for token in parts:
                if token.startswith("i-"):
                    instance_id = token
                    break
            if instance_id:
                result = ec2.terminate_instance(instance_id=instance_id)
                return f"**EC2 Instance Termination:** {result}"
            else:
                return "Please specify the EC2 instance ID to terminate (e.g., 'terminate instance i-xxxxxx')."
            
        # IAM Adaptive Card Fallbacks (submissions)
    if isinstance(user_message, dict):
        action = user_message.get("action", "").lower()

        if action == "create_iam_user":
            return iam.CreateIAMUserTool()._run(
                username=user_message["username"],
                policies=user_message.get("policies", "").split(","),
                programmatic_access=user_message.get("programmatic_access") == "true",
                console_access=user_message.get("console_access") == "true"
            )

        if action == "create_iam_group":
            return iam.CreateIAMGroupTool()._run(
                group_name=user_message["group_name"],
                policies=user_message.get("policies", "").split(",")
            )

        if action == "attach_user_to_group":
            return iam.AttachUserToGroupTool()._run(
                username=user_message["username"],
                group_name=user_message["group_name"]
            )

        if action == "attach_policy":
            return iam.AttachPolicyTool()._run(
                entity_type=user_message["entity_type"],
                name=user_message["name"],
                policy_name=user_message["policy_name"]
            )

        if action == "detach_policy":
            return iam.DetachPolicyTool()._run(
                entity_type=user_message["entity_type"],
                name=user_message["name"],
                policy_name=user_message["policy_name"]
            )

        if action == "create_inline_policy":
            return iam.CreateInlinePolicyTool()._run(
                entity_type=user_message["entity_type"],
                name=user_message["name"],
                policy_name=user_message["policy_name"],
                policy_json=user_message["policy_json"]
            )

        if action == "create_iam_role":
            return iam.CreateIAMRoleTool()._run(
                role_name=user_message["role_name"],
                trust_policy_json=user_message["trust_policy_json"],
                policies=user_message.get("policies", "").split(",")
            )

        if action == "delete_iam_user":
            return iam.DeleteIAMUserTool()._run(username=user_message["name"])

        if action == "delete_iam_group":
            return iam.DeleteIAMGroupTool()._run(group_name=user_message["name"])

        if action == "delete_iam_role":
            return iam.DeleteIAMRoleTool()._run(role_name=user_message["name"])

        if action == "enable_mfa":
            return iam.EnableMfaTool()._run(username=user_message["username"])

        if action == "audit_iam":
            return iam.AuditIAMTool()._run()


    # 3. If not handled above, use the CrewAI agent to interpret and fulfill the request.
    # We create a single Task for the agent with the user's message as the goal/description.
    task = Task(
        description=user_message,
        agent=aws_agent,
        tools=aws_agent.tools,
        expected_output="A concise result or answer for the user's request."
    )
    crew = Crew(agents=[aws_agent], tasks=[task])
    # Run the crew to let the agent process the request.
    try:
        output = crew.kickoff()
    except Exception as e:
        return f"Sorry, I couldn't complete the request due to an error: {e}"
    
    if "created" in str(output).lower() and "instance" in str(output).lower():
    # Could be hallucinated — double-check if Adaptive Card wasn't triggered
        return "Please use the EC2 creation form so I can collect instance details."


    # The output from crew.kickoff() is expected to be the final answer from the agent (string).
    if output:
        return str(output)
    else:
        return "I'm not sure how to handle that request."
    
    
