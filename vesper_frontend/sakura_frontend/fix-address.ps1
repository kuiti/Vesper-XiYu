# fix-address.ps1
# 自动将前端所有文件中的 localhost:8001 替换为 127.0.0.1:8001

$files = @(
    "src\App.vue",
    "src\components\SettingsPanel.vue",
    "src\components\MemoryPanel.vue",
    "src\components\SearchPanel.vue",
    "src\components\ChatManagePanel.vue",
    "src\components\TodoList.vue",
    "src\components\NoteList.vue",
    "src\components\RAGPanel.vue"
)

foreach ($file in $files) {
    $path = Join-Path $PSScriptRoot $file
    if (Test-Path $path) {
        Write-Host "正在处理: $file"
        $content = Get-Content $path -Raw -Encoding UTF8
        $content = $content -replace 'http://localhost:8001', 'http://127.0.0.1:8001'
        $content = $content -replace 'ws://localhost:8001', 'ws://127.0.0.1:8001'
        Set-Content $path -Value $content -Encoding UTF8 -NoNewline
        Write-Host " 完成" -ForegroundColor Green
    } else {
        Write-Host "跳过（文件不存在）: $file" -ForegroundColor Yellow
    }
}

Write-Host "`n所有文件处理完成！" -ForegroundColor Cyan