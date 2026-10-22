param([Parameter(Mandatory=$true)][string]$Compiler,
      [Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference = 'Stop'
$Compiler = (Resolve-Path -LiteralPath $Compiler).Path
$banner = (& $Compiler /O- (Join-Path $PSScriptRoot 'inno-version-probe.iss') 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw "Compiler version probe failed: $banner" }
$match = [regex]::Match($banner, 'Compiler engine version:\s*Inno Setup\s+(\d+\.\d+\.\d+(?:\.\d+)?)')
if (!$match.Success -or $match.Groups[1].Value -eq '0.0.0.0') {
    throw "No usable Inno Setup engine version in compiler output: $banner"
}
$version = $match.Groups[1].Value
$license = Join-Path (Split-Path $Compiler) 'license.txt'
if (!(Test-Path -LiteralPath $license)) { throw "Missing Inno Setup license: $license" }
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
Copy-Item -LiteralPath $license -Destination (Join-Path $Destination 'license.txt')
$version | Set-Content -LiteralPath (Join-Path $Destination 'version.txt') -Encoding utf8
$banner | Set-Content -LiteralPath (Join-Path $Destination 'compiler-banner.txt') -Encoding utf8
[ordered]@{version=$version; method='Compiler engine version from a no-output probe compilation';
    compilerSha256=(Get-FileHash -LiteralPath $Compiler -Algorithm SHA256).Hash.ToLower();
    fileVersion=(Get-Item -LiteralPath $Compiler).VersionInfo.FileVersion;
    productVersion=(Get-Item -LiteralPath $Compiler).VersionInfo.ProductVersion
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Destination 'version-evidence.json') -Encoding utf8
Write-Output "Inno Setup engine version: $version"
