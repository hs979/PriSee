# PriSee - Android隐私设置智能检测系统

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

基于大语言模型的Android应用隐私泄露智能检测与对抗系统，能够自动化识别和分析移动应用中的隐私设置项，并提供隐私保护建议。

##项目简介

PriSee是一个创新的隐私保护工具，利用先进的LLM技术，自动化地：
- 检测Android应用中的隐私相关设置选项
- 分析隐私设置的当前状态
- 提供基于隐私保护的推荐配置
- 生成结构化的隐私设置路径报告

##核心特性

- **智能图标识别**：使用多模态大模型自动定位"个人中心"和"设置"入口
- **深度遍历探索**：DFS算法深度探索应用隐私设置页面
- **隐私分析**：自动识别隐私开关并分析其隐私影响
- **个性化广告检测**：专门识别和分类个性化广告相关设置
- **结构化输出**：生成JSON格式的详细检测报告

##系统架构

```
PriSee/
├── src/                              # 主程序源码
│   ├── privacy_detection_main.py     # 主检测程序
│   ├── route.py                      # 导航路由模块
│   ├── screenshot_inspector.py       # 截图分析模块
│   ├── privacy_analyzer.py           # 隐私分析引擎
│   ├── personal_icon_detector.py     # 个人中心图标检测
│   ├── setting_icon_detector.py      # 设置图标检测
│   ├── detect_personal_icon.py       # 个人图标检测(备用)
│   ├── detect_setting_icon.py        # 设置图标检测(备用)
│   ├── prompt.txt                    # LLM提示词配置
│   └── system.txt                    # 系统提示词配置
├── baseline/                         # 基线对比方法
│   ├── baseline1.py                  # Monkey测试基线
│   └── baseline2.py                  # 关键词驱动基线
├── utils/                            # 工具函数
│   └── FormatConversion.py           # 格式转换工具
├── config.example                    # 配置文件模板
└── README.md                         # 项目文档

```

## 快速开始

### 环境要求

- Python 3.8+
- Android设备/模拟器（已启用USB调试）
- ADB工具
- uiautomator2

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/yourusername/PriSee.git
cd PriSee
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**
```bash
cp config.example .env
```

编辑`.env`文件，填入必要的配置信息：
```env
# 设备配置
DEVICE_SERIAL=your_device_serial_here

# API密钥
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_API_BASE=http://jeniya.cn
QWEN_API_KEY=your_qwen_api_key_here

# 目标应用包名
TARGET_PACKAGE=com.example.app

# 测试配置
TEST_DURATION=403.2
```

4. **连接Android设备**
```bash
# 查看设备列表
adb devices

# 安装uiautomator2到设备
python -m uiautomator2 init
```

### 使用方法

#### 基本使用

```bash
# 进入源码目录
cd src

# 运行主检测程序
python privacy_detection_main.py
```

#### 运行基线对比

```bash
# Monkey测试基线
cd baseline
python baseline1.py

# 关键词驱动基线
python baseline2.py
```

##输出结果

检测完成后，系统会在`all_paths_results/`目录下生成JSON格式的报告：

```json
{
  "privacy_switches": [
    {
      "text": "允许查看我的关注列表",
      "current_state": "on",
      "recommended_state": "off",
      "analysis": "关闭此选项可避免其他用户获取关注信息，保护用户隐私"
    }
  ],
  "personality": {
    "personality_switches": [
      {
        "text": "个性化广告推荐",
        "current_state": "on",
        "recommended_state": "off",
        "analysis": "关闭可防止平台基于用户行为投放广告，降低数据泄露风险"
      }
    ],
    "personality_layouts": [
      {
        "text": "个性化广告设置"
      }
    ]
  }
}
```

##核心模块说明

### 1. 图标检测模块
- **personal_icon_detector.py**: 使用Gemini多模态模型检测"个人中心"/"我的"图标
- **setting_icon_detector.py**: 检测"设置"图标或菜单入口

### 2. 隐私分析模块
- **privacy_analyzer.py**: 基于QVQ模型分析截图中的隐私设置项
- **screenshot_inspector.py**: 长截图拼接和分析

### 3. 导航模块
- **route.py**: 自动导航到应用的隐私设置页面

### 4. 主检测模块
- **privacy_detection_main.py**: DFS深度遍历隐私设置树

##技术亮点

1. **多模态大模型应用**: 结合视觉和文本理解能力进行UI分析
2. **智能路径规划**: 基于DFS的探索策略避免重复和死循环
3. **隐私语义理解**: LLM驱动的隐私设置识别和建议生成
4. **弹窗检测机制**: 自动识别并处理各类弹窗场景
5. **可扩展架构**: 模块化设计便于功能扩展

##基线对比

项目提供两种基线方法用于效果对比：

- **Baseline 1**: 随机Monkey测试
- **Baseline 2**: 基于关键词的启发式探索

##贡献指南

欢迎提交Issue和Pull Request！

1. Fork本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request


##开发团队

本项目由大学生创新创业项目团队开发。

---


