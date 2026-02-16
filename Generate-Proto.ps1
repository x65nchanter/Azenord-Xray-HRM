# 1. Фикс зависимостей
pip install "setuptools<70.0.0" --quiet

# 2. Сборка URL
$base_url = "https://github.com"
$repo_path = "/XTLS/Xray-core.git"
$full_url = "${base_url}${repo_path}"

# 3. Полный sparse-checkout
if (Test-Path "proto_src")
{ Remove-Item -Recurse -Force "proto_src" 
}
git clone --depth 1 --filter=blob:none --sparse $full_url proto_src
cd proto_src
git sparse-checkout set app common proxy transport core
cd ..

# 4. Собираем ВСЕ файлы из нужных директорий (теперь без ошибок путей)
$proto_files = Get-ChildItem -Path "proto_src/app", "proto_src/common", "proto_src/proxy", "proto_src/transport", "proto_src/core" -Filter *.proto -Recurse | ForEach-Object {
    Resolve-Path -Path $_.FullName -Relative
}

# 5. Компиляция
Write-Host "📡 Компиляция всех протоколов..." -ForegroundColor Cyan
python -m grpc_tools.protoc `
    --proto_path="./proto_src" `
    --python_out="./app/core/xray_api" `
    --grpc_python_out="./app/core/xray_api" `
    $proto_files

# 6. Глобальный фикс импортов
Write-Host "🧪 Фикс импортов..." -ForegroundColor Yellow
$generated = Get-ChildItem -Path "app/core/xray_api" -Filter *.py -Recurse
foreach ($file in $generated)
{
    (Get-Content $file.FullName) `
        -replace '^import (app|common|proxy|transport|core)', 'from . import $1' `
        -replace '^from (app|common|proxy|transport|core)', 'from . $1' |
        Set-Content $file.FullName
}

# 7. Финализация __init__.py
Get-ChildItem -Path "app/core/xray_api" -Directory -Recurse | ForEach-Object {
    $initFile = Join-Path $_.FullName "__init__.py"
    if (!(Test-Path $initFile))
    { New-Item -ItemType File -Path $initFile -Force | Out-Null 
    }
}

Write-Host "✅ ПОБЕДА! Инфраструктура сгенерирована." -ForegroundColor Green
