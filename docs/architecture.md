# 配置与调度设计

## 分层

- `app/models/profile.py`：Application、Profile、字段校验、复制与 ID 重建。
- `app/services/config_service.py`：AppData 存储、JSON 验证、备份恢复、原子替换。
- `app/core/launcher.py`：快捷方式解析、Windows 参数拆分、EXE/脚本启动、UAC 降级。
- `app/core/process_monitor.py`：完整可执行路径优先，明确权限不确定状态。
- `app/core/readiness_checker.py`：进程、可见窗口标题与可选路径关联、TCP 连接。
- `app/core/scheduler.py`：纯 Python 调度引擎、注入依赖测试，不依赖 Qt。
- `app/core/single_instance.py`：QLockFile 选主、QLocalServer/QLocalSocket 请求转发、同用户访问。
- `app/core/startup_manager.py`：仅 HKCU Run / LaunchFlow 值。
- `app/ui`：Qt 控件、方案编辑、日志与设置，调度信号在 GUI 线程接收。

## 执行合同

所有启动入口先调用统一 `start`。开机倒计时也占用启动入口；执行保留 token，防止取消后的旧定时器触发新任务。Scheduler 用锁在启动后台线程前同步占位，拒绝第二方案；深拷贝冻结当前方案。后台线程顺序处理启用项目：解析目标→运行检测→提交启动命令→等待策略→进度。采用 Event.wait 与 monotonic 时钟等待，取消不会终止第三方进程。退出先取消，再由 GUI 定时观察线程退出，避免主线程阻塞或释放活跃任务。

已运行项目仍执行就绪策略。进程、窗口、TCP 是不同证据，不互相替代。命令提交成功后就绪失败的重试只重试检测，避免因业务启动慢而重复创建应用进程。命令提交本身失败则可重试提交。超时按条目失败策略继续、停止或重试后继续。汇总分别报告命令提交和失败，二者可以重叠（例如命令接受但 TCP 超时）。未完成数量包含取消当前等待及未执行条目。

## JSON

两个文件均写 `schema_version: 1`。profiles.json 含 profiles 数组，每项为 Profile dataclass 序列化：id、name、description、created_at、modified_at、applications（有序数组）。Application 含 id、name、path、arguments（Windows 原始参数字符串）、working_directory、enabled、skip_if_running、launch_strategy（immediate/delay/ready）、delay_seconds、failure_action（continue/stop/retry）、retry_count、retry_interval、process_name、readiness。

readiness 为 kind（process/window/tcp）、value（进程名或标题关键字）、host、port、timeout、interval、associate。进程名留空按解析后可执行文件路径检测。窗口关联也使用目标路径对应的进程集合，不假设启动器 PID 等于最终进程。

config.json 的 settings 保存外观、关闭行为、自启动开关、默认方案、默认等待/重试策略等。导入只读取 profiles，不接受系统设置。

缺失 schema_version 的初版格式视为 v1；示例中的 arguments 数组通过 Windows list2cmdline 迁移为参数字符串；null readiness 转为默认条件，下一次保存统一写 v1。未知版本明确拒绝，不猜测新版本结构。

每次保存验证后写同目录临时文件，flush/fsync，再 os.replace。上一次有效主文件复制到 backups。备份恢复后保存不会用损坏主文件覆盖有效备份。两个 JSON 分别原子写入，并非跨文件事务；磁盘写入失败时界面提示，用户应在退出前重试保存。

## 平台边界

EXE 用 CommandLineToArgvW 拆分参数列表，shell=False。BAT/CMD 明确使用 cmd.exe /d /s /c 和原始 Windows 引号规则；脚本参数可包含命令解释器语法。LNK 通过 Windows 自带 PowerShell / WScript.Shell 解析目标、参数与工作目录；非文件 Shell 虚拟目标不支持，解析失败明确报错。提权 EXE 使用 ShellExecuteW runas，拒绝返回错误；不能获得 PID 时返回 None，就绪仍独立检测。

进程检测无法证明业务健康。TCP 检测无法证明响应内容正确；远端 DNS 的系统解析可能增加取消响应时间，建议本地检测使用 IP。Windows 环境禁用 PowerShell/COM 的企业策略会限制 LNK。日志不输出参数，但异常栈可能包含程序路径，不应将日志直接公开。
