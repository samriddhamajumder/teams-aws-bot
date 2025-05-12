# bot/adaptive_cards.py
# Defines Adaptive Card templates for collecting additional user input for AWS operations.
# Each function returns a dict representing an Adaptive Card payload.

# adaptive_cards.py - Adaptive Card JSON templates for the bot
from aws_crew_tools.ec2 import list_security_groups, list_subnets, list_iam_roles
import time
import json
version_tag = str(int(time.time()))

def ec2_launch_card():
    
    # 🔄 Format dropdowns from plain strings to {title, value}
    sg_choices = list_security_groups()
    subnet_choices = list_subnets()
    iam_choices = list_iam_roles()

    # ➕ Add manual override
    sg_choices.append({"title": "🔧 Enter manually", "value": "manual"})
    subnet_choices.append({"title": "🔧 Enter manually", "value": "manual"})
    iam_choices.append({"title": "🔧 Enter manually", "value": "manual"})

    """Fully upgraded Adaptive Card for EC2 instance creation with advanced layout for Teams."""
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "auto",
                        "items": [
                            {
                                "type": "Image",
                                "url": "https://a0.awsstatic.com/libra-css/images/logos/aws_logo_smile_1200x630.png",
                                "size": "Small",
                                "style": "Person"
                            }
                        ]
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "🚀 **Launch a New EC2 Instance**",
                                "weight": "Bolder",
                                "size": "Large"
                            },
                            {
                                "type": "TextBlock",
                                "text": "Configure your instance below with required resources, IAM, networking, and scripts.",
                                "wrap": True,
                                "spacing": "None"
                            }
                        ]
                    }
                ]
            },
            {"type": "TextBlock", "text": "🆔 Instance Name", "weight": "Bolder"},
            {"type": "Input.Text", "id": "Name", "placeholder": "Optional instance name tag"},

            {"type": "TextBlock", "text": "🧠 Instance Type", "weight": "Bolder"},
            {"type": "Input.ChoiceSet", "id": "InstanceType", "value": "t2.micro", "style": "compact",
             "choices": [
                 {"title": "t2.micro (Free tier)", "value": "t2.micro"},
                 {"title": "t3.micro", "value": "t3.micro"},
                 {"title": "m5.large", "value": "m5.large"},
                 {"title": "t3.small", "value": "t3.small"},
                 {"title": "t3.medium", "value": "t3.medium"}
             ]},

            {"type": "TextBlock", "text": "📦 AMI", "weight": "Bolder"},
            {"type": "Input.ChoiceSet", "id": "AmiId", "value": "default", "style": "compact",
             "choices": [
                 {"title": "Amazon Linux 2023 (default)", "value": "default"},
                 {"title": "Ubuntu 22.04 LTS", "value": "ami-ubuntu-22"},
                 {"title": "RHEL", "value": "ami-rhel"}
             ]},

            {"type": "TextBlock", "text": "🔐 Key Pair", "weight": "Bolder"},
            {"type": "Input.Text", "id": "KeyPairName", "placeholder": "Leave blank to auto-generate"},

            {"type": "TextBlock", "text": "🔒 Security Group ID", "weight": "Bolder"},
            {"type": "Input.ChoiceSet", "id": "SecurityGroupId", "style": "compact", "choices": sg_choices},
            {"type": "Input.Text", "id": "SecurityGroupId_Manual", "placeholder": "e.g., sg-xxxx (only if selected manual)"},

            # 🌐 Subnet ID Dropdown
            {"type": "TextBlock", "text": "🌐 Subnet ID", "weight": "Bolder"},
            {"type": "Input.ChoiceSet", "id": "SubnetId", "style": "compact", "choices": subnet_choices},
            {"type": "Input.Text", "id": "SubnetId_Manual", "placeholder": "e.g., subnet-xxxx (only if selected manual)"},

            # 🧑‍💼 IAM Role Dropdown
            {"type": "TextBlock", "text": "🧑‍💼 IAM Role / Instance Profile", "weight": "Bolder"},
            {"type": "Input.ChoiceSet", "id": "IamRole", "style": "compact", "choices": iam_choices},

            {"type": "Input.Text", "id": "IamRole_Manual", "placeholder": "e.g., ReadOnlyAccess (only if selected manual)"},

            {"type": "TextBlock", "text": "💾 EBS Size (GB)", "weight": "Bolder"},
            {"type": "Input.ChoiceSet", "id": "EBSSize", "value": "8", "style": "compact",
             "choices": [
                 {"title": "8 GB", "value": "8"},
                 {"title": "16 GB", "value": "16"},
                 {"title": "32 GB", "value": "32"},
                 {"title": "64 GB", "value": "64"},
                 {"title": "128 GB", "value": "128"}
             ]},

            {"type": "TextBlock", "text": "📜 Bootstrap Script", "weight": "Bolder"},
            {"type": "Input.ChoiceSet", "id": "BootstrapScript", "value": "None", "style": "compact",
             "choices": [
                 {"title": "None", "value": "None"},
                 {"title": "Install Apache", "value": "Install Apache"},
                 {"title": "Install NGINX", "value": "Install NGINX"},
                 {"title": "Hello from CloudBuddy", "value": "Hello from CloudBuddy"}
             ]},
             {
  "type": "TextBlock",
  "text": "🏷️ Custom Tags (key1=value1,key2=value2)",
  "weight": "Bolder"
},
{
  "type": "Input.Text",
  "id": "CustomTags",
  "placeholder": "Example: Env=Dev,Team=Ops"
},


            {"type": "TextBlock", "text": "⚙️ Advanced Options", "weight": "Bolder"},
            {"type": "Input.Toggle", "id": "PublicIp", "title": "Assign Public IP?", "valueOn": "true", "valueOff": "false"},
            {"type": "Input.Toggle", "id": "ElasticIp", "title": "Allocate Elastic IP?", "valueOn": "true", "valueOff": "false"},
            {"type": "Input.Toggle", "id": "TerminationProtection", "title": "Enable Termination Protection?", "valueOn": "true", "valueOff": "false"}
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "🚀 Launch Instance",
                "data": {"action": "create_ec2"}
            }
        ]
    }


# Adaptive card templates for VPC creation
import json

def vpc_full_creation_card():
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "🌐 Create a New VPC", "weight": "Bolder", "size": "Large"},
            {"type": "TextBlock", "text": "Enter VPC Name", "weight": "Bolder"},
            {"type": "Input.Text", "id": "vpc_name", "placeholder": "Enter VPC name"},
            {"type": "TextBlock", "text": "Enter CIDR Range", "weight": "Bolder"},
            {"type": "Input.Text", "id": "vpc_cidr", "placeholder": "CIDR block (e.g., 10.0.0.0/16)"},

            {"type": "TextBlock", "text": "Public Subnets", "weight": "Bolder"},
            {"type": "Input.Number", "id": "public_subnet_count", "placeholder": "Number of public subnets"},
            {"type": "Input.ChoiceSet", "id": "public_hosts", "style": "compact",
             "choices": [{"title": "28", "value": "28"}, {"title": "64", "value": "64"}, {"title": "128", "value": "128"}]},

            {"type": "TextBlock", "text": "Private Subnets", "weight": "Bolder"},
            {"type": "Input.Number", "id": "private_subnet_count", "placeholder": "Number of private subnets"},
            {"type": "Input.ChoiceSet", "id": "private_hosts", "style": "compact",
             "choices": [{"title": "28", "value": "28"}, {"title": "64", "value": "64"}, {"title": "128", "value": "128"}]},

            {"type": "TextBlock", "text": "⚙️ DNS Settings", "weight": "Bolder"},
            {"type": "Input.Toggle", "id": "enable_dns_support", "title": "Enable DNS Resolution", "valueOn": "true", "valueOff": "false"},
            {"type": "Input.Toggle", "id": "enable_dns_hostnames", "title": "Enable DNS Hostnames", "valueOn": "true", "valueOff": "false"},

            {"type": "TextBlock", "text": "🌐 Internet Access", "weight": "Bolder"},
            {"type": "Input.Toggle", "id": "attach_igw", "title": "Attach Internet Gateway", "valueOn": "true", "valueOff": "false"},
            {"type": "Input.Toggle", "id": "create_nat", "title": "Enable NAT Gateway", "valueOn": "true", "valueOff": "false"},

            {"type": "TextBlock", "text": "🛣️ Route Table", "weight": "Bolder"},
            {"type": "Input.ChoiceSet", "id": "route_table_count", "value": "1", "style": "compact",
             "choices": [{"title": "1 (shared)", "value": "1"}, {"title": "Separate", "value": "separate"}]},

            {"type": "TextBlock", "text": "🏷️ Tags", "weight": "Bolder"},
            {"type": "Input.Text", "id": "custom_tags", "placeholder": "key=value,key=value"}
        ],
        "actions": [
            {"type": "Action.Submit", "title": "🛠️ Create VPC", "data": {"action": "create_vpc"}}
        ]
    }

def s3_create_bucket_card():
    return {
        "type": "AdaptiveCard",
        "version": "1.4",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "🪣 Create New S3 Bucket", "weight": "Bolder", "size": "Medium"},

            {"type": "TextBlock", "text": "Bucket Name (must be globally unique):"},
            {"type": "Input.Text", "id": "bucket_name", "placeholder": "e.g. my-awesome-bucket"},

            {"type": "TextBlock", "text": "Region:"},
            {
                "type": "Input.ChoiceSet",
                "id": "region",
                "style": "compact",
                "choices": [
                    {"title": "us-east-1", "value": "us-east-1"},
                    {"title": "us-west-2", "value": "us-west-2"},
                    {"title": "ap-south-1", "value": "ap-south-1"},
                    {"title": "eu-central-1", "value": "eu-central-1"}
                ]
            },

            {"type": "TextBlock", "text": "Enable Versioning?"},
            {
                "type": "Input.Toggle",
                "title": "Yes",
                "valueOn": "true",
                "valueOff": "false",
                "id": "versioning"
            },

            {"type": "TextBlock", "text": "Encryption:"},
            {
                "type": "Input.ChoiceSet",
                "id": "encryption",
                "style": "compact",
                "choices": [
                    {"title": "None", "value": "none"},
                    {"title": "AES-256 (SSE-S3)", "value": "AES256"}
                ]
            },

            {"type": "TextBlock", "text": "Block Public Access?"},
            {
                "type": "Input.Toggle",
                "title": "Yes (Recommended)",
                "valueOn": "true",
                "valueOff": "false",
                "id": "block_public_access"
            },

            {"type": "TextBlock", "text": "Tags (optional):"},
            {"type": "Input.Text", "id": "tags", "placeholder": "key1=value1,key2=value2"}
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "🚀 Create Bucket",
                "data": {
                    "action": "create_s3_bucket"
                }
            }
        ]
    }

def s3_upload_file_card(bucket_list):
    return {
        "type": "AdaptiveCard",
        "version": "1.4",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "📤 Upload File to S3", "weight": "Bolder", "size": "Medium"},

            {"type": "TextBlock", "text": "Select Bucket:"},
            {
                "type": "Input.ChoiceSet",
                "id": "bucket_name",
                "style": "compact",
                "choices": [{"title": b, "value": b} for b in bucket_list]
            },

            {"type": "TextBlock", "text": "S3 Key Prefix (optional):"},
            {"type": "Input.Text", "id": "prefix", "placeholder": "e.g. user/docs/"},

            {"type": "TextBlock", "text": "Access Control:"},
            {
                "type": "Input.ChoiceSet",
                "id": "acl",
                "style": "compact",
                "choices": [
                    {"title": "Private", "value": "private"},
                    {"title": "Public Read", "value": "public-read"}
                ]
            },

            {"type": "TextBlock", "text": "Storage Class:"},
            {
                "type": "Input.ChoiceSet",
                "id": "storage_class",
                "style": "compact",
                "choices": [
                    {"title": "Standard", "value": "STANDARD"},
                    {"title": "Intelligent-Tiering", "value": "INTELLIGENT_TIERING"},
                    {"title": "Infrequent Access", "value": "STANDARD_IA"},
                    {"title": "Glacier", "value": "GLACIER"}
                ]
            },

            {"type": "TextBlock", "text": "Attach File:"},
            {
             "type": "TextBlock",
             "text": "📎 Please upload the file **separately** in this chat after submitting this form.",
            "wrap": True
            }
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "📤 Upload File via Form",
                "data": {
                    "msteams": { "type": "task/fetch" },
                    "action": "open_upload_module"
                }
            }
        ]
    }

def s3_download_file_card(bucket_list):
    return {
        "type": "AdaptiveCard",
        "version": "1.4",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "📥 Download File from S3", "weight": "Bolder", "size": "Medium"},

            {"type": "TextBlock", "text": "Select Bucket:"},
            {
                "type": "Input.ChoiceSet",
                "id": "bucket_name",
                "style": "compact",
                "choices": [{"title": b, "value": b} for b in bucket_list]
            },

            {"type": "TextBlock", "text": "File Key (Full S3 Object Key):"},
            {"type": "Input.Text", "id": "object_key", "placeholder": "e.g. user/docs/report.pdf"}
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "🔗 Get Download Link",
                "data": {
                    "action": "generate_download_link"
                }
            }
        ]
    }

def s3_bucket_success_card(bucket_name, region, versioning, encryption, block_public_access, tags=""):
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "size": "Large", "weight": "Bolder", "text": "✅ S3 Bucket Created Successfully"},
            {"type": "FactSet", "facts": [
                {"title": "🪣 Bucket Name:", "value": bucket_name},
                {"title": "🌎 Region:", "value": region},
                {"title": "📄 Versioning:", "value": "Enabled" if versioning else "Disabled"},
                {"title": "🔐 Encryption:", "value": encryption if encryption != "none" else "None"},
                {"title": "🚫 Public Access Blocked:", "value": "Yes" if block_public_access else "No"},
                {"title": "🏷️ Tags:", "value": tags or "None"}
            ]},
            {"type": "TextBlock", "text": "You can now upload files, apply policies, or configure lifecycle rules.", "wrap": True}
        ]
    }

def s3_upload_success_card(bucket_name, key, acl, storage_class):
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "📁 File Uploaded to S3", "weight": "Bolder", "size": "Large"},
            {"type": "FactSet", "facts": [
                {"title": "🪣 Bucket:", "value": bucket_name},
                {"title": "📂 Key:", "value": key},
                {"title": "🔒 ACL:", "value": acl},
                {"title": "💾 Storage Class:", "value": storage_class}
            ]},
            {"type": "TextBlock", "text": "The file is now stored in your S3 bucket. You may use a presigned URL to share or download it."}
        ]
    }

def s3_download_link_card(bucket_name, object_key, url, expires_in=3600):
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "🔗 S3 Presigned Download Link", "weight": "Bolder", "size": "Large"},
            {"type": "FactSet", "facts": [
                {"title": "🪣 Bucket:", "value": bucket_name},
                {"title": "📄 Object Key:", "value": object_key},
                {"title": "⏱️ Expires In:", "value": f"{expires_in // 60} minutes"}
            ]},
            {"type": "TextBlock", "text": "Click the button below to download the file:"}
        ],
        "actions": [
            {
                "type": "Action.OpenUrl",
                "title": "⬇️ Download File",
                "url": url
            }
        ]
    }
def s3_select_object_card(bucket_name, object_list):
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": f"📄 Select File from `{bucket_name}`", "weight": "Bolder", "size": "Medium"},
            {
                "type": "Input.ChoiceSet",
                "id": "object_key",
                "style": "compact",
                "choices": [{"title": obj, "value": obj} for obj in object_list]
            }
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "🔗 Generate Download Link",
                "data": {
                    "action": "generate_download_link",
                    "bucket_name": bucket_name
                }
            }
        ]
    }

# adaptive_cards.py

def iam_create_user_card(policy_list: list):
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "🔐 Create IAM User", "weight": "Bolder", "size": "Medium"},
            {"type": "Input.Text", "id": "username", "placeholder": "Enter IAM username"},

            {"type": "TextBlock", "text": "Select Managed Policies:"},
            {
                "type": "Input.ChoiceSet",
                "id": "policies",
                "style": "expanded",
                "isMultiSelect": True,
                "choices": [{"title": p, "value": p} for p in policy_list]
            },

            {"type": "TextBlock", "text": "Access Types:"},
            {
                "type": "Input.Toggle",
                "title": "✅ Programmatic Access (Access Key)",
                "value": "false",
                "id": "programmatic_access"
            },
            {
                "type": "Input.Toggle",
                "title": "🧑‍💻 Console Access (Web Login)",
                "value": "false",
                "id": "console_access"
            }
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "🚀 Create User",
                "data": {
                    "action": "create_iam_user" 
                }
            }
        ]
    }

def iam_create_group_card(policy_list: list):
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "👥 Create IAM Group", "weight": "Bolder", "size": "Medium"},
            {"type": "Input.Text", "id": "group_name", "placeholder": "Enter group name"},

            {"type": "TextBlock", "text": "Attach Policies:"},
            {
                "type": "Input.ChoiceSet",
                "id": "policies",
                "style": "expanded",
                "isMultiSelect": True,
                "choices": [{"title": p, "value": p} for p in policy_list]
            }
        ],
        "actions": [
    {
        "type": "Action.Submit",
        "title": "✅ Create Group",
        "data": {"action": "create_iam_group"}
    }
]
    }

def iam_attach_user_group_card(user_list: list, group_list: list):
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "📎 Attach User to Group", "weight": "Bolder", "size": "Medium"},

            {"type": "TextBlock", "text": "Select IAM User:"},
            {
                "type": "Input.ChoiceSet",
                "id": "username",
                "style": "compact",
                "choices": [{"title": u, "value": u} for u in user_list]
            },

            {"type": "TextBlock", "text": "Select Group:"},
            {
                "type": "Input.ChoiceSet",
                "id": "group_name",
                "style": "compact",
                "choices": [{"title": g, "value": g} for g in group_list]
            }
        ],
        "actions": [
    {
        "type": "Action.Submit",
        "title": "➕ Attach",
        "data": {"action": "attach_user_to_group"}
    }
]
    }

def iam_attach_detach_policy_card(users: list, groups: list, policies: list):
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "📜 Attach/Detach Policy", "weight": "Bolder", "size": "Medium"},

            {"type": "TextBlock", "text": "Select User (optional):"},
            {
                "type": "Input.ChoiceSet",
                "id": "user_name",
                "choices": [{"title": u, "value": u} for u in users],
                "style": "compact"
            },

            {"type": "TextBlock", "text": "Select Group (optional):"},
            {
                "type": "Input.ChoiceSet",
                "id": "group_name",
                "choices": [{"title": g, "value": g} for g in groups],
                "style": "compact"
            },

            {"type": "TextBlock", "text": "Select Policy:"},
            {
                "type": "Input.ChoiceSet",
                "id": "policy_name",
                "choices": [{"title": p, "value": p} for p in policies],
                "style": "compact"
            },

            {"type": "TextBlock", "text": "Action:"},
            {
                "type": "Input.ChoiceSet",
                "id": "action",
                "choices": [
                    {"title": "Attach", "value": "attach"},
                    {"title": "Detach", "value": "detach"}
                ],
                "style": "compact"
            }
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "🔧 Apply",
                "data": {"submit_action": "iam_policy_action"}
            }
        ]
    }


def iam_inline_policy_card(entity_list: list):
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "📄 Create Inline Policy", "weight": "Bolder", "size": "Medium"},

            {"type": "TextBlock", "text": "Entity Type:"},
            {
                "type": "Input.ChoiceSet",
                "id": "entity_type",
                "choices": [{"title": "user", "value": "user"}, {"title": "group", "value": "group"}],
                "style": "compact"
            },

            {"type": "TextBlock", "text": "Entity Name:"},
            {
                "type": "Input.ChoiceSet",
                "id": "name",
                "choices": [{"title": e, "value": e} for e in entity_list],
                "style": "compact"
            },

            {"type": "TextBlock", "text": "Policy Name:"},
            {"type": "Input.Text", "id": "policy_name", "placeholder": "Enter policy name"},

            {"type": "TextBlock", "text": "Policy JSON:"},
            {"type": "Input.Text", "id": "policy_json", "isMultiline": True, "placeholder": "Paste JSON here..."}
        ],
        "actions": [
    {
        "type": "Action.Submit",
        "title": "📥 Submit Policy",
        "data": {"action": "create_inline_policy"}
    }
]

    }

def iam_create_role_card(policy_list: list):
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "🛡️ Create IAM Role", "weight": "Bolder", "size": "Medium"},

            {"type": "Input.Text", "id": "role_name", "placeholder": "Enter role name"},
            {"type": "TextBlock", "text": "Trust Policy (JSON):"},
            {"type": "Input.Text", "id": "trust_policy_json", "isMultiline": True},

            {"type": "TextBlock", "text": "Attach Managed Policies:"},
            {
                "type": "Input.ChoiceSet",
                "id": "policies",
                "isMultiSelect": True,
                "style": "expanded",
                "choices": [{"title": p, "value": p} for p in policy_list]
            }
        ],
        "actions": [
    {
        "type": "Action.Submit",
        "title": "🎯 Create Role",
        "data": {"action": "create_iam_role"}
    }
]

    }

def iam_delete_card(user_list, group_list, role_list):
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "🗑️ Delete IAM Entity", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "Entity Type:"},
            {
                "type": "Input.ChoiceSet",
                "id": "entity_type",
                "choices": [
                    {"title": "user", "value": "user"},
                    {"title": "group", "value": "group"},
                    {"title": "role", "value": "role"}
                ],
                "style": "compact"
            },
            {"type": "TextBlock", "text": "Entity Name:"},
            {
                "type": "Input.ChoiceSet",
                "id": "name",
                "choices": [{"title": n, "value": n} for n in user_list + group_list + role_list],
                "style": "compact"
            }
        ],
        "actions": [
    {
        "type": "Action.Submit",
        "title": "❌ Delete",
        "data": {"action": "delete_iam_user"}  # This gets overridden dynamically in your routing
    }
]

    }

def iam_enable_mfa_card_step1(user_list: list):
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "🔐 Start MFA Setup for IAM User", "weight": "Bolder", "size": "large"},
            {"type": "TextBlock", "text": "Select IAM User:"},
            {
                "type": "Input.ChoiceSet",
                "id": "username",
                "choices": [{"title": u, "value": u} for u in user_list],
                "style": "compact"
            }
        ],
        "actions": [
            {"type": "Action.Submit", "title": "📥 Get QR Code", "data": {"action": "mfa_start"}}
        ]
    }

def iam_enable_mfa_card_step2(username: str, serial: str, seed_base32: str):
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": f"🔐 Enable MFA for {username}", "weight": "Bolder", "size": "large"},
            {"type": "TextBlock", "text": "Scan this seed with any authenticator app (e.g. Google Authenticator, Authy):"},
            {"type": "TextBlock", "text": f"🔑 Seed Base32: {seed_base32}", "wrap": True},
            {"type": "TextBlock", "text": "Enter 2 consecutive passcodes from the app:"},
            {"type": "Input.Text", "id": "code1", "placeholder": "First code"},
            {"type": "Input.Text", "id": "code2", "placeholder": "Second code"},
            
        ],
        "actions": [
            {"type": "Action.Submit", "title": "✅ Enable MFA", "data": {"action": "mfa_finish", "username": username ,"serial": serial}}
        ]

    }

def iam_audit_card():
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🤖 TikoGen AWS Assistant", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "🧠 Audit IAM Security", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "This will list users without MFA, unused credentials, and admin access."}
        ],
        "actions": [
    {
        "type": "Action.Submit",
        "title": "🔍 Run Audit",
        "data": {"action": "audit_iam"}
    }
]

    }

def welcome_card():
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "👋 Hello! I am TikoGen AI Assistant 🚀", "weight": "Bolder", "size": "Large"},
            {"type": "TextBlock", "text": "I can help you manage your AWS Cloud 👇\n\n➡️ Simply click any button below or type a natural command like 'create EC2' or 'launch VPC'.", "wrap": True},
            {"type": "TextBlock", "text": "Most Popular Actions:", "weight": "Bolder", "size": "Medium"},
            {
                "type": "ActionSet",
                "actions": [
                    {"type": "Action.Submit", "title": "🖥️ Create EC2", "data": {"action": "create_ec2"}},
                    {"type": "Action.Submit", "title": "🪣 Create S3 Bucket", "data": {"action": "create_s3_bucket"}},
                    {"type": "Action.Submit", "title": "🌐 Create VPC", "data": {"action": "create_vpc"}},
                    {"type": "Action.Submit", "title": "👥 Create IAM User", "data": {"action": "create_iam_user"}},
                    {"type": "Action.Submit", "title": "📋 List EC2 Instances", "data": {"action": "list_ec2"}}
                ]
            }
        ]
    }

