$root = Split-Path -Parent $PSScriptRoot
$iverilog = Get-Command iverilog -ErrorAction SilentlyContinue
if (-not $iverilog) { throw 'iverilog was not found in PATH' }
$vvp = Get-Command vvp -ErrorAction SilentlyContinue
if (-not $vvp) { throw 'vvp was not found in PATH' }
$rtl = Get-ChildItem "$root\rtl\*.v" | ForEach-Object FullName
foreach ($tb in @('quadrature_decoder_tb','wheel_pi_controller_tb','motion_top_tb','motion_status_tx_tb','encoder_direction_tb','encoder_startup_tb','pi_signed_tb','feedback_timeout_tb','motion_stop_tb','differential_signed_tb','rotate_cancel_tb')) {
  $tbfile = "$PSScriptRoot\$tb.v"
  $out = "$PSScriptRoot\$tb.vvp"
  & $iverilog.Source -g2012 -Wall -s $tb -o $out $rtl $tbfile
  if ($LASTEXITCODE -ne 0) { throw "compile failed: $tb" }
  & $vvp.Source $out
  if ($LASTEXITCODE -ne 0) { throw "simulation failed: $tb" }
}
