<#
.SYNOPSIS
    Build script for the notebook site.
.DESCRIPTION
    1. Runs all Python scripts inside each article's scripts/ folder.
    2. Converts each article's index.md to index.html via pandoc.
    3. Regenerates site index (placeholder).
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$postsDir = Join-Path $repoRoot "posts"

Write-Host "=== Building articles ===" -ForegroundColor Cyan

# Find all article folders (contain index.md)
$articleFolders = Get-ChildItem -Path $postsDir -Directory | Where-Object {
    Test-Path (Join-Path $_.FullName "index.md")
}

foreach ($article in $articleFolders) {
    Write-Host ""
    Write-Host ">> $($article.Name)" -ForegroundColor Yellow

    # 1. Run scripts in article's scripts/ folder
    $scriptsDir = Join-Path $article.FullName "scripts"
    if (Test-Path $scriptsDir) {
        $pyScripts = Get-ChildItem -Path "$scriptsDir\*.py" -ErrorAction SilentlyContinue
        foreach ($s in $pyScripts) {
            Write-Host "   Running $($s.Name)"
            python $s.FullName
        }
    }

    # 2. Convert index.md -> index.html
    $mdFile = Join-Path $article.FullName "index.md"
    $htmlFile = Join-Path $article.FullName "index.html"
    $pandoc = Get-Command pandoc -ErrorAction SilentlyContinue
    if ($pandoc) {
        Write-Host "   Converting index.md -> index.html"
        pandoc $mdFile `
            --from markdown+yaml_metadata_block `
            --to html5 `
            --standalone `
            --template="$repoRoot\templates\post.html" `
            -o $htmlFile
    } else {
        Write-Host "   pandoc not found; skipping MD conversion." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "=== Regenerating site index ===" -ForegroundColor Cyan
$indexScript = Join-Path $repoRoot "tools\generate_index.py"
if (Test-Path $indexScript) {
    python $indexScript
} else {
    Write-Host "  generate_index.py not found; skipping." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Build complete." -ForegroundColor Green
