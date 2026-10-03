"""Run one isolated Nova Lite Converse request using the deployed Lambda role."""

from __future__ import annotations

import argparse
from io import BytesIO
import json
import sys
from uuid import uuid4
import zipfile

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

REGION = "ap-south-1"
PROFILE_ID = "apac.amazon.nova-lite-v1:0"
FUNCTION_NAME = "fai-tce-team11-urbanlens-demo-processor"
EXPECTED_ROLE_ARN = "arn:aws:iam::479903269923:role/FAI-TCE-LambdaExecutionRole"

DIAGNOSTIC_HANDLER = '''
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

REGION = "ap-south-1"
PROFILE_ID = "apac.amazon.nova-lite-v1:0"


def handler(event, context):
    client = boto3.client(
        "bedrock-runtime",
        region_name=REGION,
        config=Config(retries={"total_max_attempts": 1}, connect_timeout=5, read_timeout=30),
    )
    try:
        response = client.converse(
            modelId=PROFILE_ID,
            messages=[{"role": "user", "content": [{"text": "Reply with exactly: OK"}]}],
            inferenceConfig={"maxTokens": 16, "temperature": 0},
        )
    except ClientError as exc:
        error = exc.response.get("Error", {})
        return {
            "status": "denied" if error.get("Code") in {"AccessDenied", "AccessDeniedException"} else "aws_error",
            "operation": "bedrock-runtime:Converse",
            "region": REGION,
            "model_id": PROFILE_ID,
            "error_code": error.get("Code", "ClientError"),
            "message": error.get("Message", str(exc)),
            "request_id": exc.response.get("ResponseMetadata", {}).get("RequestId"),
        }

    output = response.get("output", {}).get("message", {}).get("content", [])
    text = next((item.get("text") for item in output if isinstance(item, dict) and item.get("text")), None)
    return {
        "status": "accepted",
        "operation": "bedrock-runtime:Converse",
        "region": REGION,
        "model_id": PROFILE_ID,
        "http_status": response.get("ResponseMetadata", {}).get("HTTPStatusCode"),
        "request_id": response.get("ResponseMetadata", {}).get("RequestId"),
        "response_text": text,
    }
'''


def _package_handler() -> bytes:
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("diagnostic.py", DIAGNOSTIC_HANDLER)
    return archive.getvalue()


def _json_payload(stream) -> dict:
    raw = stream.read()
    stream.close()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"raw_payload": raw.decode("utf-8", errors="replace")}
    return payload if isinstance(payload, dict) else {"payload": payload}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="farmwiseai", help="AWS SSO profile used to create and invoke the temporary function")
    args = parser.parse_args()

    session = boto3.Session(profile_name=args.profile, region_name=REGION)
    control_config = Config(retries={"total_max_attempts": 1}, connect_timeout=5, read_timeout=30)
    lambda_client = session.client("lambda", config=control_config)
    sts_client = session.client("sts", config=control_config)
    result = {
        "region": REGION,
        "profile_id": PROFILE_ID,
        "operation": "bedrock-runtime:Converse",
        "diagnostic_function": None,
        "cleanup": "not_needed",
    }
    temporary_name = None
    temporary_created = False

    try:
        caller = sts_client.get_caller_identity()
        result["local_caller_arn"] = caller["Arn"]
        deployed = lambda_client.get_function_configuration(FunctionName=FUNCTION_NAME)
        deployed_region = deployed["FunctionArn"].split(":")[3]
        environment = deployed.get("Environment", {}).get("Variables", {})
        if deployed_region != REGION:
            raise RuntimeError(f"Existing Lambda is in {deployed_region}, expected {REGION}.")
        if deployed.get("Role") != EXPECTED_ROLE_ARN:
            raise RuntimeError(f"Existing Lambda role is {deployed.get('Role')}, expected {EXPECTED_ROLE_ARN}.")
        if environment.get("BEDROCK_INFERENCE_PROFILE", PROFILE_ID) != PROFILE_ID:
            raise RuntimeError("Existing Lambda BEDROCK_INFERENCE_PROFILE does not match the approved profile.")
        if environment.get("URBANLENS_LAMBDA_BEDROCK_ENABLED", "false").lower() == "true":
            raise RuntimeError("Production Lambda Bedrock escalation is enabled; refusing to run during active processing.")

        result["execution_role_arn"] = deployed["Role"]
        temporary_name = f"urbanlens-bedrock-diagnostic-{uuid4().hex[:12]}"
        result["diagnostic_function"] = temporary_name
        lambda_client.create_function(
            FunctionName=temporary_name,
            Runtime="python3.12",
            Role=deployed["Role"],
            Handler="diagnostic.handler",
            Code={"ZipFile": _package_handler()},
            Description="Temporary one-call Nova Lite role diagnostic; safe to delete after invocation.",
            Timeout=40,
            MemorySize=128,
            Publish=False,
        )
        temporary_created = True
        lambda_client.get_waiter("function_active_v2").wait(
            FunctionName=temporary_name,
            WaiterConfig={"Delay": 2, "MaxAttempts": 30},
        )
        invocation = lambda_client.invoke(
            FunctionName=temporary_name,
            InvocationType="RequestResponse",
            LogType="None",
            Payload=b"{}",
        )
        result["lambda_status_code"] = invocation.get("StatusCode")
        result["function_error"] = invocation.get("FunctionError")
        result["diagnostic_result"] = _json_payload(invocation["Payload"])
    except ClientError as exc:
        error = exc.response.get("Error", {})
        result["setup_error"] = {
            "code": error.get("Code", "ClientError"),
            "message": error.get("Message", str(exc)),
        }
    except Exception as exc:
        result["setup_error"] = {"code": type(exc).__name__, "message": str(exc)}
    finally:
        if temporary_created:
            try:
                lambda_client.delete_function(FunctionName=temporary_name)
                result["cleanup"] = "deleted"
            except ClientError as exc:
                error = exc.response.get("Error", {})
                if error.get("Code") == "ResourceNotFoundException":
                    result["cleanup"] = "not_created"
                else:
                    result["cleanup"] = {
                        "error_code": error.get("Code", "ClientError"),
                        "message": error.get("Message", str(exc)),
                    }
        elif temporary_name:
            result["cleanup"] = "not_created"

    print(json.dumps(result, indent=2, sort_keys=True))
    diagnostic = result.get("diagnostic_result", {})
    if diagnostic.get("status") in {"accepted", "denied"}:
        return 0 if result["cleanup"] in {"deleted", "not_created"} else 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
