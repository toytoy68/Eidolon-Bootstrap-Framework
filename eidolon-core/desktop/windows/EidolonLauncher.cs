// ==========================================================
// Projet      : Eidolon Core
// Organisation: Eidolon Core Technologies (ECT)
// Fichier     : EidolonLauncher.cs
// Description : Connexion privée silencieuse, appairage et ouverture en un clic
// Standard    : Eidolon Presentation Standard v1
// ==========================================================
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using System.Net;
using System.Net.Sockets;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;

internal sealed class ConnectionConfig {
    public string server { get; set; }
    public string user { get; set; }
    public string host_key { get; set; }
    public int port { get; set; }
    public void Validate() {
        IPAddress address;
        if (!IPAddress.TryParse(server, out address) || address.AddressFamily != AddressFamily.InterNetwork ||
            !Regex.IsMatch(user ?? "", @"\A[a-z_][a-z0-9_-]{0,31}\z") || port < 1024 || port > 65535 ||
            !Regex.IsMatch(host_key ?? "", @"\Assh-ed25519 [A-Za-z0-9+/]{60,100}={0,2}\z"))
            throw new InvalidOperationException("CONFIG_INVALID");
    }
}

internal static class EidolonLauncher {
    internal static string Quote(string value) {
        var result = new StringBuilder("\"");
        int slashes = 0;
        foreach (char c in value) {
            if (c == '\\') { slashes++; continue; }
            result.Append('\\', c == '\"' ? slashes * 2 + 1 : slashes);
            result.Append(c); slashes = 0;
        }
        result.Append('\\', slashes * 2); result.Append('\"'); return result.ToString();
    }

    internal static void PrivateDirectory(string path) {
        Directory.CreateDirectory(path);
        var acl = new DirectorySecurity();
        acl.SetAccessRuleProtection(true, false);
        var sid = WindowsIdentity.GetCurrent().User;
        acl.SetOwner(sid);
        acl.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.FullControl,
            InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
        new DirectoryInfo(path).SetAccessControl(acl);
    }
    internal static byte[] Protect(byte[] bytes) { return ProtectedData.Protect(bytes, null, DataProtectionScope.CurrentUser); }
    internal static byte[] Unprotect(byte[] bytes) { return ProtectedData.Unprotect(bytes, null, DataProtectionScope.CurrentUser); }
    internal static string Binding(ConnectionConfig config) {
        using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(
            config.server + "|" + config.user + "|" + config.port + "|" + config.host_key))).Replace("-", "");
    }
    private static Process Start(string file, string arguments) {
        return Process.Start(new ProcessStartInfo { FileName=file, Arguments=arguments, UseShellExecute=false,
            CreateNoWindow=true, RedirectStandardOutput=true, RedirectStandardError=true });
    }
    private static string SshArgs(ConnectionConfig config, string keyPath, string hostsPath) {
        return "-F NUL -o BatchMode=yes -o IdentitiesOnly=yes -o IdentityAgent=none -o StrictHostKeyChecking=yes " +
            "-o HostKeyAlgorithms=ssh-ed25519 -o GlobalKnownHostsFile=NUL -o UserKnownHostsFile=" + Quote(hostsPath) +
            " -o ConnectTimeout=8 -o ConnectionAttempts=1 -i " + Quote(keyPath);
    }
    [DllImport("iphlpapi.dll", SetLastError=true)]
    private static extern uint GetExtendedTcpTable(IntPtr table, ref int size, bool order, int family, int kind, uint reserved);
    private static bool OwnsPort(int port,int pid) {
        int size=0; GetExtendedTcpTable(IntPtr.Zero,ref size,false,2,3,0);
        if(size<4 || size>4000000) return false;
        IntPtr table=Marshal.AllocHGlobal(size);
        try {
            if(GetExtendedTcpTable(table,ref size,false,2,3,0)!=0) return false;
            int count=Marshal.ReadInt32(table);
            if(count<0 || count>(size-4)/24) return false;
            for(int i=0;i<count;i++) {
                int at=4+i*24;
                int local=(Marshal.ReadByte(table,at+8)<<8)|Marshal.ReadByte(table,at+9);
                if(local==port && Marshal.ReadInt32(table,at)==2) {
                    if(Marshal.ReadInt32(table,at+20)!=pid || Marshal.ReadInt32(table,at+4)!=16777343) return false;
                    return true;
                }
            }
            return false;
        } finally {Marshal.FreeHGlobal(table);}
    }
    private static bool Ready(int port,int pid) {
        if(!OwnsPort(port,pid)) return false;
        try {
            var request=(HttpWebRequest)WebRequest.Create("http://127.0.0.1:"+port+"/");
            request.Proxy=null; request.Timeout=1500; request.AllowAutoRedirect=false;
            using(var response=(HttpWebResponse)request.GetResponse()) return response.StatusCode==HttpStatusCode.OK;
        } catch { return false; }
    }
    private static void Stop(Process process) {
        if (process == null) return;
        try { if (!process.HasExited) { process.Kill(); process.WaitForExit(3000); } } catch { }
        process.Dispose();
    }
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern IntPtr FindWindow(string cls,string title);
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr window);
    [DllImport("user32.dll")] private static extern bool ShowWindow(IntPtr window,int command);
    [STAThread]
    private static int Main(string[] args) {
        Process tunnel=null, client=null, camera=null;
        string temporary=null, stage="initialisation";
        Mutex instance=null;bool ownsInstance=false;
        bool diagnostic=args.Length==1 && args[0]=="--diagnostic";
        try {
            string root=AppDomain.CurrentDomain.BaseDirectory;
            if (args.Length==1 && args[0]=="--shortcut") { CreateShortcut(Assembly.GetExecutingAssembly().Location,root); return 0; }
            if (args.Length!=0 && !diagnostic) throw new InvalidOperationException("ARGUMENTS_INVALID");
            stage="configuration";
            string configPath=Path.Combine(root,"connection.json");
            if (!File.Exists(configPath)) throw new InvalidOperationException("CONNECTION_CONFIG_MISSING");
            if (new FileInfo(configPath).Length>4096) throw new InvalidOperationException("CONFIG_INVALID");
            var config=new JavaScriptSerializer().Deserialize<ConnectionConfig>(File.ReadAllText(configPath));
            config.Validate();
            instance=new Mutex(true,"Local\\EidolonDesktop-"+Binding(config),out ownsInstance);
            if(!ownsInstance) {
                IntPtr existing=FindWindow(null,"Eidolon");
                if(existing!=IntPtr.Zero) {ShowWindow(existing,9);SetForegroundWindow(existing);}
                return 0;
            }
            string exe=Path.Combine(root,"eidolon-consultation.exe");
            if (!File.Exists(exe)) throw new InvalidOperationException("CLIENT_EXE_MISSING");
            string ssh=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System),@"OpenSSH\ssh.exe");
            if (!File.Exists(ssh)) throw new InvalidOperationException("OPENSSH_MISSING");
            stage="connexion-privee";
            string directory=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Eidolon",Binding(config));
            PrivateDirectory(directory);
            string saved=Path.Combine(directory,"identity.dpapi"), seed=Path.Combine(root,"desktop-identity");
            if (!File.Exists(saved)) {
                if (!File.Exists(seed)) throw new InvalidOperationException("IDENTITY_MISSING");
                byte[] bytes=File.ReadAllBytes(seed);
                try { File.WriteAllBytes(saved,Protect(bytes)); } finally { Array.Clear(bytes,0,bytes.Length); }
                // Verify before consuming the personalized bootstrap credential.
                byte[] check=Unprotect(File.ReadAllBytes(saved)); Array.Clear(check,0,check.Length);
                File.Delete(seed);
            }
            temporary=Path.Combine(directory,"session-"+Guid.NewGuid().ToString("N")); PrivateDirectory(temporary);
            string keyPath=Path.Combine(temporary,"identity"), hostsPath=Path.Combine(temporary,"known_hosts");
            byte[] identity=Unprotect(File.ReadAllBytes(saved));
            try { File.WriteAllBytes(keyPath,identity); } finally { Array.Clear(identity,0,identity.Length); }
            File.WriteAllText(hostsPath,config.server+" "+config.host_key+"\n",new UTF8Encoding(false));
            string baseArgs=SshArgs(config,keyPath,hostsPath), destination=config.user+"@"+config.server;
            string key;
            // Fetch the current paired credential on every launch: rotation needs no user action.
            using(var pairing=Start(ssh,baseArgs+" -- "+destination+" pair")) {
                var output=pairing.StandardOutput.ReadToEndAsync(); pairing.StandardError.ReadToEndAsync();
                if (!pairing.WaitForExit(15000)) { pairing.Kill(); throw new InvalidOperationException("PAIRING_TIMEOUT"); }
                if(pairing.ExitCode!=0) throw new InvalidOperationException("PAIRING_FAILED");
                key=output.Result.Trim();
            }
            if (!Regex.IsMatch(key,@"\Aecc_[A-Za-z0-9_-]{43}\z")) throw new InvalidOperationException("PAIRING_INVALID");
            int port=config.port; // Core enforces this Host/Origin; arbitrary local ports are rejected.
            string tunnelArgs=baseArgs+" -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=10 -o ServerAliveCountMax=2 -L "+
                "127.0.0.1:"+port+":127.0.0.1:"+config.port+" -- "+destination;
            tunnel=Start(ssh,tunnelArgs); tunnel.BeginOutputReadLine(); tunnel.BeginErrorReadLine();
            var deadline=DateTime.UtcNow.AddSeconds(20);
            while (!tunnel.HasExited && DateTime.UtcNow<deadline && !Ready(port,tunnel.Id)) Thread.Sleep(200);
            if(tunnel.HasExited || !Ready(port,tunnel.Id)) throw new InvalidOperationException("CONNECTION_FAILED");
            stage="ouverture";
            var start=new ProcessStartInfo {FileName=exe,Arguments="--port "+port,WorkingDirectory=root,UseShellExecute=false};
            start.EnvironmentVariables["EIDOLON_CONVERSATION_KEY"]=key;
            client=Process.Start(start); start.EnvironmentVariables.Remove("EIDOLON_CONVERSATION_KEY"); key=null;
            if(client==null) throw new InvalidOperationException("CLIENT_FAILED");
            string cameraExe=Path.Combine(root,"Eidolon-camera.exe");
            // An unavailable camera companion must not close an already working conversation.
            if(File.Exists(cameraExe)) try {
                camera=Process.Start(new ProcessStartInfo {FileName=cameraExe,WorkingDirectory=root,UseShellExecute=false});
            } catch (System.ComponentModel.Win32Exception) { }
            // Keep transport supervised for the lifetime of the app. Never replay a chat message.
            while(!client.WaitForExit(1000)) {
                if(tunnel.HasExited) {
                    Stop(tunnel); tunnel=null;
                    Thread.Sleep(2000);
                    if(!client.HasExited) { tunnel=Start(ssh,tunnelArgs); tunnel.BeginOutputReadLine(); tunnel.BeginErrorReadLine(); }
                    else break;
                }
            }
            return 0;
        } catch(Exception error) {
            string code=Regex.IsMatch(error.Message ?? "", @"\A[A-Z_]{3,60}\z") ? error.Message : "WINDOWS_OPERATION_FAILED";
            string log=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Eidolon");
            Directory.CreateDirectory(log); File.WriteAllText(Path.Combine(log,"last-launch-error.txt"),"Etape="+stage+" ; Code="+code);
            if(!diagnostic) MessageBox.Show("Eidolon ne peut pas se connecter. Vérifiez que le serveur et le réseau sont disponibles.\nCode : "+code,
                "Eidolon",MessageBoxButtons.OK,MessageBoxIcon.Error);
            return 2;
        } finally {
            Stop(camera); Stop(client); Stop(tunnel);
            if(instance!=null) {if(ownsInstance)instance.ReleaseMutex();instance.Dispose();}
            if(temporary!=null) try { Directory.Delete(temporary,true); } catch { }
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
