from fastapi import APIRouter, Depends 
from app.models.instance_models import InstanceRequest, InstanceResponse, TerminateRequest
from app.services import instance_service
from app.dependencies import get_ec2_client
import logging
import aioboto3 


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(funcName)s: %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

router = APIRouter()

# Define an async POST endpoint for creating EC2 instances.
@router.post("/create-instance", response_model=InstanceResponse)
async def api_create_instance(instance_req: InstanceRequest, ec2_client = Depends(get_ec2_client)):
    """
    Create an EC2 instance using the provided instance request parameters.

    Args:
        instance_req (InstanceRequest): The request object containing details for the EC2 instance creation, 
            such as AMI ID, instance count, key pair, and security group configurations.
        ec2_client (boto3.client, optional): The EC2 client dependency for interacting with AWS EC2. 
            Defaults to the result of `get_ec2_client`.

    Returns:
        InstanceResponse: A response object containing the created instance IDs and their status.

    Raises:
        HTTPException: If there is an error during the instance creation process.
    """
    # Await the asynchronous service call.
    instance_ids = await instance_service.create_instance(
        ec2_client,
        instance_req.ami_id,
        instance_req.min_count,
        instance_req.max_count,
        instance_req.create_key_pair,
        instance_req.key_name,
        instance_req.create_security_group,
        instance_req.security_group_name,
        instance_req.security_group_description,
        instance_req.security_group_rules
    )
    # Return the response data conforming to the InstanceResponse model.
    return InstanceResponse(instance_ids=instance_ids, status="running")

# Define an async POST endpoint for terminating EC2 instances.
@router.delete("/terminate-instance", response_model=InstanceResponse)
async def api_terminate_instance(terminate_req: TerminateRequest,ec2_client = Depends(get_ec2_client)):
    """
    Terminate specified EC2 instances.

    This endpoint handles the termination of one or more EC2 instances by calling
    the appropriate service method. It uses an injected EC2 client dependency
    to interact with AWS EC2.

    Args:
        terminate_req (TerminateRequest): The request object containing the list
            of instance IDs to be terminated.
        ec2_client: The EC2 client dependency, injected via FastAPI's `Depends`.

    Returns:
        InstanceResponse: A response object containing the list of terminated
        instance IDs and their status.

    Raises:
        HTTPException: If the termination process fails or encounters an error.
    """
    # Call your async terminate service
    terminated_instance_ids = await instance_service.terminate_instance(
        ec2_client,
        terminate_req.instance_ids
    )

    # Return the correct status after termination initiation
    return InstanceResponse(instance_ids=terminated_instance_ids, status="terminated")
