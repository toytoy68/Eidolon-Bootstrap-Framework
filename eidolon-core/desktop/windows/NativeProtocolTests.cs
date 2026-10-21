// ==========================================================
// Projet      : Eidolon Core
// Organisation: Eidolon Core Technologies (ECT)
// Fichier     : NativeProtocolTests.cs
// Description : Validation des paquets HID, entrées, quoting et stockage Windows
// Standard    : Eidolon Presentation Standard v1
// ==========================================================
using System;
using System.IO;
using System.Linq;
using System.Text;
internal static class NativeProtocolTests {
    static void Check(bool ok,string label){if(!ok)throw new Exception(label);}
    static void Refused(Action action){try{action();}catch(ArgumentException){return;}catch(InvalidOperationException){return;}throw new Exception("invalid accepted");}
    public static int Main(){
        Check(PixyReports.Mode(1).Length==32,"report length");
        Check(BitConverter.ToString(PixyReports.Mode(1).Take(9).ToArray())=="09-01-01-00-00-01-00-01-01","tracking packet");
        Check(BitConverter.ToString(PixyReports.Command("left").Last().Take(13).ToArray())=="09-03-01-19-00-05-00-05-01-00-00-A0-C0","left five degrees");
        var center=PixyReports.Command("center");Check(center.Count==4 && center[2][3]==0x18 && center[2][8]==1 && center[3][8]==2,"two-axis center");
        Refused(()=>PixyReports.Motor(1,6,false));Refused(()=>PixyReports.Motor(1,float.NaN,false));Refused(()=>PixyReports.Motor(3,0,true));Refused(()=>PixyReports.Command("shell"));
        var config=new ConnectionConfig{server="192.0.2.1",user="fixture",port=8767,host_key="ssh-ed25519 "+new string('A',68)};config.Validate();
        string binding=EidolonLauncher.Binding(config);config.user="other";Check(binding!=EidolonLauncher.Binding(config),"binding");
        config.server="192.0.2.1 -oProxyCommand=evil";Refused(config.Validate);
        Check(EidolonLauncher.Quote("a b & c")=="\"a b & c\"","quoted spaces");
        Check(EidolonLauncher.Quote("a\"b")=="\"a\\\"b\"","quoted double quote");
        Check(EidolonLauncher.Quote("C:\\end\\")=="\"C:\\end\\\\\"","trailing slash");
        if(Environment.OSVersion.Platform==PlatformID.Win32NT){
            byte[] plain=Encoding.UTF8.GetBytes("synthetic-test-no-real-credential");
            byte[] encrypted=EidolonLauncher.Protect(plain);Check(!plain.SequenceEqual(encrypted),"DPAPI encrypted");
            Check(plain.SequenceEqual(EidolonLauncher.Unprotect(encrypted)),"DPAPI roundtrip");
            string dir=Path.Combine(Path.GetTempPath(),"eidolon-native-"+Guid.NewGuid().ToString("N"));
            try{EidolonLauncher.PrivateDirectory(dir);Check(new DirectoryInfo(dir).GetAccessControl().AreAccessRulesProtected,"private ACL");}finally{Directory.Delete(dir);}
            Console.WriteLine("WINDOWS_DPAPI_ACL_PASS");
        }else Console.WriteLine("WINDOWS_DPAPI_ACL_NOT_RUN");
        Console.WriteLine("NATIVE_PROTOCOL_PASS");return 0;
    }
}
