$root = Split-Path -Parent $PSScriptRoot
$iverilog = Get-Command iverilog -ErrorAction SilentlyContinue
if (-not $iverilog) { throw 'iverilog was not found in PATH' }
$vvp = Get-Command vvp -ErrorAction SilentlyContinue
if (-not $vvp) { throw 'vvp was not found in PATH' }
$rtl = Get-ChildItem "$root\rtl\*.v" | ForEach-Object FullName
New-Item -ItemType Directory -Force "$root\.local\sim" | Out-Null
foreach ($test in Get-ChildItem "$PSScriptRoot\*_tb.v") {
  $tb = $test.BaseName
  $tbfile = $test.FullName
  $out = "$root\.local\sim\$tb.vvp"
  & $iverilog.Source -g2012 -Wall -s $tb -o $out $rtl $tbfile
  if ($LASTEXITCODE -ne 0) { throw "compile failed: $tb" }
  $result = & $vvp.Source $out 2>&1
  $result | Tee-Object -FilePath "$root\.local\sim\$tb.log"
  if ($LASTEXITCODE -ne 0 -or ($result -match 'FATAL|FAIL') -or -not ($result -match 'PASS')) {
    throw "simulation failed: $tb"
  }
}
