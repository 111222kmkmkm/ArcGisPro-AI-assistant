using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Windows;

namespace ArcGISProAddin
{
    public class ParameterItemViewModel : INotifyPropertyChanged
    {
        private string _value = "";
        private bool _hasError = false;

        public string Name { get; set; } = "";
        public string DisplayName { get; set; } = "";
        public string TypeHint { get; set; } = "";
        public bool IsRequired { get; set; }
        public bool HasFilter { get; set; }
        public List<string> FilterOptions { get; set; } = new();

        public string Value
        {
            get => _value;
            set { _value = value; OnPropertyChanged(); HasError = IsRequired && string.IsNullOrWhiteSpace(value); }
        }

        public bool HasError
        {
            get => _hasError;
            set { _hasError = value; OnPropertyChanged(); }
        }

        public event PropertyChangedEventHandler? PropertyChanged;
        protected void OnPropertyChanged([CallerMemberName] string? n = null)
            => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(n));
    }

    public partial class ParameterEditorDialog : Window, INotifyPropertyChanged
    {
        private readonly StepViewModel _step;

        public new string Title => $"参数编辑 — 步骤 {_step.StepId}";
        public string StepName => _step.Name;
        public string ToolPath => _step.Tool;
        public string Description => _step.Description;
        public ObservableCollection<ParameterItemViewModel> Parameters { get; } = new();

        public ParameterEditorDialog(StepViewModel step)
        {
            _step = step;
            InitializeComponent();
            DataContext = this;
            LoadParameters();
        }

        private void LoadParameters()
        {
            try
            {
                var paramsDict = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(_step.ParamsJson)
                    ?? new Dictionary<string, JsonElement>();

                foreach (var kv in paramsDict)
                {
                    Parameters.Add(new ParameterItemViewModel
                    {
                        Name = kv.Key,
                        DisplayName = FormatDisplayName(kv.Key),
                        TypeHint = InferTypeHint(kv.Value),
                        IsRequired = false,
                        HasFilter = false,
                        Value = kv.Value.ValueKind == JsonValueKind.Null ? "" : kv.Value.ToString() ?? "",
                    });
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"解析参数失败: {ex.Message}", "错误", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }

        private static string FormatDisplayName(string name)
            => System.Text.RegularExpressions.Regex.Replace(name, "_", " ")
               .Replace("in ", "输入:").Replace("out ", "输出:")
               .Trim();

        private static string InferTypeHint(JsonElement el) => el.ValueKind switch
        {
            JsonValueKind.Number => "数字",
            JsonValueKind.True or JsonValueKind.False => "布尔值",
            JsonValueKind.Array => "列表",
            JsonValueKind.Object => "对象",
            _ => "字符串 / 路径",
        };

        private void OnConfirm(object sender, RoutedEventArgs e)
        {
            // Rebuild params JSON from edited values
            var updatedParams = new Dictionary<string, object?>();
            foreach (var param in Parameters)
            {
                if (double.TryParse(param.Value, out double d))
                    updatedParams[param.Name] = d;
                else if (param.Value.Equals("true", StringComparison.OrdinalIgnoreCase))
                    updatedParams[param.Name] = true;
                else if (param.Value.Equals("false", StringComparison.OrdinalIgnoreCase))
                    updatedParams[param.Name] = false;
                else
                    updatedParams[param.Name] = param.Value;
            }

            _step.ParamsJson = JsonSerializer.Serialize(updatedParams, new JsonSerializerOptions { WriteIndented = true });
            DialogResult = true;
            Close();
        }

        private void OnCancel(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
            Close();
        }

        public event PropertyChangedEventHandler? PropertyChanged;
        protected void OnPropertyChanged([CallerMemberName] string? n = null)
            => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(n));
    }
}
