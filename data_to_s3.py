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


# Example usage
if __name__ == "__main__":
    # Get configuration from environment variables
    LOCAL_PDF_PATH = os.getenv('PDF_FILE_PATH')
    BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
    S3_FILE_NAME = "pdfs/AWSGuide.pdf"  # Upload to pdfs/ folder
    
    # Get AWS credentials from environment variables
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.getenv('AWS_DEFAULT_REGION')
    
    # Upload the file using environment variables
    upload_pdf_to_s3(
        LOCAL_PDF_PATH, 
        BUCKET_NAME, 
        S3_FILE_NAME,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )