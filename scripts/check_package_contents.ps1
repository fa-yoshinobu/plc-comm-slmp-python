[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$workRoot = Join-Path $repositoryRoot ("build/package-contract-" + [guid]::NewGuid().ToString("N"))
$artifactDirectory = Join-Path $workRoot "artifacts"
$consumerDirectory = Join-Path $workRoot "consumer"
$venvDirectory = Join-Path $workRoot "consumer-venv"
$preexistingEggInfoDirectories = @(Get-ChildItem -LiteralPath $repositoryRoot -Directory -Filter "*.egg-info" -ErrorAction SilentlyContinue |
    ForEach-Object { $_.FullName })

function Test-RepositoryOnlyPath {
    param([Parameter(Mandatory)][string]$Path)

    $normalized = $Path.Replace("\", "/")
    $leafName = [System.IO.Path]::GetFileName($normalized)
    $rootOnlyFiles = @(
        ".gitattributes",
        ".gitignore",
        ".npmrc",
        ".pypirc",
        "AGENTS.md",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "SUPPORT.md",
        "TODO.md",
        "release_check.bat",
        "run_ci.bat"
    )

    return (
        $normalized -in $rootOnlyFiles -or
        $normalized -match '^(test|tests|samples|sample|examples|example|\.github|\.codex|docsrc|docs|internal_docs|scripts|tools|build|build_win|dist|out|release|releases|release-artifacts)/' -or
        $normalized -match '(^|/)(__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.tox|\.nox|\.venv|venv|htmlcov|coverage|\.cache)(/|$)' -or
        $leafName -match '^(\.coverage(?:\..+)?|coverage-final\.json|lcov\.info)$' -or
        $leafName -match '^(\.env(?:\..+)?|\.npmrc|\.pypirc|id_rsa(?:\.pub)?|id_ed25519(?:\.pub)?|credentials?(?:\..+)?|secrets?(?:\..+)?)$' -or
        $leafName -match '\.(pem|key|pfx|p12|jks|keystore)$'
    )
}

$guardContractForbidden = @(
    "AGENTS.md",
    "scripts/release.ps1",
    ".github/workflows/ci.yml",
    "build/package.whl",
    "release-artifacts/package.tar.gz",
    "nested/.env.production",
    "nested/private-key.pem",
    "nested/.pytest_cache/state",
    "coverage/lcov.info"
)
$guardContractAllowed = @(
    "LICENSE",
    "README.md",
    "pyproject.toml",
    "slmp/client.py",
    "src/slmp/client.py",
    "slmp/py.typed"
)
$guardMisses = @($guardContractForbidden | Where-Object { -not (Test-RepositoryOnlyPath -Path $_) })
$guardFalsePositives = @($guardContractAllowed | Where-Object { Test-RepositoryOnlyPath -Path $_ })
if ($guardMisses.Count -ne 0 -or $guardFalsePositives.Count -ne 0) {
    throw "Repository-only path guard contract failed: misses=$($guardMisses -join ', ') false-positives=$($guardFalsePositives -join ', ')"
}

try {
    [void](New-Item -ItemType Directory -Path $artifactDirectory -Force)
    [void](New-Item -ItemType Directory -Path $consumerDirectory -Force)
    Push-Location $repositoryRoot
    try {
        & python -m build --outdir $artifactDirectory
        if ($LASTEXITCODE -ne 0) { throw "python -m build failed." }
    }
    finally {
        Pop-Location
    }

    $wheel = @(Get-ChildItem -LiteralPath $artifactDirectory -Filter "*.whl")
    $sdist = @(Get-ChildItem -LiteralPath $artifactDirectory -Filter "*.tar.gz")
    if ($wheel.Count -ne 1 -or $sdist.Count -ne 1) {
        throw "Expected one wheel and one sdist; found wheel=$($wheel.Count) sdist=$($sdist.Count)."
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($wheel[0].FullName)
    try {
        $wheelFiles = @($archive.Entries |
            Where-Object { -not $_.FullName.EndsWith("/") } |
            ForEach-Object { $_.FullName.Replace("\", "/") } |
            Sort-Object -Unique)
    }
    finally {
        $archive.Dispose()
    }

    $tarExecutable = if ($env:OS -eq "Windows_NT") { "tar.exe" } else { "tar" }
    $sdistFiles = @(& $tarExecutable -tf $sdist[0].FullName |
        ForEach-Object {
            $path = $_.Replace("\", "/")
            if ($path.Contains("/")) { $path.Substring($path.IndexOf("/") + 1) }
        } |
        Where-Object { $_ -and -not $_.EndsWith("/") } |
        Sort-Object -Unique)
    if ($LASTEXITCODE -ne 0) { throw "Cannot inspect sdist." }

    foreach ($artifact in @(@{ Name = "wheel"; Files = $wheelFiles }, @{ Name = "sdist"; Files = $sdistFiles })) {
        $forbidden = @($artifact.Files | Where-Object { Test-RepositoryOnlyPath -Path $_ })
        if ($forbidden.Count -ne 0) {
            throw "$($artifact.Name) contains repository-only files: $($forbidden -join ', ')"
        }
    }

    if (@($wheelFiles | Where-Object { $_ -match '\.dist-info/METADATA$' }).Count -ne 1 -or
        @($wheelFiles | Where-Object { $_ -match '\.dist-info/(licenses/)?LICENSE$' }).Count -ne 1 -or
        "slmp/py.typed" -notin $wheelFiles) {
        throw "Wheel is missing metadata, license, or py.typed."
    }
    $missingSdist = @(@("LICENSE", "README.md", "pyproject.toml", "slmp/py.typed") |
        Where-Object { $_ -notin $sdistFiles -and $_ -ne "slmp/py.typed" }
    )
    if (@($sdistFiles | Where-Object { $_ -eq "slmp/py.typed" -or $_ -eq "src/slmp/py.typed" }).Count -ne 1) {
        $missingSdist += "slmp/py.typed"
    }
    if ($missingSdist.Count -ne 0) {
        throw "sdist is missing required consumer files: $($missingSdist -join ', ')"
    }

    & python -m venv $venvDirectory
    if ($LASTEXITCODE -ne 0) { throw "Cannot create isolated package-consumer virtual environment." }
    $consumerPython = if ($env:OS -eq "Windows_NT") {
        Join-Path $venvDirectory "Scripts/python.exe"
    }
    else {
        Join-Path $venvDirectory "bin/python"
    }
    & $consumerPython -m pip install --disable-pip-version-check --no-deps $wheel[0].FullName
    if ($LASTEXITCODE -ne 0) { throw "Cannot install the wheel into the isolated consumer environment." }

    $consumerSmoke = @'
from importlib.metadata import distribution
from pathlib import Path
import site

import slmp
from slmp import (
    AsyncSlmpClient,
    Command,
    SlmpClient,
    SlmpOutcomeUnknownError,
    SlmpTarget,
    write_bit_in_word,
    write_bit_in_word_sync,
)

module_path = Path(slmp.__file__).resolve()
site_roots = [Path(item).resolve() for item in site.getsitepackages()]
assert any(module_path.is_relative_to(root) for root in site_roots), (module_path, site_roots)
assert distribution("plc-comm-slmp").metadata["Name"] == "plc-comm-slmp"
assert Command.DEVICE_READ == 0x0401
assert Command.DEVICE_WRITE == 0x1401
assert SlmpClient.__module__.startswith("slmp.")
assert AsyncSlmpClient.__module__.startswith("slmp.")
assert SlmpTarget.__module__.startswith("slmp.")
assert issubclass(SlmpOutcomeUnknownError, Exception)
for helper in (write_bit_in_word, write_bit_in_word_sync):
    doc = helper.__doc__ or ""
    assert "FIFO turn" in doc
    assert "never retries automatically" in doc
print(f"[OK] installed wheel import: {module_path}")
'@
    $consumerSmokePath = Join-Path $consumerDirectory "installed-wheel-smoke.py"
    [System.IO.File]::WriteAllText(
        $consumerSmokePath,
        $consumerSmoke,
        [System.Text.UTF8Encoding]::new($false)
    )

    $savedPythonPath = $env:PYTHONPATH
    try {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        Push-Location $consumerDirectory
        try {
            & $consumerPython -I $consumerSmokePath
            if ($LASTEXITCODE -ne 0) { throw "Installed wheel public API/RMW docstring smoke failed." }
        }
        finally {
            Pop-Location
        }
    }
    finally {
        if ($null -eq $savedPythonPath) {
            Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        }
        else {
            $env:PYTHONPATH = $savedPythonPath
        }
    }

    Write-Host "[OK] Python package consumer passed: wheel=$($wheelFiles.Count) sdist=$($sdistFiles.Count)"
}
finally {
    if (Test-Path -LiteralPath $workRoot) {
        Remove-Item -LiteralPath $workRoot -Recurse -Force
    }
    $generatedEggInfoDirectories = @(Get-ChildItem -LiteralPath $repositoryRoot -Directory -Filter "*.egg-info" -ErrorAction SilentlyContinue |
        ForEach-Object { $_.FullName } |
        Where-Object { $_ -notin $preexistingEggInfoDirectories })
    foreach ($eggInfoDirectory in $generatedEggInfoDirectories) {
        Remove-Item -LiteralPath $eggInfoDirectory -Recurse -Force
    }
}
