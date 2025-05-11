import os
import base64
import logging
import re
import requests
import spacy
from botbuilder.core import TurnContext, MessageFactory
from botbuilder.schema import Attachment
from botbuilder.core.teams import TeamsActivityHandler
from crew_handler import process_user_message
from bot import adaptive_cards
from botbuilder.schema import Activity
from aws_crew_tools import iam
import pyotp
import qrcode
import io
from aws_crew_tools.ec2 import create_instance, list_instance_profiles
from aws_crew_tools.vpc import create_vpc_advanced
from botbuilder.schema.teams import TaskModuleRequest
from botbuilder.schema.teams import TaskModuleContinueResponse, TaskModuleTaskInfo, TaskModuleResponse
from bot.adaptive_cards import (
    s3_create_bucket_card,
    s3_upload_file_card,
    s3_download_file_card,
    s3_select_object_card  # ✅ newly added
)
from aws_crew_tools.s3 import (
    create_s3_bucket,
    list_s3_buckets,
    list_s3_objects,  # ✅ add this
    upload_file_to_s3,
    generate_presigned_download_url
)

from bot.adaptive_cards import (
    iam_create_user_card,
    iam_create_group_card,
    iam_attach_user_group_card,
    iam_attach_detach_policy_card,
    iam_inline_policy_card,
    iam_create_role_card,
    iam_delete_card,
    iam_enable_mfa_card_step1,
    iam_enable_mfa_card_step2,
    iam_audit_card,
)
from aws_crew_tools.iam import (
    list_iam_users_and_groups
)



user_upload_context = {}

BASE_URL = os.getenv("BASE_URL", "http://localhost:3978")

# Configure logging
logging.basicConfig(filename='bot.log',
                    format='%(asctime)s %(levelname)s:%(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Load NLP
try:
    nlp = spacy.load("en_core_web_sm")
except Exception:
    import spacy.cli
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

# Intent matchers
launch_triggers = [
    "create an instance", "launch ec2", "new ec2", "create ec2",
    "spin up server", "start a vm", "make ec2", "build instance", "i want instance"
]

greeting_triggers = ["hi", "hello", "hey", "yo", "how are you"]
vpc_triggers = ["create vpc", "launch vpc", "build vpc", "new vpc"]



def is_intent_match(user_input: str, trigger_list: list, threshold=80) -> bool:
    from fuzzywuzzy import fuzz
    user_input = user_input.lower()
    return any(fuzz.partial_ratio(user_input, phrase) >= threshold for phrase in trigger_list)

def parse_bool(val: str) -> bool:
    return val.strip().lower() == "true" if isinstance(val, str) else False

def generate_subnet_requests(data):
    public_count = int(data.get("public_subnet_count", 0))
    private_count = int(data.get("private_subnet_count", 0))
    subnet_requests = []

    for i in range(1, public_count + 1):
        key = f"public_{i}_hosts"
        hosts = int(data.get(key, 0))
        if hosts > 0:
            subnet_requests.append({"type": "public", "hosts": hosts})

    for i in range(1, private_count + 1):
        key = f"private_{i}_hosts"
        hosts = int(data.get(key, 0))
        if hosts > 0:
            subnet_requests.append({"type": "private", "hosts": hosts})

    return subnet_requests

class TeamsBot(TeamsActivityHandler):

    async def on_message_activity(self, turn_context: TurnContext):
        activity = turn_context.activity
        if activity.attachments and activity.attachments[0].content_type.startswith("application/"):
          user_id = turn_context.activity.from_property.id
          if user_id not in user_upload_context:
            await turn_context.send_activity("❌ No pending upload configuration found. Please fill the upload form first.")
            return

          upload_cfg = user_upload_context.pop(user_id)
          file = activity.attachments[0]
          file_name = file.name
          file_bytes = await turn_context.adapter.download_attachment(file, turn_context)

          success, message = upload_file_to_s3(
            upload_cfg["bucket_name"],
            file_bytes,
            file_name,
            upload_cfg["prefix"],
            upload_cfg["acl"],
            upload_cfg["storage_class"]
        )

          if success:
            key = f"{upload_cfg['prefix']}{file_name}" if upload_cfg["prefix"] else file_name
            card = adaptive_cards.s3_upload_success_card(upload_cfg["bucket_name"], key, upload_cfg["acl"], upload_cfg["storage_class"])
            await turn_context.send_activity(
                MessageFactory.attachment(
                    Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)
                )
            )
          else:
            await turn_context.send_activity(message)
          return

        if activity.value:
            data = activity.value
            action = data.get("action")

            if action == "create_ec2":
                await self._handle_ec2_creation(data, turn_context)
                return
            if action == "create_vpc":
                await self._handle_vpc_creation(data, turn_context)
                return
                        # 🔐 IAM Card Submissions Routing
            if action == "create_iam_user":
                await self._handle_iam_user_creation(data, turn_context)
                return

            if action == "create_iam_group":
                await self._handle_iam_group_creation(data, turn_context)
                return

            if action == "attach_user_to_group":
                await self._handle_attach_user_to_group(data, turn_context)
                return
            if action == "delete_iam_user":
                await self._handle_iam_deletion(data, turn_context)
                return
            if action in ["enable_mfa", "mfa_start"]:
                await self._handle_mfa_enabling(data, turn_context)
                return
            if action == "mfa_finish":
                 await self._handle_mfa_enabling(data, turn_context)
                 return
            if action == "audit_iam":
                await self._handle_iam_audit(data, turn_context)
                return

            if action == "create_iam_role":
                await self._handle_iam_role_creation(data, turn_context)
                return

            if action == "create_inline_policy":
                await self._handle_inline_policy_creation(data, turn_context)
                return
            
            submit_action = data.get("submit_action")

            if submit_action == "iam_policy_action":
                user_name = data.get("user_name")
                group_name = data.get("group_name")
                policy_name = data.get("policy_name")
                action = data.get("action")

                if not policy_name or not action:
                  await turn_context.send_activity("❌ Please select policy and action.")
                  return

                if not user_name and not group_name:
                  await turn_context.send_activity("❌ Please select at least a user or group.")
                  return

                if user_name:
                  if action == "attach":
                      await self._handle_attach_policy({"entity_type": "user", "name": user_name, "policy_name": policy_name}, turn_context)
                  else:
                      await self._handle_detach_policy({"entity_type": "user", "name": user_name, "policy_name": policy_name}, turn_context)

                if group_name:
                  if action == "attach":
                    await self._handle_attach_policy({"entity_type": "group", "name": group_name, "policy_name": policy_name}, turn_context)
                  else:
                    await self._handle_detach_policy({"entity_type": "group", "name": group_name, "policy_name": policy_name}, turn_context)

                return



            if action == "create_s3_bucket":
                await self._handle_s3_bucket_creation(data, turn_context)
                return

            elif action == "open_upload_module":
                task_info = TaskModuleTaskInfo(
                    title="Upload File to S3",
                    height="medium",
                    width="medium",
                    url=f"{BASE_URL}/upload",
                    fallback_url=f"{BASE_URL}/upload"
            )
                continue_response = TaskModuleContinueResponse(value=task_info)
                invoke_response = TaskModuleResponse(task=continue_response)

                await turn_context.send_activity(
                    Activity(type="invokeResponse", value=invoke_response)
            )
                return


            elif action == "generate_download_link":
                    await self._handle_s3_download_link(data, turn_context)
                    return
            

        
        elif activity.text:
            user_message = activity.text.strip().lower()

            doc = nlp(user_message)

            if any(greet in user_message for greet in greeting_triggers):
                await turn_context.send_activity("👋 Hello! How can I help you today?")
                return

            # 🌐 Match VPC intents
            if any(word in user_message for word in ["create", "launch", "new"]) and "vpc" in user_message:
                card = adaptive_cards.vpc_full_creation_card()
                await turn_context.send_activity(
                    MessageFactory.attachment(
                        Attachment(
                            content_type="application/vnd.microsoft.card.adaptive",
                            content=card
                        )
                    )
                )
                return

            # 🚀 Match EC2 intents
            if any(word in user_message for word in ["create", "launch", "new"]) and "ec2" in user_message:
                detected_type = next((token.text for token in doc if re.match(r"t\d+\.\w+", token.text)), "t2.micro")
                card = adaptive_cards.ec2_launch_card()
                for item in card["body"]:
                    if item.get("id") == "InstanceType":
                        item["value"] = detected_type
                        break
                await turn_context.send_activity(
                    MessageFactory.attachment(
                        Attachment(
                            content_type="application/vnd.microsoft.card.adaptive",
                            content=card
                        )
                    )
                )
                return


            if "list instance profiles" in user_message.lower():
                profiles = list_instance_profiles()
                if isinstance(profiles, list):
                    formatted = "\n".join(f"- {p}" for p in profiles)
                    await turn_context.send_activity(f"🧾 **Available Instance Profiles:**\n{formatted}")
                else:
                    await turn_context.send_activity(profiles)
                return
            
            # 🪣 S3: Create Bucket
            if "create" in user_message and "bucket" in user_message:
                card = s3_create_bucket_card()
                await turn_context.send_activity(
                     MessageFactory.attachment(
                          Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)
                     )
                )
                return
        

            # 🪣 S3: Upload to Bucket
            logging.info(f"[UserMessage] Received: {user_message}")
            if "upload" in user_message and ("file" in user_message or "s3" in user_message or "upload file" in user_message):
                logging.info("[IntentMatch] Upload file intent matched.")
                success, buckets = list_s3_buckets()
                if success:
                   card = s3_upload_file_card([b["name"] for b in buckets])
                   await turn_context.send_activity(
                        MessageFactory.attachment(
                           Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)
                        )
                   )
                else:
                    await turn_context.send_activity(buckets)
                return
        

            # 🪣 S3: Download from Bucket
            if "download" in user_message and "file" in user_message or "s3" in user_message:
                success, buckets = list_s3_buckets()
                if success:
                   card = s3_download_file_card([b["name"] for b in buckets])
                   await turn_context.send_activity(
                      MessageFactory.attachment(
                        Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)
                      )
                   )
                else:
                  await turn_context.send_activity(buckets)
                return
            
                        # 🔐 IAM: Create User
            if "create" in user_message and "iam user" in user_message:
                policies = ["ReadOnlyAccess", "AdministratorAccess", "PowerUserAccess"]
                card = iam_create_user_card(policies)
                await turn_context.send_activity(MessageFactory.attachment(Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)))
                return

            # 👥 IAM: Create Group
            if "create" in user_message and "iam group" in user_message:
                policies = ["ReadOnlyAccess", "AdministratorAccess", "PowerUserAccess"]
                card = iam_create_group_card(policies)
                await turn_context.send_activity(MessageFactory.attachment(Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)))
                return

            # ➕ IAM: Attach User to Group
            if "attach" in user_message and "user" in user_message and "group" in user_message:
                data = list_iam_users_and_groups()
                if "error" in data:
                    await turn_context.send_activity(data["error"])
                    return
                card = iam_attach_user_group_card([u["UserName"] for u in data["users"]], [g["GroupName"] for g in data["groups"]])
                await turn_context.send_activity(MessageFactory.attachment(Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)))
                return

            # 📜 IAM: Attach/Detach Policy
            if "policy" in user_message and ("attach" in user_message or "detach" in user_message):
                data = list_iam_users_and_groups()
                if "error" in data:
                    await turn_context.send_activity(data["error"])
                    return

                users = [u["UserName"] for u in data["users"]]
                groups = [g["GroupName"] for g in data["groups"]]
                policies = ["ReadOnlyAccess", "AdministratorAccess", "PowerUserAccess"]

    # ✅ NEW WAY: pass both users and groups
                card = adaptive_cards.iam_attach_detach_policy_card(
                users=users,
                groups=groups,
                policies=policies
    )

                await turn_context.send_activity(
                   MessageFactory.attachment(
                        Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)
                )
          )
                return

            # 📄 IAM: Inline Policy
            if "inline policy" in user_message:
                data = list_iam_users_and_groups()
                if "error" in data:
                    await turn_context.send_activity(data["error"])
                    return
                entities = [u["UserName"] for u in data["users"]] + [g["GroupName"] for g in data["groups"]]
                card = iam_inline_policy_card(entities)
                await turn_context.send_activity(MessageFactory.attachment(Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)))
                return

            # 🛡️ IAM: Create Role
            if "create" in user_message and "iam role" in user_message:
                policies = ["ReadOnlyAccess", "AdministratorAccess", "PowerUserAccess"]
                card = iam_create_role_card(policies)
                await turn_context.send_activity(MessageFactory.attachment(Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)))
                return

            # ❌ IAM: Delete User/Group/Role
            if "delete" in user_message and ("iam" in user_message or "user" in user_message or "group" in user_message or "role" in user_message):
                data = list_iam_users_and_groups()
                if "error" in data:
                    await turn_context.send_activity(data["error"])
                    return
                card = iam_delete_card([u["UserName"] for u in data["users"]],
                                       [g["GroupName"] for g in data["groups"]],
                                       [])  # add role list if needed later
                await turn_context.send_activity(MessageFactory.attachment(Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)))
                return

            # 🔐 IAM: Enable MFA
            if "enable mfa" in user_message or "mfa user" in user_message:
                data = list_iam_users_and_groups()
                if "error" in data:
                    await turn_context.send_activity(data["error"])
                    return
                card = adaptive_cards.iam_enable_mfa_card_step1([u["UserName"] for u in data["users"]])
                await turn_context.send_activity(MessageFactory.attachment(Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)))
                return

            # 🧠 IAM: Audit
            if "audit" in user_message and "iam" in user_message:
                card = iam_audit_card()
                await turn_context.send_activity(MessageFactory.attachment(Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)))
                return

            # CrewAI NLP fallback
            response = process_user_message(user_message)
            if isinstance(response, dict):
                await turn_context.send_activity(
                    MessageFactory.attachment(
                        Attachment(
                            content_type="application/vnd.microsoft.card.adaptive",
                            content=response
                        )
                    )
                )
            elif response:
                await turn_context.send_activity(response)
            else:
                await turn_context.send_activity("Sorry, I couldn't process your request.")
    
    async def on_teams_task_module_fetch(self, turn_context: TurnContext, task_module_request: TaskModuleRequest):
        data = task_module_request.data

        if data.get("action") == "open_upload_module":
            task_info = TaskModuleTaskInfo(
                title="Upload File to S3",
                height="medium",
                width="medium",
                url=f"{BASE_URL}/upload",
                fallback_url=f"{BASE_URL}/upload"
        )
        return TaskModuleResponse(task=TaskModuleContinueResponse(value=task_info))


                

    async def _handle_ec2_creation(self, data, turn_context: TurnContext):
        try:
            name = data.get("Name", "")
            instance_type = data.get("InstanceType", "t2.micro")
            ami_id = data.get("AmiId", "default")
            key_name = data.get("KeyPairName", "")
            security_group_id = data.get("SecurityGroupId", "")
            if security_group_id == "manual":
                security_group_id = data.get("SecurityGroupId_Manual", "")
            subnet_id = data.get("SubnetId", "")
            if subnet_id == "manual":
                subnet_id = data.get("SubnetId_Manual", "")
            iam_role = data.get("IamRole", "")
            if iam_role == "manual":
                iam_role = data.get("IamRole_Manual", "")
            ebs_size = int(data.get("EBSSize", 8))
            bootstrap_script_name = data.get("BootstrapScript", "None")
            public_ip = parse_bool(data.get("PublicIp"))
            elastic_ip = parse_bool(data.get("ElasticIp"))
            termination_protection = parse_bool(data.get("TerminationProtection"))

            # Tags
            custom_tags = {}
            for pair in data.get("CustomTags", "").split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    custom_tags[k.strip()] = v.strip()

            logger.info(f"[TeamsBot] Creating EC2 with: {locals()}")

            result = create_instance(
                name=name,
                ami_id=ami_id,
                instance_type=instance_type,
                key_name=key_name,
                security_group_id=security_group_id,
                subnet_id=subnet_id,
                ebs_size=ebs_size,
                iam_role=iam_role,
                public_ip=public_ip,
                termination_protection=termination_protection,
                bootstrap_script_name=bootstrap_script_name,
                elastic_ip=elastic_ip,
                custom_tags=custom_tags
            )

            # Result summary
            details = (
                f"✅ **EC2 Instance Created Successfully!**\n\n"
                f"🆔 **Name:** {name or 'N/A'}\n"
                f"📦 **AMI:** {ami_id}\n"
                f"⚙️ **Type:** {result['InstanceType']}\n"
                f"🔐 **Key Pair:** {result['KeyPair']}\n"
                f"🌐 **Subnet:** {result['SubnetId']}\n"
                f"🛡️ **Security Group:** {result['SecurityGroupId']}\n"
                f"💰 **Est. Cost:** {result['EstimatedCost']}\n"
                f"📄 **Instance ID:** `{result['InstanceId']}`"
            )
            await turn_context.send_activity(details)

            if not result["ExistingKey"] and result.get("PEMFilePath"):
                pem_filename = os.path.basename(result["PEMFilePath"])
                pem_url = f"{BASE_URL}/static/{pem_filename}"
                await turn_context.send_activity(f"🔑 PEM file ready: [Click to Download]({pem_url})")

        except Exception as e:
            logger.exception("❌ EC2 Creation Failed")
            await turn_context.send_activity(f"❌ Error creating EC2 instance: {str(e)}")

    async def _handle_vpc_creation(self, data, turn_context: TurnContext):
        def parse_bool(val: str) -> bool:
            return val.strip().lower() == "true" if isinstance(val, str) else False
        try:
            vpc_name = data.get("vpc_name", "")
            cidr_block = data.get("vpc_cidr", "")
            region = data.get("region", "us-east-1")
            enable_dns_support = parse_bool(data.get("enable_dns_support"))
            enable_dns_hostnames = parse_bool(data.get("enable_dns_hostnames"))
            attach_igw = parse_bool(data.get("attach_igw"))
            attach_nat = parse_bool(data.get("create_nat"))
            route_table_mode = data.get("route_table_count", "1")

            # 🏗️ Construct dynamic subnet_requests array
            public_count = int(data.get("public_subnet_count", 0))
            private_count = int(data.get("private_subnet_count", 0))
            public_hosts = int(data.get("public_hosts", 28))
            private_hosts = int(data.get("private_hosts", 28))

            subnet_requests = []
            for _ in range(public_count):
                subnet_requests.append({"type": "public", "hosts": public_hosts})
            for _ in range(private_count):
                subnet_requests.append({"type": "private", "hosts": private_hosts})


            # 🏷️ Tags
            custom_tags_str = data.get("custom_tags", "")
            custom_tags = {}
            if custom_tags_str:
                for pair in custom_tags_str.split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        custom_tags[k.strip()] = v.strip()

            # ⛵ Call create_vpc_advanced from vpc.py
            logger.info(f"[TeamsBot] Proceeding to create VPC with name: {vpc_name}")

            result = create_vpc_advanced(
                vpc_name=vpc_name,
                cidr_block=cidr_block,
                region=region,
                enable_dns_support=enable_dns_support,
                enable_dns_hostnames=enable_dns_hostnames,
                enable_igw=attach_igw,
                enable_nat=attach_nat,
                route_table_mode=route_table_mode,
                subnet_requests=subnet_requests,
                custom_tags=custom_tags
            )

            if isinstance(result, dict):
                summary = (
                    f"✅ **VPC Created Successfully!**\n\n"
                    f"🔗 **VPC ID:** `{result['vpc_id']}`\n"
                    f"🌐 **CIDR:** `{result['cidr']}`\n"
                    f"📡 **IGW Attached:** {'Yes' if result['igw_id'] else 'No'}\n"
                    f"🔀 **Subnets Created:** {result['subnet_count']}\n"
                    f"🌐 **NAT Gateway:** {'Yes' if result['nat_gateway'] else 'No'}"
                )
                await turn_context.send_activity(summary)
            else:
                await turn_context.send_activity(result)

        except Exception as e:
            logger.exception("❌ VPC creation failed")
            await turn_context.send_activity(f"❌ Failed to create VPC: {str(e)}")
    

    async def _handle_s3_bucket_creation(self, data, turn_context: TurnContext):
       bucket_name = data.get("bucket_name")
       region = data.get("region")
       versioning = data.get("versioning") == "true"
       encryption = data.get("encryption", "none")
       block_public_access = data.get("block_public_access") == "true"
       tags = data.get("tags", "")

       success, message = create_s3_bucket(bucket_name, region, versioning, encryption, block_public_access, tags)
       if success:
           card = adaptive_cards.s3_bucket_success_card(
             bucket_name=bucket_name,
             region=region,
             versioning=versioning,
             encryption=encryption,
             block_public_access=block_public_access,
             tags=tags
          )
           await turn_context.send_activity(
             MessageFactory.attachment(
               Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)
             )
           )
       else:
          await turn_context.send_activity(message)


    async def _handle_s3_upload(self, data, turn_context: TurnContext):
       bucket_name = data.get("bucket_name")
       prefix = data.get("prefix", "")
       acl = data.get("acl", "private")
       storage_class = data.get("storage_class", "STANDARD")

       if not turn_context.activity.attachments:
         await turn_context.send_activity("❌ No file was attached.")
         return

       file = turn_context.activity.attachments[0]
       file_name = file.name
       file_bytes = await turn_context.adapter.download_attachment(file, turn_context)

       success, message = upload_file_to_s3(bucket_name, file_bytes, file_name, prefix, acl, storage_class)
       if success:
          key = f"{prefix}{file_name}" if prefix else file_name
          card = adaptive_cards.s3_upload_success_card(bucket_name, key, acl, storage_class)
          await turn_context.send_activity(
            MessageFactory.attachment(
              Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)
            )
          )
       else:
         await turn_context.send_activity(message)


    async def _handle_s3_download_link(self, data, turn_context: TurnContext):
        try:
            bucket_name = data.get("bucket_name")
            object_key = data.get("object_key")

            if bucket_name and not object_key:
                # Step 2: show object list from selected bucket
                success, object_list = list_s3_objects(bucket_name)
                if success:
                    if not object_list:
                        await turn_context.send_activity("⚠️ No files found in the selected bucket.")
                        return
                    card = adaptive_cards.s3_select_object_card(bucket_name, object_list)
                    await turn_context.send_activity(
                        MessageFactory.attachment(
                            Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)
                        )
                    )
                else:
                    await turn_context.send_activity(object_list)
                return

            if not bucket_name or not object_key:
                await turn_context.send_activity("⚠️ Bucket name or file key is missing. Please check the form.")
                return

            success, result = generate_presigned_download_url(bucket_name, object_key)

            if success:
                card = adaptive_cards.s3_download_link_card(bucket_name, object_key, result)
                await turn_context.send_activity(
                    MessageFactory.attachment(
                        Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)
                    )
                )
            else:
                await turn_context.send_activity(f"❌ Failed to generate link: {result}")
        except Exception as e:
            logger.exception("Download link generation failed")
            await turn_context.send_activity(f"❌ Error: {str(e)}")

    async def _handle_iam_user_creation(self, data, turn_context: TurnContext):
        try:
            username = data.get("username")
            if not username:
                await turn_context.send_activity("❌ Username is required.")
                return

            policies = data.get("policies", "")
            policy_list = [p.strip() for p in policies.split(",") if p.strip()]
            programmatic = data.get("programmatic_access") == "true"
            console = data.get("console_access") == "true"

            result = iam.CreateIAMUserTool()._run(
                username=username,
                policies=policy_list,
                programmatic_access=programmatic,
                console_access=console
            )

            if isinstance(result, dict):
                msg = f"✅ **User Created:** {username}\n"
                if "access_key" in result:
                    msg += f"🔑 Access Key: `{result['access_key']}`\n"
                    msg += f"🔐 Secret Key: `{result['secret_key']}`\n"
                if "console" in result:
                    msg += f"🌐 Console Access Enabled: `{result['console']}`"
                await turn_context.send_activity(msg)
            else:
                await turn_context.send_activity(result)

        except Exception as e:
            await turn_context.send_activity(f"❌ Failed to create IAM user: {e}")

    async def _handle_iam_group_creation(self, data, turn_context: TurnContext):
        try:
            group_name = data.get("group_name")
            policies = data.get("policies", "")
            policy_list = [p.strip() for p in policies.split(",") if p.strip()]

            result = iam.CreateIAMGroupTool()._run(
                group_name=group_name,
                policies=policy_list
            )
            await turn_context.send_activity(result)

        except Exception as e:
            await turn_context.send_activity(f"❌ Failed to create IAM group: {e}")


    async def _handle_mfa_enabling(self, data, turn_context: TurnContext):
        try:
            action = data.get("action")
            if action == "mfa_start":
                username = data.get("username")
                if not username:
                    await turn_context.send_activity("❌ Username is required.")
                    return

                exists, serial, seed_base32 = iam.create_virtual_mfa_device(username)
                if exists:
                    await turn_context.send_activity(f"ℹ️ MFA already enabled for `{username}`.")
                    return

                if serial and seed_base32:
                    # ✅ Generate QR Code from TOTP URI
                    totp_uri = pyotp.totp.TOTP(seed_base32).provisioning_uri(
                        name=username,
                        issuer_name="AWS"
                )
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=20,
                        border=4,
                )
                    qr.add_data(totp_uri)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")

                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    img_bytes = buf.getvalue()
                    img_base64 = base64.b64encode(img_bytes).decode("utf-8")
                    img_data_url = f"data:image/png;base64,{img_base64}"

                # ✅ Send image as inline image in Adaptive Card
                    card = {
    "type": "AdaptiveCard",
    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
    "version": "1.4",
    "body": [
        {"type": "TextBlock", "text": f"🔐 Scan this QR Code for `{username}`", "weight": "Bolder", "size": "Large"},
        {
            "type": "Image",
            "url": img_data_url,
            "pixelWidth": 350,
            "pixelHeight": 350,
            "altText": "Scan this QR code"
        },
        {"type": "TextBlock", "text": "Enter two consecutive MFA codes:"},
        {"type": "Input.Text", "id": "code1", "placeholder": "First code"},
        {"type": "Input.Text", "id": "code2", "placeholder": "Second code"},
        # ✅ Just keep them normal so they post back correctly
    ],
    "actions": [
        {"type": "Action.Submit", "title": "✅ Enable MFA", "data": {"action": "mfa_finish", "username": username ,"serial": serial}}
    ]
}



                    await turn_context.send_activity(
                        MessageFactory.attachment(
                            Attachment(
                                content_type="application/vnd.microsoft.card.adaptive",
                                content=card
                        )
                    )
                )
                else:
                    await turn_context.send_activity("❌ Failed to start MFA setup.")

            elif action == "mfa_finish":
                username = data.get("username")
                serial = data.get("serial")
                code1 = data.get("code1")
                code2 = data.get("code2")

                if not all([username, serial, code1, code2]):
                    await turn_context.send_activity("❌ Missing MFA information.")
                    return

                result = iam.enable_mfa_device(username, serial, code1, code2)
                await turn_context.send_activity(result)

        except Exception as e:
            await turn_context.send_activity(f"❌ MFA Setup failed: {e}")



    async def _handle_attach_user_to_group(self, data, turn_context: TurnContext):
        try:
            user = data.get("username")
            group = data.get("group_name")
            if not user or not group:
                await turn_context.send_activity("❌ Please select both user and group.")
                return

            result = iam.AttachUserToGroupTool()._run(
                username=user,
                group_name=group
            )
            await turn_context.send_activity(result)

        except Exception as e:
            await turn_context.send_activity(f"❌ Failed to attach user to group: {e}")

    async def _handle_iam_role_creation(self, data, turn_context: TurnContext):
        try:
            role_name = data.get("role_name")
            trust_policy = data.get("trust_policy_json")
            policies = data.get("policies", "")
            policy_list = [p.strip() for p in policies.split(",") if p.strip()]

            result = iam.CreateIAMRoleTool()._run(
                role_name=role_name,
                trust_policy_json=trust_policy,
                policies=policy_list
            )
            await turn_context.send_activity(result)

        except Exception as e:
            await turn_context.send_activity(f"❌ Failed to create IAM role: {e}")

    async def _handle_inline_policy_creation(self, data, turn_context: TurnContext):
        try:
            entity_type = data.get("entity_type")
            name = data.get("name")
            policy_name = data.get("policy_name")
            policy_json = data.get("policy_json")

            result = iam.CreateInlinePolicyTool()._run(
                entity_type=entity_type,
                name=name,
                policy_name=policy_name,
                policy_json=policy_json
            )
            await turn_context.send_activity(result)

        except Exception as e:
            await turn_context.send_activity(f"❌ Failed to create inline policy: {e}")

    async def _handle_attach_policy(self, data, turn_context: TurnContext):
        try:
            result = iam.AttachPolicyTool()._run(
            entity_type=data.get("entity_type"),
            name=data.get("name"),
            policy_name=data.get("policy_name")
        )
            await turn_context.send_activity(result)
        except Exception as e:
            await turn_context.send_activity(f"❌ Failed to attach policy: {e}")    

    async def _handle_detach_policy(self, data, turn_context: TurnContext):
        try:
            result = iam.DetachPolicyTool()._run(
            entity_type=data.get("entity_type"),
            name=data.get("name"),
            policy_name=data.get("policy_name")
        )
            await turn_context.send_activity(result)
        except Exception as e:
            await turn_context.send_activity(f"❌ Failed to detach policy: {e}")



    async def _handle_iam_deletion(self, data, turn_context: TurnContext):
        try:
            entity_type = data.get("entity_type")
            name = data.get("name")

            if entity_type == "user":
                result = iam.DeleteIAMUserTool()._run(username=name)
            elif entity_type == "group":
                result = iam.DeleteIAMGroupTool()._run(group_name=name)
            elif entity_type == "role":
                result = iam.DeleteIAMRoleTool()._run(role_name=name)
            else:
                result = "❌ Unknown IAM entity type."

            await turn_context.send_activity(result)

        except Exception as e:
            await turn_context.send_activity(f"❌ Failed to delete IAM entity: {e}")

    
    async def _handle_iam_audit(self, data, turn_context: TurnContext):
        try:
            result = iam.AuditIAMTool()._run()
            if isinstance(result, dict):
                msg = "🧠 **IAM Audit Report:**\n\n"
                msg += f"🔓 Users without MFA:\n" + "\n".join(f"- {u}" for u in result['no_mfa_users']) + "\n\n"
                msg += f"🛡️ Admin Users:\n" + "\n".join(f"- {u}" for u in result['admin_users']) + "\n\n"
                msg += f"🗝️ Unused Access Keys:\n" + "\n".join(f"- {i['user']} - {i['key']}" for i in result['unused_keys'])
                await turn_context.send_activity(msg)
            else:
                await turn_context.send_activity(result)

        except Exception as e:
            await turn_context.send_activity(f"❌ IAM Audit failed: {e}")











