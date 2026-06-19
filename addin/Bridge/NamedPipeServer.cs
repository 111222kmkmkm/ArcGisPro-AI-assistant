using System;
using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using ArcGIS.Desktop.Framework;
using ArcGIS.Desktop.Mapping;
using ArcGIS.Desktop.Framework.Threading.Tasks;

namespace ArcGISProAddin
{
    /// <summary>
    /// Named Pipe server that receives commands from the MCP Python server.
    /// Runs on a background thread; dispatches UI actions to the correct thread.
    /// </summary>
    internal sealed class NamedPipeServer
    {
        private const string PipeName = "mcp_arcgis_bridge";
        private CancellationTokenSource? _cts;
        private static readonly Lazy<NamedPipeServer> _lazy = new(() => new NamedPipeServer());
        public static NamedPipeServer Instance => _lazy.Value;

        private static readonly string _logPath = System.IO.Path.Combine(
            System.Environment.GetFolderPath(System.Environment.SpecialFolder.Desktop),
            "arcgis_addin_log.txt");

        private static void Log(string msg)
        {
            try { System.IO.File.AppendAllText(_logPath, $"[{DateTime.Now:HH:mm:ss.fff}] {msg}\n"); } catch { }
        }

        private NamedPipeServer() { }

        public void Start()
        {
            _cts = new CancellationTokenSource();
            Log($"NamedPipeServer.Start() pipe={PipeName}");
            Task.Run(() => ListenLoop(_cts.Token));
        }

        public void Stop() => _cts?.Cancel();

        private async Task ListenLoop(CancellationToken ct)
        {
            Log("ListenLoop started");
            while (!ct.IsCancellationRequested)
            {
                try
                {
                    var pipe = new NamedPipeServerStream(
                        PipeName,
                        PipeDirection.InOut,
                        NamedPipeServerStream.MaxAllowedServerInstances,
                        PipeTransmissionMode.Byte,
                        PipeOptions.Asynchronous);

                    Log("Waiting for connection...");
                    await pipe.WaitForConnectionAsync(ct);
                    Log("Client connected");
                    _ = HandleClientAsync(pipe, ct);
                }
                catch (OperationCanceledException) { break; }
                catch (Exception ex)
                {
                    Log($"ListenLoop error: {ex.Message}");
                    await Task.Delay(1000, ct);
                }
            }
            Log("ListenLoop exited");
        }

        private async Task HandleClientAsync(NamedPipeServerStream pipe, CancellationToken ct)
        {
            try
            {
                // Read 4-byte length prefix
                var lenBytes = new byte[4];
                await pipe.ReadAsync(lenBytes, 0, 4, ct);
                int len = (lenBytes[0] << 24) | (lenBytes[1] << 16) | (lenBytes[2] << 8) | lenBytes[3];

                var payload = new byte[len];
                int totalRead = 0;
                while (totalRead < len)
                    totalRead += await pipe.ReadAsync(payload, totalRead, len - totalRead, ct);

                var json = Encoding.UTF8.GetString(payload);
                var command = JsonSerializer.Deserialize<JsonElement>(json);
                var action = command.TryGetProperty("action", out var a) ? a.GetString() : "?";
                Log($"HandleClient: action={action}, payload_len={len}, canWrite={pipe.CanWrite}");
                var response = await ProcessCommand(command);
                var responseJson = JsonSerializer.Serialize(response);
                Log($"HandleClient: response_json={responseJson}");

                var responseBytes = Encoding.UTF8.GetBytes(responseJson);
                // 合并长度前缀和数据为单次写入，避免竞态条件
                var frame = new byte[4 + responseBytes.Length];
                frame[0] = (byte)(responseBytes.Length >> 24);
                frame[1] = (byte)(responseBytes.Length >> 16);
                frame[2] = (byte)(responseBytes.Length >> 8);
                frame[3] = (byte)(responseBytes.Length);
                Array.Copy(responseBytes, 0, frame, 4, responseBytes.Length);

                if (pipe.CanWrite)
                {
                    pipe.Write(frame, 0, frame.Length);
                    pipe.Flush();
                    Log($"HandleClient: response written OK ({frame.Length} bytes)");
                }
                else
                {
                    Log("HandleClient: pipe.CanWrite=false, cannot send response");
                }
            }
            catch (Exception ex)
            {
                Log($"HandleClient error: {ex.Message}");
            }
            finally
            {
                pipe.Dispose();
            }
        }

        private async Task<object> ProcessCommand(JsonElement cmd)
        {
            string action = cmd.GetProperty("action").GetString() ?? "";

            return action switch
            {
                "ping" => new { success = true, message = "ArcGIS Pro MCP Bridge is running" },

                "show_workflow" => await ShowWorkflow(cmd),

                "update_step_status" => await UpdateStepStatus(cmd),

                "zoom_to_layer" => await ZoomToLayer(cmd.GetProperty("layer_name").GetString() ?? ""),

                "set_layer_visibility" => await SetLayerVisibility(
                    cmd.GetProperty("layer_name").GetString() ?? "",
                    cmd.GetProperty("visible").GetBoolean()),

                "add_layer" => await AddLayer(
                    cmd.GetProperty("layer_path").GetString() ?? "",
                    cmd.TryGetProperty("map_name", out var mn) ? mn.GetString() ?? "" : ""),

                "get_extent" => await GetExtent(),

                "set_extent" => await SetExtent(cmd),

                "open_attribute_table" => await OpenAttributeTable(cmd.GetProperty("layer_name").GetString() ?? ""),

                "export_map" => await ExportMap(cmd),

                _ => new { success = false, error = $"未知命令: {action}" },
            };
        }

        private async Task<object> ShowWorkflow(JsonElement cmd)
        {
            try
            {
                var wfJson = cmd.GetProperty("workflow").GetRawText();
                var wf = JsonSerializer.Deserialize<JsonElement>(wfJson);
                Log($"ShowWorkflow: wfJson length={wfJson.Length}");

                await System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
                {
                    var vm = WorkflowDockPaneViewModel.Show();
                    Log($"ShowWorkflow: vm={vm?.GetType().Name ?? "null"}");
                    if (vm != null)
                    {
                        vm.LoadWorkflow(wf);
                        Log("ShowWorkflow: LoadWorkflow called OK");
                    }
                    else
                    {
                        Log("ShowWorkflow: vm is null, dock pane not found");
                    }
                });
                return new { success = true };
            }
            catch (Exception ex)
            {
                Log($"ShowWorkflow error: {ex.Message}");
                return new { success = false, error = ex.Message };
            }
        }

        private async Task<object> UpdateStepStatus(JsonElement cmd)
        {
            try
            {
                int stepId = cmd.GetProperty("step_id").GetInt32();
                string status = cmd.GetProperty("status").GetString() ?? "";
                string message = cmd.TryGetProperty("message", out var m) ? m.GetString() ?? "" : "";

                System.Windows.Application.Current.Dispatcher.InvokeAsync(() =>
                {
                    var vm = WorkflowDockPaneViewModel.Show();
                    vm?.UpdateStepStatus(stepId, status, message);
                });
                return new { success = true };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private async Task<object> ZoomToLayer(string layerName)
        {
            try
            {
                await QueuedTask.Run(() =>
                {
                    var mapView = MapView.Active;
                    if (mapView == null) return;
                    var lyr = mapView.Map.FindLayers(layerName)?[0];
                    if (lyr != null)
                        mapView.ZoomTo(lyr);
                });
                return new { success = true };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private async Task<object> SetLayerVisibility(string layerName, bool visible)
        {
            try
            {
                await QueuedTask.Run(() =>
                {
                    var mapView = MapView.Active;
                    if (mapView == null) return;
                    var layers = mapView.Map.FindLayers(layerName);
                    foreach (var lyr in layers)
                        lyr.SetVisibility(visible);
                });
                return new { success = true };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private async Task<object> AddLayer(string layerPath, string mapName)
        {
            try
            {
                await QueuedTask.Run(() =>
                {
                    var mapView = MapView.Active;
                    if (mapView == null) return;
                    var uri = new Uri(layerPath);
                    LayerFactory.Instance.CreateLayer(uri, mapView.Map);
                });
                return new { success = true, message = $"已添加: {layerPath}" };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private async Task<object> GetExtent()
        {
            try
            {
                ArcGIS.Core.Geometry.Envelope? ext = null;
                await QueuedTask.Run(() =>
                {
                    ext = MapView.Active?.Extent;
                });
                if (ext == null) return new { success = false, error = "无活动地图视图" };
                return new { success = true, xmin = ext.XMin, ymin = ext.YMin, xmax = ext.XMax, ymax = ext.YMax };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private async Task<object> SetExtent(JsonElement cmd)
        {
            try
            {
                double xmin = cmd.GetProperty("xmin").GetDouble();
                double ymin = cmd.GetProperty("ymin").GetDouble();
                double xmax = cmd.GetProperty("xmax").GetDouble();
                double ymax = cmd.GetProperty("ymax").GetDouble();

                await QueuedTask.Run(() =>
                {
                    var mv = MapView.Active;
                    if (mv == null) return;
                    var env = ArcGIS.Core.Geometry.EnvelopeBuilderEx.CreateEnvelope(
                        xmin, ymin, xmax, ymax, mv.Map.SpatialReference);
                    mv.ZoomTo(env);
                });
                return new { success = true };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private async Task<object> OpenAttributeTable(string layerName)
        {
            // Opening attribute table programmatically requires ArcGIS.Desktop.Core
            // which provides table pane APIs. Delegate this to the Python side via arcpy.mp.
            return new { success = false, note = "请通过 ArcGIS Pro 界面手动打开属性表，或由 Python 端处理" };
        }

        private async Task<object> ExportMap(JsonElement cmd)
        {
            try
            {
                string outputPath = cmd.GetProperty("output_path").GetString() ?? "";
                int resolution = cmd.TryGetProperty("resolution", out var r) ? r.GetInt32() : 300;

                await QueuedTask.Run(() =>
                {
                    var mv = MapView.Active;
                    if (mv == null) return;
                    // Export via arcpy.mp — handled on Python side; here just trigger a refresh
                    // MapView does not expose ExportPDF/PNG directly in the .NET SDK
                    // The actual export is delegated to the Python MCP Server
                });
                return new { success = true, output = outputPath, note = "Export delegated to Python MCP Server" };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }
    }
}
