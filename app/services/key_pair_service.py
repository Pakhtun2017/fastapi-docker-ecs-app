import logging
from fastapi import HTTPException 
from botocore.exceptions import ClientError, NoCredentialsError
import aioboto3 

# Configure logging for the integration test.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(funcName)s: %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

async def create_keypair(ec2_client, key_name):
    """
    Asynchronously creates an EC2 key pair if it does not already exist.
    This function checks for the existence of a specified EC2 key pair. If the key pair
    does not exist, it creates a new one, saves the private key material to a `.pem` file
    with secure permissions, and returns the key name. If the key pair already exists,
    it logs the information and returns the key name.
    Args:
        ec2_client (botocore.client.EC2): An asynchronous EC2 client instance used to
            interact with AWS EC2 services.
        key_name (str): The name of the key pair to create or check for existence.
    Returns:
        str: The name of the key pair, whether newly created or already existing.
    Raises:
        botocore.exceptions.BotoCoreError: If there is an error with the AWS EC2 client.
        botocore.exceptions.ClientError: If there is an error in the AWS EC2 API call.
    Side Effects:
        - Creates a `.pem` file containing the private key material if a new key pair is created.
        - Changes the file permissions of the `.pem` file to read-only for security.
    Note:
        - The file operations for saving the private key are synchronous.
        - Ensure that the AWS credentials and permissions allow for the creation of key pairs.
    """

    key_pairs_response = await ec2_client.describe_key_pairs()
    existing_keys = [kp['KeyName'] for kp in key_pairs_response.get('KeyPairs', [])]
    
    # Check if the desired key pair does not already exist.
    if key_name not in existing_keys:
        # Create a new key pair if it doesn't exist.
        key_response = await ec2_client.create_key_pair(KeyName=key_name)
        # Extract the private key material from the response.
        key_material = key_response.get('KeyMaterial')
        # Save the private key to a file. This file operation is synchronous.
        filename = f"{key_name}.pem"
        with open(filename, "w") as key_file:
            key_file.write(key_material)
        # Change file permissions to read-only for security.
        import os
        os.chmod(filename, 0o400)
        # Return the key name as confirmation that it was created.
        return key_name
        # NOTE: The following logging statement will never be reached because it's after the return.
        logging.info(f"Created and saved key pair: {key_name}")
    else:
        # Log that the key pair already exists.
        logging.info(f"Key pair '{key_name}' already exists; reusing it.")
        # Consider returning the key_name here as well if needed.
        return key_name

