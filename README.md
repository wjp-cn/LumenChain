# 光启 LumenChain

原生 Windows 桌面应用：一次编排，一键启动。Python 3.11+、PySide6、Qt Widgets，无账号、数据库或运行时联网要求。

支持从桌面或资源管理器把应用图标拖入软件列表，直接添加 EXE、LNK 快捷方式、BAT、CMD，也可一次拖入多个文件。添加后自动保存，不会立即执行；重复路径自动跳过，双击条目可进一步设置参数与就绪条件。尚未创建方案时会先提示创建。为兼容已有配置和开机启动设置，目前 EXE 文件名及 AppData 数据目录继续使用 LaunchFlow。

## 许可：仅限非商业用途

本项目原创代码采用 [PolyForm Noncommercial License 1.0.0](LICENSE)（SPDX：`PolyForm-Noncommercial-1.0.0`）。允许在协议规定的非商业用途范围内使用、学习、修改和分发；**不授予商业使用权**。商业使用须事先取得相关权利人的单独授权。

分发原版或修改版时，须保留许可条款或协议链接，以及协议要求保留的声明。具体许可范围、例外和条件以 [LICENSE 原文](LICENSE) 为准；本节为中文摘要。

由于限制商业使用，本项目属于“源码可用（source-available）”项目，不属于 OSI 定义的开源软件。第三方依赖继续适用各自的许可，本协议不限制其原有权利，详见 [第三方许可说明](THIRD_PARTY_NOTICES.md)。

## 直接使用

当前 1.1.0 构建：`dist/1.1.0/LaunchFlow/LaunchFlow.exe`，单文件版为 `dist/1.1.0/LaunchFlow.exe`。退出旧版后再打开新版，已有方案会继续保留。请复制整个 `dist/1.1.0/LaunchFlow` 目录，保留 `_internal`，不能只复制其中的 EXE。双击运行，无需安装 Python。

首次运行为空白方案库，不会自动启动任何第三方程序。新建方案后点击“添加软件”，选择 EXE、LNK、BAT 或 CMD。编辑弹窗可填写参数、工作目录、就绪条件与失败策略。双击条目编辑；右键可单独启动、移动、启用、删除；拖动列表调整顺序，立即保存。方案操作菜单支持复制、重命名、描述、默认方案及删除。

- 立即继续：系统接受启动命令即处理下一项，不表示软件已经加载完成。
- 延迟：命令接受后等待指定秒数，可随时停止。
- 等待就绪：检测目标进程、窗口标题或 TCP 连接。Docker 等后台服务建议配置独立的 TCP 条件；请使用服务实际提供的端口，不要为此开启未经保护的 Docker API。TCP 连接成功只能证明端口可连接，不能保证业务健康。

“跳过已运行”只跳过启动命令，仍执行配置的就绪检测。完整路径优先匹配；同名不同安装目录不会直接判定为已运行。权限导致无法确认时会记录提示，避免盲目重复启动。可明确设置进程名作为权限不足时的降级匹配。

所有入口共用一条执行队列。启动开发方案期间点击办公方案、单独启动、托盘方案或从第二实例请求启动，会提示已有方案执行。开机倒计时同样占用启动入口，可点击停止取消。当前运行使用方案快照，编辑只影响下一次运行。停止只取消后续调度与当前等待，保留已运行软件。

## 开发运行

建议 Python 3.12 x64（最低 3.11）：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py
.\.venv\Scripts\python -m pytest -q
```

本工作区已经准备 `.venv312`，可直接执行：

```powershell
.\.venv312\Scripts\python main.py
.\.venv312\Scripts\python -m pytest -q
```

`requirements-lock.txt` 记录本次验证使用的完整版本。联网只在安装构建依赖时需要；离线安装可使用预先下载的 wheels：`python -m pip install --no-index --find-links wheels -r requirements-lock.txt`。

## 托盘与开机启动

设置中明确开启“开机启动编排器”，才会写入当前用户 HKCU Run 的 LaunchFlow 值，无需管理员权限。再开启“开机自动执行方案”、选择默认方案并设置延迟，才会在开机后自动运行。默认均关闭。方案删除后取消对应的自动执行设置。

```powershell
LaunchFlow.exe --autostart --minimized
LaunchFlow.exe --profile <方案ID>
LaunchFlow.exe --minimized
```

第二次打开会通过本地实例通信唤出已有窗口；合法 `--profile` 请求会转给已有实例。托盘单击/双击可恢复窗口，菜单可启动方案或退出。系统托盘不可用时，即使传入 `--minimized` 也显示窗口。首次关闭到托盘时有说明。

移动 EXE 后配置仍保留；若自启动命令指向旧位置，下次运行会提示进入设置保存修复。仅在设置保存时修改开机注册表，不在普通启动时偷偷修复。

## 数据与日志

默认数据目录：`%APPDATA%\LaunchFlow`，包含 `config.json`、`profiles.json`、`backups` 和 `logs`。程序不在源码目录或 onefile 解包目录保存用户数据。JSON 使用 UTF-8、写入前校验、临时文件与原子替换，保留上一次有效版本；主文件损坏尝试恢复备份并提示，主文件与备份均损坏则保留文件并报错。

“数据管理”提供目录入口和导入/导出。导入先展示方案名称与软件数量，选择新增（生成新 ID）或覆盖同 ID（二次确认），不会导入系统开机设置或执行程序。外部配置中的脚本与参数应在启动前审阅。

“查看日志”打开最近日志，按方案名、批次标识或关键字过滤，支持刷新、复制、导出和清空。每个运行批次独立标识，单文件 2 MB，最多保留 5 个轮转文件。不记录启动参数，减少令牌等信息意外写入日志的机会。

## 构建

```powershell
.\build.bat
.\build.bat onefile
```

默认 onedir：`dist/LaunchFlow/LaunchFlow.exe`，可选 onefile：`dist/LaunchFlow.exe`。脚本先运行测试，通过后构建，无控制台窗口。已有 `.venv312` 时优先使用它，否则使用或创建 `.venv`。也可以直接执行 `python -m PyInstaller --noconfirm launchflow.spec`；设置 `LAUNCHFLOW_ONEFILE=1` 切换单文件。开发环境应使用 Python 3.11+。

## 设计与验证

- [配置与调度设计](docs/architecture.md)
- [测试结果及验证边界](docs/validation.md)
- [第三方许可说明](THIRD_PARTY_NOTICES.md)

当前发布验证以 Windows 11 x64、Python 3.12、onedir 为准。Windows 10、真实登录自启动、UAC 人工拒绝、多显示器 DPI、休眠恢复与 onefile 的完整兼容性仍待实机验证，不能据本次自动化结果视作全部验收完成。
