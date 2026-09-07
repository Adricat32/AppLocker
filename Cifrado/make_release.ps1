$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$compiler = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $compiler) {
    throw "No se encontró ISCC.exe. Instala Inno Setup y vuelve a ejecutar este script."
}

$version = (Select-String -Path updater.py -Pattern 'APP_VERSION = "([^"]+)"').Matches.Groups[1].Value
if (-not $version) {
    throw "No se pudo leer APP_VERSION desde updater.py."
}

$iss = (Get-Content installer.iss -Raw) -replace '#define AppVersion "[^"]+"', "#define AppVersion `"$version`""
Set-Content installer.generated.iss $iss -Encoding ASCII
& $compiler installer.generated.iss
Remove-Item installer.generated.iss -Force

$installer = Get-ChildItem installer -Filter "AppLocker-Setup-$version.exe" | Select-Object -First 1
$hash = (Get-FileHash $installer.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
$size = "{0:N1} MB" -f ($installer.Length / 1MB)
$githubOwner = "Adricat32"
$githubRepo = "AppLocker"
$releaseTag = "v$version"

$manifest = [ordered]@{
    version = $version
    release_date = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd")
    size = $size
    summary = "Nueva versión de App Locker disponible."
    notes = "Actualiza este texto con los cambios de la versión."
    details_url = "https://github.com/$githubOwner/$githubRepo/releases/tag/$releaseTag"
    installer_url = "https://github.com/$githubOwner/$githubRepo/releases/download/$releaseTag/$($installer.Name)"
    sha256 = $hash
}
$manifest | ConvertTo-Json | Set-Content update.json -Encoding UTF8

Write-Host "Instalador: $($installer.FullName)"
Write-Host "SHA-256: $hash"
Write-Host "Manifiesto: $PSScriptRoot\update.json"
