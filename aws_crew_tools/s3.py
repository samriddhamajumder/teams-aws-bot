import boto3
import logging
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
from crewai.tools import BaseTool
from typing import Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

def create_s3_bucket(bucket_name, region, versioning=False, encryption="none", block_public_access=True, tags=None):
    try:
        s3_client = boto3.client("s3", region_name=region)

        create_params = {"Bucket": bucket_name}
        if region != "us-east-1":
            create_params["CreateBucketConfiguration"] = {"LocationConstraint": region}

        s3_client.create_bucket(**create_params)

        if versioning:
            s3_client.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={"Status": "Enabled"}
            )

        if encryption == "AES256":
            s3_client.put_bucket_encryption(
                Bucket=bucket_name,
                ServerSideEncryptionConfiguration={
                    "Rules": [{
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256"
                        }
                    }]
                }
            )

        if block_public_access:
            s3_client.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True
                }
            )

        if tags:
            tag_set = [{"Key": kv.split("=")[0], "Value": kv.split("=")[1]} for kv in tags.split(",") if "=" in kv]
            s3_client.put_bucket_tagging(
                Bucket=bucket_name,
                Tagging={"TagSet": tag_set}
            )

        return True, f"✅ Bucket `{bucket_name}` created successfully in region `{region}`."

    except ClientError as e:
        logger.error(e)
        return False, f"❌ Error creating bucket: {e}"


def list_s3_objects(bucket_name, prefix=""):
    try:
        s3_client = boto3.client("s3")
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

        if "Contents" not in response:
            return True, []

        objects = [obj["Key"] for obj in response["Contents"]]
        return True, objects

    except ClientError as e:
        logger.error(e)
        return False, f"❌ Error listing objects: {e}"
    
def list_s3_buckets():
    try:
        s3_client = boto3.client("s3")
        response = s3_client.list_buckets()

        buckets = []
        for b in response["Buckets"]:
            region = s3_client.get_bucket_location(Bucket=b["Name"])["LocationConstraint"] or "us-east-1"
            creation_time = b["CreationDate"].strftime("%Y-%m-%d %H:%M")
            buckets.append({
                "name": b["Name"],
                "region": region,
                "created": creation_time
            })
        return True, buckets
    except ClientError as e:
        logger.error(e)
        return False, f"❌ Error listing buckets: {e}"




def upload_file_to_s3(bucket_name, file_bytes, file_name, prefix="", acl="private", storage_class="STANDARD"):
    try:
        s3_client = boto3.client("s3")
        s3_key = f"{prefix}{file_name}" if prefix else file_name

        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=file_bytes,
            ACL=acl,
            StorageClass=storage_class
        )

        return True, f"✅ File `{file_name}` uploaded to `{bucket_name}/{s3_key}` with ACL `{acl}` and storage class `{storage_class}`."

    except ClientError as e:
        logger.error(e)
        return False, f"❌ Error uploading file: {e}"


def generate_presigned_download_url(bucket_name, object_key, expires_in=3600):
    try:
        s3_client = boto3.client("s3")
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": object_key},
            ExpiresIn=expires_in
        )
        return True, url

    except ClientError as e:
        logger.error(e)
        return False, f"❌ Error generating download URL: {e}"


class CreateBucketTool(BaseTool):
    name: str = "CreateS3Bucket"
    description: str = "Creates a new S3 bucket with optional versioning and encryption."

    def _run(self, **kwargs) -> str:
        bucket_name = kwargs.get("bucket_name")
        region = kwargs.get("region", "us-east-1")
        versioning = kwargs.get("versioning", False)
        encryption = kwargs.get("encryption", "none")
        block_public_access = kwargs.get("block_public_access", True)
        tags = kwargs.get("tags", "")

        success, message = create_s3_bucket(
            bucket_name, region, versioning, encryption, block_public_access, tags
        )
        return message


class ListObjectsInBucketTool(BaseTool):
    name: str = "ListObjectsInBucket"
    description: str = "Lists all objects inside a specific S3 bucket."

    def _run(self, **kwargs) -> str:
        bucket_name = kwargs.get("bucket_name")
        if not bucket_name:
            return "❌ Please provide the 'bucket_name'."

        prefix = kwargs.get("prefix", "")
        success, result = list_s3_objects(bucket_name, prefix)
        
        if not success:
            return result

        if not result:
            return f"⚠️ No files found in bucket `{bucket_name}`."

        return f"📄 Files in `{bucket_name}`:\n" + "\n".join(f"- {obj}" for obj in result)
    
class ListS3BucketsTool(BaseTool):
    name: str = "ListS3Buckets"
    description: str = "Lists all S3 buckets in the account."

    def _run(self, **kwargs) -> str:
        success, buckets = list_s3_buckets()
        if not success:
            return buckets

        return "\n".join(
            f"- {b['name']} (Region: {b['region']}, Created: {b['created']})"
            for b in buckets
        )


    
class TerminateBucketTool(BaseTool):
    name: str = "TerminateS3Bucket"
    description: str = "Deletes an S3 bucket and all its contents."

    def _run(self, **kwargs) -> str:
        bucket_name = kwargs.get("bucket_name")
        if not bucket_name:
            return "❌ Please provide the 'bucket_name' to delete."

        s3 = boto3.resource("s3")
        bucket = s3.Bucket(bucket_name)

        try:
            # Check if the bucket exists
            bucket.load()

            # Empty the bucket (delete all objects)
            bucket.objects.all().delete()

            # Delete the bucket itself
            bucket.delete()

            return f"✅ Bucket `{bucket_name}` and all its contents have been deleted."
        except ClientError as e:
            return f"❌ Failed to delete bucket `{bucket_name}`: {e}"