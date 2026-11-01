
$ErrorActionPreference = "Stop"

# Xac dinh thu muc repository
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$core = Join-Path $repo "core\ccapi_core"

# Tao thu muc output moi trong TEMP, khong ghi de
$output = Join-Path $env:TEMP (
    "ccapi-faas-" + [guid]::NewGuid().ToString("N")
)

New-Item -ItemType Directory -Path $output | Out-Null
New-Item -ItemType Directory -Path "$output\ccapi_core" | Out-Null

# Copy ma nguon adapter
Copy-Item "$PSScriptRoot\main.py" "$output\main.py"
Copy-Item "$PSScriptRoot\requirements.txt" "$output\requirements.txt"

# Copy thu vien core, khong thay doi ban goc
Copy-Item "$core\*.py" "$output\ccapi_core\"

Write-Host "FaaS package created:"
Write-Host $output
tree $output /F /A
