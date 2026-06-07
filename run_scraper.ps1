# sedori-navi scraper launcher (Task Scheduler)
$REPO    = "C:\Users\makki\sedori-navi"
$SCRAPER = "$REPO\scraper"
$PYTHON  = "C:\Users\makki\AppData\Local\Programs\Python\Python311\python.exe"
$LOG     = "$REPO\logs\scraper.log"

New-Item -ItemType Directory -Force -Path "$REPO\logs" | Out-Null

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "$ts $msg"
    Add-Content -Path $LOG -Value $line -Encoding UTF8
    Write-Output $line
}

Write-Log "=== START ==="

Set-Location $REPO
Write-Log "--- sync before scrape ---"
git fetch origin main 2>&1 | ForEach-Object { Write-Log "$_" }
if ($LASTEXITCODE -ne 0) {
    Write-Log "WARNING: git fetch before scrape failed (exit $LASTEXITCODE) - continuing"
} else {
    git rebase --autostash origin/main 2>&1 | ForEach-Object { Write-Log "$_" }
    if ($LASTEXITCODE -ne 0) {
        Write-Log "WARNING: git rebase before scrape failed (exit $LASTEXITCODE) - aborting rebase and continuing with local state"
        git rebase --abort 2>&1 | ForEach-Object { Write-Log "$_" }
    }
}

Write-Log "--- scrape.py start ---"
$env:PYTHONUNBUFFERED = "1"
$env:SEDORI_FORCE_SCRAPE = "1"
$r1 = & $PYTHON "$SCRAPER\scrape.py" 2>&1
Remove-Item Env:\SEDORI_FORCE_SCRAPE -ErrorAction SilentlyContinue
$r1 | ForEach-Object { Write-Log "$_" }
if ($LASTEXITCODE -ne 0) {
    Write-Log "ERROR: scrape.py failed (exit $LASTEXITCODE)"
    exit 1
}
Write-Log "--- scrape.py done ---"

Write-Log "--- scrape_yahoo.py start ---"
$r2 = & $PYTHON "$SCRAPER\scrape_yahoo.py" 2>&1
$r2 | ForEach-Object { Write-Log "$_" }
if ($LASTEXITCODE -ne 0) {
    Write-Log "WARNING: scrape_yahoo.py failed (exit $LASTEXITCODE) - continuing"
}
Write-Log "--- scrape_yahoo.py done ---"

Write-Log "--- copy to docs/ ---"
Copy-Item "$REPO\data\prices.csv"      "$REPO\docs\prices.csv"      -Force
Copy-Item "$REPO\data\msrp.csv"        "$REPO\docs\msrp.csv"        -Force
Copy-Item "$REPO\data\last_scrape.txt" "$REPO\docs\last_scrape.txt" -Force
if (Test-Path "$REPO\data\last_yahoo_scrape.txt") {
    Copy-Item "$REPO\data\last_yahoo_scrape.txt" "$REPO\docs\last_yahoo_scrape.txt" -Force
}

Write-Log "--- generate_coverage_report.py start ---"
New-Item -ItemType Directory -Force -Path "$REPO\reports" | Out-Null
$r3 = & $PYTHON "$SCRAPER\generate_coverage_report.py" 2>&1
$r3 | ForEach-Object { Write-Log "$_" }
if ($LASTEXITCODE -ne 0) {
    Write-Log "WARNING: generate_coverage_report.py failed (exit $LASTEXITCODE) - continuing"
} else {
    Write-Log "--- generate_coverage_report.py done ---"
}

Write-Log "--- coverage summary check ---"
$csvPath = "$REPO\reports\coverage_matrix.csv"
if (Test-Path $csvPath) {
    $rows = Import-Csv $csvPath
    $zero = @()
    $one = @()
    foreach ($row in $rows) {
        $count = [int]$row.ever_buyback_store_count
        if ($count -eq 0) { $zero += $row.product_name }
        if ($count -eq 1) { $one += $row.product_name }
    }

    Write-Log "COVERAGE: store_count_0 = $($zero.Count)"
    if ($zero.Count -gt 0) { Write-Log "COVERAGE: store_count_0_products: $($zero -join ', ')" }
    Write-Log "COVERAGE: store_count_1 = $($one.Count)"
    if ($one.Count -gt 0) { Write-Log "COVERAGE: store_count_1_products: $($one -join ', ')" }

    $prevPath = "$REPO\reports\coverage_matrix_prev.csv"
    if (Test-Path $prevPath) {
        $prevRows = Import-Csv $prevPath
        $prevMap = @{}
        foreach ($pr in $prevRows) {
            $prevMap[$pr.product_name] = [int]$pr.ever_buyback_store_count
        }

        $degraded = @()
        foreach ($row in $rows) {
            $count = [int]$row.ever_buyback_store_count
            $prev = if ($prevMap.ContainsKey($row.product_name)) { $prevMap[$row.product_name] } else { $count }
            if ($count -lt $prev) { $degraded += "$($row.product_name)($prev->$count)" }
        }

        if ($degraded.Count -gt 0) {
            Write-Log "COVERAGE WARNING: degraded_products: $($degraded -join ', ')"
        } else {
            Write-Log "COVERAGE: no degraded products"
        }
    }

    Copy-Item $csvPath "$REPO\reports\coverage_matrix_prev.csv" -Force
} else {
    Write-Log "WARNING: coverage_matrix.csv not found"
}

Write-Log "--- log error check ---"
$today = Get-Date -Format "yyyy-MM-dd"
if (Test-Path $LOG) {
    $errLines = Get-Content $LOG | Where-Object { $_ -match $today -and ($_ -match "ERROR" -or $_ -match "failed" -or $_ -match "Traceback" -or $_ -match "Exception") }
    if ($errLines.Count -gt 0) {
        Write-Log "LOG WARNING: today's error-like lines = $($errLines.Count)"
    } else {
        Write-Log "LOG: no error-like lines today"
    }
}

Write-Log "--- git add/commit/push ---"
Set-Location $REPO

git add data/prices.csv docs/prices.csv data/last_scrape.txt docs/last_scrape.txt 2>&1 | ForEach-Object { Write-Log "$_" }
if (Test-Path "data\last_yahoo_scrape.txt") {
    git add data/last_yahoo_scrape.txt docs/last_yahoo_scrape.txt 2>&1 | ForEach-Object { Write-Log "$_" }
}
if (Test-Path "reports\coverage_matrix.md") {
    git add reports/coverage_matrix.md reports/coverage_matrix.csv 2>&1 | ForEach-Object { Write-Log "$_" }
}

git diff --cached --quiet
$changed = ($LASTEXITCODE -ne 0)

if ($changed) {
    git commit -m "chore: update prices $today" 2>&1 | ForEach-Object { Write-Log "$_" }
    if ($LASTEXITCODE -ne 0) {
        Write-Log "ERROR: git commit failed"
        exit 1
    }

    git fetch origin main 2>&1 | ForEach-Object { Write-Log "$_" }
    if ($LASTEXITCODE -eq 0) {
        git rebase --autostash origin/main 2>&1 | ForEach-Object { Write-Log "$_" }
        if ($LASTEXITCODE -ne 0) {
            Write-Log "ERROR: git rebase before push failed"
            git rebase --abort 2>&1 | ForEach-Object { Write-Log "$_" }
            exit 1
        }
    } else {
        Write-Log "WARNING: git fetch before push failed (exit $LASTEXITCODE) - trying push anyway"
    }

    git push origin main 2>&1 | ForEach-Object { Write-Log "$_" }
    if ($LASTEXITCODE -eq 0) {
        Write-Log "=== push OK ==="
    } else {
        Write-Log "ERROR: git push failed"
        exit 1
    }
} else {
    Write-Log "No changes - skipping commit"
}

Write-Log "=== DONE ==="
