"""Optional AWS configuration and connectivity status endpoint."""

from __future__ import annotations

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter

from app.config import get_settings
from app.services.dynamodb_service import DynamoDBService
from app.services.s3_storage_service import APPROVED_AWS_REGION, S3ConfigurationError, S3StorageService

router = APIRouter()


def _error_code(error: Exception) -> str:
    if isinstance(error, ClientError):
        code = str(error.response.get("Error", {}).get("Code", "AWSClientError"))
        return "permission_denied" if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"} else code
    if isinstance(error, BotoCoreError):
        return "credentials_or_connection_unavailable"
    if isinstance(error, S3ConfigurationError):
        return "invalid_configuration"
    return "aws_unavailable"


@router.get("/status")
def aws_status() -> dict[str, object]:
    settings = get_settings()
    bucket_configured = bool(settings.urbanlens_s3_bucket)
    function_configured = bool(settings.urbanlens_lambda_function)
    table_configured = bool(settings.urbanlens_dynamodb_table)
    api_configured = bool(settings.urbanlens_api_gateway_id or settings.urbanlens_api_gateway_url)
    status: dict[str, object] = {
        "configured": bucket_configured and function_configured and table_configured,
        "region": settings.aws_region,
        "profile": settings.aws_profile,
        "s3": {
            "bucket": settings.urbanlens_s3_bucket,
            "configured": bucket_configured,
            "reachable": None,
            "error": None,
        },
        "lambda": {
            "function_name": settings.urbanlens_lambda_function,
            "configured": function_configured,
            "exists": None,
            "runtime": None,
            "handler": None,
            "error": None,
        },
        "dynamodb": {
            "configured": table_configured,
            "table": settings.urbanlens_dynamodb_table,
            "exists": None,
            "status": None,
            "item_count": None,
            "error": None,
        },
        "bedrock": {
            "configured": bool(settings.bedrock_inference_profile),
            "region": settings.aws_region,
            "inference_profile": settings.bedrock_inference_profile,
            "lambda_enabled": settings.urbanlens_lambda_bedrock_enabled,
        },
        "api_gateway": {
            "configured": api_configured,
            "api_id": settings.urbanlens_api_gateway_id,
            "url": settings.urbanlens_api_gateway_url,
            "exists": None,
            "error": None,
        },
        "cloudwatch": {
            "configured": function_configured,
            "log_group": f"/aws/lambda/{settings.urbanlens_lambda_function}" if function_configured else None,
            "log_group_exists": None,
            "error": None,
        },
    }
    if settings.aws_region != APPROVED_AWS_REGION:
        status["configuration_error"] = f"AWS_REGION must be {APPROVED_AWS_REGION}."
        return status

    if bucket_configured:
        try:
            S3StorageService().head_bucket()
            status["s3"]["reachable"] = True
        except Exception as exc:
            status["s3"]["reachable"] = False
            status["s3"]["error"] = _error_code(exc)

    if function_configured:
        try:
            session = boto3.Session(profile_name=settings.aws_profile or None, region_name=settings.aws_region)
            function = session.client("lambda").get_function_configuration(
                FunctionName=settings.urbanlens_lambda_function
            )
            status["lambda"].update({
                "exists": True,
                "runtime": function.get("Runtime"),
                "handler": function.get("Handler"),
            })
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", "AWSClientError"))
            status["lambda"]["exists"] = False if code in {"ResourceNotFoundException", "404"} else None
            status["lambda"]["error"] = _error_code(exc)
        except Exception as exc:
            status["lambda"]["error"] = _error_code(exc)

    if table_configured:
        try:
            status["dynamodb"].update(DynamoDBService().get_status())
        except Exception as exc:
            status["dynamodb"]["error"] = _error_code(exc)

    if settings.urbanlens_api_gateway_id:
        try:
            session = boto3.Session(profile_name=settings.aws_profile or None, region_name=settings.aws_region)
            api = session.client("apigatewayv2").get_api(ApiId=settings.urbanlens_api_gateway_id)
            status["api_gateway"].update({"exists": True, "url": api.get("ApiEndpoint")})
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", "AWSClientError"))
            status["api_gateway"]["exists"] = False if code in {"NotFoundException", "NotFound"} else None
            status["api_gateway"]["error"] = _error_code(exc)
        except Exception as exc:
            status["api_gateway"]["error"] = _error_code(exc)

    if function_configured:
        try:
            session = boto3.Session(profile_name=settings.aws_profile or None, region_name=settings.aws_region)
            groups = session.client("logs").describe_log_groups(
                logGroupNamePrefix=f"/aws/lambda/{settings.urbanlens_lambda_function}",
                limit=10,
            ).get("logGroups", [])
            status["cloudwatch"]["log_group_exists"] = any(
                group.get("logGroupName") == status["cloudwatch"]["log_group"] for group in groups
            )
        except Exception as exc:
            status["cloudwatch"]["error"] = _error_code(exc)
    return status