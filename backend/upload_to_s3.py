import boto3
from botocore.exceptions import ClientError
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def upload_pdf_to_s3(local_file_path, bucket_name, s3_file_name=None, 
                     aws_access_key_id=None, aws_secret_access_key=None, region_name='us-east-1'):
    """
    Upload a PDF file to an S3 bucket
    
    Args:
        local_file_path: Path to the local PDF file
        bucket_name: Name of the S3 bucket
        s3_file_name: S3 object name. If not specified, local filename is used
        aws_access_key_id: AWS access key (optional, uses default credentials if not provided)
        aws_secret_access_key: AWS secret key (optional)
        region_name: AWS region name (default: us-east-1)
    
    Returns:
        True if file was uploaded successfully, False otherwise
    """
    
    # If S3 file name not specified, use the local filename
    if s3_file_name is None:
        s3_file_name = os.path.basename(local_file_path)
    
    # Create an S3 client with optional credentials
    if aws_access_key_id and aws_secret_access_key:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )
    else:
        s3_client = boto3.client('s3', region_name=region_name)
    
    try:
        # Upload the file
        s3_client.upload_file(
            local_file_path, 
            bucket_name, 
            s3_file_name,
            ExtraArgs={'ContentType': 'application/pdf'}
        )
        print(f"✓ Successfully uploaded {local_file_path} to s3://{bucket_name}/{s3_file_name}")
        return True
        
    except FileNotFoundError:
        print(f"✗ Error: The file {local_file_path} was not found")
        return False
        
    except ClientError as e:
        print(f"✗ Error uploading file: {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upload a PDF to S3")
    parser.add_argument("--file", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--key")
    parser.add_argument("--region", default=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    args = parser.parse_args()
    upload_pdf_to_s3(args.file, args.bucket, args.key, region_name=args.region)
