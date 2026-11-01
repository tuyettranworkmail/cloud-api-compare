param(
    [string]$Path = "reports/generated/demo/benchmark_results_demo.xlsx",
    [string]$PreviewDirectory = "reports/excel_previews"
)
$ErrorActionPreference = "Stop"
$targetPath = (Resolve-Path -LiteralPath $Path).Path
$previewPath = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $PreviewDirectory))
[void][System.IO.Directory]::CreateDirectory($previewPath)
$excelApp = $null
$book = $null
$sheetErrors = @()
try {
    $excelApp = New-Object -ComObject Excel.Application
    $excelApp.Visible = $false
    $excelApp.DisplayAlerts = $false
    $excelApp.AskToUpdateLinks = $false
    $excelApp.AutomationSecurity = 3
    $book = $excelApp.Workbooks.Open($targetPath, 0, $false)
    $excelApp.CalculateFullRebuild()
    $book.Save()
    foreach ($sheet in $book.Worksheets) {
        $badCells = $null
        try { $badCells = $sheet.UsedRange.SpecialCells(-4123, 16) } catch {}
        if ($null -ne $badCells) { $sheetErrors += "$($sheet.Name): $($badCells.Address())" }
        $sheet.PageSetup.Zoom = $false
        $sheet.PageSetup.FitToPagesWide = 1
        $sheet.PageSetup.FitToPagesTall = 1
        $sheet.PageSetup.Orientation = 2
        $sheet.PageSetup.PaperSize = 8
        if ($sheet.Name -eq "Overview") { $sheet.PageSetup.PrintArea = "A1:I39" }
        elseif ($sheet.Name -eq "Cost Summary") { $sheet.PageSetup.PrintArea = "N1:AA36" }
        elseif ($sheet.Name -eq "Method and Provenance") { $sheet.PageSetup.PrintArea = "A1:H18" }
        elseif ($sheet.Name -eq "Assumptions") { $sheet.PageSetup.PrintArea = "A1:F16" }
        else { $sheet.PageSetup.PrintArea = "A1:H16" }
        $pdfPath = Join-Path $previewPath ($sheet.Name.Replace(" ", "_") + ".pdf")
        $sheet.ExportAsFixedFormat(0, $pdfPath, 0, $true, $false)
        Write-Output "Rendered: $($sheet.Name)"
    }
    if ($sheetErrors.Count -gt 0) { throw ("Formula errors: " + ($sheetErrors -join "; ")) }
    $book.Close($false)
    $book = $null
    Write-Output "PASS: native Excel recalculated; no formula errors; all sheet previews exported."
} finally {
    if ($null -ne $book) { $book.Close($false) }
    if ($null -ne $excelApp) { $excelApp.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($excelApp) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
