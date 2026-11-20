#requires -Version 5.1
<#
.SYNOPSIS
Sets up Quick-Sheet in this folder for the current Windows user.
.DESCRIPTION
Requires Python 3.10+ with Tcl/Tk. Reuses an existing .venv, installs the
requirements, and creates desktop and Start menu shortcuts to Launch.vbs.
Keep the application folder in place after setup.
.PARAMETER PythonExecutable
Optional path to the Python interpreter used when creating a new environment.
#>
[CmdletBinding()]
param(
    [string]$PythonExecutable,
    [switch]$NoDesktopShortcut,
    [switch]$NoStartMenuShortcut
)

$ErrorActionPreference = 'Stop'
$installDirectory = $PSScriptRoot
$launcherPath = Join-Path $installDirectory 'Launch.vbs'
$iconPath = Join-Path $installDirectory 'assets\Quick-Sheet.ico'
$environmentDirectory = Join-Path $installDirectory '.venv'
$environmentPython = Join-Path $environmentDirectory 'Scripts\python.exe'
$windowedPython = Join-Path $environmentDirectory 'Scripts\pythonw.exe'
$requirementsPath = Join-Path $installDirectory 'requirements.txt'

function Invoke-Python {
    param([string]$Executable, [string[]]$PythonArguments)
    & $Executable @PythonArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE. Setup stopped."
    }
}

function Set-QuickSheetShortcut {
    param([string]$Directory)
    if ([string]::IsNullOrWhiteSpace($Directory)) {
        throw 'Windows did not provide a shortcut folder for the current user.'
    }
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    $shortcutPath = Join-Path $Directory 'Quick-Sheet.lnk'
    # Reuse an existing alias, such as q-s, when it launches this installation.
    foreach ($file in Get-ChildItem -LiteralPath $Directory -Filter '*.lnk' -File) {
        $existing = $shortcutShell.CreateShortcut($file.FullName)
        if ($existing.TargetPath -ieq $scriptHost -and
            $existing.Arguments.Trim().Trim('"') -ieq $launcherPath) {
            $shortcutPath = $file.FullName
            break
        }
    }
    if (Test-Path -LiteralPath $shortcutPath) {
        $existing = $shortcutShell.CreateShortcut($shortcutPath)
        if ($existing.TargetPath -ine $scriptHost -or
            $existing.Arguments.Trim().Trim('"') -ine $launcherPath) {
            throw "An unrelated shortcut already exists at $shortcutPath. Rename it before retrying."
        }
    }
    $shortcut = $shortcutShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $scriptHost
    $shortcut.Arguments = '"' + $launcherPath + '"'
    $shortcut.WorkingDirectory = $installDirectory
    $shortcut.IconLocation = $iconPath + ',0'
    $shortcut.Description = 'Quick-Sheet spreadsheet'
    $shortcut.Save()
    Write-Host "Shortcut ready: $shortcutPath"
}

foreach ($requiredPath in @($launcherPath, $iconPath, $requirementsPath, (Join-Path $installDirectory 'main.py'))) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required application file is missing: $requiredPath"
    }
}

$pythonCheck = "import sys; assert sys.version_info >= (3, 10), 'Quick-Sheet requires Python 3.10 or newer'; import tkinter; print('Python ' + sys.version.split()[0] + ' with Tk ' + str(tkinter.TkVersion))"
if (Test-Path -LiteralPath $environmentDirectory) {
    if (-not (Test-Path -LiteralPath $environmentPython -PathType Leaf)) {
        throw 'The existing .venv is incomplete. Preserve or repair it before running setup again.'
    }
    Write-Host 'Using the existing Python environment.'
} else {
    $pythonPrefix = @()
    if ($PythonExecutable) {
        $basePython = (Get-Command $PythonExecutable -ErrorAction Stop).Source
    } elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
        $basePython = (Get-Command py.exe).Source
        $pythonPrefix = @('-3')
    } elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
        $basePython = (Get-Command python.exe).Source
    } else {
        throw 'Install Python 3.10 or newer with Tcl/Tk support, then run setup again.'
    }
    Invoke-Python $basePython ($pythonPrefix + @('-c', $pythonCheck))
    Write-Host 'Creating the application Python environment.'
    Invoke-Python $basePython ($pythonPrefix + @('-m', 'venv', $environmentDirectory))
}
Invoke-Python $environmentPython @('-c', $pythonCheck)
if (-not (Test-Path -LiteralPath $windowedPython -PathType Leaf)) {
    throw 'The Python environment is missing pythonw.exe, which is required for console-free startup.'
}
Invoke-Python $environmentPython @('-m', 'pip', 'install', '-r', $requirementsPath)

if (-not $NoDesktopShortcut -or -not $NoStartMenuShortcut) {
    $scriptHost = Join-Path $env:WINDIR 'System32\wscript.exe'
    if (-not (Test-Path -LiteralPath $scriptHost -PathType Leaf)) {
        throw 'Windows Script Host (wscript.exe) is required by the existing launcher.'
    }
    $shortcutShell = New-Object -ComObject WScript.Shell
    if (-not $NoDesktopShortcut) {
        Set-QuickSheetShortcut ([Environment]::GetFolderPath('Desktop'))
    }
    if (-not $NoStartMenuShortcut) {
        Set-QuickSheetShortcut ([Environment]::GetFolderPath('Programs'))
    }
}
Write-Host "Setup complete. Start Quick-Sheet with its shortcut or $launcherPath"
