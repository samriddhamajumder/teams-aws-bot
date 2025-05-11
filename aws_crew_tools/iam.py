import boto3
import logging
from pydantic import BaseModel, Field
from typing import List, Optional, Type
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from crewai.tools import BaseTool
import base64

logger = logging.getLogger(__name__)
region = "us-east-1"
iam = boto3.client("iam", region_name=region)
sts = boto3.client("sts")

# =========================== CORE FUNCTIONS ===========================

def create_iam_user(username, policies, programmatic_access, console_access):
    response = {}
    try:
        iam.create_user(UserName=username)
        response['user'] = f"IAM user '{username}' created successfully."

        if console_access:
            password = "CloudbuddyTemp#123"
            iam.create_login_profile(UserName=username, Password=password, PasswordResetRequired=True)
            response['console'] = f"Console access enabled. Temp password: {password}"

        if programmatic_access:
            keys = iam.create_access_key(UserName=username)["AccessKey"]
            response['access_key'] = keys["AccessKeyId"]
            response['secret_key'] = keys["SecretAccessKey"]

        for policy in policies:
            policy_arn = f"arn:aws:iam::aws:policy/{policy}"
            iam.attach_user_policy(UserName=username, PolicyArn=policy_arn)

    except ClientError as e:
        logger.error(e)
        return {"error": str(e)}
    return response


def create_iam_group(group_name, policies):
    try:
        iam.create_group(GroupName=group_name)
        for policy in policies:
            policy_arn = f"arn:aws:iam::aws:policy/{policy}"
            iam.attach_group_policy(GroupName=group_name, PolicyArn=policy_arn)
        return f"Group '{group_name}' created with attached policies."
    except ClientError as e:
        return str(e)


def attach_user_to_group(username, group_name):
    try:
        iam.add_user_to_group(UserName=username, GroupName=group_name)
        return f"User '{username}' added to group '{group_name}'."
    except ClientError as e:
        return str(e)


def list_iam_users_and_groups():
    try:
        users = iam.list_users()["Users"]
        groups = iam.list_groups()["Groups"]
        return {
            "users": [{"UserName": u["UserName"], "Created": str(u["CreateDate"])} for u in users],
            "groups": [{"GroupName": g["GroupName"], "Created": str(g["CreateDate"])} for g in groups],
        }
    except ClientError as e:
        return {"error": str(e)}


def attach_policy(entity_type, name, policy_name):
    try:
        arn = f"arn:aws:iam::aws:policy/{policy_name}"
        if entity_type == "user":
            iam.attach_user_policy(UserName=name, PolicyArn=arn)
        elif entity_type == "group":
            iam.attach_group_policy(GroupName=name, PolicyArn=arn)
        return f"Policy {policy_name} attached to {entity_type} '{name}'"
    except ClientError as e:
        return str(e)


def detach_policy(entity_type, name, policy_name):
    try:
        arn = f"arn:aws:iam::aws:policy/{policy_name}"
        if entity_type == "user":
            iam.detach_user_policy(UserName=name, PolicyArn=arn)
        elif entity_type == "group":
            iam.detach_group_policy(GroupName=name, PolicyArn=arn)
        return f"Policy {policy_name} detached from {entity_type} '{name}'"
    except ClientError as e:
        return str(e)


def create_inline_policy(entity_type, name, policy_name, policy_json):
    try:
        if entity_type == "user":
            iam.put_user_policy(UserName=name, PolicyName=policy_name, PolicyDocument=policy_json)
        elif entity_type == "group":
            iam.put_group_policy(GroupName=name, PolicyName=policy_name, PolicyDocument=policy_json)
        return f"Inline policy '{policy_name}' attached to {entity_type} '{name}'"
    except ClientError as e:
        return str(e)


def create_iam_role(role_name, trust_policy_json, policies):
    try:
        iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=trust_policy_json)
        for policy in policies:
            arn = f"arn:aws:iam::aws:policy/{policy}"
            iam.attach_role_policy(RoleName=role_name, PolicyArn=arn)
        return f"Role '{role_name}' created with attached policies."
    except ClientError as e:
        return str(e)


def delete_iam_user(username):
    try:
        attached_policies = iam.list_attached_user_policies(UserName=username)["AttachedPolicies"]
        for p in attached_policies:
            iam.detach_user_policy(UserName=username, PolicyArn=p["PolicyArn"])
        try:
            iam.delete_login_profile(UserName=username)
        except iam.exceptions.NoSuchEntityException:
            pass
        keys = iam.list_access_keys(UserName=username)["AccessKeyMetadata"]
        for k in keys:
            iam.delete_access_key(UserName=username, AccessKeyId=k["AccessKeyId"])
        groups = iam.list_groups_for_user(UserName=username)["Groups"]
        for g in groups:
            iam.remove_user_from_group(UserName=username, GroupName=g["GroupName"])
        iam.delete_user(UserName=username)
        return f"IAM user '{username}' deleted successfully."
    except ClientError as e:
        return str(e)


def delete_iam_group(group_name):
    try:
        attached_policies = iam.list_attached_group_policies(GroupName=group_name)["AttachedPolicies"]
        for p in attached_policies:
            iam.detach_group_policy(GroupName=group_name, PolicyArn=p["PolicyArn"])
        iam.delete_group(GroupName=group_name)
        return f"IAM group '{group_name}' deleted."
    except ClientError as e:
        return str(e)


def delete_iam_role(role_name):
    try:
        attached = iam.list_attached_role_policies(RoleName=role_name)["AttachedPolicies"]
        for p in attached:
            iam.detach_role_policy(RoleName=role_name, PolicyArn=p["PolicyArn"])
        iam.delete_role(RoleName=role_name)
        return f"IAM role '{role_name}' deleted."
    except ClientError as e:
        return str(e)


def enable_mfa_device(username, serial, code1, code2):
    try:
        iam.enable_mfa_device(
            UserName=username,
            SerialNumber=serial,
            AuthenticationCode1=code1,
            AuthenticationCode2=code2
        )
        return f"✅ MFA device '{serial}' enabled for user '{username}'"
    except ClientError as e:
        return str(e)
def create_virtual_mfa_device(username):
    try:
        # check if MFA already exists
        existing = iam.list_mfa_devices(UserName=username)["MFADevices"]
        if existing:
            return (True, None, None)

        # create new virtual MFA
        account_id = sts.get_caller_identity()["Account"]
        serial = f"arn:aws:iam::{account_id}:mfa/{username}"
        result = iam.create_virtual_mfa_device(VirtualMFADeviceName=username)
        seed_bytes = result["VirtualMFADevice"]["Base32StringSeed"]
        return (False, serial, seed_bytes)

    except ClientError as e:
        return (False, None, str(e))


def audit_iam():
    result = {
        "no_mfa_users": [],
        "admin_users": [],
        "unused_keys": []
    }

    users = iam.list_users()["Users"]
    for user in users:
        uname = user["UserName"]
        mfa = iam.list_mfa_devices(UserName=uname)["MFADevices"]
        if not mfa:
            result["no_mfa_users"].append(uname)
        policies = iam.list_attached_user_policies(UserName=uname)["AttachedPolicies"]
        if any("AdministratorAccess" in p["PolicyName"] for p in policies):
            result["admin_users"].append(uname)
        access_keys = iam.list_access_keys(UserName=uname)["AccessKeyMetadata"]
        for key in access_keys:
            last_used = iam.get_access_key_last_used(AccessKeyId=key["AccessKeyId"])["AccessKeyLastUsed"]
            if "LastUsedDate" not in last_used:
                result["unused_keys"].append({"user": uname, "key": key["AccessKeyId"]})
    return result

# =========================== TOOL CLASSES ===========================

class CreateIAMUserInput(BaseModel):
    username: str
    policies: List[str]
    programmatic_access: bool
    console_access: bool

class CreateIAMUserTool(BaseTool):
    name: str = "create_iam_user"
    description: str = "Create an IAM user with access and policy options"
    args_schema: Type[BaseModel] = CreateIAMUserInput
    def _run(self, username, policies, programmatic_access, console_access):
        return create_iam_user(username, policies, programmatic_access, console_access)


class CreateIAMGroupInput(BaseModel):
    group_name: str
    policies: List[str]

class CreateIAMGroupTool(BaseTool):
    name: str = "create_iam_group"
    description: str = "Create a group and attach policies"
    args_schema: Type[BaseModel] = CreateIAMGroupInput
    def _run(self, group_name, policies):
        return create_iam_group(group_name, policies)


class AttachUserToGroupInput(BaseModel):
    username: str
    group_name: str

class AttachUserToGroupTool(BaseTool):
    name: str = "attach_user_to_group"
    description: str = "Attach a user to a group"
    args_schema: Type[BaseModel] = AttachUserToGroupInput
    def _run(self, username, group_name):
        return attach_user_to_group(username, group_name)


class ListIAMResourcesTool(BaseTool):
    name: str = "list_iam_resources"
    description: str = "List IAM users and groups"
    def _run(self):
        return list_iam_users_and_groups()


class AttachPolicyInput(BaseModel):
    entity_type: str = Field(..., description="user or group")
    name: str = Field(..., description="IAM user or group name")
    policy_name: str = Field(..., description="Policy name, e.g. AdministratorAccess")

class AttachPolicyTool(BaseTool):
    name: str = "attach_policy"
    description: str = "Attach a policy to a user or group"
    args_schema: Type[BaseModel] = AttachPolicyInput
    def _run(self, entity_type, name, policy_name):
        return attach_policy(entity_type, name, policy_name)


class DetachPolicyTool(BaseTool):
    name: str = "detach_policy"
    description: str = "Detach a policy from a user or group"
    args_schema: Type[BaseModel] = AttachPolicyInput
    def _run(self, entity_type, name, policy_name):
        return detach_policy(entity_type, name, policy_name)


class CreateInlinePolicyInput(BaseModel):
    entity_type: str
    name: str
    policy_name: str
    policy_json: str

class CreateInlinePolicyTool(BaseTool):
    name: str = "create_inline_policy"
    description: str = "Create and attach an inline policy to a user or group"
    args_schema: Type[BaseModel] = CreateInlinePolicyInput
    def _run(self, entity_type, name, policy_name, policy_json):
        return create_inline_policy(entity_type, name, policy_name, policy_json)


class CreateIAMRoleInput(BaseModel):
    role_name: str
    trust_policy_json: str
    policies: List[str]

class CreateIAMRoleTool(BaseTool):
    name: str = "create_iam_role"
    description: str = "Create IAM role with trust policy and managed policies"
    args_schema: Type[BaseModel] = CreateIAMRoleInput
    def _run(self, role_name, trust_policy_json, policies):
        return create_iam_role(role_name, trust_policy_json, policies)


class DeleteIAMUserInput(BaseModel):
    username: str

class DeleteIAMUserTool(BaseTool):
    name: str = "delete_iam_user"
    description: str = "Delete IAM user after detaching policies and keys"
    args_schema: Type[BaseModel] = DeleteIAMUserInput
    def _run(self, username):
        return delete_iam_user(username)


class DeleteIAMGroupInput(BaseModel):
    group_name: str

class DeleteIAMGroupTool(BaseTool):
    name: str = "delete_iam_group"
    description: str = "Delete IAM group after detaching policies"
    args_schema: Type[BaseModel] = DeleteIAMGroupInput
    def _run(self, group_name):
        return delete_iam_group(group_name)


class DeleteIAMRoleInput(BaseModel):
    role_name: str

class DeleteIAMRoleTool(BaseTool):
    name: str = "delete_iam_role"
    description: str = "Delete IAM role after detaching policies"
    args_schema: Type[BaseModel] = DeleteIAMRoleInput
    def _run(self, role_name):
        return delete_iam_role(role_name)


class EnableMfaInput(BaseModel):
    username: str

class EnableMfaTool(BaseTool):
    name: str = "enable_mfa"
    description: str = "Start virtual MFA setup for user (check existing or create QR seed)"
    args_schema: Type[BaseModel] = EnableMfaInput
    def _run(self, username):
        return create_virtual_mfa_device(username)


class AuditIAMTool(BaseTool):
    name: str = "audit_iam"
    description: str = "Audit IAM for users without MFA, unused keys, and admin access"
    def _run(self):
        return audit_iam()

