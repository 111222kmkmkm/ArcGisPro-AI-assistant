# 诊断 ArcGISProAddin.dll 的加载错误
$ErrorActionPreference = 'Continue'
$dll = 'E:\arcGIS Pro\mcp_arcgis\addin\bin\x64\Release\net8.0-windows\ArcGISProAddin.dll'
$bin = 'E:\arcGIS Pro\bin'

# 让运行时能找到 ArcGIS 依赖 DLL
$resolver = {
    param($sender, $args)
    $name = (New-Object System.Reflection.AssemblyName($args.Name)).Name
    foreach ($dir in @($bin, "$bin\Extensions\Core", "$bin\Extensions\Mapping")) {
        $candidate = Join-Path $dir "$name.dll"
        if (Test-Path $candidate) {
            try { return [System.Reflection.Assembly]::LoadFrom($candidate) } catch {}
        }
    }
    return $null
}
[System.AppDomain]::CurrentDomain.add_AssemblyResolve($resolver)

Write-Host "=== 加载 DLL ==="
try {
    $asm = [System.Reflection.Assembly]::LoadFrom($dll)
    Write-Host "Assembly loaded OK:" $asm.FullName
} catch {
    Write-Host "LoadFrom FAILED:" $_.Exception.GetType().FullName
    Write-Host $_.Exception.Message
    if ($_.Exception.InnerException) { Write-Host "INNER:" $_.Exception.InnerException.Message }
    exit 1
}

Write-Host ""
Write-Host "=== 枚举类型 (这一步会暴露类型加载错误) ==="
try {
    $types = $asm.GetTypes()
    Write-Host "GetTypes OK, count =" $types.Count
    $types | Where-Object { $_.Name -like "*Button*" -or $_.Name -like "*Module*" -or $_.Name -like "*ViewModel*" } |
        ForEach-Object { Write-Host "  " $_.FullName "(public=" $_.IsPublic ")" }
} catch [System.Reflection.ReflectionTypeLoadException] {
    Write-Host "ReflectionTypeLoadException!"
    foreach ($le in $_.Exception.LoaderExceptions) {
        Write-Host "  LOADER ERROR:" $le.Message
    }
} catch {
    Write-Host "GetTypes FAILED:" $_.Exception.Message
    if ($_.Exception.InnerException) { Write-Host "INNER:" $_.Exception.InnerException.Message }
}
