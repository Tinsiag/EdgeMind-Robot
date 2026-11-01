param(
  [string]$Model = "yolov5n.onnx",
  [string]$OutDir = "output/th1520-yolov5n"
)
$py = "F:\conda-env\test\python.exe"
$hhb = "F:\conda-env\test\Scripts\hhb.exe"
if (!(Test-Path $hhb)) { throw "HHB executable missing: $hhb" }
New-Item -ItemType Directory -Force $OutDir | Out-Null
& $hhb -r $Model --board th1520 --input-strings "images" --input-shapes "images:1,3,384,640" --output-type "int8_asym" --quantization-scheme "int8_asym" --save-temps --output $OutDir
if ($LASTEXITCODE -ne 0) { throw "HHB conversion failed with exit code $LASTEXITCODE" }
