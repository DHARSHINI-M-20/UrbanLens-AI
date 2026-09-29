$ErrorActionPreference = "Stop"

$backendDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $backendDirectory ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Backend virtual environment not found at $python"
}

$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $backendDirectory ".venv\Lib\site-packages"
    Push-Location $backendDirectory
    & $python -m pytest @args
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
    if ($null -ne $previousPythonPath) {
        $env:PYTHONPATH = $previousPythonPath
    }
    else {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
}