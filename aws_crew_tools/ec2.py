import os
import boto3
import botocore.exceptions
import re
import logging
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import os
import boto3
import botocore.exceptions
from typing import Type, Optional
from datetime import datetime


logger = logging.getLogger(__name__)
_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# Predefined Bootstrap scripts for dropdown (name -> actual script)
BOOTSTRAP_SCRIPTS = {
    "None": "",
    "Install Apache": "#!/bin/bash\nyum update -y\nyum install -y httpd\nsystemctl enable httpd\nsystemctl start httpd",
    "Install NGINX": "#!/bin/bash\nyum install -y nginx\nsystemctl enable nginx\nsystemctl start nginx",
    "Hello from CloudBuddy": "#!/bin/bash\necho 'Hello from CloudBuddy' > /home/ec2-user/hello.txt"
}

def estimate_instance_cost(instance_type, region="us-east-1"):
    try:
        pricing = boto3.client("pricing", region_name="us-east-1")
        response = pricing.get_products(
            ServiceCode="AmazonEC2",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
                {"Type": "TERM_MATCH", "Field": "location", "Value": "US East (N. Virginia)"},
                {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
                {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
                {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"}
            ],
            MaxResults=1
        )
        price_dimensions = next(iter(eval(response['PriceList'][0])['terms']['OnDemand'].values()))
        price = float(next(iter(price_dimensions['priceDimensions'].values()))['pricePerUnit']['USD'])
        return f"${price:.4f}/hr (~${price * 730:.2f}/mo)"
    except Exception as e:
        return f"Cost Estimation Failed: {e}"

def create_instance(name, ami_id, instance_type, key_name, security_group_id,
                    subnet_id, ebs_size=8, iam_role=None, public_ip=True,
                    termination_protection=False, bootstrap_script_name="None",
                    region_name=_region, **kwargs):
    ec2_client = boto3.client('ec2', region_name=region_name)
    ssm_client = boto3.client('ssm', region_name=region_name)
    iam_client = boto3.client("iam", region_name=region_name)

    existing_key = False
    pem_content = None
    key_file = None

    # ✅ Move all_tags to the top so it’s always defined
    all_tags = [{"Key": "Name", "Value": name}] if name else []
    all_tags += [{"Key": k, "Value": v} for k, v in kwargs.get("custom_tags", {}).items()]

    if not ami_id or ami_id.strip().lower() == 'default':
        try:
            parameter = ssm_client.get_parameter(
                Name='/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64'
            )
            ami_id = parameter['Parameter']['Value']
        except botocore.exceptions.ClientError as e:
            raise RuntimeError(f"Unable to get latest Amazon Linux 2023 AMI: {e}")

    if not key_name:
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        key_name = f"cloudbuddy-key-{timestamp}"

    try:
        ec2_client.describe_key_pairs(KeyNames=[key_name])
        existing_key = True
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'InvalidKeyPair.NotFound':
            key_pair = ec2_client.create_key_pair(KeyName=key_name)
            pem_content = key_pair['KeyMaterial']
            os.makedirs("static", exist_ok=True)
            key_file = os.path.join("static", f"{key_name}.pem")
            with os.fdopen(os.open(key_file, os.O_WRONLY | os.O_CREAT, 0o400), 'w') as f:
                f.write(pem_content)
        if not name:
            raise Exception("Missing instance name. Possibly auto-run from invalid fallback.")
        else:
            raise RuntimeError(f"Key pair error: {e}")

    if not security_group_id:
        sg = ec2_client.create_security_group(
            Description="Auto-created by CloudBuddy",
            GroupName=f"cloudbuddy-sg-{datetime.utcnow().strftime('%H%M%S')}",
            VpcId=ec2_client.describe_subnets(SubnetIds=[subnet_id])['Subnets'][0]['VpcId']
        )
        security_group_id = sg['GroupId']
        ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}
            ]
        )

    # Private subnet detection logic
    try:
        route_table_response = ec2_client.describe_route_tables(
            Filters=[{"Name": "association.subnet-id", "Values": [subnet_id]}]
        )
        has_igw = any(
            "GatewayId" in route and route["GatewayId"].startswith("igw-")
            for rt in route_table_response.get("RouteTables", [])
            for route in rt.get("Routes", [])
        )
        if not has_igw:
            logger.warning(f"Private subnet detected: {subnet_id}. Consider using NAT Gateway or SSM Session Manager.")
    except Exception:
        pass  # Route table logic isn't critical

    instance_params = {
        "ImageId": ami_id,
        "InstanceType": instance_type,
        "KeyName": key_name,
        "MinCount": 1,
        "MaxCount": 1,
        "UserData": BOOTSTRAP_SCRIPTS.get(bootstrap_script_name, ""),
        "NetworkInterfaces": [{
            "AssociatePublicIpAddress": public_ip,
            "DeviceIndex": 0,
            "SubnetId": subnet_id,
            "Groups": [security_group_id]
        }],
        "BlockDeviceMappings": [{
            "DeviceName": "/dev/xvda",
            "Ebs": {
                "VolumeSize": ebs_size,
                "VolumeType": "gp2",
                "DeleteOnTermination": True
            }
        }],
        "TagSpecifications": [{
            "ResourceType": "instance",
            "Tags": all_tags
        }]
    }

    if kwargs.get("use_spot"):
        instance_params["InstanceMarketOptions"] = {
            "MarketType": "spot",
            "SpotOptions": {
                "SpotInstanceType": "one-time",
                "InstanceInterruptionBehavior": "terminate"
            }
        }

    if iam_role:
        try:
            role_name = iam_role.split('/')[-1] if ':' in iam_role else iam_role
            try:
                iam_client.get_instance_profile(InstanceProfileName=role_name)
            except iam_client.exceptions.NoSuchEntityException:
                iam_client.create_instance_profile(InstanceProfileName=role_name)
                iam_client.add_role_to_instance_profile(
                    InstanceProfileName=role_name,
                    RoleName=role_name
                )
            iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
            )
            instance_params["IamInstanceProfile"] = {"Name": role_name}
        except botocore.exceptions.ClientError as e:
            raise ValueError(f"IAM Role/Profile '{iam_role}' is invalid or does not exist: {e}")

    # ✅ Launch instance now
    try:
        response = ec2_client.run_instances(**instance_params)
        instance_id = response['Instances'][0]['InstanceId']

        # ✅ Apply termination protection if requested
        if termination_protection:
            ec2_client.modify_instance_attribute(
                InstanceId=instance_id,
                DisableApiTermination={'Value': True}
            )

        # ✅ Allocate and attach Elastic IP (now that we have instance_id)
        if kwargs.get("elastic_ip"):
            if not public_ip:
                raise ValueError("Elastic IP requires public_ip=True")
            allocation = ec2_client.allocate_address(Domain='vpc')
            ec2_client.associate_address(
                InstanceId=instance_id,
                AllocationId=allocation['AllocationId']
            )

        cost_est = estimate_instance_cost(instance_type)
        return {
            "Name": name,
            "InstanceId": instance_id,
            "InstanceType": instance_type,
            "SubnetId": subnet_id,
            "SecurityGroupId": security_group_id,
            "KeyPair": key_name,
            "PEMFilePath": key_file,
            "PEMContent": pem_content,
            "ExistingKey": existing_key,
            "EstimatedCost": cost_est
        }
    except botocore.exceptions.ClientError as e:
        raise RuntimeError(f"Failed to create EC2 instance: {e}")



def list_instance_profiles(region_name=_region):
    iam_client = boto3.client("iam", region_name=region_name)
    try:
        profiles = []
        paginator = iam_client.get_paginator("list_instance_profiles")
        for page in paginator.paginate():
            for profile in page["InstanceProfiles"]:
                profiles.append(profile["InstanceProfileName"])
        return profiles
    except Exception as e:
        return [f"Error listing instance profiles: {e}"]
    
def stop_instance(instance_id: str, region_name=_region):
    ec2_client = boto3.client("ec2", region_name=region_name)
    try:
        ec2_client.stop_instances(InstanceIds=[instance_id])
        return f"Stop request sent for instance **{instance_id}**."
    except botocore.exceptions.ClientError as e:
        return f"Error stopping instance: {e}"

class StopEC2Input(BaseModel):
    instance_id: str = Field(..., description="Instance ID to stop")

class StopEC2Tool(BaseTool):
    name: str = "stop_ec2_instance"
    description: str = "Stop an EC2 instance by ID."
    args_schema: Type[BaseModel] = StopEC2Input

    def _run(self, instance_id: str):
        return stop_instance(instance_id)

    async def _arun(self, *args, **kwargs):
        raise NotImplementedError("StopEC2Tool does not support async")

def start_instance(instance_id: str, region_name=_region):
    ec2_client = boto3.client("ec2", region_name=region_name)
    try:
        ec2_client.start_instances(InstanceIds=[instance_id])
        return f"Start request sent for instance **{instance_id}**."
    except botocore.exceptions.ClientError as e:
        return f"Error starting instance: {e}"

class StartEC2Input(BaseModel):
    instance_id: str = Field(..., description="Instance ID to start")

class StartEC2Tool(BaseTool):
    name: str = "start_ec2_instance"
    description: str = "Start an EC2 instance by ID."
    args_schema: Type[BaseModel] = StartEC2Input

    def _run(self, instance_id: str):
        return start_instance(instance_id)

    async def _arun(self, *args, **kwargs):
        raise NotImplementedError("StartEC2Tool does not support async")


def list_instances(region_name=_region):
    ec2_client = boto3.client("ec2", region_name=region_name)
    try:
        response = ec2_client.describe_instances()
        instances_info = []
        for reservation in response.get("Reservations", []):
            for inst in reservation.get("Instances", []):
                state = inst.get("State", {}).get("Name")
                inst_id = inst.get("InstanceId")
                instances_info.append(f"- {inst_id} ({state})")
        return "\n".join(instances_info) if instances_info else "No instances found."
    except botocore.exceptions.ClientError as e:
        return f"Error listing instances: {e}"

def terminate_instance(instance_id: str, region_name=_region):
    ec2_client = boto3.client("ec2", region_name=region_name)
    try:
        ec2_client.terminate_instances(InstanceIds=[instance_id])
        return f"Termination initiated for instance **{instance_id}**."
    except botocore.exceptions.ClientError as e:
        return f"Error terminating instance: {e}"

# CrewAI Tools

class CreateEC2Input(BaseModel):
    name: str = Field("", description="EC2 instance name tag")
    instance_type: str = Field(..., description="EC2 instance type (e.g., t2.micro)")
    ami_id: str = Field("", description="AMI ID or 'default'")
    key_name: str = Field("", description="Key Pair Name (optional, auto-generated if blank)")
    security_group_id: str = Field("", description="Security Group ID (optional, auto-created if blank)")
    subnet_id: str = Field(..., description="Subnet ID")
    ebs_size: int = Field(8, description="EBS volume size in GB")
    iam_role: str = Field("", description="IAM Role Name or ARN (optional)")
    public_ip: bool = Field(True, description="Assign public IP to the instance?")
    termination_protection: bool = Field(False, description="Enable termination protection?")
    bootstrap_script_name: str = Field("None", description="Name of bootstrap script to run (e.g., Install Apache)")
    elastic_ip: bool = Field(False, description="Allocate and associate an Elastic IP?")
    custom_tags: dict = Field(default_factory=dict, description="Custom tags as key-value pairs (e.g., {'Env': 'Dev'})")
    asg_name: str = Field("", description="Name of Auto Scaling Group (optional)")




class CreateEC2Tool(BaseTool):
    name: str = "create_ec2_instance"
    description: str = "Create an EC2 instance with extended parameters including IAM, public IP, scripts, and protection."
    args_schema: Type[BaseModel] = CreateEC2Input
    use_spot: bool = Field(False, description="Launch as Spot instance?")

    def _run(self, **kwargs):
        return create_instance(**kwargs)

    async def _arun(self, *args, **kwargs):
        raise NotImplementedError("CreateEC2Tool does not support async")


class ListEC2Tool(BaseTool):
    name: str = "list_ec2_instances"
    description: str = "List all EC2 instances."

    def _run(self):
        return list_instances()

    async def _arun(self, *args, **kwargs):
        raise NotImplementedError("ListEC2Tool does not support async")


class TerminateEC2Input(BaseModel):
    instance_id: str = Field(..., description="EC2 Instance ID to terminate")

class TerminateEC2Tool(BaseTool):
    name: str = "terminate_ec2_instance"
    description: str = "Terminate EC2 instance by ID."
    args_schema: Type[BaseModel] = TerminateEC2Input

    def _run(self, instance_id: str):
        return terminate_instance(instance_id)

    async def _arun(self, *args, **kwargs):
        raise NotImplementedError("TerminateEC2Tool does not support async")
def list_security_groups(region_name=_region):
    ec2 = boto3.client("ec2", region_name=region_name)
    groups = ec2.describe_security_groups()["SecurityGroups"]
    return [{"title": f"{g['GroupName']} ({g['GroupId']})", "value": g["GroupId"]} for g in groups]

def list_subnets(region_name=_region):
    
    ec2 = boto3.client("ec2", region_name=region_name)
    subnets = ec2.describe_subnets()["Subnets"]
    return [{"title": f"{s['SubnetId']} ({s['AvailabilityZone']})", "value": s["SubnetId"]} for s in subnets]

def list_iam_roles(region_name=_region):
    iam = boto3.client("iam", region_name=region_name)
    roles = iam.list_roles()["Roles"]
    return [{"title": role["RoleName"], "value": role["RoleName"]} for role in roles]


