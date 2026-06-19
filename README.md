# ArcGIS Pro MCP 插件

基于 Model Context Protocol (MCP) 的 ArcGIS Pro AI 助手插件，支持自然语言驱动 GIS 分析、自动化工作流执行、地图控制等功能。

---

## 功能概览

### AI 对话面板
- 自然语言交互，AI 自动识别 GIS 分析意图
- 支持多轮对话，上下文记忆
- 回车发送，Shift+回车换行
- 连接文件夹功能，AI 可直接读取文件夹中的数据
- 自动获取当前工作空间和内容窗格图层信息
- 支持多种 AI 模型（Claude、MiMo 等兼容 Anthropic API 的模型）

### 工作流引擎
- AI 自动生成分析步骤链，可视化显示在工作流面板
- 支持自定义步骤（AI 可定义每步的工具和参数）
- 逐步执行或一键全部执行
- 实时状态更新（灰色=待执行，蓝色=执行中，绿色=成功，红色=失败）
- 执行失败时 AI 自动分析错误并重试（最多 5 次）
- 执行成功后自动将输出图层添加到地图

### 支持的 GIS 工具（50+）

#### 空间分析
| 工具 | 说明 |
|------|------|
| Buffer | 缓冲区分析 |
| Clip | 裁剪 |
| Intersect | 交集叠加 |
| Union | 并集合并 |
| Erase | 擦除 |
| Spatial Join | 空间连接 |
| Select | 要素选择 |
| Near | 最近距离分析 |
| Dissolve | 融合 |

#### 数据管理
| 工具 | 说明 |
|------|------|
| Add Field | 添加字段 |
| Calculate Field | 计算字段值 |
| Select By Attribute | 属性查询 |
| Select By Location | 位置选择 |
| Project | 投影变换 |
| Copy Features | 复制要素 |
| Create Feature Class | 创建要素类 |
| Clip Raster | 裁剪栅格 |
| Delete | 删除数据 |

#### 栅格分析
| 工具 | 说明 |
|------|------|
| Slope | 坡度分析 |
| Aspect | 坡向分析 |
| HillShade | 山体阴影 |
| Viewshed | 通视分析 |
| Kernel Density | 核密度估计 |
| Reclassify | 重分类 |
| Zonal Statistics | 分区统计 |
| Raster Calculator | 栅格计算器 |
| Con | 条件判断 |
| IDW | 反距离权重插值 |

#### 网络分析
| 工具 | 说明 |
|------|------|
| Make Route Layer | 创建路径图层 |
| Make Service Area Layer | 服务区分析 |
| Make OD Cost Matrix Layer | 起止点成本矩阵 |
| Make Closest Facility Layer | 最近设施点 |
| Add Locations | 添加分析位置 |
| Solve | 求解网络分析 |

#### 空间统计
| 工具 | 说明 |
|------|------|
| Hot Spots (Getis-Ord Gi*) | 热点分析 |
| Cluster/Outlier Analysis | 聚类与异常值分析 |
| Spatial Autocorrelation | 空间自相关 |
| Optimized Hot Spot Analysis | 优化热点分析 |
| Space Time Cube | 时空立方体 |
| Emerging Hot Spots | 新兴热点分析 |

#### 地图制图
| 工具 | 说明 |
|------|------|
| Add Layer To Map | 添加图层到地图 |
| Apply Symbology | 应用符号化样式 |
| Export Map (PDF/PNG) | 导出地图 |
| Zoom To Layer | 缩放到图层 |
| Set Layer Visibility | 显示/隐藏图层 |

#### MCP 高级工具
| 工具 | 说明 |
|------|------|
| plan_workflow | 生成工作流步骤链 |
| execute_workflow | 执行工作流 |
| execute_single_tool | 执行任意 arcpy 工具 |
| describe_data | 查看数据信息（字段、坐标系、范围） |
| list_workspace_data | 列出工作空间数据集 |
| search_gis_tools | 按关键字搜索工具 |
| get_map_info | 获取当前地图信息 |
| set_arcpy_env | 设置 arcpy 环境 |
| check_extensions | 检查扩展许可 |

---

## 系统要求

- **操作系统**: Windows 10/11 (64-bit)
- **ArcGIS Pro**: 3.0 或更高版本
- **Python**: ArcGIS Pro 内置 Python 3.11 (arcgispro-py3)
- **.NET**: .NET 8.0 SDK（编译 Add-In 时需要）
- **AI API**: Anthropic API Key 或兼容 Anthropic API 的第三方服务（如 MiMo）

---

## 安装步骤

### 第一步：放置插件文件

将 `mcp_arcgis/` 目录整体放到 **ArcGIS Pro 安装根目录**下，与 `bin/`、`Resources/` 同级：

```
<ArcGIS Pro 安装根目录>/
    bin/
    Resources/
    mcp_arcgis/                ← 插件目录放这里
        server.py
        tools/
        workflow/
        bridge/
        addin/
        ...
```

> `server.py` 会自动从自身位置向上一层推导安装根目录，无需手动配置路径。

### 第二步：安装 Python 依赖

在 ArcGIS Pro 内置 Python 环境中安装（**一次性**）：

```bat
cd "<ArcGIS Pro 安装根目录>"

bin\Python\envs\arcgispro-py3\python.exe -m pip install "mcp[cli]>=1.28.0" anthropic>=0.109.0 pywin32>=312 pydantic>=2.0.0
```

如果网络较慢，可使用国内镜像：

```bat
bin\Python\envs\arcgispro-py3\python.exe -m pip install "mcp[cli]>=1.28.0" anthropic>=0.109.0 pywin32>=312 pydantic>=2.0.0 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 第三步：编译并安装 Add-In

#### 3.1 安装 .NET 8 SDK

从 https://dotnet.microsoft.com/download/dotnet/8.0 下载 **.NET 8 SDK**（Windows x64），安装后重新打开终端。

#### 3.2 编译 Add-In

```bat
cd "<ArcGIS Pro 安装根目录>\mcp_arcgis\addin"
dotnet build ArcGISProAddin.csproj -c Release -p:Platform=x64
```

编译成功后会自动打包并部署到 ArcGIS Pro AddIns 目录。

#### 3.3 验证安装

编译输出应显示：
```
已成功生成。
    0 个警告
    0 个错误
Addin packed and deployed to AddIns directory
```

### 第四步：配置 AI 模型

1. 打开 ArcGIS Pro，Ribbon 出现「**AI Assistant**」Tab
2. 点击「**AI Settings**」按钮
3. 填入 API Key 和 Base URL（如果使用第三方服务）
4. 点击「获取模型」选择模型，或手动输入模型名称
5. 点击「测试连接」确认可用
6. 点击「保存」

#### 支持的 AI 服务

| 服务 | Base URL | 模型名称示例 |
|------|----------|-------------|
| Anthropic (官方) | 留空 | claude-sonnet-4-6 |
| 其他兼容服务 | 对应的 API 地址 | 对应的模型名 |

### 第五步：启动使用

1. **启动 MCP Server**：
   ```bat
   cd "<ArcGIS Pro 安装根目录>\mcp_arcgis"
   start_server.bat
   ```
   或手动运行：
   ```bat
   "<ArcGIS Pro 安装根目录>\bin\Python\envs\arcgispro-py3\python.exe" "<ArcGIS Pro 安装根目录>\mcp_arcgis\server.py"
   ```

2. **打开 ArcGIS Pro**，点击「AI Chat」打开对话面板

3. **使用自然语言描述任务**，例如：
   - "对三甲医院做 20 公里缓冲区分析"
   - "帮我做坡度分析，输入数据是 DEM"
   - "分析人口密度并高亮密度超过 5000 的区域"

---

## 配置 MCP 客户端（可选）

如果需要通过 Claude Desktop 或其他 MCP 客户端使用，在配置文件中添加：

```json
{
  "mcpServers": {
    "arcgis-pro": {
      "command": "<ArcGIS Pro 安装根目录>\\bin\\Python\\envs\\arcgispro-py3\\python.exe",
      "args": ["<ArcGIS Pro 安装根目录>\\mcp_arcgis\\server.py"]
    }
  }
}
```

---

## 使用技巧

### 连接文件夹
点击 AI 对话面板顶部的「📁 连接文件夹」按钮，选择数据所在文件夹。AI 会自动读取文件夹内容，输入数据名称时会自动匹配完整路径。

### 工作流编辑
- 点击步骤卡片上的「Edit」按钮可修改参数
- 参数中的模板变量（如 `${data_sources.输入要素}`）会自动解析为实际路径
- 修改后点击「确认修改」保存

### 错误处理
- AI 执行失败时会自动分析错误并重试（最多 5 次）
- 5 次都失败后会输出详细的错误报告
- 可以修改参数后手动重新执行

---

## 项目结构

```
mcp_arcgis/
├── server.py               ← MCP Server 入口
├── config.json             ← 运行时配置（API Key、模型等）
├── start_server.bat        ← 启动脚本
├── requirements.txt        ← Python 依赖列表
├── tools/                  ← arcpy 工具包装层
│   ├── analysis.py         ← 空间分析（缓冲区/裁剪/交集等）
│   ├── management.py       ← 数据管理（字段/选择/投影等）
│   ├── raster.py           ← 栅格分析（坡度/密度/重分类等）
│   ├── network.py          ← 网络分析（路径/服务区/OD矩阵等）
│   ├── mapping.py          ← 制图控制（符号化/导出等）
│   └── statistics.py       ← 空间统计（热点/聚类/自相关等）
├── workflow/               ← 工作流引擎
│   ├── step.py             ← 数据模型（Workflow/WorkflowStep）
│   ├── planner.py          ← 意图识别 → 步骤链生成
│   ├── engine.py           ← 步骤执行 + 状态管理
│   └── validator.py        ← 参数验证
├── bridge/                 ← ArcGIS Pro 通信层
│   ├── arcpro_bridge.py    ← arcpy 操作 + UI 指令转发
│   ├── ai_chat_service.py  ← Claude API 调用 + tool_use 循环
│   └── named_pipe.py       ← Named Pipe 客户端/服务端
├── resources/
│   └── toolbox_schema.py   ← 工具元数据 + 工具搜索
└── addin/                  ← ArcGIS Pro Add-In (.NET WPF)
    ├── Config.daml         ← Add-In 注册配置
    ├── Module1.cs          ← 插件入口 + 按钮类
    ├── Converters.cs       ← WPF 值转换器
    ├── Localization.cs     ← 本地化支持
    ├── Panes/
    │   ├── AIChatDockPane.xaml       ← AI 对话面板
    │   ├── WorkflowDockPane.xaml     ← 工作流面板
    │   ├── AISettingsDialog.xaml     ← 设置对话框
    │   └── ParameterEditorDialog.xaml ← 参数编辑器
    ├── ViewModels/
    │   ├── AIChatViewModel.cs        ← 对话 ViewModel
    │   └── WorkflowViewModel.cs      ← 工作流 ViewModel
    └── Bridge/
        └── NamedPipeServer.cs        ← 接收 Python 端指令
```

---

## 日志文件

调试时可查看桌面上的日志文件：
- `mcp_server_log.txt` — Python MCP Server 运行日志
- `arcgis_addin_log.txt` — ArcGIS Pro Add-In 运行日志

---

## 常见问题

### Q: 点击按钮后窗口闪退
A: 检查 Python 环境是否正确安装依赖。在命令行手动运行 `start_server.bat` 查看错误信息。

### Q: AI 显示"未返回文字回复"
A: 可能是模型不支持 tool_use 或轮次超限。尝试简化请求或换用支持 tool_use 的模型。

### Q: 工作流面板不显示步骤
A: 确保 MCP Server 和 ArcGIS Pro 都已重启。检查 `arcgis_addin_log.txt` 是否有管道连接错误。

### Q: 获取模型列表失败
A: 部分 API 服务（如 MiMo）不支持 `/v1/models` 端点，会自动返回默认模型列表，不影响使用。
