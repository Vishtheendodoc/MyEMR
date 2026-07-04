$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$batPath = Join-Path $projectDir "Start_EMR.bat"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Endo EMR.lnk"

if (-not (Test-Path $batPath)) {
    Write-Error "Start_EMR.bat not found in $projectDir"
    exit 1
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $batPath
$shortcut.WorkingDirectory = $projectDir
$shortcut.Description = "Start Endocrinology EMR"
$shortcut.IconLocation = "$env:SystemRoot\System32\imageres.dll,109"
$shortcut.Save()

Write-Host ""
Write-Host "Desktop shortcut created:"
Write-Host "  $shortcutPath"
Write-Host ""
Write-Host "Double-click 'Endo EMR' on your desktop to start the app."
Write-Host ""
