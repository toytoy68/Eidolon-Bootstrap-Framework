// ==========================================================
// Projet      : Eidolon Core
// Organisation: Eidolon Core Technologies (ECT)
// Fichier     : ResidentTests.cs
// Description : Import d'appairage, refus des entrées et protection du secret
// Standard    : Eidolon Presentation Standard v1
// ==========================================================
using System;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;

internal static class ResidentTests {
    static void Check(bool value, string label) { if (!value) throw new Exception(label); }
    static void Refused(Action f) { try { f(); } catch (InvalidOperationException) { return; }
        catch (ArgumentException) { return; } throw new Exception("INVALID_ACCEPTED"); }
    public static int Main() {
        Check(!ResidentArguments.Background(new string[0]), "interactive launch");
        Check(ResidentArguments.Background(new[]{"--background"}), "silent startup");
        Refused(() => ResidentArguments.Background(new[]{"--background", "--shell"}));
        string root = Path.Combine(Path.GetTempPath(), "eidolon-import-test-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        string account = null;
        try {
            string source = Path.Combine(root, "source"), target = Path.Combine(root, "target");
            Directory.CreateDirectory(source); Directory.CreateDirectory(target);
            string file = Path.Combine(source, "connection.json");
            File.WriteAllText(file, "null"); Refused(() => PairingImport.ReadConfig(file));
            File.WriteAllText(file, new string(' ', 4097)); Refused(() => PairingImport.ReadConfig(file));
            var config = new ConnectionConfig { server="192.0.2.1", port=8767,
                user="test" + Guid.NewGuid().ToString("N").Substring(0, 20),
                host_key="ssh-ed25519 " + new string('A', 68) };
            var serializer = new JavaScriptSerializer();
            File.WriteAllText(file, serializer.Serialize(config));
            Check(PairingImport.ReadConfig(file).server == "192.0.2.1", "config parsed");
            config.server = "192.0.2.1 -oProxyCommand=bad";
            File.WriteAllText(file, serializer.Serialize(config)); Refused(() => PairingImport.ReadConfig(file));
            config.server = "192.0.2.1"; File.WriteAllText(file, serializer.Serialize(config));
            if (Environment.OSVersion.Platform == PlatformID.Win32NT) {
                account = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "Eidolon", EidolonLauncher.Binding(config));
                string secret = "-----BEGIN OPENSSH PRIVATE KEY-----\n" + new string('A', 100) + "\n-----END OPENSSH PRIVATE KEY-----\n";
                string seed = Path.Combine(source, "desktop-identity");
                // Failure leaves no configuration that could pretend pairing succeeded.
                Refused(() => PairingImport.Import(source, target));
                Check(!File.Exists(Path.Combine(target, "connection.json")), "no partial config");
                File.WriteAllText(seed, secret);
                PairingImport.Import(source, target);
                Check(PairingImport.ReadConfig(Path.Combine(target, "connection.json")).user == config.user, "imported config");
                Check(!File.Exists(Path.Combine(target, "desktop-identity")), "no plaintext copied");
                string saved = Path.Combine(account, "identity.dpapi");
                byte[] protectedBytes = File.ReadAllBytes(saved);
                Check(Encoding.UTF8.GetString(protectedBytes) != secret, "not plaintext");
                byte[] plain = EidolonLauncher.Unprotect(protectedBytes);
                Check(Encoding.UTF8.GetString(plain) == secret, "DPAPI roundtrip");
                Array.Clear(plain, 0, plain.Length);
                File.Delete(seed);
                PairingImport.Import(source, target); // reinstall reuses protected identity
                Check(Convert.ToBase64String(File.ReadAllBytes(saved)) == Convert.ToBase64String(protectedBytes), "identity preserved");
                Console.WriteLine("RESIDENT_WINDOWS_IMPORT_PASS");
            } else Console.WriteLine("RESIDENT_WINDOWS_IMPORT_NOT_RUN");
            Console.WriteLine("RESIDENT_INPUTS_PASS");
            return 0;
        } finally {
            Directory.Delete(root, true);
            if (account != null && Directory.Exists(account)) Directory.Delete(account, true);
        }
    }
}
