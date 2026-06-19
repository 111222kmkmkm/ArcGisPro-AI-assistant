using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.IO;
using System.Text;
using System.Text.Json;

namespace ArcGISProAddin
{
    /// <summary>
    /// 应用级本地化。语言保存在 ai_settings.json 的 "language" 字段（"zh" | "en"）。
    /// UI 通过绑定 Loc.Instance[key] 获取文本；切换语言时触发 PropertyChanged 实现热更新。
    /// </summary>
    public sealed class Loc : INotifyPropertyChanged
    {
        public static Loc Instance { get; } = new Loc();

        private string _lang = "zh";

        private Loc() { _lang = LoadLanguage(); }

        public string Language
        {
            get => _lang;
            set
            {
                var v = value == "en" ? "en" : "zh";
                if (_lang == v) return;
                _lang = v;
                // 通知所有键的绑定刷新（索引器 + 当前语言）
                PropertyChanged?.Invoke(this, new PropertyChangedEventArgs("Item[]"));
                PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(Language)));
                LanguageChanged?.Invoke(this, EventArgs.Empty);
            }
        }

        /// <summary>XAML 绑定入口：{Binding Source={x:Static local:Loc.Instance}, Path=[Key]}</summary>
        public string this[string key] => T(key);

        public string T(string key)
        {
            if (_strings.TryGetValue(key, out var pair))
                return _lang == "en" ? pair.En : pair.Zh;
            return key;
        }

        public event PropertyChangedEventHandler? PropertyChanged;
        public event EventHandler? LanguageChanged;

        // -- persistence (shares ai_settings.json with AISettingsDialog) --
        private static readonly string _settingsPath = Path.Combine(
            AppDomain.CurrentDomain.BaseDirectory, "ai_settings.json");

        private static string LoadLanguage()
        {
            try
            {
                if (File.Exists(_settingsPath))
                {
                    var json = File.ReadAllText(_settingsPath, Encoding.UTF8);
                    var s = JsonSerializer.Deserialize<JsonElement>(json);
                    if (s.TryGetProperty("language", out var l))
                        return l.GetString() == "en" ? "en" : "zh";
                }
            }
            catch { }
            return "zh";
        }

        private readonly record struct Pair(string Zh, string En);

        private static readonly Dictionary<string, Pair> _strings = new()
        {
            // ---- AI Chat pane ----
            ["chat.title"]        = new("AI 对话助手", "AI Chat Assistant"),
            ["chat.subtitle"]     = new("与 Claude AI 对话，直接执行 GIS 分析", "Chat with Claude AI to run GIS tasks"),
            ["chat.settingsTip"]  = new("AI 设置（API Key、模型）", "AI settings (API key, model)"),
            ["chat.placeholder"]  = new("输入问题，按 Enter 发送...", "Type a message, press Enter to send..."),
            ["chat.send"]         = new("发送", "Send"),
            ["chat.sendTip"]      = new("发送（Enter）", "Send (Enter)"),
            ["chat.thinking"]     = new("AI 思考中...", "AI is thinking..."),
            ["chat.ready"]        = new("就绪", "Ready"),
            ["chat.error"]        = new("出错", "Error"),
            ["chat.connectFail"]  = new("连接失败", "Connection failed"),
            ["chat.serverHint"]   = new("请确认 Python MCP Server 正在运行。", "Make sure the Python MCP Server is running."),

            // ---- Workflow pane ----
            ["wf.title"]          = new("AI 工作流", "AI Workflow"),
            ["wf.runAll"]         = new("▶ 全部执行", "▶ Run All"),
            ["wf.stepByStep"]     = new("⏭ 逐步执行", "⏭ Step by Step"),
            ["wf.clearTip"]       = new("清除工作流", "Clear workflow"),
            ["wf.editTip"]        = new("编辑参数", "Edit parameters"),
            ["wf.empty"]          = new("暂无工作流。向 AI 描述分析目标即可生成步骤链。",
                                        "No workflow yet. Describe a goal to the AI to generate steps."),

            // ---- Settings dialog ----
            ["set.title"]         = new("AI 设置", "AI Settings"),
            ["set.apiKey"]        = new("Anthropic API Key *", "Anthropic API Key *"),
            ["set.baseUrl"]       = new("API 地址 (Base URL，可选)", "API Base URL (optional)"),
            ["set.baseUrlHint"]   = new("留空使用官方地址，填写可走代理/中转", "Leave empty for official endpoint, or set a proxy/relay"),
            ["set.model"]         = new("模型", "Model"),
            ["set.fetchModels"]   = new("获取模型", "Fetch Models"),
            ["set.language"]      = new("界面语言", "Language"),
            ["set.cancel"]        = new("取消", "Cancel"),
            ["set.test"]          = new("测试连接", "Test"),
            ["set.save"]          = new("保存", "Save"),
            ["set.needKey"]       = new("⚠ 请输入 API Key", "⚠ Please enter an API key"),
            ["set.saved"]         = new("✓ 已保存", "✓ Saved"),
            ["set.testing"]       = new("测试中...", "Testing..."),
            ["set.testOk"]        = new("✓ 连接成功！", "✓ Connected!"),
            ["set.fetching"]      = new("获取模型列表中...", "Fetching models..."),
            ["set.fetchOk"]       = new("✓ 已获取 {0} 个模型", "✓ Fetched {0} models"),
            ["set.needKeyFirst"]  = new("⚠ 请先输入 API Key", "⚠ Enter an API key first"),
            ["set.serverHint"]    = new("（请先启动 Python MCP Server）", "(start the Python MCP Server first)"),
        };
    }
}
