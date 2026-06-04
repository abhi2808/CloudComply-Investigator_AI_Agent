"""
Application configuration using Pydantic BaseSettings.
All environment variables are declared here with typed fields.
"""


from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # AWS Configuration
    aws_region: str = Field(default="ap-south-1", description="AWS region for CloudTrail queries")

    # AWS Bedrock — backend credentials (NEVER shared with customer boto3 sessions)
    bedrock_access_key_id: str = Field(default="", description="AWS access key for Bedrock")
    bedrock_secret_access_key: str = Field(default="", description="AWS secret key for Bedrock")
    bedrock_region: str = Field(default="ap-south-1", description="AWS region for Bedrock runtime")
    bedrock_model_id: str = Field(
        default="apac.anthropic.claude-3-5-haiku-20241022-v1:0",
        description="Bedrock cross-region inference model ID (APAC Claude 3.5 Haiku v1)",
    )

    # Application Configuration
    port: int = Field(default=8000, description="Backend server port")
    client_url: str = Field(
        default="http://localhost:5173", description="Frontend client URL for CORS"
    )

    # MongoDB Configuration
    mongodb_uri: str = Field(..., description="MongoDB URI")

    # JWT Authentication
    jwt_secret: str = Field(..., description="JWT Secret For Hashing")
    jwt_expiry_hours: int = Field(default=24, description="JWT Expiry in Hours")

    # AWS Key Encryption
    encryption_secret: str = Field(..., description="Fernet Key Encryption Secret")

    # Microsoft Teams Bot
    teams_app_id: str = Field(default="", description="Azure Bot App (client) ID")
    teams_app_password: str = Field(default="", description="Azure Bot client secret value")
    teams_app_tenant_id: str = Field(default="", description="Azure AD tenant ID")
    # Shared MongoDB account _id used by all Teams users (PoC — single AWS account)
    teams_default_account_id: str = Field(default="", description="MongoDB account _id for Teams queries")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


settings = Settings()
