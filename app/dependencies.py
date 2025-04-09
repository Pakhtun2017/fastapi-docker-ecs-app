import aioboto3 
from fastapi import Header, HTTPException

async def get_ec2_client(
    region: str | None = Header(default="us-east-1", description="AWS region to use.")
):
    try:
        session = aioboto3.Session(region_name=region)
        async with session.client("ec2") as client:
            yield client
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not create EC2 client: {str(e)}"
        )
