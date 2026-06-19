using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.IO;
using System.IO.Pipes;
using System.Runtime.CompilerServices;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Input;
using ArcGIS.Desktop.Framework;
using ArcGIS.Desktop.Framework.Contracts;

namespace ArcGISProAddin
{
    // -----------------------------------------------------------------------
    // ChatMessageViewModel — 单条消息气泡的数据模型
    // -----------------------------------------------------------------------
    public class ChatMessageViewModel : INotifyPropertyChanged
    {
        public string Role { get; init; } = "user";       // "user" | "assistant" | "system"
        public string Content { get; set; } = "";
        public DateTime Timestamp { get; init; } = DateTime.Now;

        // UI helpers
        public bool IsUser => Role == "user";
        public string BubbleBackground => IsUser ? "#0E639C" : "#2D2D30";
        public string TextColor => IsDarkBackground(BubbleBackground) ? "#E8E8E8" : "#1E1E1E";
        public System.Windows.HorizontalAlignment Alignment =>
            IsUser ? System.Windows.HorizontalAlignment.Right : System.Windows.HorizontalAlignment.Left;
        public string TimestampText => Timestamp.ToString("HH:mm");

        private static bool IsDarkBackground(string hex)
        {
            // 解析 hex 颜色，计算亮度
            hex = hex.TrimStart('#');
            if (hex.Length == 3)
                hex = $"{hex[0]}{hex[0]}{hex[1]}{hex[1]}{hex[2]}{hex[2]}";
            if (hex.Length < 6) return true;
            if (!int.TryParse(hex[..2], System.Globalization.NumberStyles.HexNumber, null, out int r)) return true;
            if (!int.TryParse(hex[2..4], System.Globalization.NumberStyles.HexNumber, null, out int g)) return true;
            if (!int.TryParse(hex[4..6], System.Globalization.NumberStyles.HexNumber, null, out int b)) return true;
            double luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0;
            return luminance < 0.5;
        }

        public event PropertyChangedEventHandler? PropertyChanged;
        protected void OnPropertyChanged([CallerMemberName] string? n = null)
            => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(n));
    }

    // -----------------------------------------------------------------------
    // AIChatDockPaneViewModel — AI 对话面板的 ViewModel
    // -----------------------------------------------------------------------
    public class AIChatDockPaneViewModel : DockPane, INotifyPropertyChanged
    {
        private const string _dockPaneID = "ArcGISProAddin_AIChatDockPane";

        private string _inputText = "";
        private bool _isBusy = false;
        private string _statusText = Loc.Instance["chat.ready"];
        private string _connectedFolder = "";

        // 完整的消息历史（发给 Python 端）
        private readonly List<Dictionary<string, object>> _messageHistory = new();

        public ObservableCollection<ChatMessageViewModel> Messages { get; } = new();

        public string InputText
        {
            get => _inputText;
            set { _inputText = value; NotifyPropertyChanged(); NotifyPropertyChanged(nameof(CanSend)); }
        }

        public new bool IsBusy
        {
            get => _isBusy;
            set { _isBusy = value; NotifyPropertyChanged(); NotifyPropertyChanged(nameof(CanSend)); }
        }

        public string StatusText
        {
            get => _statusText;
            set { _statusText = value; NotifyPropertyChanged(); }
        }

        public bool CanSend => !IsBusy && !string.IsNullOrWhiteSpace(InputText);

        public ICommand SendCommand => new RelayCommand(Send, () => CanSend);
        public ICommand ClearCommand => new RelayCommand(Clear);
        public ICommand OpenSettingsCommand => new RelayCommand(() => new AISettingsDialog().ShowDialog());
        public ICommand ConnectFolderCommand => new RelayCommand(ConnectFolder);

        public string ConnectedFolderDisplay =>
            string.IsNullOrEmpty(_connectedFolder) ? "" : $"📁 {_connectedFolder}";

        private void ConnectFolder()
        {
            var dialog = new System.Windows.Forms.FolderBrowserDialog
            {
                Description = "选择文件夹，AI可读取其中的文件",
                ShowNewFolderButton = false,
            };
            if (!string.IsNullOrEmpty(_connectedFolder))
                dialog.SelectedPath = _connectedFolder;

            if (dialog.ShowDialog() == System.Windows.Forms.DialogResult.OK)
            {
                _connectedFolder = dialog.SelectedPath;
                NotifyPropertyChanged(nameof(ConnectedFolderDisplay));
            }
        }

        protected AIChatDockPaneViewModel() { }

        internal static void Show()
        {
            var pane = FrameworkApplication.DockPaneManager.Find(_dockPaneID);
            pane?.Activate();
        }

        private async void Send()
        {
            if (string.IsNullOrWhiteSpace(InputText)) return;

            var userText = InputText.Trim();
            InputText = "";
            IsBusy = true;
            StatusText = Loc.Instance["chat.thinking"];

            // 添加用户气泡
            AddMessage("user", userText);

            // 追加到历史
            _messageHistory.Add(new Dictionary<string, object>
            {
                ["role"] = "user",
                ["content"] = userText,
            });

            // 添加占位 AI 气泡（显示加载动画）
            var thinkingBubble = new ChatMessageViewModel { Role = "assistant", Content = "..." };
            System.Windows.Application.Current.Dispatcher.Invoke(() => Messages.Add(thinkingBubble));
            ScrollToBottom?.Invoke();

            try
            {
                var response = await Task.Run(() => SendChatRequest(_messageHistory));

                if (response.TryGetValue("success", out var ok) && ok is JsonElement okEl && okEl.GetBoolean())
                {
                    var reply = ((JsonElement)response["reply"]).GetString() ?? "";

                    // 更新历史（Python 端已追加 tool_use 轮次）
                    if (response.TryGetValue("messages", out var msgs))
                    {
                        _messageHistory.Clear();
                        var msgsEl = (JsonElement)msgs;
                        foreach (var m in msgsEl.EnumerateArray())
                        {
                            var dict = JsonSerializer.Deserialize<Dictionary<string, object>>(m.GetRawText())
                                       ?? new Dictionary<string, object>();
                            _messageHistory.Add(dict);
                        }
                    }

                    System.Windows.Application.Current.Dispatcher.Invoke(() =>
                    {
                        Messages.Remove(thinkingBubble);
                        Messages.Add(new ChatMessageViewModel { Role = "assistant", Content = reply });
                    });
                    StatusText = Loc.Instance["chat.ready"];
                }
                else
                {
                    var error = response.TryGetValue("error", out var e)
                        ? ((JsonElement)e).GetString() ?? "?"
                        : "?";
                    System.Windows.Application.Current.Dispatcher.Invoke(() =>
                    {
                        Messages.Remove(thinkingBubble);
                        Messages.Add(new ChatMessageViewModel
                        {
                            Role = "assistant",
                            Content = $"⚠️ {error}",
                        });
                    });
                    StatusText = Loc.Instance["chat.error"];
                }
            }
            catch (Exception ex)
            {
                System.Windows.Application.Current.Dispatcher.Invoke(() =>
                {
                    Messages.Remove(thinkingBubble);
                    Messages.Add(new ChatMessageViewModel
                    {
                        Role = "assistant",
                        Content = $"⚠️ {ex.Message}\n\n{Loc.Instance["chat.serverHint"]}",
                    });
                });
                StatusText = Loc.Instance["chat.connectFail"];
            }
            finally
            {
                IsBusy = false;
                ScrollToBottom?.Invoke();
            }
        }

        private void Clear()
        {
            Messages.Clear();
            _messageHistory.Clear();
            StatusText = Loc.Instance["chat.ready"];
        }

        private void AddMessage(string role, string content)
        {
            System.Windows.Application.Current.Dispatcher.Invoke(() =>
                Messages.Add(new ChatMessageViewModel { Role = role, Content = content }));
        }

        // Called by View after messages update
        public Action? ScrollToBottom { get; set; }

        // ---- Named Pipe communication ----

        private Dictionary<string, object> SendChatRequest(
            List<Dictionary<string, object>> messages)
        {
            const string pipeName = "mcp_arcgis_chat";

            using var pipe = new NamedPipeClientStream(".", pipeName,
                PipeDirection.InOut, PipeOptions.None);

            pipe.Connect(timeout: 5000);

            var payload = JsonSerializer.SerializeToUtf8Bytes(new
            {
                action = "chat",
                messages,
                connected_folder = _connectedFolder ?? "",
            });

            var lenPrefix = new byte[4];
            lenPrefix[0] = (byte)(payload.Length >> 24);
            lenPrefix[1] = (byte)(payload.Length >> 16);
            lenPrefix[2] = (byte)(payload.Length >> 8);
            lenPrefix[3] = (byte)payload.Length;
            pipe.Write(lenPrefix, 0, 4);
            pipe.Write(payload, 0, payload.Length);
            pipe.Flush();

            // read response
            var respLenBuf = new byte[4];
            pipe.Read(respLenBuf, 0, 4);
            int respLen = (respLenBuf[0] << 24) | (respLenBuf[1] << 16)
                        | (respLenBuf[2] << 8) | respLenBuf[3];

            var respBuf = new byte[respLen];
            int read = 0;
            while (read < respLen)
                read += pipe.Read(respBuf, read, respLen - read);

            return JsonSerializer.Deserialize<Dictionary<string, object>>(respBuf)
                   ?? new Dictionary<string, object> { ["success"] = false, ["error"] = "empty response" };
        }
    }
}
