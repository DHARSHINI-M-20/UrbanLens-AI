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

$currentConfiguration = aws lambda get-function-configuration --profile $Profile --region $region --function-name $FunctionName --query "{Runtime:Runtime,Role:Role,Environment:Environment.Variables}" --output json --no-cli-pager
if ($LASTEXITCODE -ne 0) {
    throw "Existing Lambda was not found or cannot be inspected; refusing to create or replace it."
}
if (-not $currentConfiguration) {
    throw "Existing Lambda configuration was empty; refusing to update it."
}
$parsedConfiguration = $currentConfiguration | ConvertFrom-Json
$current = @{}
$parsedConfiguration.PSObject.Properties | ForEach-Object {
    $current[$_.Name] = $_.Value
}
if ($null -ne $current.Environment) {
    $environment = @{}
    $current.Environment.PSObject.Properties | ForEach-Object {
        $environment[$_.Name] = $_.Value
    }
    $current.Environment = $environment
}
if (($current.Role -split "/")[-1] -ne $expectedRoleName) {
    throw "Existing Lambda uses a different execution role; refusing to update it."
}
if ($current.Runtime -ne "python3.12") {
    throw "Existing Lambda does not use Python 3.12; refusing to update it."
}
$environment = $current.Environment
if ($null -eq $environment) { $environment = @{} }
$environment["URBANLENS_LAMBDA_BEDROCK_ENABLED"] = "true"
$environment["BEDROCK_INFERENCE_PROFILE"] = "apac.amazon.nova-lite-v1:0"
$environmentFile = Join-Path $env:TEMP ("urbanlens-lambda-environment-" + [guid]::NewGuid().ToString("N") + ".json")
$environmentJson = ConvertTo-Json -InputObject @{ Variables = $environment } -Depth 20 -Compress
[System.IO.File]::WriteAllText($environmentFile, $environmentJson, [System.Text.UTF8Encoding]::new($false))
Write-Output ([pscustomobject]@{
    FunctionName = $FunctionName
    Region = $region
    Runtime = $current.Runtime
    ExecutionRole = ($current.Role -split "/")[-1]
    PreservesExistingEnvironmentVariables = $true
    AddsOrUpdates = @{
        URBANLENS_LAMBDA_BEDROCK_ENABLED = "true"
        BEDROCK_INFERENCE_PROFILE = "apac.amazon.nova-lite-v1:0"
    }
} | ConvertTo-Json -Depth 5)

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

    aws lambda update-function-configuration --profile $Profile --region $region --function-name $FunctionName --environment "file://$environmentFile" --query "{FunctionName:FunctionName,LastModified:LastModified,State:State,LastUpdateStatus:LastUpdateStatus}" --output json --no-cli-pager
    if ($LASTEXITCODE -ne 0) {
        throw "Lambda code was updated, but enabling Bedrock configuration failed."
    }
    aws lambda wait function-updated-v2 --profile $Profile --region $region --function-name $FunctionName --no-cli-pager
    if ($LASTEXITCODE -ne 0) {
        throw "Lambda environment update waiter failed."
    }
    $verification = aws lambda get-function-configuration --profile $Profile --region $region --function-name $FunctionName --query "{FunctionName:FunctionName,Runtime:Runtime,Role:Role,State:State,LastUpdateStatus:LastUpdateStatus,BedrockEnabled:Environment.Variables.URBANLENS_LAMBDA_BEDROCK_ENABLED,InferenceProfile:Environment.Variables.BEDROCK_INFERENCE_PROFILE}" --output json --no-cli-pager
    if ($LASTEXITCODE -ne 0) {
        throw "Could not verify the Bedrock-enabled Lambda configuration."
    }
    $verified = $verification | ConvertFrom-Json
    if ($verified.Role -notmatch "/$expectedRoleName$" -or $verified.Runtime -ne "python3.12" -or
        $verified.BedrockEnabled -ne "true" -or $verified.InferenceProfile -ne "apac.amazon.nova-lite-v1:0" -or
        $verified.State -ne "Active" -or $verified.LastUpdateStatus -ne "Successful") {
        throw "Updated Lambda did not match the required role, runtime, or Bedrock configuration."
    }
    $verification
}
finally {
    Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $environmentFile -Force -ErrorAction SilentlyContinue
}
