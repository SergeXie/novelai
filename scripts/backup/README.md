# Windows MySQL 定时备份

该方案每天通过 Windows 任务计划程序调用 `mysqldump.exe`，数据库连接读取项目根目录的 `.env` 中的 `DATABASE_URL`。

## 1. 确认 MySQL 客户端工具

服务器需要存在 `mysqldump.exe` 和 `mysql.exe`。它们通常位于：

```text
C:\Program Files\MySQL\MySQL Server 8.4\bin\
```

如果没有，请安装与服务器版本兼容的 MySQL Client。脚本会搜索常见安装目录；也可以通过参数明确指定工具路径。

## 2. 先手动测试备份

在 PowerShell 中运行：

```powershell
cd D:\Workspace\novelAi
.\scripts\backup\backup-mysql.ps1 `
  -BackupRoot "D:\DatabaseBackups\novelAi" `
  -RetentionDays 30 `
  -MySqlDumpPath "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe"
```

成功后会生成：

```text
D:\DatabaseBackups\novelAi\backups\数据库名_日期时间.sql.zip
D:\DatabaseBackups\novelAi\logs\backup.log
```

如果 `mysqldump.exe` 已加入 PATH，`-MySqlDumpPath` 可以省略。

## 3. 安装每天执行的计划任务

以管理员身份打开 PowerShell，然后运行：

```powershell
cd D:\Workspace\novelAi
.\scripts\backup\install-backup-task.ps1 `
  -DailyAt "02:00" `
  -BackupRoot "D:\DatabaseBackups\novelAi" `
  -RetentionDays 30 `
  -MySqlDumpPath "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe"
```

任务默认以 Windows `SYSTEM` 账户运行，不要求用户保持登录。安装后立即测试：

```powershell
Start-ScheduledTask -TaskName "novelAi-MySQL-Backup"
Start-Sleep -Seconds 10
Get-ScheduledTaskInfo -TaskName "novelAi-MySQL-Backup"
Get-Content "D:\DatabaseBackups\novelAi\logs\backup.log" -Tail 20
```

`LastTaskResult` 为 `0` 表示成功。

## 4. 恢复备份

恢复会修改数据库，请先停止应用写入，并确认目标数据库无误：

```powershell
.\scripts\backup\restore-mysql.ps1 `
  -BackupZip "D:\DatabaseBackups\novelAi\backups\数据库名_2026-08-03_020000.sql.zip" `
  -MySqlPath "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe"
```

脚本要求手动输入 `RESTORE` 才会继续。

## 注意事项

- `.env` 必须使用标准 SQLAlchemy MySQL URL，例如 `mysql+aiomysql://用户:密码@主机:3306/数据库名`。
- 用户名、密码中的特殊字符应进行 URL 编码。
- 临时凭据文件只在执行期间创建，执行结束后自动删除。
- 本地备份无法防范整块硬盘损坏；建议再同步到 NAS 或对象存储。
- 至少每月在测试数据库上执行一次恢复演练。

## 完全脱离项目运行

新建独立目录，并复制所需文件：

```powershell
New-Item -ItemType Directory -Path "D:\DatabaseBackupTool" -Force
Copy-Item ".\scripts\backup\backup-mysql.ps1" "D:\DatabaseBackupTool\"
Copy-Item ".\scripts\backup\restore-mysql.ps1" "D:\DatabaseBackupTool\"
Copy-Item ".\scripts\backup\install-backup-task.ps1" "D:\DatabaseBackupTool\"
Copy-Item ".\scripts\backup\backup.env.example" "D:\DatabaseBackupTool\backup.env"
notepad "D:\DatabaseBackupTool\backup.env"
```

编辑 `backup.env`，只保留真实的 `DATABASE_URL`。手动测试：

```powershell
& "D:\DatabaseBackupTool\backup-mysql.ps1" `
  -EnvFile "D:\DatabaseBackupTool\backup.env" `
  -BackupRoot "D:\DatabaseBackups\novelAi" `
  -RetentionDays 30 `
  -MySqlDumpPath "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe"
```

确认成功后，以管理员身份安装独立计划任务：

```powershell
& "D:\DatabaseBackupTool\install-backup-task.ps1" `
  -EnvFile "D:\DatabaseBackupTool\backup.env" `
  -DailyAt "02:00" `
  -BackupRoot "D:\DatabaseBackups\novelAi" `
  -RetentionDays 30 `
  -MySqlDumpPath "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe"
```

限制配置文件只允许管理员和计划任务使用的 `SYSTEM` 账户访问：

```powershell
icacls "D:\DatabaseBackupTool\backup.env" /inheritance:r
icacls "D:\DatabaseBackupTool\backup.env" /grant:r "SYSTEM:F" "Administrators:F"
```
