param(
    [string] $ProjectPath = "pyproject.toml",
    [string] $InitPath = "slmp/__init__.py"
)

$ErrorActionPreference = "Stop"

function Read-RegexValue([string] $Path, [string] $Pattern, [string] $Label) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing $Label file: $Path"
    }

    $text = Get-Content -LiteralPath $Path -Raw
    $match = [regex]::Match($text, $Pattern, [System.Text.RegularExpressions.RegexOptions]::Multiline)
    if (-not $match.Success) {
        throw "Could not find $Label version in '$Path'."
    }

    return $match.Groups[1].Value
}

$projectVersion = Read-RegexValue $ProjectPath '^\s*version\s*=\s*"([^"]+)"' "pyproject"
$runtimeVersion = Read-RegexValue $InitPath '^\s*__version__\s*=\s*"([^"]+)"' "runtime"

if ($projectVersion -ne $runtimeVersion) {
    throw "Version mismatch: '$ProjectPath' has '$projectVersion', but '$InitPath' has '$runtimeVersion'."
}

Write-Host "[OK] pyproject version and slmp.__version__ are both $projectVersion."
