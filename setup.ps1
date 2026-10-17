<#
Installer for the Search Console Stack on Windows.
This script does three tasks:
  - It makes sure that Python 3.9 or later is on the system.
  - It makes a local Python environment in the .venv folder.
  - It installs the Python packages that the pull scripts need.
You can run this script again. It examines the system first. It changes only the
items that you agree to change.

How to use this script:
  .\setup.ps1        The script asks before it installs or changes software.
  .\setup.ps1 -Yes   The script does not ask. It uses yes for each question.
                     Use this mode for an agent or an unattended run.
#>
[CmdletBinding()]
param([switch]$Yes)

$ErrorActionPreference = "Stop"
$MinimumPythonMinor = 9
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $RepoRoot ".venv"
$Requirements = Join-Path $RepoRoot "requirements.txt"

# Ask a yes/no question. The function returns a boolean. With -Yes, it returns
# true. With an empty answer, it uses the default.
function Confirm-Step([string]$Question, [bool]$DefaultYes = $true) {
  if ($Yes) { return $true }
  $hint = if ($DefaultYes) { "Y/n" } else { "y/N" }
  $reply = Read-Host "$Question [$hint]"
  if ([string]::IsNullOrWhiteSpace($reply)) { return $DefaultYes }
  return ($reply -match '^(y|yes)$')
}

function Say([string]$Message)  { Write-Host "`n$Message" }
function Step([string]$Message) { Write-Host "`n==> $Message" }

# Find a Python launcher. The function prefers the py launcher, then python on
# PATH. It returns the executable and any prefix arguments, or null.
function Resolve-Python {
  $launcher = Get-Command py -ErrorAction SilentlyContinue
  if ($launcher) { return @{ Exe = $launcher.Source; Prefix = @("-3") } }
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) { return @{ Exe = $python.Source; Prefix = @() } }
  return $null
}

# The function returns true when the given Python is new enough.
function Test-PythonVersion($Python) {
  if (-not $Python) { return $false }
  $script = "import sys; sys.exit(0 if sys.version_info[:2] >= (3,$MinimumPythonMinor) else 1)"
  & $Python.Exe @($Python.Prefix) "-c" $script 2>$null
  return ($LASTEXITCODE -eq 0)
}

function Install-Python {
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Step "Install Python with winget."
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  }
  elseif (Get-Command choco -ErrorAction SilentlyContinue) {
    Step "Install Python with Chocolatey."
    choco install -y python
  }
  else {
    throw "Install Python 3.$MinimumPythonMinor or later from https://www.python.org/downloads/ (select 'Add python.exe to PATH'). Then run this script again."
  }
}

function Ensure-Python {
  $python = Resolve-Python
  if (Test-PythonVersion $python) {
    $version = (& $python.Exe @($python.Prefix) "--version") 2>&1
    Say "Python is on the system: $version."
    if (Confirm-Step "Install a newer Python?" $false) {
      Install-Python
    }
    return (Resolve-Python)
  }

  if ($python) { Say "Python is on the system, but it is older than the required 3.$MinimumPythonMinor." }
  else { Say "Python 3 is not on the system." }
  if (-not (Confirm-Step "Install Python 3 now?" $true)) {
    throw "You must have Python 3.$MinimumPythonMinor or later. The script did not change anything."
  }
  Install-Python

  # A new install can be absent from PATH in this session.
  $python = Resolve-Python
  if (-not (Test-PythonVersion $python)) {
    throw "Python is installed but is not on PATH yet. Close PowerShell, open it again, then run .\setup.ps1 again."
  }
  return $python
}

function Ensure-VirtualEnv($Python) {
  if (Test-Path $VenvDir) {
    Say "The Python environment is already at $VenvDir."
  }
  else {
    Step "Make the Python environment at $VenvDir."
    & $Python.Exe @($Python.Prefix) "-m" "venv" $VenvDir
  }
}

function Install-Packages {
  $venvPython = Join-Path $VenvDir "Scripts\python.exe"
  Step "Upgrade pip in the Python environment."
  & $venvPython "-m" "pip" "install" "--upgrade" "pip" | Out-Null

  # The package google-cloud-bigquery is present when a previous run installed
  # the packages.
  & $venvPython "-m" "pip" "show" "google-cloud-bigquery" *> $null
  if ($LASTEXITCODE -eq 0) {
    if (Confirm-Step "The Python packages are installed. Install the latest versions?" $false) {
      Step "Install the latest versions of the packages."
      & $venvPython "-m" "pip" "install" "--upgrade" "-r" $Requirements
    }
    else { Say "The script keeps the installed versions." }
  }
  else {
    Step "Install the Python packages."
    & $venvPython "-m" "pip" "install" "-r" $Requirements
  }
}

# --- main ---
Say "Search Console Stack installer (Windows)."
if (-not (Test-Path $Requirements)) { throw "The file requirements.txt is not next to this script." }
$python = Ensure-Python
Ensure-VirtualEnv $python
Install-Packages

Write-Host @"

The installation is complete.

Do these steps:
  1. Put your Google credentials in the GSC-setup folder:
       service_account.json   (service account method), or
       client_secret.json     (OAuth method)
  2. Open the script basic_gsc_pull.py or basic_big_query_pull.py in the
     GSC-setup folder. Set SITE_URL, PROJECT, and the dates at the top.
  3. Run a pull. Then check the result:
       .\.venv\Scripts\Activate.ps1
       cd GSC-setup
       python basic_gsc_pull.py      # the Search Console API backfill
       python basic_check.py         # the check of the database
"@
