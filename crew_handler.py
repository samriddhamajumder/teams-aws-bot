# crew_handler.py
import os
from crewai import Agent, Task, Crew, LLM
from aws_crew_tools import ec2, s3, iam, vpc
from bot import adaptive_cards
from bot.nlp_engine import nlp_engine

# Initialize the LLM (Ollama model)
os.environ.setdefault("OLLAMA_API_BASE", "http://192.168.0.177:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://192.168.0.177:11434")
aws_llm = LLM(model=OLLAMA_MODEL, base_url=OLLAMA_URL, stream=False, timeout=90)

import logging
logger = logging.getLogger(__name__)

conversation_state = None

aws_agent = Agent(
    role="AWS Cloud Assistant",
    goal="Assist users with AWS resource management based on natural language commands.",
    backstory=(
        "You are a smart AWS assistant. You understand cloud infrastructure needs and can create, manage, or recommend AWS resources using specialized tools."
    ),
    llm=aws_llm,
    tools=[
        ec2.CreateEC2Tool(), ec2.ListEC2Tool(), ec2.TerminateEC2Tool(),
        s3.CreateBucketTool(), s3.ListS3BucketsTool(),
        vpc.CreateVPCTool(), vpc.ListVPCsTool(),
        iam.CreateIAMUserTool(), iam.CreateIAMGroupTool(), iam.AttachUserToGroupTool(),
        iam.AttachPolicyTool(), iam.DetachPolicyTool(),
        iam.CreateInlinePolicyTool(), iam.CreateIAMRoleTool(),
        iam.DeleteIAMUserTool(), iam.DeleteIAMGroupTool(), iam.DeleteIAMRoleTool(),
        iam.EnableMfaTool(), iam.AuditIAMTool(),
    ],
    verbose=False
)

def process_user_message(user_message):
    global conversation_state

    def reset_state():
        global conversation_state
        conversation_state = None

    # Handle form data first
    if isinstance(user_message, dict):
        reset_state()
        return _handle_form_submission(user_message)

    message_lower = user_message.lower().strip()
    intent = nlp_engine.detect_intent(message_lower)

    # ✅ ABSOLUTE FAST PATH for list commands (never use conversation_state here)
    if message_lower.startswith("list"):
        if "instance" in message_lower or "ec2" in message_lower:
            reset_state()
            return f"🖥️ **EC2 Instances:**\n{ec2.list_instances()}"
        if "bucket" in message_lower or "s3" in message_lower:
            reset_state()
            return f"🪣 **S3 Buckets:**\n{s3.list_s3_buckets()}"
        if "user" in message_lower or "iam" in message_lower:
            reset_state()
            return f"👥 **IAM Users:**\n{iam.list_users()}"
        if "vpc" in message_lower:
            reset_state()
            return f"🌐 **VPCs:**\n{vpc.ListVPCsTool()._run()}"  # ✅ use tool
        reset_state()

    # ✅ Terminate instance
    if message_lower.startswith("terminate") or message_lower.startswith("delete"):
        if "instance" in message_lower:
            parts = message_lower.split()
            instance_id = next((word for word in parts if word.startswith("i-")), None)
            if instance_id:
                reset_state()
                return ec2.terminate_instance(instance_id=instance_id)
            return "❗ Please specify an EC2 instance ID (e.g., `terminate instance i-0abcd1234`)."

    # ✅ Check for conversation states
    if conversation_state == "awaiting_ec2_choice":
        if "card" in message_lower:
            reset_state()
            return adaptive_cards.ec2_launch_card()
        elif "default" in message_lower:
            reset_state()
            return ec2.CreateEC2Tool()._run(
                instance_type="t2.micro",
                key_name="demo-key",
                security_group_ids=[],
                subnet_id="",
                user_data="",
                ebs_volume_size=8,
                ebs_volume_type="gp2",
                enable_public_ip=True,
                instance_name="DemoInstance"
            )
        else:
            return "❓ Please reply with 'card' or 'default'."

    if conversation_state == "awaiting_s3_choice":
        if "card" in message_lower:
            reset_state()
            return adaptive_cards.s3_create_bucket_card()
        elif "default" in message_lower:
            reset_state()
            return s3.CreateBucketTool()._run(bucket_name="demo-bucket-123456")
        else:
            return "❓ Please reply with 'card' or 'default'."

    if conversation_state == "awaiting_vpc_choice":
        if "card" in message_lower:
            reset_state()
            return adaptive_cards.vpc_full_creation_card()
        elif "default" in message_lower:
            reset_state()
            return vpc.CreateVPCTool()._run(
                vpc_name="DemoVPC",
                cidr_block="10.0.0.0/16",
                region_name="us-east-1",
                enable_dns_support=True,
                enable_dns_hostnames=True,
                attach_igw=True,
                create_nat=False,
                subnet_requests=[],
                custom_tags={},
                route_table_mode="1"
            )
        else:
            return "❓ Please reply with 'card' or 'default'."

    if conversation_state == "awaiting_iam_choice":
        if "card" in message_lower:
            reset_state()
            from aws_crew_tools.iam import list_policies
            policies = list_policies()
            return adaptive_cards.iam_create_user_card(policies)
        elif "default" in message_lower:
            reset_state()
            return iam.CreateIAMUserTool()._run(
                username="my_new_user_unique",
                policies=["AmazonS3ReadOnlyAccess"],
                programmatic_access=True,
                console_access=False
            )
        else:
            return "❓ Please reply with 'card' or 'default'."

    # ✅ Trigger new conversations
    if any(kw in message_lower for kw in [
        "create ec2", "launch ec2", "spin up ec2", "new ec2", "create an ec2",
        "need ec2", "ec2 instance", "start ec2", "setup ec2", "spin up an ec2",
        "start new ec2", "deploy ec2", "provision ec2", "build ec2",
        "initiate ec2", "bring up ec2", "launch an ec2", "ec2 for test",
        "test ec2 instance", "make ec2 instance", "generate ec2", "add ec2",
        "spawn ec2", "create aws ec2", "setup aws ec2", "create amazon ec2",
        "start up ec2", "boot ec2", "run ec2"
    ]):
        conversation_state = "awaiting_ec2_choice"
        return "👉 Do you want to launch EC2 instance via **Adaptive Card** or **Default settings**? (Reply: 'card' or 'default')"

    if any(kw in message_lower for kw in [
        "create s3 bucket", "new s3 bucket", "make s3 bucket", "setup s3 bucket",
        "s3 bucket create", "launch s3 bucket", "provision s3 bucket",
        "spin up s3 bucket", "need s3 bucket", "create s3", "create bucket",
        "start s3 bucket", "generate s3 bucket", "add s3 bucket", "spawn s3 bucket",
        "create aws s3 bucket", "setup aws s3 bucket", "create amazon s3 bucket",
        "start up s3 bucket", "boot s3 bucket", "run s3 bucket"
    ]):
        conversation_state = "awaiting_s3_choice"
        return "👉 Do you want to create S3 bucket via **Adaptive Card** or **Default settings**? (Reply: 'card' or 'default')"

    if any(kw in message_lower for kw in [
        "create vpc", "new vpc", "setup vpc", "provision vpc", "launch vpc",
        "spin up vpc", "build vpc", "initiate vpc", "start vpc", "need vpc",
        "generate vpc", "add vpc", "spawn vpc", "create aws vpc", "setup aws vpc",
        "create amazon vpc", "start up vpc", "boot vpc", "run vpc"
    ]):
        conversation_state = "awaiting_vpc_choice"
        return "👉 Do you want to create VPC via **Adaptive Card** or **Default settings**? (Reply: 'card' or 'default')"

    if message_lower.strip() == "create iam user":
        conversation_state = "awaiting_iam_choice"
        return "👉 Do you want to create IAM user via **Adaptive Card** or **Default settings**? (Reply: 'card' or 'default')"

    # ✅ NLP fallback
    if intent == "instance_recommendation":
        reset_state()
        return nlp_engine.recommend_instance(message_lower)

    if intent == "knowledge_query":
        reset_state()
        return nlp_engine.knowledge_lookup(message_lower)

    # ✅ FINAL fallback → CrewAI agent
    reset_state()
    task = Task(
        description=user_message,
        agent=aws_agent,
        tools=aws_agent.tools,
        expected_output="Clear, concise AWS resource response.",
        streaming_supported=True
    )
    crew = Crew(agents=[aws_agent], tasks=[task])
    try:
        output = crew.kickoff()
        return str(output) if output else "🤔 I'm not sure how to handle that request."
    except Exception as e:
        logger.exception("❌ CrewAI task failed")
        return "❌ I faced an unexpected error while thinking. Please try again later or rephrase your request."


def _handle_form_submission(form_data):
    action = form_data.get("action", "").lower()

    if action == "create_iam_user":
        return iam.CreateIAMUserTool()._run(
            username=form_data["username"],
            policies=form_data.get("policies", "").split(","),
            programmatic_access=form_data.get("programmatic_access") == "true",
            console_access=form_data.get("console_access") == "true"
        )

    if action == "create_iam_group":
        return iam.CreateIAMGroupTool()._run(
            group_name=form_data["group_name"],
            policies=form_data.get("policies", "").split(",")
        )

    if action == "attach_user_to_group":
        return iam.AttachUserToGroupTool()._run(
            username=form_data["username"],
            group_name=form_data["group_name"]
        )

    if action == "create_inline_policy":
        return iam.CreateInlinePolicyTool()._run(
            entity_type=form_data["entity_type"],
            name=form_data["name"],
            policy_name=form_data["policy_name"],
            policy_json=form_data["policy_json"]
        )

    if action == "create_iam_role":
        return iam.CreateIAMRoleTool()._run(
            role_name=form_data["role_name"],
            trust_policy_json=form_data["trust_policy_json"],
            policies=form_data.get("policies", "").split(",")
        )

    if action == "delete_iam_user":
        return iam.DeleteIAMUserTool()._run(username=form_data["name"])

    if action == "delete_iam_group":
        return iam.DeleteIAMGroupTool()._run(group_name=form_data["name"])

    if action == "delete_iam_role":
        return iam.DeleteIAMRoleTool()._run(role_name=form_data["name"])

    if action == "enable_mfa":
        return iam.EnableMfaTool()._run(username=form_data["username"])

    if action == "audit_iam":
        return iam.AuditIAMTool()._run()

    return "⚠️ Unknown form submission received."

def fast_path(func):
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if result:
            return result
        return None
    return wrapper
