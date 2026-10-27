param(
    [string] $RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
)

$docsRoot = Join-Path $RepositoryRoot 'docs'
$currentFolder = Join-Path $docsRoot 'estado-actual-2026-08-27'
$outputPath = Join-Path $currentFolder 'data\inventario-documental.json'

$files = Get-ChildItem -LiteralPath $docsRoot -Recurse -File |
    Where-Object { -not $_.FullName.StartsWith($currentFolder, [System.StringComparison]::OrdinalIgnoreCase) } |
    Sort-Object FullName |
    ForEach-Object {
        $relative = $_.FullName.Substring($docsRoot.Length + 1).Replace('\', '/')
        $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
        [pscustomobject]@{
            path = $relative
            extension = $_.Extension.ToLowerInvariant()
            bytes = $_.Length
            modified_at = $_.LastWriteTimeUtc.ToString('o')
            sha256 = $hash
        }
    }

$duplicates = $files |
    Group-Object sha256 |
    Where-Object Count -gt 1 |
    ForEach-Object {
        [pscustomobject]@{
            sha256 = $_.Name
            count = $_.Count
            paths = @($_.Group.path)
        }
    }

$byExtension = [ordered]@{}
$files | Group-Object extension | Sort-Object Name | ForEach-Object {
    $byExtension[$_.Name] = $_.Count
}

$inventory = [ordered]@{
    schema_version = '1.0'
    generated_at = (Get-Date).ToUniversalTime().ToString('o')
    scope = 'Contenido previo de docs; excluye docs/estado-actual-2026-08-27.'
    total_files = $files.Count
    total_bytes = ($files | Measure-Object bytes -Sum).Sum
    by_extension = $byExtension
    files = @($files)
    duplicate_content_groups = @($duplicates)
}

$inventory | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $outputPath -Encoding utf8 -ErrorAction Stop
Write-Output "Inventario generado: $outputPath ($($files.Count) archivos)."
