[CmdletBinding()]
param(
    [string]$Treeish = "HEAD",
    [switch]$IncludeWorktree,
    [switch]$UseWorktreeAttributes,
    [switch]$SkipValidation
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$workRoot = Join-Path $repositoryRoot ("build/source-archive-check-" + [guid]::NewGuid().ToString("N"))
$archivePath = Join-Path $workRoot "source.zip"
$extractRoot = Join-Path $workRoot "extracted"
$temporaryIndexPath = $null
$savedIndexFile = $env:GIT_INDEX_FILE

try {
    if ($IncludeWorktree -and $PSBoundParameters.ContainsKey("Treeish")) {
        throw "-IncludeWorktree cannot be combined with an explicit -Treeish."
    }
    if ($IncludeWorktree) {
        $gitDirectory = (& git -C $repositoryRoot rev-parse --absolute-git-dir).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $gitDirectory) { throw "Cannot resolve the repository Git directory." }
        $temporaryIndexPath = Join-Path $gitDirectory ("source-archive-index-" + [guid]::NewGuid().ToString("N"))
        $env:GIT_INDEX_FILE = $temporaryIndexPath
        & git -C $repositoryRoot read-tree HEAD
        if ($LASTEXITCODE -ne 0) { throw "Cannot initialize the synthetic current-worktree tree." }
        & git -C $repositoryRoot add -A
        if ($LASTEXITCODE -ne 0) { throw "Cannot stage modified, untracked, and deleted files in the synthetic tree." }
        $effectiveTreeish = (& git -C $repositoryRoot write-tree).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $effectiveTreeish) { throw "Cannot write the synthetic current-worktree tree." }
        $archiveLabel = "current-worktree:$effectiveTreeish"
    }
    else {
        $effectiveTreeish = $Treeish
        $archiveLabel = "treeish:$Treeish"
        & git -C $repositoryRoot rev-parse --verify "$effectiveTreeish`^{tree}" *> $null
        if ($LASTEXITCODE -ne 0) { throw "Cannot resolve treeish '$effectiveTreeish'." }
    }
    if ($null -eq $savedIndexFile) {
        Remove-Item Env:GIT_INDEX_FILE -ErrorAction SilentlyContinue
    }
    else {
        $env:GIT_INDEX_FILE = $savedIndexFile
    }

    [void](New-Item -ItemType Directory -Path $workRoot -Force)

    $archiveArguments = @("archive", "--format=zip", "--output=$archivePath")
    if ($UseWorktreeAttributes) { $archiveArguments += "--worktree-attributes" }
    $archiveArguments += $effectiveTreeish
    & git -C $repositoryRoot @archiveArguments
    if ($LASTEXITCODE -ne 0) { throw "git archive failed for '$archiveLabel'." }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($archivePath)
    try {
        $archiveFiles = @($archive.Entries |
            Where-Object { -not $_.FullName.EndsWith("/") } |
            ForEach-Object { $_.FullName.Replace("\", "/") } |
            Sort-Object -Unique)
    }
    finally {
        $archive.Dispose()
    }

    $trackedFiles = @(& git -C $repositoryRoot ls-tree -r --name-only $effectiveTreeish |
        ForEach-Object { $_.Replace("\", "/") } |
        Sort-Object -Unique)
    if ($LASTEXITCODE -ne 0) { throw "Cannot enumerate files for '$archiveLabel'." }

    $requiredRootFiles = @("CHANGELOG.md", "LICENSE", "README.md", "run_ci.bat")
    $missingRootFiles = @($requiredRootFiles | Where-Object { $_ -notin $archiveFiles })
    if ($missingRootFiles.Count -ne 0) {
        throw "Source archive is missing required root files: $($missingRootFiles -join ', ')"
    }

    $manifestCandidates = @("package.json", "pyproject.toml", "Cargo.toml", "library.json", "library.properties", "CMakeLists.txt") +
        @($trackedFiles | Where-Object { $_ -match '\.(sln|csproj)$' })
    if (@($manifestCandidates | Where-Object { $_ -in $archiveFiles }).Count -eq 0) {
        throw "Source archive contains no recognized build manifest."
    }

    $guideRoots = @("docsrc/user", "docs")
    foreach ($guide in @("GETTING_STARTED.md", "USAGE_GUIDE.md", "PROFILES.md", "GOTCHAS.md", "API_REFERENCE.md")) {
        if (@($guideRoots | ForEach-Object { "$_/$guide" } | Where-Object { $_ -in $archiveFiles }).Count -eq 0) {
            throw "Source archive is missing standard user guide '$guide'."
        }
    }

    $requiredTracked = @($trackedFiles | Where-Object {
        $_ -match '^(test|tests|\.github|docsrc/maintainer|internal_docs|scripts|tools)/' -or
        $_ -in @("AGENTS.md", "TODO.md", "release_check.bat", "run_ci.bat")
    })
    $missingTracked = @($requiredTracked | Where-Object { $_ -notin $archiveFiles })
    if ($missingTracked.Count -ne 0) {
        throw "Source archive omits tracked validation or maintainer material: $($missingTracked -join ', ')"
    }
    if (@($archiveFiles | Where-Object { $_ -match '^(test|tests)/' }).Count -eq 0) {
        throw "Source archive contains no repository tests."
    }

    $forbidden = @($archiveFiles | Where-Object {
        $_ -match '^(build|build_win|release-artifacts)/'
    })
    if ($forbidden.Count -ne 0) {
        throw "Source archive contains generated or release-output files: $($forbidden -join ', ')"
    }

    if (-not $SkipValidation) {
        Expand-Archive -LiteralPath $archivePath -DestinationPath $extractRoot
        Push-Location $extractRoot
        try {
            if ($env:OS -eq "Windows_NT") {
                & cmd.exe /d /c run_ci.bat
                if ($LASTEXITCODE -ne 0) { throw "run_ci.bat failed from the extracted source archive." }
            }
            else {
                & python -m ruff check .
                if ($LASTEXITCODE -ne 0) { throw "ruff failed from the extracted source archive." }
                & python -m ruff format --check .
                if ($LASTEXITCODE -ne 0) { throw "ruff format check failed from the extracted source archive." }
                & python -m mypy slmp
                if ($LASTEXITCODE -ne 0) { throw "mypy failed from the extracted source archive." }
                & python scripts/check_public_api_docs.py
                if ($LASTEXITCODE -ne 0) { throw "public API documentation check failed from the extracted source archive." }
                & python -m pytest tests -q
                if ($LASTEXITCODE -ne 0) { throw "pytest failed from the extracted source archive." }
            }
            & (Join-Path $extractRoot "scripts/check_package_contents.ps1")
            if ($LASTEXITCODE -ne 0) { throw "Package consumer gate failed from the extracted source archive." }
        }
        finally {
            Pop-Location
        }
    }

    Write-Host "[OK] Source archive contract passed: source=$archiveLabel files=$($archiveFiles.Count) validation=$(-not $SkipValidation)"
}
finally {
    if ($null -eq $savedIndexFile) {
        Remove-Item Env:GIT_INDEX_FILE -ErrorAction SilentlyContinue
    }
    else {
        $env:GIT_INDEX_FILE = $savedIndexFile
    }
    if ($temporaryIndexPath -and (Test-Path -LiteralPath $temporaryIndexPath)) {
        Remove-Item -LiteralPath $temporaryIndexPath -Force
    }
    if (Test-Path -LiteralPath $workRoot) {
        Remove-Item -LiteralPath $workRoot -Recurse -Force
    }
}
