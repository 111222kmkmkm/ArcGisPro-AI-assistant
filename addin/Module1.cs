using ArcGIS.Desktop.Framework;
using ArcGIS.Desktop.Framework.Contracts;
using System;
using System.IO;
using System.Windows;

namespace ArcGISProAddin
{
    internal class Module1 : Module
    {
        private static readonly string _logPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.Desktop),
            "arcgis_addin_log.txt");

        private static Module1? _this = null;
        public static Module1 Current =>
            _this ?? (_this = (Module1)FrameworkApplication.FindModule("ArcGISProAddin_Module"));

        protected override bool Initialize()
        {
            try
            {
                Log("Module1.Initialize() 开始");
                NamedPipeServer.Instance.Start();
                Log("NamedPipeServer 启动成功");
                var result = base.Initialize();
                Log($"base.Initialize() 返回: {result}");
                return result;
            }
            catch (Exception ex)
            {
                Log($"Initialize 异常: {ex.GetType().Name}: {ex.Message}\n{ex.StackTrace}");
                return false;
            }
        }

        protected override void Uninitialize()
        {
            NamedPipeServer.Instance.Stop();
            base.Uninitialize();
        }

        internal static void LogError(string context, Exception ex)
        {
            Log($"{context}: {ex.GetType().Name}: {ex.Message}\n{ex.StackTrace}");
        }

        private static void Log(string msg)
        {
            try
            {
                File.AppendAllText(_logPath,
                    $"[{DateTime.Now:HH:mm:ss.fff}] {msg}\n");
            }
            catch { }
        }
    }

    public class ShowAIChatPaneButton : Button
    {
        protected override void OnClick()
        {
            try
            {
                var pane = FrameworkApplication.DockPaneManager.Find("ArcGISProAddin_AIChatDockPane");
                if (pane == null)
                    throw new InvalidOperationException("AI chat pane was not found.");
                pane.Activate();
            }
            catch (Exception ex)
            {
                Module1.LogError("ShowAIChatPaneButton.OnClick", ex);
                MessageBox.Show($"Failed to open AI chat pane.\n\n{ex.Message}", "ArcGIS Pro AI Assistant");
            }
        }
    }

    public class ShowSettingsButton : Button
    {
        protected override void OnClick()
        {
            try
            {
                var dlg = new AISettingsDialog();
                dlg.ShowDialog();
            }
            catch (Exception ex)
            {
                Module1.LogError("ShowSettingsButton.OnClick", ex);
                MessageBox.Show($"Failed to open settings.\n\n{ex.Message}", "ArcGIS Pro AI Assistant");
            }
        }
    }

    public class ShowWorkflowPaneButton : Button
    {
        protected override void OnClick()
        {
            try
            {
                var pane = FrameworkApplication.DockPaneManager.Find("ArcGISProAddin_WorkflowDockPane");
                if (pane == null)
                    throw new InvalidOperationException("Workflow pane was not found.");
                pane.Activate();
            }
            catch (Exception ex)
            {
                Module1.LogError("ShowWorkflowPaneButton.OnClick", ex);
                MessageBox.Show($"Failed to open workflow pane.\n\n{ex.Message}", "ArcGIS Pro AI Assistant");
            }
        }
    }
}
