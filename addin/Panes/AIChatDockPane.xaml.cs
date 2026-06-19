using System.Windows.Controls;
using System.Windows.Input;

namespace ArcGISProAddin
{
    public partial class AIChatDockPane : UserControl
    {
        public AIChatDockPane()
        {
            InitializeComponent();
            // 每次 Messages 集合变化后滚动到底部
            Loaded += (_, _) =>
            {
                if (DataContext is AIChatDockPaneViewModel vm)
                    vm.ScrollToBottom = ScrollToBottom;
            };
            DataContextChanged += (_, _) =>
            {
                if (DataContext is AIChatDockPaneViewModel vm)
                    vm.ScrollToBottom = ScrollToBottom;
            };
        }

        private void ScrollToBottom()
        {
            Dispatcher.InvokeAsync(() =>
            {
                MessagesScrollViewer.ScrollToBottom();
            }, System.Windows.Threading.DispatcherPriority.Background);
        }

        private void OnInputKeyDown(object sender, KeyEventArgs e)
        {
            if (e.Key == Key.Enter && !Keyboard.IsKeyDown(Key.LeftShift) && !Keyboard.IsKeyDown(Key.RightShift))
            {
                e.Handled = true;
                if (DataContext is AIChatDockPaneViewModel vm && vm.CanSend)
                    vm.SendCommand.Execute(null);
            }
        }
    }
}
