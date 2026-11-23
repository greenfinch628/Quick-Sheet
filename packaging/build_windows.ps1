param(
    [string]$Python = 'python',
    [string]$InnoCompiler = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
)

$ErrorActionPreference = 'Stop'
$pythonCommand = (Get-Command $Python -ErrorAction Stop).Source
$innoCommand = (Get-Command $InnoCompiler -ErrorAction Stop).Source

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $version = (Get-Content VERSION -Raw).Trim()
    if ($version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid VERSION: $version" }
    if ($env:GITHUB_REF_TYPE -eq 'tag' -and $env:GITHUB_REF_NAME -ne "v$version") {
        throw "Tag $env:GITHUB_REF_NAME does not match VERSION $version"
    }

    $repoRoot = (Get-Location).Path
    & $pythonCommand -m PyInstaller --noconfirm --clean --windowed --onedir --name Quick-Sheet `
        --icon "$repoRoot/assets/Quick-Sheet.ico" --add-data "$repoRoot/VERSION:." `
        --add-data "$repoRoot/assets/Quick-Sheet.ico:assets" --add-data "$repoRoot/assets/Quick-Sheet.png:assets" `
        --distpath windows-build/dist --workpath windows-build/work --specpath windows-build main.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit $LASTEXITCODE" }

    & $innoCommand "/DAppVersion=$version" packaging/Quick-Sheet.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit $LASTEXITCODE" }

    $name = "Quick-Sheet-Setup-$version.exe"
    $installer = Get-Item "windows-build/release/$name"
    if ($installer.Length -le 0) { throw "Installer is empty: $name" }
    $hash = (Get-FileHash -Algorithm SHA256 $installer.FullName).Hash.ToLowerInvariant()
    "$hash  $name" | Set-Content -Encoding ascii "windows-build/release/$name.sha256"
    if ($env:GITHUB_OUTPUT) { "version=$version" >> $env:GITHUB_OUTPUT }
} finally {
    Pop-Location
}
