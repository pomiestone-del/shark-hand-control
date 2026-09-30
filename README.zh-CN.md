# 鲨鱼头手势控制

[English](README.md) | 简体中文

通过电脑摄像头、MediaPipe Hand Landmarker 和 Arduino Uno 控制双舵机鲨鱼头。同一只手左右移动控制转头，手指张开或握紧控制嘴巴。画面只在本地处理，不保存、不上传。

## 当前状态

这是开发中的版本快照，并非已确认正常运行的发布版。当前源码存在两个已知问题：

1. `hand_preview.py` 绘制校准按钮时使用了不存在的 OpenCV 常量 `FONT_HERSHEY_pySIMPLEX`，正确名称是 `FONT_HERSHEY_SIMPLEX`。执行到该行会报错，预览模式也会受影响。
2. 固件设置为**闭嘴180°、张嘴0°**，但 Python 的 `Mouth target` 文字仍按**120°到0°**计算。实际输出由固件决定，画面中的这个预估值与固件不一致。

转头间歇性不动或完全不动的问题尚未确定根因。此前版本曾完成编译、上传并收到串口确认，但这些结果不能证明舵机实际转动。使用下方运行步骤前，需要修正启动错误并统一期望的嘴巴角度范围。

## 硬件与映射

| 部件 | 连接或行为 |
|---|---|
| 控制板 | Arduino Uno，默认USB串口 `COM7` |
| 转头舵机 | 信号线接 **D9** |
| 嘴巴舵机 | 信号线接 **D10** |
| 摄像头 | 电脑摄像头，默认编号 `0` |
| 转头映射 | 镜像画面左侧 → 120°，中间 → 90°，右侧 → 60° |
| 固件中的嘴巴映射 | 握拳 → 180°，完全张开手 → 0°，中间连续变化 |

转头使用画面中央70%的宽度进行映射，超出这一区域时限制在端点。`--reverse` 只反转转头方向。

舵机供电电压和可用电流应匹配具体型号。使用独立电源时，舵机电源与Uno需要共地。代码里的角度是指令值，不是实测机械角度，需要确认机构可用范围。

## 文件说明

| 文件 | 用途 |
|---|---|
| `Robot.ino` | 上传到Uno的固件 |
| `hand_preview.py` | 摄像头、手部识别、显示和串口控制 |
| `hand_mapping.py` | 手指弯曲程度估算及嘴巴连续映射 |
| `hand_landmarker.task` | 本地MediaPipe手部模型 |
| `start-control.cmd` | 一键启动COM7控制 |
| `start-reversed.cmd` | 反转转头方向后启动 |
| `start-preview.cmd` | 只预览摄像头，不连接串口 |
| `requirements.txt` | 固定版本的Python直接依赖 |
| `MODEL.md` | 模型来源与校验值 |
| `.gitignore` | 防止环境、缓存和日志进入Git |

## 安装

本项目在Windows上使用Python 3.10、Arduino AVR core 1.8.8及Servo 1.3.0开发。全新依赖环境尚未单独验证。

仓库为私有，需要访问权限。克隆时将本地文件夹命名为 `Robot`，使其与Arduino主文件名称一致：

```powershell
git clone https://github.com/pomiestone-del/shark-hand-control.git Robot
cd Robot
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`opencv-contrib-python` 已提供 `cv2`，不要在同一环境中额外安装另一种OpenCV发行包。

在Arduino IDE中打开 `Robot.ino`，安装 **Servo** 库和 **Arduino Uno** 开发板支持，选择实际USB串口并上传。启动Python前关闭串口监视器和串口绘图器。只修改电脑上的 `.ino` 文件不会更新控制板，必须重新上传。

## 运行

处理上述已知问题后，在项目文件夹中的PowerShell或Cursor Terminal运行：

```powershell
# 控制两个舵机
.\.venv\Scripts\python.exe hand_preview.py --port COM7

# 只预览摄像头
.\.venv\Scripts\python.exe hand_preview.py --preview

# 反转转头方向
.\.venv\Scripts\python.exe hand_preview.py --port COM7 --reverse

# 使用另一摄像头
.\.venv\Scripts\python.exe hand_preview.py --port COM7 --camera 1

# 输出识别和指令确认的诊断日志
.\.venv\Scripts\python.exe hand_preview.py --port COM7 --diagnostics
```

如果依赖装在系统Python中，可以把 `.\.venv\Scripts\python.exe` 换成 `python`。

双击 `.cmd` 启动文件也可以：存在项目内 `.venv` 时优先使用它，否则使用PATH中的 `python`。不要同时打开多个控制窗口。按 **Q**、**Esc** 或关闭摄像头窗口退出。

## 嘴巴校准

程序使用四根手指（不含拇指）的PIP关节平均角度估算张开程度，优先使用MediaPipe三维世界坐标关键点。默认将70°作为握拳、165°作为张开。这是几何估计，会受遮挡和识别误差影响。

让摄像头窗口获得焦点后：

1. 保持握拳入镜，按 **C** 或点击 **FIST**。
2. 张开手，按 **O** 或点击 **OPEN**。
3. 确认出现 `FIST SAVED` / `OPEN SAVED`。若出现 `NOT SAVED`，查看其后的原因。

大小写按键均可。校准仅在本次运行有效，两端校准值至少相差20°。修正启动错误后，不校准也能先使用默认映射。

## 控制行为

- 控制板启动时，两路舵机输出均未启用，各自在收到第一条有效位置指令后启用。
- 手的位置直接映射到微秒脉冲，不加软件平滑或转速渐变。发送频率上限为每秒50次，实际取决于画面处理速度。
- 手离开画面或退出程序时发送 `S`，停止更新目标，但**不会停用舵机输出或切断电源**。舵机仍可能继续到达或保持最后目标。
- 固件500毫秒指令超时同样保留最后的脉冲输出，不是急停功能。
- 跟踪过程中检测到控制板重启或缺少指令确认，Python会退出，不自动重连。
- `Arduino target` 和 `Arduino mouth` 是控制板确认的指令，不是位置传感器读数。

## 串口协议

115200波特率，ASCII指令，以换行符结束：

| 指令 | 含义及回复 |
|---|---|
| `?` | 查询身份 → `SHARK_READY` |
| `H0` … `H1000` | 归一化转头位置 → `OK <角度> <脉冲微秒数>` |
| `M0` … `M1000` | 张开比例：0为握拳，1000为张开 → `MOK <角度> <脉冲微秒数>` |
| `S` | 保持最后输出 → `STOPPED` |

当前端点计算值：转头 `H0` → 120° / 1781µs，`H1000` → 60° / 1162µs；嘴巴 `M0` → 180° / 2400µs，`M1000` → 0° / 544µs。

## 故障排查

| 现象 | 检查内容 |
|---|---|
| OpenCV字体常量报错 | 修正前述 `FONT_HERSHEY_pySIMPLEX` 拼写 |
| 找不到COM7 | 重新连接控制板，并在Arduino IDE确认实际串口 |
| 串口拒绝访问 | 关闭串口监视器、绘图器和其他控制进程 |
| `programmer is not responding` | 上传失败，新固件尚未确认写入 |
| 没收到 `SHARK_READY` | 确认串口并上传配套的 `Robot.ino` |
| 摄像头打不开 | 关闭其他摄像头软件，或尝试 `--camera 1` |
| 识别到手但不动 | 确认显示 `USB CONTROL`、确认角度是否变化；这些信息本身不能验证供电、接线或实际转动 |
| 持续嗡嗡响、发热或机构卡住 | 断开舵机电源后检查机构和供电，不要通电强行拨轴 |

调整范围时，修改 `HEAD_LEFT`、`HEAD_RIGHT`、`MOUTH_CLOSED`、`MOUTH_OPEN`，同步相关显示计算，然后重新上传固件。当前Servo库会把 `Servo.write(190)` 限制为180；扩大实际机械行程需要按具体型号标定脉冲。
