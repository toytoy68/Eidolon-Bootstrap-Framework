// ==========================================================
// Projet      : Eidolon Core
// Organisation: Eidolon Core Technologies (ECT)
// Fichier     : PairingImport.cs
// Description : Reprise graphique d'un appairage G286 existant
// Standard    : Eidolon Presentation Standard v1
// ==========================================================
using System;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;

internal static class PairingImport {
    internal static ConnectionConfig ReadConfig(string source) {
        var info = new FileInfo(source);
        if (!info.Exists || info.Length == 0 || info.Length > 4096)
            throw new InvalidOperationException("CONFIG_INVALID");
        var config = new JavaScriptSerializer().Deserialize<ConnectionConfig>(File.ReadAllText(source));
        if (config == null) throw new InvalidOperationException("CONFIG_INVALID");
        config.Validate(); return config;
    }

    internal static void Import(string sourceDirectory, string destinationDirectory) {
        var config = ReadConfig(Path.Combine(sourceDirectory, "connection.json"));
        string account = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Eidolon", EidolonLauncher.Binding(config));
        EidolonLauncher.PrivateDirectory(account);
        string saved = Path.Combine(account, "identity.dpapi");
        // Existing protected identity wins; it is shared with the original launcher.
        if (File.Exists(saved)) {
            byte[] check = EidolonLauncher.Unprotect(File.ReadAllBytes(saved));
            Array.Clear(check, 0, check.Length);
        } else {
            string seed = Path.Combine(sourceDirectory, "desktop-identity");
            var info = new FileInfo(seed);
            if (!info.Exists || info.Length < 100 || info.Length > 16384)
                throw new InvalidOperationException("IDENTITY_MISSING");
            byte[] bytes = File.ReadAllBytes(seed);
            string temp = Path.Combine(account, Guid.NewGuid().ToString("N") + ".tmp");
            try {
                if (!Encoding.ASCII.GetString(bytes).StartsWith("-----BEGIN OPENSSH PRIVATE KEY-----"))
                    throw new InvalidOperationException("IDENTITY_INVALID");
                File.WriteAllBytes(temp, EidolonLauncher.Protect(bytes));
                byte[] check = EidolonLauncher.Unprotect(File.ReadAllBytes(temp));
                try {
                    if (check.Length != bytes.Length) throw new InvalidOperationException("IDENTITY_INVALID");
                    for (int i = 0; i < bytes.Length; i++)
                        if (bytes[i] != check[i]) throw new InvalidOperationException("IDENTITY_INVALID");
                } finally { Array.Clear(check, 0, check.Length); }
                File.Move(temp, saved);
            } finally {
                Array.Clear(bytes, 0, bytes.Length);
                if (File.Exists(temp)) File.Delete(temp);
            }
        }
        string destination = Path.Combine(destinationDirectory, "connection.json");
        string staging = Path.Combine(destinationDirectory, Guid.NewGuid().ToString("N") + ".json.tmp");
        try {
            File.WriteAllText(staging, new JavaScriptSerializer().Serialize(config), new UTF8Encoding(false));
            if (File.Exists(destination)) File.Replace(staging, destination, null);
            else File.Move(staging, destination);
        } finally { if (File.Exists(staging)) File.Delete(staging); }
    }
}
