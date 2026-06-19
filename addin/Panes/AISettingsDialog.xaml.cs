using System;
using System.IO;
using System.IO.Pipes;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;

namespace ArcGISProAddin
{
    public partial class AISettingsDialog : Window
    {
        private static readonly string _settingsPath = Path.Combine(
            AppDomain.CurrentDomain.BaseDirectory, "ai_settings.json");

        private static readonly string[] _defaultModels =
        {
            "claude-sonnet-4-6",
            "claude-opus-4-7",
            "claude-haiku-4-5-20251001",
        };

        public AISettingsDialog()
        {
            InitializeComponent();
            foreach (var m in _defaultModels) ModelCombo.Items.Add(m);
            LoadSettings();
        }

        private void LoadSettings()
        {
            // language combo reflects current Loc state
            SelectLanguage(Loc.Instance.Language);

            if (!File.Exists(_settingsPath)) { ModelCombo.Text = _defaultModels[0]; return; }
            try
            {
                var json = File.ReadAllText(_settingsPath, Encoding.UTF8);
                var s = JsonSerializer.Deserialize<JsonElement>(json);

                if (s.TryGetProperty("api_key", out var key))
                    ApiKeyBox.Password = key.GetString() ?? "";
                if (s.TryGetProperty("base_url", out var url))
                    BaseUrlBox.Text = url.GetString() ?? "";
                if (s.TryGetProperty("model", out var model))
                    ModelCombo.Text = model.GetString() ?? _defaultModels[0];
                else
                    ModelCombo.Text = _defaultModels[0];
            }
            catch { ModelCombo.Text = _defaultModels[0]; }
        }

        private void SelectLanguage(string lang)
        {
            foreach (ComboBoxItem item in LanguageCombo.Items)
                if ((string)item.Tag == lang) { item.IsSelected = true; return; }
            LanguageCombo.SelectedIndex = 0;
        }

        private string SelectedLanguage() =>
            (LanguageCombo.SelectedItem as ComboBoxItem)?.Tag as string ?? "zh";

        private string SelectedModel() =>
            string.IsNullOrWhiteSpace(ModelCombo.Text) ? _defaultModels[0] : ModelCombo.Text.Trim();

        private void OnLanguageChanged(object sender, SelectionChangedEventArgs e)
        {
            // live UI switch; persisted on Save
            if (IsLoaded) Loc.Instance.Language = SelectedLanguage();
        }

        // PLACEHOLDER_HANDLERS

        // ---- shared length-prefixed pipe round-trip ----
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

        private void SaveSettings(string apiKey, string model, string baseUrl, string language)
        {
            var settings = new { api_key = apiKey, model, base_url = baseUrl, language };
            File.WriteAllText(_settingsPath,
                JsonSerializer.Serialize(settings, new JsonSerializerOptions { WriteIndented = true }),
                Encoding.UTF8);

            try
            {
                PipeRequest(new
                {
                    action = "configure",
                    api_key = apiKey,
                    model,
                    base_url = baseUrl,
                    language,
                }, 2000);
            }
            catch { /* server may not be running yet */ }
        }

        private async void OnFetchModels(object sender, RoutedEventArgs e)
        {
            var apiKey = ApiKeyBox.Password.Trim();
            if (string.IsNullOrEmpty(apiKey))
            {
                StatusText.Text = Loc.Instance["set.needKeyFirst"];
                return;
            }
            StatusText.Text = Loc.Instance["set.fetching"];
            FetchBtn.IsEnabled = false;
            try
            {
                var baseUrl = BaseUrlBox.Text.Trim();
                var resp = await System.Threading.Tasks.Task.Run(() =>
                    PipeRequest(new { action = "list_models", api_key = apiKey, base_url = baseUrl }, 8000));

                if (resp.TryGetProperty("success", out var ok) && ok.GetBoolean()
                    && resp.TryGetProperty("models", out var models))
                {
                    var current = SelectedModel();
                    ModelCombo.Items.Clear();
                    int count = 0;
                    foreach (var m in models.EnumerateArray())
                    {
                        var id = m.GetString();
                        if (!string.IsNullOrEmpty(id)) { ModelCombo.Items.Add(id); count++; }
                    }
                    ModelCombo.Text = current;
                    StatusText.Text = string.Format(Loc.Instance["set.fetchOk"], count);
                }
                else
                {
                    var err = resp.TryGetProperty("error", out var er) ? er.GetString() : "unknown";
                    StatusText.Text = $"⚠ {err}";
                }
            }
            catch (Exception ex)
            {
                StatusText.Text = $"⚠ {ex.Message} {Loc.Instance["set.serverHint"]}";
            }
            finally { FetchBtn.IsEnabled = true; }
        }

        private void OnSave(object sender, RoutedEventArgs e)
        {
            var apiKey = ApiKeyBox.Password.Trim();
            if (string.IsNullOrEmpty(apiKey))
            {
                StatusText.Text = Loc.Instance["set.needKey"];
                return;
            }
            var lang = SelectedLanguage();
            Loc.Instance.Language = lang;
            SaveSettings(apiKey, SelectedModel(), BaseUrlBox.Text.Trim(), lang);
            StatusText.Text = Loc.Instance["set.saved"];
            DialogResult = true;
            Close();
        }

        private async void OnTest(object sender, RoutedEventArgs e)
        {
            var apiKey = ApiKeyBox.Password.Trim();
            if (string.IsNullOrEmpty(apiKey))
            {
                StatusText.Text = Loc.Instance["set.needKeyFirst"];
                return;
            }
            StatusText.Text = Loc.Instance["set.testing"];
            try
            {
                SaveSettings(apiKey, SelectedModel(), BaseUrlBox.Text.Trim(), SelectedLanguage());
                await System.Threading.Tasks.Task.Delay(300);

                var resp = await System.Threading.Tasks.Task.Run(() =>
                    PipeRequest(new
                    {
                        action = "chat",
                        messages = new[] { new { role = "user", content = "hi" } },
                    }, 15000));

                StatusText.Text = resp.TryGetProperty("success", out var ok) && ok.GetBoolean()
                    ? Loc.Instance["set.testOk"]
                    : $"⚠ {(resp.TryGetProperty("error", out var err) ? err.GetString() : "?")}";
            }
            catch (Exception ex)
            {
                StatusText.Text = $"⚠ {ex.Message} {Loc.Instance["set.serverHint"]}";
            }
        }

        private void OnCancel(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
            Close();
        }
    }
}
