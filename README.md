# 鲨鱼头手势控制

用电脑摄像头追踪手掌的横向位置，通过 USB 串口控制 Arduino Uno 上的转头舵机。摄像头画面只在本地处理，不保存、不上传。

## 当前行为

- D9：转头舵机，范围60～120°。默认镜像画面左侧对应120°，中间90°，右侧60°。
- D10：嘴巴舵机，握拳闭嘴对应120°（1781us），完全张开手对应0°（544us），中间按张开比例连续映射。
- 手的位置直接映射目标角度，无软件平滑或转速限制。实际速度受摄像头、识别速度、舵机及机械负载限制。
- 串口发送上限50次/秒，实际取决于画面处理速度。
- 启动时不强制回中；D9、D10分别在首次收到对应手部指令时启用输出。
- 手离开画面时停止更新目标，保持最后命令的位置。没有位置传感器反馈，因此舵机可能继续到达该目标，并非急停或断电。
- 画面的 Arduino target 显示目标角度（两位小数）与控制板输出的脉冲微秒数，均不是实测机械角度。
- 运行期间检测到控制板重启，或持续发送指令却超过2秒没有角度确认时，Python 会报错退出，不自动重连。

## 文件

| 文件 | 用途 |
|---|---|
| Robot.ino | 当前 Arduino 固件 |
| hand_preview.py | 摄像头识别与串口控制 |
| hand_mapping.py | 四指弯曲程度计算及连续开合映射 |
| hand_landmarker.task | 已备份的 MediaPipe 模型 |
| start-control.cmd | 一键启动 COM7 控制 |
| start-reversed.cmd | 在当前默认方向上再次反转 |
| start-preview.cmd | 只预览摄像头 |
| requirements.txt | Python 依赖版本 |
| MODEL.md | 模型来源与校验值 |

## 从备份恢复

建议使用 Python 3.10（本项目使用3.10测试）、Arduino IDE、Arduino Uno 开发板支持包和 Servo 1.3.0 库。

克隆时把本地文件夹命名为 Robot，保持与 Arduino 主文件 Robot.ino 一致：

```powershell
git clone https://github.com/pomiestone-del/shark-hand-control.git Robot
cd Robot
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

requirements.txt 记录本机运行时的直接依赖版本。只安装 opencv-contrib-python 即提供 cv2，不要额外安装另一个 OpenCV 发行包。全新环境尚未单独验证。

在 Arduino IDE 中打开 Robot.ino，安装 Servo 库，选择 Arduino Uno 和实际 USB 串口，然后上传。串口默认 COM7；换电脑后可能不同。

接线：转头信号接D9，嘴巴信号接D10。舵机供电按具体型号匹配，使用独立电源时与 Uno 共地。60～120°只是当前软件范围，需要匹配机械活动范围。

## 启动

上传固件后，关闭串口监视器和串口绘图器，在项目文件夹的 PowerShell 或 Cursor Terminal 中运行：

```powershell
python hand_preview.py --port COM7
```

新建虚拟环境后，可以明确使用该环境：

```powershell
.\.venv\Scripts\python.exe hand_preview.py --port COM7
```

直接双击 start-control.cmd 也可以；启动文件使用系统PATH中的 python，若存在本目录 .venv 则优先使用它。

把一只手放进镜像画面并左右移动。按Q、Esc或关闭窗口退出。

```powershell
# 只预览，不连接控制板
python hand_preview.py --preview
# 将当前默认方向反过来
python hand_preview.py --port COM7 --reverse
# 使用另一摄像头
python hand_preview.py --port COM7 --camera 1
```

## 排查

- COM端口拒绝访问：关闭串口监视器、绘图器及其他控制窗口。
- 未收到 SHARK_READY：确认配套固件已上传、串口正确。
- programmer is not responding：这是上传通信失败，固件还没上传成功。
- 能识别但不转头：确认显示 USB CONTROL，并观察 Arduino target 是否变化。
- 机构顶住或舵机持续异常发热：断开舵机电源，检查机械范围及供电；Q退出仍保持输出，不等于断电。
- 调整范围：修改 Robot.ino 的 HEAD_LEFT、HEAD_RIGHT 后重新上传。

## 备份时验证

Arduino 编译和上传已通过，Python 摄像头识别与串口握手已通过。微秒控制版本已验证496→90.24°/1474us、500→90.00°/1472us、504→89.76°/1470us以及越界拒绝和停止指令。模型文件一并备份，可在恢复后离线加载。

## 微小转动的连续性

Arduino 使用 writeMicroseconds 直接映射0～1000位置到1781～1162微秒，保持原先60～120°的两个端点脉冲，避免整数角度仅61档造成的台阶。控制输出约620档，不代表舵机能机械分辨每一档；仍取决于舵机死区、齿轮和负载。没有增加平滑延迟或速度限制。

## 手掌开合控制嘴巴

同一只手的横向位置控制转头，四根手指（不含拇指）的PIP关节平均角度控制张嘴。使用MediaPipe三维手部关键点，默认70°弯曲对应握拳、165°对应张开。这是几何估计，遮挡和识别误差可能影响结果。

嘴巴目标角度 = 120 × (1 - 张开比例)（0～1）。微秒脉冲直接连续映射，不添加时间平滑或速度限制。手丢失时两路都保持最后命令，不主动回正。

若握拳/张开无法达到0%/100%，在摄像头窗口聚焦时握拳按C、伸直四指张开按O。校准只在本次运行生效；两个校准角至少相差20°才接受。屏幕显示Hand open百分比和Arduino mouth确认角度。

串口新增 M0～M1000，控制板返回 MOK 角度 脉冲。当前映射为M0→120°/1781us、M500→60°/1163us、M1000→0°/544us（端点为计算值；M250→90°/1472us及M500已验证返回）；实际开闭位置由舵机安装决定。

Servo.write(190)会被当前Servo库限制为180，程序角度不等于已经测量的机械角度。超过现有范围必须根据具体舵机规格校准脉冲端点，不能仅因为手拨得动就扩大范围。

校准也支持点击画面底部 FIST / OPEN 按钮，键盘C/O不区分大小写。校准成功或失败会显示屏幕提示；启动后即可按默认参数控制，不必先校准。
