param(
    [string]$Profile = "farmwiseai",
    [string]$FunctionName = "fai-tce-team11-urbanlens-demo-processor"
)

$ErrorActionPreference = "Stop"
$region = "ap-south-1"
$expectedRoleName = "FAI-TCE-LambdaExecutionRole"
$backendDirectory = Split-Path -Parent $PSScriptRoot
$python = Join-Path $backendDirectory ".venv\Scripts\python.exe"
$sources = @(
    (Join-Path $backendDirectory "aws\lambda\process_demo_object\cloud_api.py"),
    (Join-Path $backendDirectory "aws\lambda\process_demo_object\handler.py"),
    (Join-Path $backendDirectory "app\services\bedrock_runtime.py"),
    (Join-Path $backendDirectory "app\services\dynamodb_service.py"),
    (Join-Path $backendDirectory "app\services\challenge_queries.py")
)
$archiveNames = @("cloud_api.py", "handler.py", "bedrock_runtime.py", "dynamodb_service.py")

if ($FunctionName -ne "fai-tce-team11-urbanlens-demo-processor") {
    throw "Refusing to update an unapproved function name."
}
if (-not (Test-Path $python)) {
    throw "Backend virtual environment not found at $python"
}
foreach ($source in $sources) {
    if (-not (Test-Path $source)) {
        throw "Lambda package source is missing: $source"
    }
}

$role = aws lambda get-function-configuration --profile $Profile --region $region --function-name $FunctionName --query "Role" --output text --no-cli-pager
if ($LASTEXITCODE -ne 0) {
    throw "Existing Lambda was not found or cannot be inspected; refusing to create or replace it."
}
if (($role -split "/")[-1] -ne $expectedRoleName) {
    throw "Existing Lambda uses a different execution role; refusing to update it."
}

$zip = Join-Path $env:TEMP ("urbanlens-cloud-lambda-" + [guid]::NewGuid().ToString("N") + ".zip")
$packageScript = @'
import sys
import zipfile

sources = sys.argv[1:6]
archive = sys.argv[6]
names = ("cloud_api.py", "handler.py", "bedrock_runtime.py", "dynamodb_service.py", "challenge_query_rules.py")
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
    for source, name in zip(sources, names):
        bundle.write(source, name)
'@

try {
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($packageScript))
    & $python -c "import base64; exec(base64.b64decode('$encoded'))" $sources[0] $sources[1] $sources[2] $sources[3] $sources[4] $zip
    if ($LASTEXITCODE -ne 0) {
        throw "Lambda packaging failed with exit code $LASTEXITCODE."
    }
    $size = (Get-Item $zip).Length
    if ($size -gt 50000000) {
        throw "Lambda ZIP package is unexpectedly large ($size bytes)."
    }
    aws lambda update-function-code --profile $Profile --region $region --function-name $FunctionName --zip-file "fileb://$zip" --query "{FunctionName:FunctionName,LastModified:LastModified,State:State}" --output json --no-cli-pager
    if ($LASTEXITCODE -ne 0) {
        throw "Lambda code update failed with exit code $LASTEXITCODE."
    }
    aws lambda wait function-updated-v2 --profile $Profile --region $region --function-name $FunctionName --no-cli-pager
    if ($LASTEXITCODE -ne 0) {
        throw "Lambda update waiter failed with exit code $LASTEXITCODE."
    }
    aws lambda get-function-configuration --profile $Profile --region $region --function-name $FunctionName --query "{FunctionName:FunctionName,Handler:Handler,Runtime:Runtime,Role:Role,State:State,LastUpdateStatus:LastUpdateStatus}" --output json --no-cli-pager
    if ($LASTEXITCODE -ne 0) {
        throw "Could not verify the updated Lambda."
    }
}
finally {
    Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
}
