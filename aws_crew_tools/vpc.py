import os
import boto3
import ipaddress
import logging
from botocore.exceptions import ClientError
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List
import math

logger = logging.getLogger(__name__)
_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

def get_ec2_client(region_name):
    return boto3.client("ec2", region_name=region_name)

def get_available_cidr(existing_vpcs):
    """
    Suggest a non-conflicting 10.x.0.0/16 CIDR.
    """
    used_blocks = [ipaddress.IPv4Network(vpc['CidrBlock']) for vpc in existing_vpcs]
    for i in range(1, 255):
        new_block = ipaddress.IPv4Network(f'10.{i}.0.0/16')
        if all(not new_block.overlaps(block) for block in used_blocks):
            return str(new_block)
    raise ValueError("No available CIDR block found in 10.0.0.0/8")

def estimate_vpc_cost(nat_enabled=False):
    igw_price = 0.00  # IGW is free
    nat_price = 32.40 if nat_enabled else 0.00  # Static estimate per month
    total = igw_price + nat_price
    return f"Estimated monthly cost: ${total:.2f} (IGW + NAT)"

def create_vpc_advanced(vpc_name, cidr_block, region, enable_dns_support=False, enable_dns_hostnames=False, enable_igw=False, enable_nat=False, subnet_requests=None, custom_tags=None, route_table_mode="1"):
    """
    Create a VPC with dynamic subnets and optional IGW/NAT.
    subnet_requests: list of dicts with 'hosts' and 'type' ('public' or 'private').
    """
    if subnet_requests is None:
        subnet_requests = []
    if custom_tags is None:
        custom_tags = {}

    ec2 = boto3.client('ec2', region_name=region)

    vpc = ec2.create_vpc(CidrBlock=cidr_block)
    vpc_id = vpc['Vpc']['VpcId']

    # Enable DNS support/hostnames if requested
    if enable_dns_support:
        ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsSupport={'Value': True})
    if enable_dns_hostnames:
        ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={'Value': True})

    # Tag the VPC
    tags = [{'Key': 'Name', 'Value': vpc_name}]
    tags += [{'Key': k, 'Value': v} for k, v in custom_tags.items()]
    ec2.create_tags(Resources=[vpc_id], Tags=tags)

    # Create and attach Internet Gateway if requested (IGW required for NAT as well)
    igw_id = None
    if enable_igw or enable_nat:
        igw = ec2.create_internet_gateway()
        igw_id = igw['InternetGateway']['InternetGatewayId']
        ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)

    allocated = []
    if subnet_requests:
        net = ipaddress.ip_network(cidr_block)
        # Sort subnets by host count descending for allocation
        sorted_subs = sorted(subnet_requests, key=lambda x: x['hosts'], reverse=True)
        current_addr = net.network_address
        for idx, sub in enumerate(sorted_subs):
            hosts = sub['hosts']
            needed = hosts + 2  # include network/broadcast
            new_prefix = 32 - math.ceil(math.log2(needed))
            if current_addr > net.broadcast_address:
                raise ValueError("Not enough space in VPC for requested subnets.")
            # Align candidate network at or after current_addr
            candidate = ipaddress.IPv4Network(f"{current_addr}/{new_prefix}", strict=False)
            if candidate.network_address < current_addr:
                step = 2 ** (32 - new_prefix)
                base_int = int(current_addr)
                multiple = (base_int // step) * step
                if multiple < base_int:
                    multiple += step
                candidate = ipaddress.IPv4Network((multiple, new_prefix))
            while candidate.network_address < current_addr:
                candidate = ipaddress.IPv4Network((int(candidate.network_address) + 2**(32-new_prefix), new_prefix))
            if candidate.broadcast_address > net.broadcast_address:
                raise ValueError("Not enough space in VPC for requested subnets.")
            # Append allocated subnet with its type
            allocated.append({'network': candidate, 'type': sub['type'], 'id': idx})
            current_addr = candidate.broadcast_address + 1
        # Sort back by original request order if needed
        allocated = sorted(allocated, key=lambda x: x['id'])

        # Create subnets in AWS
    public_subnets = []
    private_subnets = []
    for alloc in allocated:
        net_cidr = str(alloc['network'])
        subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock=net_cidr)
        subnet_id = subnet['Subnet']['SubnetId']
        # Tag each subnet
        ec2.create_tags(Resources=[subnet_id], Tags=[{'Key': 'Name', 'Value': f"{vpc_name}-{net_cidr}"}])
        if alloc['type'] == 'public':
            public_subnets.append(subnet_id)
        else:
            private_subnets.append(subnet_id)

    # Create route tables
    public_rt_id = None
    private_rt_ids = []
    if public_subnets:
        # Public route table for IGW
        rt_pub = ec2.create_route_table(VpcId=vpc_id)
        public_rt_id = rt_pub['RouteTable']['RouteTableId']
        if igw_id:
            ec2.create_route(RouteTableId=public_rt_id, DestinationCidrBlock='0.0.0.0/0', GatewayId=igw_id)
        for sub_id in public_subnets:
            ec2.associate_route_table(SubnetId=sub_id, RouteTableId=public_rt_id)

    if private_subnets:
        if route_table_mode == "separate":
        # Create separate route table per private subnet
            for sub_id in private_subnets:
                rt = ec2.create_route_table(VpcId=vpc_id)
                rt_id = rt['RouteTable']['RouteTableId']
                ec2.associate_route_table(SubnetId=sub_id, RouteTableId=rt_id)
                private_rt_ids.append(rt_id)
        else:
        # Use one shared route table
            rt_priv = ec2.create_route_table(VpcId=vpc_id)
            private_rt_id = rt_priv['RouteTable']['RouteTableId']
            private_rt_ids.append(private_rt_id)
            for sub_id in private_subnets:
                ec2.associate_route_table(SubnetId=sub_id, RouteTableId=private_rt_id)

        # NAT route will be added after NAT creation

    # 🔧 NAT Gateway creation (only once) and routing for all private subnets:
    nat_id = None
    if enable_nat and private_subnets and public_subnets:
        eip = ec2.allocate_address(Domain='vpc')
        nat = ec2.create_nat_gateway(SubnetId=public_subnets[0], AllocationId=eip['AllocationId'])
        nat_id = nat['NatGateway']['NatGatewayId']
        # Wait for NAT to become available (error handling omitted for brevity)
        waiter = ec2.get_waiter('nat_gateway_available')
        waiter.wait(NatGatewayIds=[nat_id])
        for rt_id in private_rt_ids:
            ec2.create_route(RouteTableId=rt_id, DestinationCidrBlock='0.0.0.0/0', NatGatewayId=nat_id)
    # Summary of creation
    summary = {
        'vpc_id': vpc_id,
        'cidr': cidr_block,
        'igw_id': igw_id,
        'subnet_count': len(allocated),
        'nat_gateway': nat_id if nat_id else None
    }
    try:
        return summary   
    except ClientError as e:
        return f"❌ AWS error: {e.response['Error']['Message']}"
    except Exception as e:
        return f"❌ Unexpected error: {e}"

# CrewAI Models

class CreateVPCInput(BaseModel):
    vpc_name: str = Field("", description="Name for the VPC")
    cidr_block: str = Field("", description="CIDR (e.g., 10.0.0.0/16). Leave blank to auto-generate")
    region_name: str = Field("us-east-1", description="AWS region")
    enable_dns_support: bool = Field(True, description="Enable DNS resolution")
    enable_dns_hostnames: bool = Field(True, description="Enable DNS hostnames")
    #auto_subnet: bool = Field(True, description="Auto-create public/private subnets?")
    attach_igw: bool = Field(True, description="Attach Internet Gateway?")
    create_nat: bool = Field(False, description="Create NAT Gateway?")
    custom_tags: dict = Field(default_factory=dict, description="Custom tags (e.g., Env=Dev,Project=Cloud)")
    subnet_requests: List[dict] = Field(default_factory=list, description="List of subnets with host count and type")
    route_table_mode: str = Field("1", description="Route table setup: '1' (shared) or 'separate'")

class CreateVPCTool(BaseTool):
    name: str = "create_vpc"
    description: str = "Create an advanced VPC with custom CIDR, DNS options, subnets, IGW/NAT, and tags"
    args_schema: Type[BaseModel] = CreateVPCInput

    def _run(self, **kwargs):
        return create_vpc_advanced(**kwargs)

    async def _arun(self, *args, **kwargs):
        raise NotImplementedError("CreateVPCTool does not support async")

class ListVPCsTool(BaseTool):
    name: str = "list_vpcs"
    description: str = "List all VPCs and their CIDR blocks"

    def _run(self):
        ec2 = get_ec2_client(_region)
        try:
            response = ec2.describe_vpcs()
            vpcs = response.get("Vpcs", [])
            if not vpcs:
                return "No VPCs found."
            result = ""
            for v in vpcs:
                vid = v.get("VpcId")
                cidr = v.get("CidrBlock")
                name = next((t["Value"] for t in v.get("Tags", []) if t.get("Key") == "Name"), "")
                result += f"- {vid} ({cidr}){' – ' + name if name else ''}\n"
            return result
        except ClientError as e:
            return f"Error listing VPCs: {e.response['Error']['Message']}"

    async def _arun(self, *args, **kwargs):
        raise NotImplementedError("ListVPCsTool does not support async")
