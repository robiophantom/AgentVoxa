param(
    [string]$VenvPath = ".venv"
)

$ErrorActionPreference = "Stop"

function Get-PythonCommand {
    $candidates = @(
        @{ Label = "py-3.11"; Exe = "py"; Args = @("-3.11") },
        @{ Label = "py-3.12"; Exe = "py"; Args = @("-3.12") },
        @{ Label = "python"; Exe = "python"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        try {
            $versionArgs = @()
            $versionArgs += $candidate.Args
            $versionArgs += @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            $version = & $candidate.Exe @versionArgs
            if (-not $version) {
                continue
            }

            $majorMinor = $version.Trim()
            if ($majorMinor -eq "3.11" -or $majorMinor -eq "3.12") {
                Write-Host "Using Python $majorMinor via $($candidate.Label)"
                return $candidate
            }
        }
        catch {
            continue
        }
    }

    throw "Python 3.11/3.12 not found. Install Python 3.11+ and ensure it is available via 'py' or 'python'."
}

$pythonCmd = Get-PythonCommand

if (Test-Path $VenvPath) {
    Write-Host "Virtual environment already exists at '$VenvPath'. Reusing it."
} else {
    Write-Host "Creating virtual environment at '$VenvPath'..."
    $venvArgs = @()
    $venvArgs += $pythonCmd.Args
    $venvArgs += @("-m", "venv", $VenvPath)
    & $pythonCmd.Exe @venvArgs
}

$venvPython = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Virtual environment is missing python executable at '$venvPython'."
}

Write-Host "Upgrading pip tooling..."
& $venvPython -m pip install --upgrade pip setuptools wheel

Write-Host "Installing backend requirements..."
& $venvPython -m pip install --prefer-binary --upgrade-strategy only-if-needed -r requirements.txt

Write-Host "Done. Activate with: .\\$VenvPath\\Scripts\\Activate.ps1"
