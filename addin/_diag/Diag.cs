using System;
using System.IO;
using System.Reflection;

class Diag
{
    static readonly string Bin = @"E:\arcGIS Pro\bin";

    static void Main()
    {
        AppDomain.CurrentDomain.AssemblyResolve += (s, e) =>
        {
            var name = new AssemblyName(e.Name).Name;
            foreach (var dir in new[] { Bin, Bin + @"\Extensions\Core", Bin + @"\Extensions\Mapping" })
            {
                var candidate = Path.Combine(dir, name + ".dll");
                if (File.Exists(candidate))
                {
                    try { return Assembly.LoadFrom(candidate); } catch { }
                }
            }
            return null;
        };

        var dll = @"E:\arcGIS Pro\mcp_arcgis\addin\bin\x64\Release\net8.0-windows\ArcGISProAddin.dll";
        Console.WriteLine("=== Loading DLL ===");
        Assembly asm;
        try
        {
            asm = Assembly.LoadFrom(dll);
            Console.WriteLine("Loaded OK: " + asm.FullName);
        }
        catch (Exception ex)
        {
            Console.WriteLine("LoadFrom FAILED: " + ex.GetType().FullName);
            Console.WriteLine(ex.Message);
            for (var ie = ex.InnerException; ie != null; ie = ie.InnerException)
                Console.WriteLine("INNER: " + ie.Message);
            return;
        }

        Console.WriteLine("\n=== Enumerating types ===");
        try
        {
            var types = asm.GetTypes();
            Console.WriteLine("GetTypes OK, count = " + types.Length);
            foreach (var t in types)
                if (t.Name.Contains("Button") || t.Name.Contains("Module") || t.Name.Contains("ViewModel") || t.Name.Contains("DockPane"))
                    Console.WriteLine($"  {t.FullName}  public={t.IsPublic}");
        }
        catch (ReflectionTypeLoadException rtle)
        {
            Console.WriteLine("ReflectionTypeLoadException!");
            foreach (var le in rtle.LoaderExceptions)
                Console.WriteLine("  LOADER: " + le?.Message);
        }
        catch (Exception ex)
        {
            Console.WriteLine("GetTypes FAILED: " + ex.Message);
            for (var ie = ex.InnerException; ie != null; ie = ie.InnerException)
                Console.WriteLine("INNER: " + ie.Message);
        }
    }
}
