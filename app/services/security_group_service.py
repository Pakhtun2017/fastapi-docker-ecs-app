import logging
from fastapi import HTTPException 
from botocore.exceptions import ClientError, NoCredentialsError
import aioboto3 
import asyncio
import json

from typing import List

# Configure logging for the integration test.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(funcName)s: %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

async def describe_instances_with_retry(ec2_client, instance_ids, max_attempts: int = 5, initial_delay: float = 1.0):
    """
    Attempts to call ec2_client.describe_instances with exponential backoff.
    :param ec2_client: The AWS EC2 client.
    :param instance_ids: List of instance IDs to describe.
    :param max_attempts: Maximum number of retry attempts.
    :param initial_delay: Initial delay in seconds before retrying.
    :return: The response from ec2_client.describe_instances.
    :raises Exception: If all attempts fail.
    """
    delay = initial_delay
    attempt = 0
    while attempt < max_attempts:
        try:
            response = await ec2_client.describe_instances(InstanceIds=instance_ids)
            if response.get('Reservations') and response['Reservations'][0].get('Instances'):
                return response
            else:
                # If the expected data is missing, raise an exception to trigger a retry.
                raise ValueError("Instance data not available yet")
        except Exception as e:
            attempt += 1
            logging.warning(f"Attempt {attempt} failed with error: {e}. Retrying in {delay} seconds...")
            if attempt >= max_attempts:
                logging.error("Maximum retry attempts reached. Giving up.")
                raise e
            await asyncio.sleep(delay)
            delay *= 2  # Exponential backoff: double the delay on each retry

def rule_exists(desired_rule: dict, existing_rules: List[dict]) -> bool:
    """
    Checks if a desired security group rule exists within a list of existing rules.
    Args:
        desired_rule (dict): The security group rule to check for. It should contain the keys:
            - "IpProtocol" (str): The IP protocol (e.g., "tcp", "udp").
            - "FromPort" (int): The starting port of the rule.
            - "ToPort" (int): The ending port of the rule.
            - "IpRanges" (list): A list of IP ranges (e.g., [{"CidrIp": "0.0.0.0/0"}]).
        existing_rules (List[dict]): A list of existing security group rules, where each rule is a dictionary
            with the same structure as `desired_rule`.
    Returns:
        bool: True if the desired rule exists in the list of existing rules, False otherwise.
    """
    for existing in existing_rules:
        if (desired_rule.get("IpProtocol") == existing.get("IpProtocol") and
            desired_rule.get("FromPort") == existing.get("FromPort") and
            desired_rule.get("ToPort") == existing.get("ToPort") and
            desired_rule.get("IpRanges") == existing.get("IpRanges")):
            return True
    return False


async def create_security_group(ec2_client, group_name: str, group_description: str) -> str:
    """
    Asynchronously creates or retrieves an AWS EC2 Security Group.
    This function checks if a Security Group with the specified name already exists.
    If it exists, the function retrieves and returns its Group ID. If it does not exist,
    a new Security Group is created with the provided name and description, and its
    Group ID is returned.
    Args:
        ec2_client: An asynchronous AWS EC2 client instance.
        group_name (str): The name of the Security Group to create or retrieve.
        group_description (str): A description for the Security Group (used only if creating a new one).
    Returns:
        str: The Group ID of the created or retrieved Security Group.
    Raises:
        HTTPException: If AWS credentials are missing or invalid, if a client error occurs,
                       or if an unexpected error occurs during the operation.
    """
    try:
        logging.info("Retrieving existing Security Groups.")
        existing_sg_response = await ec2_client.describe_security_groups()
        existing_sg_names = [
            sg['GroupName'] 
            for sg in existing_sg_response.get('SecurityGroups', [])
        ]
        
        if group_name not in existing_sg_names:
            response = await ec2_client.create_security_group(
                GroupName=group_name, 
                Description=group_description
            )
            group_id = response["GroupId"]
        else:
            logging.info(f"Security Group '{group_name}' already exists; reusing it.")
            group_id = next(
                (
                    sg['GroupId'] 
                    for sg in existing_sg_response["SecurityGroups"] 
                    if group_name == sg["GroupName"]
                ), 
                None
            )
        return group_id
    
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


async def authorize_ingress(ec2_client,group_id: str,ip_permissions: List[dict]):
    """
    Authorize ingress rules for a specified security group in AWS EC2.
    This function checks the existing ingress rules of a security group and adds any missing rules 
    from the provided `ip_permissions` list. If the security group already contains all the desired 
    rules, no changes are made.
    Args:
        ec2_client: An asynchronous AWS EC2 client instance.
        group_id (str): The ID of the security group to modify.
        ip_permissions (List[dict]): A list of desired ingress rules to authorize. Each rule should 
            follow the AWS EC2 IpPermissions format.
    Returns:
        List[dict]: A list of the authorized ingress rules for the security group.
    Raises:
        HTTPException: If the security group is not found (404), if there is an issue with AWS 
            credentials (400), if a client error occurs (400), or if an unexpected error occurs (500).
    """
    
    try:
        logging.info("Retrieve all existing security groups.")
        existing_sg_response = await ec2_client.describe_security_groups()
        
        # Find the security group with the given group_id.
        sg = next((sg for sg in existing_sg_response.get('SecurityGroups', []) if sg.get('GroupId') == group_id), None)
        if sg is None:
            logging.error(f"Security group {group_id} not found.")
            raise HTTPException(status_code=404, detail=f"Security group {group_id} not found.")
        
        logging.info(f"Extracting existing security group permissions from the security group {group_id}")
        existing_rules = sg.get('IpPermissions', [])
        
        # Build a list of desired rules that are missing.
        missing_rules = []
        for desired_rule in ip_permissions:
            logging.info("Checking to see if the security group rule is not already in the existing security group rules.")
            if not rule_exists(desired_rule, existing_rules):
                missing_rules.append(desired_rule)
        
        if missing_rules:
            logging.info(f"Adding missing security group rules to the security group {group_id}.")
            authorized_ingress = await ec2_client.authorize_security_group_ingress(
                GroupId=group_id, 
                IpPermissions=missing_rules
            )
        else: 
            logging.info(f"Security group {group_id} already has all desired ingress rules.")
            authorized_ingress = existing_rules
        
        return authorized_ingress

    except NoCredentialsError:
        logging.exception("Error: AWS credentials not found or are invalid.")
        raise HTTPException(status_code=400, detail="AWS credentials error")
    except ClientError:
        logging.exception("A client error occurred:")
        raise HTTPException(status_code=400, detail="AWS client error")
    except Exception as e:
        logging.exception("An unexpected error occurred: %s", e)
        raise HTTPException(status_code=500, detail="Unexpected error")
    

async def attach_security_group(ec2_client,group_id: str,instance_id: str):
    """
    Attach a security group to an EC2 instance.
    This function retrieves the current security groups attached to the specified EC2 instance,
    checks if the provided security group is already attached, and attaches it if not. It ensures
    that the AWS limit of 5 security groups per instance is not exceeded.
    Args:
        ec2_client: An asynchronous boto3 EC2 client instance.
        group_id (str): The ID of the security group to attach.
        instance_id (str): The ID of the EC2 instance to which the security group will be attached.
    Returns:
        dict: The response from the `modify_instance_attribute` API call.
    Raises:
        HTTPException: If AWS credentials are missing or invalid, if a client error occurs, 
                       if the AWS limit of 5 security groups per instance is exceeded, 
                       or if an unexpected error occurs.
    """
    
    try:
        # Retrieve current security groups for the instance
        response = await describe_instances_with_retry(ec2_client, [instance_id])
        instance = response['Reservations'][0]['Instances'][0]
        current_sg_ids = [sg['GroupId'] for sg in instance['SecurityGroups']]
        
        if group_id not in current_sg_ids:
            if len(current_sg_ids) < 5:  # AWS limit for security groups per instance
                current_sg_ids.append(group_id)
            else:
                logging.error("Cannot attach security group. AWS limit of 5 security groups per instance exceeded.")
                raise HTTPException(status_code=400, detail="AWS limit of 5 security groups per instance exceeded.")
        response = await ec2_client.modify_instance_attribute(
            InstanceId=instance_id,
            Groups=current_sg_ids           
        )
        return response
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
    
    