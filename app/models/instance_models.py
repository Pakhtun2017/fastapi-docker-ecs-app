from pydantic import BaseModel # type: ignore
from typing import Optional, List

# This model represents a single security group rule.
# It defines the protocol, port range, and allowed IP ranges for inbound traffic.
class SecurityGroupRule(BaseModel):
    ip_protocol: str
    from_port: int
    to_port: int
    ip_ranges: Optional[List[str]] = None

# Pydantic model for the incoming request body.
# It defines the expected JSON structure (fields, defaults, and types).
class InstanceRequest(BaseModel):
    ami_id: str = 'ami-02a53b0d62d37a757'
    min_count: int = 1
    max_count: int = 1
    create_key_pair: bool = False
    key_name: Optional[str] = None
    create_security_group: bool = False
    security_group_name: Optional[str] = None
    security_group_description: Optional[str] = None
    security_group_rules: Optional[List[SecurityGroupRule]]
    

# Pydantic model for the response.
# This model will be used to validate and document the JSON response.
class InstanceResponse(BaseModel):
    instance_ids: list[str]
    status: str


class TerminateRequest(BaseModel):
    instance_ids: list[str]