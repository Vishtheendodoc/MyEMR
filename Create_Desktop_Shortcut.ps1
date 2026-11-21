$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $projectDir "Launch_EndoEMR.vbs"
$desktop = [Environment]::GetFolderPath("Desktop")
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$targets = @(
    (Join-Path $desktop "Endo EMR.lnk"),
    (Join-Path $startMenu "Endo EMR.lnk")
)

if (-not (Test-Path $launcher)) {
    Write-Error "Launch_EndoEMR.vbs not found in $projectDir"
    exit 1
}

$shell = New-Object -ComObject WScript.Shell
foreach ($shortcutPath in $targets) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $launcher
    $shortcut.WorkingDirectory = $projectDir
    $shortcut.WindowStyle = 7
    $shortcut.Description = "Open Endo EMR"
    $shortcut.IconLocation = "$env:SystemRoot\System32\imageres.dll,109"
    $shortcut.Save()
    Write-Host "Shortcut: $shortcutPath"
}
