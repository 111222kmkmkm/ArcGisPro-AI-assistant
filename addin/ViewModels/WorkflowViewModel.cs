using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.IO;
using System.IO.Pipes;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Windows;
using System.Windows.Input;
using ArcGIS.Desktop.Framework;
using ArcGIS.Desktop.Framework.Contracts;
using ArcGIS.Desktop.Framework.Threading.Tasks;

namespace ArcGISProAddin
{
    public class StepViewModel : INotifyPropertyChanged
    {
        private int _stepId;
        private string _name = "";
        private string _tool = "";
        private string _description = "";
        private string _status = "pending";
        private string _statusColor = "#888888";
        private string _errorMessage = "";
        private bool _isExpanded = false;
        private string _paramsJson = "{}";
        private System.Collections.Generic.List<string> _editableParams = new();

        public int StepId { get => _stepId; set { _stepId = value; OnPropertyChanged(); } }
        public string Name { get => _name; set { _name = value; OnPropertyChanged(); } }
        public string Tool { get => _tool; set { _tool = value; OnPropertyChanged(); } }
        public string Description { get => _description; set { _description = value; OnPropertyChanged(); } }
        public string ParamsJson { get => _paramsJson; set { _paramsJson = value; OnPropertyChanged(); } }

        public string Status
        {
            get => _status;
            set
            {
                _status = value;
                StatusColor = value switch
                {
                    "completed" => "#27AE60",
                    "running" => "#2980B9",
                    "error" => "#E74C3C",
                    "skipped" => "#95A5A6",
                    _ => "#888888",
                };
                StatusLabel = value switch
                {
                    "completed" => "✓",
                    "running" => "⟳",
                    "error" => "✗",
                    "skipped" => "—",
                    _ => "○",
                };
                OnPropertyChanged();
            }
        }

        public string StatusColor { get => _statusColor; private set { _statusColor = value; OnPropertyChanged(); } }
        public string StatusLabel { get; private set; } = "○";
        public string ErrorMessage { get => _errorMessage; set { _errorMessage = value; OnPropertyChanged(); } }
        public bool IsExpanded { get => _isExpanded; set { _isExpanded = value; OnPropertyChanged(); } }

        public ICommand ToggleExpandCommand => new RelayCommand(() => IsExpanded = !IsExpanded);
        public ICommand EditParamsCommand => new RelayCommand(OpenParamEditor);

        private void OpenParamEditor()
        {
            var dialog = new ParameterEditorDialog(this);
            dialog.ShowDialog();
        }

        public event PropertyChangedEventHandler? PropertyChanged;
        protected void OnPropertyChanged([CallerMemberName] string? n = null)
            => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(n));
    }

    public class WorkflowDockPaneViewModel : DockPane, INotifyPropertyChanged
    {
        private const string _dockPaneID = "ArcGISProAddin_WorkflowDockPane";

        private string _workflowTitle = "尚未生成工作流";
        private string _workflowId = "";
        private string _statusMessage = "等待 AI 生成步骤链...";
        private bool _hasWorkflow = false;
        private bool _isRunning = false;

        public ObservableCollection<StepViewModel> Steps { get; } = new();

        public string WorkflowTitle { get => _workflowTitle; set { _workflowTitle = value; NotifyPropertyChanged(); } }
        public string StatusMessage { get => _statusMessage; set { _statusMessage = value; NotifyPropertyChanged(); } }
        public bool HasWorkflow { get => _hasWorkflow; set { _hasWorkflow = value; NotifyPropertyChanged(); } }
        public bool IsRunning { get => _isRunning; set { _isRunning = value; NotifyPropertyChanged(); } }

        public ICommand RunAllCommand => new RelayCommand(RunAll, () => HasWorkflow && !IsRunning);
        public ICommand StepByStepCommand => new RelayCommand(RunStepByStep, () => HasWorkflow && !IsRunning);
        public ICommand ClearCommand => new RelayCommand(Clear, () => HasWorkflow);

        protected WorkflowDockPaneViewModel() { }

        internal static WorkflowDockPaneViewModel? Show()
        {
            var pane = FrameworkApplication.DockPaneManager.Find(_dockPaneID);
            return pane as WorkflowDockPaneViewModel;
        }

        // Called by NamedPipeServer when a workflow arrives
        public void LoadWorkflow(System.Text.Json.JsonElement wf)
        {
            System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
            {
                try
                {
                    _workflowId = wf.GetProperty("workflow_id").GetString() ?? "";
                    WorkflowTitle = wf.GetProperty("title").GetString() ?? "";
                    Steps.Clear();
                    HasWorkflow = true;
                    StatusMessage = "步骤链已加载，点击执行或逐步运行。";

                    // 解析数据源映射，用于替换模板变量
                    var dsMap = new Dictionary<string, string>();
                    if (wf.TryGetProperty("data_sources", out var dsArray))
                    {
                        foreach (var ds in dsArray.EnumerateArray())
                        {
                            var name = ds.GetProperty("name").GetString() ?? "";
                            var path = ds.GetProperty("path").GetString() ?? "";
                            if (!string.IsNullOrEmpty(name))
                                dsMap[name] = path;
                        }
                    }
                    var workspace = wf.TryGetProperty("output_workspace", out var wsEl)
                        ? wsEl.GetString() ?? "" : "";

                    foreach (var s in wf.GetProperty("steps").EnumerateArray())
                    {
                        var paramsRaw = s.GetProperty("params").GetRawText();
                        var resolvedParams = ResolveTemplateVars(paramsRaw, dsMap, workspace);

                        Steps.Add(new StepViewModel
                        {
                            StepId = s.GetProperty("step_id").GetInt32(),
                            Name = s.GetProperty("name").GetString() ?? "",
                            Tool = s.GetProperty("tool").GetString() ?? "",
                            Description = s.GetProperty("description").GetString() ?? "",
                            Status = s.GetProperty("status").GetString() ?? "pending",
                            ParamsJson = resolvedParams,
                        });
                    }
                }
                catch (Exception ex)
                {
                    System.IO.File.AppendAllText(
                        System.IO.Path.Combine(System.Environment.GetFolderPath(System.Environment.SpecialFolder.Desktop), "arcgis_addin_log.txt"),
                        $"[{DateTime.Now:HH:mm:ss.fff}] LoadWorkflow error: {ex.Message}\n");
                }
            });
        }

        private static string ResolveTemplateVars(string paramsJson, Dictionary<string, string> dsMap, string workspace)
        {
            var dict = System.Text.Json.JsonSerializer.Deserialize<Dictionary<string, System.Text.Json.JsonElement>>(paramsJson)
                       ?? new Dictionary<string, System.Text.Json.JsonElement>();
            var resolved = new Dictionary<string, object?>();
            foreach (var kv in dict)
            {
                if (kv.Value.ValueKind == System.Text.Json.JsonValueKind.String)
                {
                    var val = kv.Value.GetString() ?? "";
                    // ${data_sources.XXX} → 实际路径
                    val = System.Text.RegularExpressions.Regex.Replace(val,
                        @"\$\{data_sources\.([^}]+)\}", m =>
                        {
                            var key = m.Groups[1].Value;
                            return dsMap.TryGetValue(key, out var p) ? p : m.Value;
                        });
                    // ${workspace}/XXX → 工作空间/XXX
                    if (!string.IsNullOrEmpty(workspace))
                        val = val.Replace("${workspace}", workspace);
                    resolved[kv.Key] = val;
                }
                else
                {
                    resolved[kv.Key] = System.Text.Json.JsonSerializer.Deserialize<object>(kv.Value.GetRawText());
                }
            }
            return System.Text.Json.JsonSerializer.Serialize(resolved,
                new System.Text.Json.JsonSerializerOptions { WriteIndented = true });
        }

        public void UpdateStepStatus(int stepId, string status, string message)
        {
            System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
            {
                foreach (var s in Steps)
                {
                    if (s.StepId == stepId)
                    {
                        s.Status = status;
                        s.ErrorMessage = message;
                        break;
                    }
                }
            });
        }

        private async void RunAll()
        {
            if (string.IsNullOrEmpty(_workflowId)) return;
            IsRunning = true;
            StatusMessage = "正在执行全部步骤...";

            try
            {
                var resp = await System.Threading.Tasks.Task.Run(() =>
                    PipeRequest(new { action = "execute_workflow", workflow_id = _workflowId }, 60000));

                if (resp.TryGetProperty("success", out var ok) && ok.GetBoolean())
                {
                    var result = resp.GetProperty("result");
                    bool overallOk = result.TryGetProperty("overall_success", out var os) && os.GetBoolean();
                    int executed = result.TryGetProperty("steps_executed", out var se) ? se.GetInt32() : 0;

                    // 更新步骤状态
                    if (result.TryGetProperty("workflow", out var wf) && wf.TryGetProperty("steps", out var stepsArr))
                    {
                        foreach (var s in stepsArr.EnumerateArray())
                        {
                            var sid = s.GetProperty("step_id").GetInt32();
                            var st = s.GetProperty("status").GetString() ?? "pending";
                            foreach (var step in Steps)
                            {
                                if (step.StepId == sid)
                                {
                                    step.Status = st;
                                    if (s.TryGetProperty("error_message", out var em))
                                        step.ErrorMessage = em.GetString() ?? "";
                                    break;
                                }
                            }
                        }
                    }

                    // 构建结果消息
                    var msg = overallOk
                        ? $"工作流执行成功！\n\n已执行 {executed} 个步骤。"
                        : $"工作流执行失败\n\n已执行 {executed} 个步骤。";

                    if (result.TryGetProperty("results", out var resultsArr))
                    {
                        foreach (var r in resultsArr.EnumerateArray())
                        {
                            var name = r.TryGetProperty("name", out var n) ? n.GetString() : "?";
                            var success = r.TryGetProperty("success", out var s2) && s2.GetBoolean();
                            var err = r.TryGetProperty("error", out var e) ? e.GetString() : "";
                            msg += $"\n  {(success ? "✓" : "✗")} {name}";
                            if (!success && !string.IsNullOrEmpty(err))
                                msg += $": {err}";
                        }
                    }

                    MessageBox.Show(msg, overallOk ? "执行成功" : "执行失败",
                        MessageBoxButton.OK, overallOk ? MessageBoxImage.Information : MessageBoxImage.Warning);
                    StatusMessage = overallOk ? "执行完成。" : "执行失败，请查看错误信息。";
                }
                else
                {
                    var err = resp.TryGetProperty("error", out var e) ? e.GetString() : "未知错误";
                    MessageBox.Show($"执行失败: {err}", "执行失败", MessageBoxButton.OK, MessageBoxImage.Warning);
                    StatusMessage = "执行失败。";
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"执行出错: {ex.Message}", "执行失败", MessageBoxButton.OK, MessageBoxImage.Warning);
                StatusMessage = "执行出错。";
            }
            finally
            {
                IsRunning = false;
            }
        }

        private async void RunStepByStep()
        {
            if (string.IsNullOrEmpty(_workflowId)) return;
            IsRunning = true;
            StatusMessage = "正在执行全部步骤...";

            try
            {
                var resp = await System.Threading.Tasks.Task.Run(() =>
                    PipeRequest(new { action = "execute_workflow", workflow_id = _workflowId }, 60000));

                if (resp.TryGetProperty("success", out var ok) && ok.GetBoolean())
                {
                    var result = resp.GetProperty("result");
                    bool overallOk = result.TryGetProperty("overall_success", out var os) && os.GetBoolean();

                    if (result.TryGetProperty("workflow", out var wf) && wf.TryGetProperty("steps", out var stepsArr))
                    {
                        foreach (var s in stepsArr.EnumerateArray())
                        {
                            var sid = s.GetProperty("step_id").GetInt32();
                            var st = s.GetProperty("status").GetString() ?? "pending";
                            foreach (var step in Steps)
                            {
                                if (step.StepId == sid)
                                {
                                    step.Status = st;
                                    if (s.TryGetProperty("error_message", out var em))
                                        step.ErrorMessage = em.GetString() ?? "";
                                    break;
                                }
                            }
                        }
                    }

                    StatusMessage = overallOk ? "执行完成。" : "执行失败。";
                }
                else
                {
                    var err = resp.TryGetProperty("error", out var e) ? e.GetString() : "未知错误";
                    MessageBox.Show($"执行失败: {err}", "执行失败", MessageBoxButton.OK, MessageBoxImage.Warning);
                    StatusMessage = "执行失败。";
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"执行出错: {ex.Message}", "执行失败", MessageBoxButton.OK, MessageBoxImage.Warning);
                StatusMessage = "执行出错。";
            }
            finally
            {
                IsRunning = false;
            }
        }

        private void Clear()
        {
            Steps.Clear();
            WorkflowTitle = "尚未生成工作流";
            HasWorkflow = false;
            _workflowId = "";
            StatusMessage = "等待 AI 生成步骤链...";
        }

        private static JsonElement PipeRequest(object payload, int timeoutMs)
        {
            using var pipe = new NamedPipeClientStream(".", "mcp_arcgis_chat",
                PipeDirection.InOut, PipeOptions.None);
            pipe.Connect(timeoutMs);

            var bytes = JsonSerializer.SerializeToUtf8Bytes(payload);
            var lenBuf = new byte[4];
            lenBuf[0] = (byte)(bytes.Length >> 24);
            lenBuf[1] = (byte)(bytes.Length >> 16);
            lenBuf[2] = (byte)(bytes.Length >> 8);
            lenBuf[3] = (byte)bytes.Length;
            pipe.Write(lenBuf, 0, 4);
            pipe.Write(bytes, 0, bytes.Length);
            pipe.Flush();

            var rl = new byte[4];
            ReadExact(pipe, rl, 4);
            int len = (rl[0] << 24) | (rl[1] << 16) | (rl[2] << 8) | rl[3];
            var buf = new byte[len];
            ReadExact(pipe, buf, len);
            return JsonSerializer.Deserialize<JsonElement>(buf);
        }

        private static void ReadExact(Stream s, byte[] buf, int count)
        {
            int read = 0;
            while (read < count)
            {
                int n = s.Read(buf, read, count - read);
                if (n <= 0) break;
                read += n;
            }
        }
    }

    // Minimal relay command
    internal class RelayCommand : ICommand
    {
        private readonly Action _execute;
        private readonly Func<bool>? _canExecute;

        public RelayCommand(Action execute, Func<bool>? canExecute = null)
        {
            _execute = execute;
            _canExecute = canExecute;
        }

        public bool CanExecute(object? p) => _canExecute?.Invoke() ?? true;
        public void Execute(object? p) => _execute();
        public event EventHandler? CanExecuteChanged
        {
            add => CommandManager.RequerySuggested += value;
            remove => CommandManager.RequerySuggested -= value;
        }
    }
}
