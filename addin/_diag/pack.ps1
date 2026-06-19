$ErrorActionPreference = 'Stop'
$bd = 'E:\arcGIS Pro\mcp_arcgis\addin\bin\x64\Release\net8.0-windows'
$output = 'E:\arcGIS Pro\mcp_arcgis\addin\ArcGISProAddin.esriAddinX'

Remove-Item $output -ErrorAction SilentlyContinue
Add-Type -Assembly System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($output, 'Create')

# Config.daml at root
[System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
    $zip, (Join-Path $bd 'Config.daml'), 'Config.daml') | Out-Null

# DLL + deps under Install/ (ArcGIS Pro standard layout)
foreach ($file in @('ArcGISProAddin.deps.json', 'ArcGISProAddin.dll', 'ArcGISProAddin.pdb')) {
    $entryName = 'Install/' + $file
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip, (Join-Path $bd $file), $entryName) | Out-Null
}
$zip.Dispose()

Write-Host ('Packaged: ' + (Get-Item $output).Length + ' bytes')
Write-Host '--- entries ---'
$z = [System.IO.Compression.ZipFile]::OpenRead($output)
$z.Entries | ForEach-Object { Write-Host ('  ' + $_.FullName) }
$z.Dispose()
