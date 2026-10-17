// ==========================================================
// Projet      : Eidolon Core
// Organisation: Eidolon Core Technologies (ECT)
// Fichier     : EidolonLauncher.cs
// Description : Lanceur Windows avec icone et raccourci vers l'appairage G279
// Standard    : Eidolon Presentation Standard v1
// ==========================================================
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Windows.Forms;

internal static class EidolonLauncher {
    [STAThread]
    private static int Main(string[] args) {
        try {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            string self = Assembly.GetExecutingAssembly().Location;
            if (args.Length == 1 && args[0] == "--shortcut") {
                CreateShortcut(self, root);
                return 0;
            }
            if (args.Length != 0) throw new InvalidOperationException("Arguments invalides.");
            string script = Path.Combine(root, "eidolon-open.ps1");
            if (!File.Exists(script) || !File.Exists(Path.Combine(root, "eidolon-consultation.exe")))
                throw new FileNotFoundException("Le paquet est incomplet. Extrayez tout le ZIP dans un dossier permanent.");
            string powershell = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System),
                @"WindowsPowerShell\v1.0\powershell.exe");
            var start = new ProcessStartInfo {
                FileName = powershell,
                Arguments = "-NoProfile -ExecutionPolicy RemoteSigned -File \"" + script + "\"",
                WorkingDirectory = root,
                UseShellExecute = false
            };
            // A console remains available for the first SSH password prompt.
            // No token or password is accepted in the launcher's command line.
            using (var process = Process.Start(start)) {
                if (process == null) throw new InvalidOperationException("Demarrage impossible.");
                process.WaitForExit();
                if (process.ExitCode != 0)
                    throw new InvalidOperationException("Verifiez le tunnel Eidolon et l'appairage, puis reessayez.");
            }
            return 0;
        } catch (Exception error) {
            // Do not display arbitrary exception messages or private command contents.
            string message = error is FileNotFoundException
                ? "Le paquet est incomplet. Extrayez tout le ZIP dans un dossier permanent."
                : "Ouverture impossible. Verifiez le tunnel, les fichiers du paquet et l'appairage Windows.";
            MessageBox.Show(message, "Eidolon", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 2;
        }
    }

    private static void CreateShortcut(string self, string root) {
        string path = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Eidolon.lnk");
        // Preserve an existing shortcut rather than overwriting user customizations.
        if (File.Exists(path)) throw new IOException("Le raccourci existe deja.");
        object shell = null;
        object shortcut = null;
        try {
            var shellType = Type.GetTypeFromProgID("WScript.Shell", true);
            shell = Activator.CreateInstance(shellType);
            shortcut = shellType.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { path });
            Type type = shortcut.GetType();
            type.InvokeMember("TargetPath", BindingFlags.SetProperty, null, shortcut, new object[] { self });
            type.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, shortcut, new object[] { root });
            type.InvokeMember("IconLocation", BindingFlags.SetProperty, null, shortcut, new object[] { self + ",0" });
            type.InvokeMember("Description", BindingFlags.SetProperty, null, shortcut, new object[] { "Ouvrir Eidolon" });
            type.InvokeMember("Save", BindingFlags.InvokeMethod, null, shortcut, null);
            if (!File.Exists(path)) throw new IOException("Raccourci absent.");
        } finally {
            if (shortcut != null && Marshal.IsComObject(shortcut)) Marshal.FinalReleaseComObject(shortcut);
            if (shell != null && Marshal.IsComObject(shell)) Marshal.FinalReleaseComObject(shell);
        }
    }
}
