import logging
from fastapi import HTTPException 
from botocore.exceptions import ClientError, NoCredentialsError
import aioboto3  
from .security_group_service import create_security_group, authorize_ingress, attach_security_group
from .key_pair_service import create_keypair
from app.config.config import FEATURE_SECURITY_GROUPS


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(funcName)s: %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

async def create_instance(
    ec2_client, 
    ami_id: str, 
    min_count: int, 
    max_count: int, 
    create_key_pair: bool, 
    key_name: str,
    create_sg: bool,
    security_group_name: str,
    security_group_description: str,
    security_group_rules                          
) -> list[str]:
    """
    Asynchronously creates one or more EC2 instances with optional configurations for security groups and key pairs.
    Args:
        ec2_client: The boto3 EC2 client object used to interact with AWS EC2.
        ami_id (str): The ID of the Amazon Machine Image (AMI) to use for the instance(s).
        min_count (int): The minimum number of instances to launch. Defaults to 1 if not provided.
        max_count (int): The maximum number of instances to launch. Defaults to 1 if not provided.
        create_key_pair (bool): Whether to create a new key pair for the instance(s).
        key_name (str): The name of the key pair to create or use.
        create_sg (bool): Whether to create a new security group for the instance(s).
        security_group_name (str): The name of the security group to create.
        security_group_description (str): A description for the security group.
        security_group_rules: A list of rules to apply to the security group. Each rule should include:
            - ip_protocol (str): The IP protocol (e.g., 'tcp', 'udp', 'icmp').
            - from_port (int): The starting port for the rule.
            - to_port (int): The ending port for the rule.
            - ip_ranges (list[str]): A list of CIDR IP ranges to allow.
    Returns:
        list[str]: A list of instance IDs for the created EC2 instances.
    Raises:
        HTTPException: If AWS credentials are missing or invalid, a client error occurs, or an unexpected error occurs.
    """

    try:
        
        params = {
            "ImageId": ami_id,
            "MinCount": min_count or 1,
            "MaxCount": max_count or 1,
            "InstanceType": 't2.micro'
        }

        # --- Security Group Creation Block ---
        if FEATURE_SECURITY_GROUPS and create_sg:
            logging.info("Creating security group")
            group_id = await create_security_group(
                                ec2_client, 
                                security_group_name, 
                                security_group_description
            )

            ip_permissions = []
            for rule in security_group_rules:
                ip_ranges = [{"CidrIp": ip} for ip in rule.ip_ranges] if rule.ip_ranges else []
                ip_permission = {
                    "IpProtocol": rule.ip_protocol,
                    "FromPort": rule.from_port,
                    "ToPort": rule.to_port,
                    "IpRanges": ip_ranges,
                }
                ip_permissions.append(ip_permission)

            await authorize_ingress(
                ec2_client,
                group_id=group_id,
                ip_permissions=ip_permissions
            )
        
        # --- Key Pair Creation Block ---
        if create_key_pair:
            key_name = await create_keypair(ec2_client, key_name)
            params["KeyName"] = key_name
            
        # --- EC2 Instance Creation Block ---
        logging.info("Creating the EC2 instance")
        new_instances = await ec2_client.run_instances(**params)
        
        # Extract the instance IDs from the response.
        # Loop over the list of instances in the response.
        instance_ids = [
            instance.get('InstanceId') 
            for instance in new_instances['Instances']
        ]
        if FEATURE_SECURITY_GROUPS and create_sg:
            for instance_id in instance_ids:
                logging.info("Attaching security group to the instance")
                await attach_security_group(ec2_client, group_id=group_id, instance_id=instance_id)
        
        # Get a waiter object to check when the instances reach the 'running' state.
        waiter = ec2_client.get_waiter('instance_running')
        # Await the waiter until the specified instances are running.
        await waiter.wait(InstanceIds=instance_ids)
        
        # Log a success message with the list of created instance IDs.
        logging.info(f"Successfully created instances: {', '.join(instance_ids)}")
        # Return the list of instance IDs.
        return instance_ids

    # --- Error Handling ---
    except NoCredentialsError:
        logging.exception("Error: AWS credentials not found or are invalid.")
        raise HTTPException(status_code=400, detail="AWS credentials error")
    except ClientError:
        logging.exception("A client error occurred:")
        raise HTTPException(status_code=400, detail="AWS client error")
    except Exception as e:
        logging.exception("An unexpected error occurred:")
        raise HTTPException(status_code=500, detail="Unexpected error")


async def terminate_instance(ec2_client, instance_ids: list[str]) -> list[str]:
    """
    Asynchronously terminates a list of EC2 instances using the provided EC2 client.
    This function uses aioboto3 to terminate the specified EC2 instances and waits
    for their termination to complete. It handles various exceptions related to AWS
    credentials, client errors, and unexpected issues.
    Args:
        ec2_client: An aioboto3 EC2 client instance used to interact with AWS EC2.
        instance_ids (list[str]): A list of EC2 instance IDs to be terminated.
    Returns:
        list[str]: A list of successfully terminated instance IDs.
    Raises:
        HTTPException: If AWS credentials are invalid or missing, or if an AWS client
                       error or unexpected error occurs.
    """
    
    try:
        logging.info(f"Initiating asynchronous termination for instances: {instance_ids}")
        # Terminate instances asynchronously using aioboto3
        await ec2_client.terminate_instances(InstanceIds=instance_ids)

        # Await the termination confirmation with aioboto3's waiter
        waiter = ec2_client.get_waiter('instance_terminated')
        await waiter.wait(InstanceIds=instance_ids)

        logging.info(f"Successfully terminated instances: {', '.join(instance_ids)}")

        return instance_ids  # Returning IDs directly (simple approach)

    except NoCredentialsError:
        logging.exception("AWS credentials are invalid or missing.")
        raise HTTPException(status_code=400, detail="AWS credentials error")

    except ClientError as e:
        logging.exception("AWS client error: %s", e)
        raise HTTPException(status_code=400, detail=f"AWS client error: {e}")

    except Exception as e:
        logging.exception("Unexpected error occurred: %s", e)
        raise HTTPException(status_code=500, detail="Unexpected error")