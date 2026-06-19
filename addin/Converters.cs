using System;
using System.Globalization;
using System.Windows;
using System.Windows.Data;
using System.Windows.Media;

namespace ArcGISProAddin
{
    /// <summary>bool false → Visible, true → Collapsed</summary>
    public class InverseBoolToVisibilityConverter : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
            => value is bool b && b ? Visibility.Collapsed : Visibility.Visible;

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
            => value is Visibility v && v == Visibility.Collapsed;
    }

    /// <summary>bool true → "▲", false → "▼"</summary>
    public class BoolToExpandIconConverter : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
            => value is bool b && b ? "▲" : "▼";

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
            => throw new NotImplementedException();
    }

    /// <summary>null or empty string → Collapsed, otherwise Visible</summary>
    public class NullOrEmptyToVisibilityConverter : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
            => string.IsNullOrEmpty(value as string) ? Visibility.Collapsed : Visibility.Visible;

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
            => throw new NotImplementedException();
    }

    /// <summary>bool hasError → Red brush, false → Gray brush</summary>
    public class ErrorBorderBrushConverter : IValueConverter
    {
        private static readonly Brush _error = new SolidColorBrush(Color.FromRgb(0xF1, 0x4C, 0x4C));
        private static readonly Brush _normal = new SolidColorBrush(Color.FromRgb(0x55, 0x55, 0x55));

        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
            => value is bool b && b ? _error : _normal;

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
            => throw new NotImplementedException();
    }
}
