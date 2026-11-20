// ==========================================================
// Projet      : Eidolon Core
// Organisation: Eidolon Core Technologies (ECT)
// Fichier     : EidolonResident.cs
// Description : Compagnon Windows résident, ouverture du client connecté
// Standard    : Eidolon Presentation Standard v1
// ==========================================================
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Threading;
using System.Windows.Forms;

internal static class ResidentArguments {
    internal static bool Background(string[] args) {
        if (args.Length == 0) return false;
        if (args.Length == 1 && args[0] == "--background") return true;
        throw new ArgumentException("ARGUMENTS_INVALID");
    }
}

internal sealed class ResidentContext : ApplicationContext {
    private readonly NotifyIcon tray;
    private readonly ContextMenuStrip menu = new ContextMenuStrip();
    private readonly System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer();
    private readonly EventWaitHandle openRequest;
    private readonly ToolStripMenuItem status;
    private readonly string root;
    private Process client;

    [DllImport("user32.dll", CharSet=CharSet.Unicode)]
    private static extern IntPtr FindWindow(string cls, string title);
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr window);
    [DllImport("user32.dll")] private static extern bool ShowWindow(IntPtr window, int command);

    internal ResidentContext(string directory, EventWaitHandle request, bool background) {
        root = directory; openRequest = request;
        status = new ToolStripMenuItem("Prêt — ouvrir la conversation") { Enabled = false };
        menu.Items.Add(status);
        menu.Items.Add("Ouvrir Eidolon", null, delegate { Open(); });
        menu.Items.Add("Importer une connexion existante…", null, delegate { ImportConnection(); });
        menu.Items.Add(new ToolStripMenuItem("Réveil vocal local : qualification en cours") { Enabled = false });
        menu.Items.Add("Quitter le compagnon", null, delegate { Quit(); });
        tray = new NotifyIcon {
            Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath),
            Text = "Eidolon — compagnon", ContextMenuStrip = menu, Visible = true
        };
        tray.DoubleClick += delegate { Open(); };
        timer.Interval = 500;
        timer.Tick += delegate {
            if (client != null && client.HasExited) {
                int code = client.ExitCode;
                client.Dispose(); client = null;
                status.Text = code == 0 ? "Prêt — ouvrir la conversation" : "Connexion interrompue — réessayez";
            }
            if (openRequest.WaitOne(0)) Open();
        };
        timer.Start();
        if (!background) Open();
    }

    private void Open() {
        if (client != null && !client.HasExited) {
            // Existing launcher owns the only transport; never start a second one.
            IntPtr window = FindWindow(null, "Eidolon");
            if (window != IntPtr.Zero) { ShowWindow(window, 9); SetForegroundWindow(window); }
            return;
        }
        if (client != null) { client.Dispose(); client = null; }
        try {
            if (!File.Exists(Path.Combine(root, "connection.json")) && !ImportConnection()) return;
            string exe = Path.Combine(root, "Eidolon.exe");
            if (!File.Exists(exe)) throw new IOException("CLIENT_MISSING");
            client = Process.Start(new ProcessStartInfo {
                FileName = exe, WorkingDirectory = root, UseShellExecute = false
            });
            if (client == null) throw new IOException("CLIENT_START_FAILED");
            status.Text = "Client lancé — connexion gérée automatiquement";
        } catch {
            status.Text = "Client indisponible";
            tray.ShowBalloonTip(4000, "Eidolon", "Le client n’a pas pu démarrer. Réparez l’installation.", ToolTipIcon.Error);
        }
    }

    private bool ImportConnection() {
        if (client != null && !client.HasExited) {
            MessageBox.Show("Fermez la conversation avant de changer de connexion.", "Eidolon");
            return false;
        }
        using (var picker = new FolderBrowserDialog()) {
            picker.Description = "Choisissez le dossier de votre ancien client Eidolon (connexion existante).";
            picker.ShowNewFolderButton = false;
            if (picker.ShowDialog() != DialogResult.OK) return false;
            try {
                PairingImport.Import(picker.SelectedPath, root);
                status.Text = "Connexion importée — serveur à vérifier à l’ouverture";
                return true;
            } catch {
                MessageBox.Show("Connexion non importée. Choisissez le dossier d’origine sur ce compte Windows, ou le paquet personnel contenant sa clé d’appairage.",
                    "Eidolon", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return false;
            }
        }
    }

    private void Quit() {
        if (client != null && !client.HasExited) {
            MessageBox.Show("Fermez d’abord la conversation Eidolon. Cela arrête son micro et sa connexion.",
                "Eidolon", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }
        ExitThread();
    }

    protected override void Dispose(bool disposing) {
        if (disposing) {
            timer.Stop(); timer.Dispose(); tray.Visible = false;
            Icon icon = tray.Icon; tray.Dispose(); if (icon != null) icon.Dispose();
            menu.Dispose(); if (client != null) client.Dispose();
        }
        base.Dispose(disposing);
    }
}

internal static class EidolonResident {
    [STAThread]
    private static int Main(string[] args) {
        try {
            bool background = ResidentArguments.Background(args);
            string name = "Local\\EidolonResident-" + WindowsIdentity.GetCurrent().User.Value;
            bool created;
            // The event is created before the mutex: a concurrent second launch can
            // signal safely even while the first instance is constructing its tray.
            using (var request = new EventWaitHandle(false, EventResetMode.AutoReset, name + "-Open"))
            using (var single = new Mutex(true, name, out created)) {
                if (!created) { if (!background) request.Set(); return 0; }
                try {
                    Application.EnableVisualStyles();
                    Application.SetCompatibleTextRenderingDefault(false);
                    using (var context = new ResidentContext(AppDomain.CurrentDomain.BaseDirectory, request, background))
                        Application.Run(context);
                } finally { single.ReleaseMutex(); }
            }
            return 0;
        } catch {
            MessageBox.Show("Le compagnon Eidolon n’a pas pu démarrer.", "Eidolon",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 2;
        }
    }
}
