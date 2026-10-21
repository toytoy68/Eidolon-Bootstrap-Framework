// ==========================================================
// Projet      : Eidolon Core
// Organisation: Eidolon Core Technologies (ECT)
// Fichier     : PixyControl.cs
// Description : Commandes HID PIXY Windows bornées, sans flux vidéo ni serveur réseau
// Standard    : Eidolon Presentation Standard v1
// ==========================================================
// Protocol reference: Romonaga/PixyPilot docs/EMEET_PIXY_HID_REFERENCE.md
// Independent implementation from documented report layouts, no Linux code dependency.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Win32.SafeHandles;

internal static class PixyReports {
    internal static byte[] Pad(params byte[] prefix) { var b=new byte[32]; Array.Copy(prefix,b,prefix.Length); return b; }
    internal static byte[] Mode(byte mode) {
        if(mode>2) throw new ArgumentOutOfRangeException("mode");
        return Pad(9,1,1,0,0,1,0,1,mode);
    }
    internal static byte[] Motor(byte axis,float degrees,bool absolute) {
        if((axis!=1 && axis!=2) || float.IsNaN(degrees) || float.IsInfinity(degrees) ||
           (absolute ? degrees!=0 : Math.Abs(degrees)>5)) throw new ArgumentOutOfRangeException("movement");
        var b=Pad(9,3,1,(byte)(absolute?0x18:0x19),0,5,0,5,axis);
        var value=BitConverter.GetBytes(degrees); if(!BitConverter.IsLittleEndian) Array.Reverse(value);
        Array.Copy(value,0,b,9,4); return b;
    }
    internal static List<byte[]> Command(string command) {
        var result=new List<byte[]>();
        if(command=="track" || command=="idle" || command=="privacy") {
            result.Add(Mode((byte)(command=="track"?1:command=="privacy"?2:0)));
            result.Add(Pad(9,1,1,1)); return result;
        }
        // Manual movement releases tracking first; finite five-degree steps, no held motor command.
        result.Add(Mode(0)); result.Add(Pad(9,1,1,1));
        switch(command) {
            case "left":result.Add(Motor(1,-5,false));break;
            case "right":result.Add(Motor(1,5,false));break;
            case "up":result.Add(Motor(2,5,false));break;
            case "down":result.Add(Motor(2,-5,false));break;
            case "center":result.Add(Motor(1,0,true));result.Add(Motor(2,0,true));break;
            case "stop":result.Add(Pad(9,0x63,1,0x20,0,12,0,12));break;
            default:throw new ArgumentException("UNKNOWN_COMMAND");
        }
        return result;
    }
}

internal static class PixyHid {
    [StructLayout(LayoutKind.Sequential)] struct InterfaceData {public int size;public Guid guid;public int flags;public IntPtr reserved;}
    [StructLayout(LayoutKind.Sequential)] struct Attributes {public int size;public ushort vendor,product,version;}
    [StructLayout(LayoutKind.Sequential)] struct Caps {
        public ushort usage,page,input,output,feature;
        [MarshalAs(UnmanagedType.ByValArray,SizeConst=17)] public ushort[] reserved;
        public ushort links,inputButtons,inputValues,inputIndices,outputButtons,outputValues,outputIndices,featureButtons,featureValues,featureIndices;
    }
    [DllImport("hid.dll")] static extern void HidD_GetHidGuid(out Guid guid);
    [DllImport("hid.dll")] static extern bool HidD_GetAttributes(SafeFileHandle handle,ref Attributes attributes);
    [DllImport("hid.dll")] static extern bool HidD_GetPreparsedData(SafeFileHandle handle,out IntPtr data);
    [DllImport("hid.dll")] static extern bool HidD_FreePreparsedData(IntPtr data);
    [DllImport("hid.dll")] static extern int HidP_GetCaps(IntPtr data,out Caps caps);
    [DllImport("setupapi.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr SetupDiGetClassDevs(ref Guid guid,IntPtr enumerator,IntPtr parent,uint flags);
    [DllImport("setupapi.dll",SetLastError=true)] static extern bool SetupDiEnumDeviceInterfaces(IntPtr set,IntPtr device,ref Guid guid,uint index,ref InterfaceData data);
    [DllImport("setupapi.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool SetupDiGetDeviceInterfaceDetail(IntPtr set,ref InterfaceData data,IntPtr detail,uint size,out uint required,IntPtr device);
    [DllImport("setupapi.dll")] static extern bool SetupDiDestroyDeviceInfoList(IntPtr set);
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern SafeFileHandle CreateFile(string path,uint access,uint share,IntPtr security,uint creation,uint flags,IntPtr template);
    internal static string Find() {
        Guid guid;HidD_GetHidGuid(out guid);IntPtr set=SetupDiGetClassDevs(ref guid,IntPtr.Zero,IntPtr.Zero,0x12);
        if(set==new IntPtr(-1)) throw new IOException("HID_UNAVAILABLE");
        var matches=new List<string>();
        try {
            for(uint i=0;i<256;i++) {
                var info=new InterfaceData{size=Marshal.SizeOf(typeof(InterfaceData))};
                if(!SetupDiEnumDeviceInterfaces(set,IntPtr.Zero,ref guid,i,ref info)) break;
                uint size;SetupDiGetDeviceInterfaceDetail(set,ref info,IntPtr.Zero,0,out size,IntPtr.Zero);
                if(size<8 || size>65536) continue;
                IntPtr detail=Marshal.AllocHGlobal((int)size);
                try {
                    Marshal.WriteInt32(detail,IntPtr.Size==8?8:6);
                    if(!SetupDiGetDeviceInterfaceDetail(set,ref info,detail,size,out size,IntPtr.Zero)) continue;
                    string path=Marshal.PtrToStringUni(IntPtr.Add(detail,4));
                    using(var h=CreateFile(path,0,3,IntPtr.Zero,3,0,IntPtr.Zero)) {
                        if(h.IsInvalid) continue;
                        var attr=new Attributes{size=Marshal.SizeOf(typeof(Attributes))};
                        if(!HidD_GetAttributes(h,ref attr) || attr.vendor!=0x328f || attr.product!=0x00c0) continue;
                        IntPtr data;if(!HidD_GetPreparsedData(h,out data)) continue;
                        try {Caps cap;if(HidP_GetCaps(data,out cap)>=0 && cap.usage==0x83 && cap.page==0x83 && cap.output==32) matches.Add(path);}
                        finally {HidD_FreePreparsedData(data);}
                    }
                } finally {Marshal.FreeHGlobal(detail);}
            }
        } finally {SetupDiDestroyDeviceInfoList(set);}
        if(matches.Count!=1) throw new IOException(matches.Count==0?"PIXY_NOT_FOUND":"MULTIPLE_PIXY");
        return matches[0];
    }
    internal static void Send(string command) {
        var reports=PixyReports.Command(command);string path=Find();
        using(var handle=CreateFile(path,0x40000000,3,IntPtr.Zero,3,0x40000000,IntPtr.Zero)) {
            if(handle.IsInvalid) throw new IOException("PIXY_BUSY");
            using(var stream=new FileStream(handle,FileAccess.Write,32,true)) {
                foreach(var report in reports) {
                    var task=stream.WriteAsync(report,0,report.Length);
                    if(!task.Wait(1500)) throw new IOException("PIXY_WRITE_TIMEOUT");
                    // Config-to-commit delay confirmed by the protocol references.
                    System.Threading.Thread.Sleep(200);
                }
            }
        }
    }
}

internal sealed class PixyPanel:Form {
    readonly Label state=new Label {AutoSize=false,Height=65,Dock=DockStyle.Top};
    readonly FlowLayoutPanel commands=new FlowLayoutPanel {Dock=DockStyle.Fill};
    readonly NotifyIcon tray;
    bool working;
    internal PixyPanel() {
        Text="Eidolon — caméra PIXY";Width=430;Height=300;StartPosition=FormStartPosition.CenterScreen;
        state.Text="Détection de la PIXY…";Controls.Add(commands);Controls.Add(state);
        foreach(var pair in new[]{new[]{"left","← Gauche"},new[]{"up","↑ Haut"},new[]{"down","↓ Bas"},new[]{"right","Droite →"},
            new[]{"center","Recentrer"},new[]{"stop","Arrêter"},new[]{"track","Suivi auto"},new[]{"idle","Suivi arrêté"},new[]{"privacy","Confidentialité caméra"}}) {
            var action=pair[0];var button=new Button{Text=pair[1],Width=125,Height=35};
            button.Click+=async(s,e)=>await Run(action);commands.Controls.Add(button);
        }
        var refresh=new Button{Text="Redétecter",Width=125,Height=35};refresh.Click+=async(s,e)=>await Detect();commands.Controls.Add(refresh);
        tray=new NotifyIcon{Icon=SystemIcons.Application,Text="Eidolon — caméra PIXY",Visible=true};
        tray.DoubleClick+=(s,e)=>{Show();WindowState=FormWindowState.Normal;Activate();};
        var menu=new ContextMenuStrip();menu.Items.Add("Caméra PIXY",null,(s,e)=>{Show();Activate();});
        menu.Items.Add("Fermer le panneau",null,(s,e)=>{tray.Visible=false;Application.Exit();});tray.ContextMenuStrip=menu;
        FormClosing+=(s,e)=>{if(e.CloseReason==CloseReason.UserClosing){e.Cancel=true;Hide();}};
        Shown+=async(s,e)=>await Detect();
    }
    async Task Detect(){if(working)return;working=true;try{await Task.Run(()=>PixyHid.Find());state.Text="PIXY détectée. Déplacements par pas de 5°.\nSuivi : un flux vidéo ouvert peut être nécessaire.";}catch{state.Text="PIXY absente, occupée ou interface non reconnue.\nBranchez la caméra, fermez EMEET Studio puis Redétecter.";}finally{working=false;}}
    async Task Run(string action){if(working)return;working=true;commands.Enabled=false;try{await Task.Run(()=>PixyHid.Send(action));state.Text="Commande transmise à la PIXY.\nLe mouvement physique reste à vérifier. Le micro est indépendant.";}catch{state.Text="Commande non confirmée : caméra absente, occupée ou erreur USB.\nAucun renvoi automatique.";}finally{working=false;commands.Enabled=true;}}
    protected override void Dispose(bool disposing){if(disposing)tray.Dispose();base.Dispose(disposing);}
    [STAThread] public static void Main(){Application.EnableVisualStyles();Application.Run(new PixyPanel());}
}
