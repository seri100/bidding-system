[CmdletBinding(DefaultParameterSetName='Disk')]
param(
    [Parameter(Mandatory=$true,ParameterSetName='Disk')][int]$DiskNumber,
    [Parameter(Mandatory=$true,ParameterSetName='Disk')][char]$DriveLetter,
    [Parameter(Mandatory=$true,ParameterSetName='Disk')][UInt64]$ExpectedBytes,
    [Parameter(Mandatory=$true,ParameterSetName='Disk')][string]$ExpectedModel,
    [Parameter(Mandatory=$true,ParameterSetName='Fixture')][string]$FixtureFile,
    [long]$ReadOffset=0,
    [long]$ReadLength=0,
    [Parameter(Mandatory=$true)][string]$KeyFile,
    [Parameter(Mandatory=$true)][string]$OutputFile,
    [string]$OpenSsl='C:\Program Files\Git\usr\bin\openssl.exe'
)
$ErrorActionPreference='Stop'
if (!(Test-Path -LiteralPath $KeyFile) -or !(Test-Path -LiteralPath $OpenSsl)) { throw 'Key/OpenSSL missing' }
if (Test-Path -LiteralPath $OutputFile) { throw 'Output already exists' }
New-Item -ItemType Directory -Force (Split-Path $OutputFile) | Out-Null
if ($PSCmdlet.ParameterSetName -eq 'Disk') {
    $disk=Get-Disk -Number $DiskNumber
    $partition=Get-Partition -DriveLetter $DriveLetter
    if ($disk.IsBoot -or $disk.IsSystem -or $disk.BusType -ne 'USB' -or $disk.Size -ne $ExpectedBytes -or $disk.FriendlyName -ne $ExpectedModel -or $partition.DiskNumber -ne $DiskNumber) { throw 'Disk identity mismatch; nothing opened' }
    $source='\\.\PhysicalDrive'+$DiskNumber
    $volume='\\.\'+$DriveLetter+':'
    $length=[long]$disk.Size
} else {
    $source=(Resolve-Path -LiteralPath $FixtureFile).Path
    $volume=''
    $length=(Get-Item -LiteralPath $source).Length
}
if ($ReadOffset -lt 0 -or $ReadOffset -ge $length -or $ReadLength -lt 0) { throw 'Invalid read range' }
if ($ReadLength -eq 0) { $ReadLength=$length-$ReadOffset }
if ($ReadOffset+$ReadLength -gt $length) { throw 'Read extends beyond source' }
if ($PSCmdlet.ParameterSetName -eq 'Disk' -and (($ReadOffset % 512) -ne 0 -or ($ReadLength % 512) -ne 0)) { throw 'Raw disk reads must be sector aligned' }
$length=$ReadLength
$code=@'
using System;
using System.IO;
using System.IO.Compression;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class ReadOnlySdBackup {
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
 static extern SafeFileHandle CreateFile(string name,uint access,uint share,IntPtr security,uint creation,uint flags,IntPtr template);
 [DllImport("kernel32.dll",SetLastError=true)]
 static extern bool DeviceIoControl(SafeFileHandle h,uint code,IntPtr input,uint inputLen,IntPtr output,uint outputLen,out uint returned,IntPtr overlap);
 static string Hex(byte[] b){return BitConverter.ToString(b).Replace("-","").ToLowerInvariant();}
 static Process Crypto(string exe,string key,string file,bool decrypt){
   var p=new Process(); p.StartInfo.FileName=exe;
   p.StartInfo.Arguments="enc "+(decrypt?"-d ":"")+"-aes-256-cbc -pbkdf2 -iter 200000 "+(decrypt?"-in ":"-salt -out ")+"\""+file+"\" -pass file:\""+key+"\"";
   p.StartInfo.UseShellExecute=false;p.StartInfo.CreateNoWindow=true;p.StartInfo.RedirectStandardError=true;
   p.StartInfo.RedirectStandardInput=!decrypt;p.StartInfo.RedirectStandardOutput=decrypt;p.Start();return p;
 }
 static void Progress(string path,string phase,long count,long total,Stopwatch clock){
   string text="{\"phase\":\""+phase+"\",\"bytes\":"+count+",\"total\":"+total+",\"seconds\":"+(long)clock.Elapsed.TotalSeconds+"}";
   File.WriteAllText(path,text);
   Console.WriteLine("SD_BACKUP phase="+phase+" bytes="+count+" total="+total+" percent="+(100.0*count/total).ToString("F1"));
 }
 public static string Run(string source,string volume,long offset,long length,string exe,string key,string output){
   SafeFileHandle locked=null;uint returned;string rawHash=null;var clock=Stopwatch.StartNew();
   try {
    if(volume.Length>0){
     locked=CreateFile(volume,0xC0000000,3,IntPtr.Zero,3,0,IntPtr.Zero);
     if(locked.IsInvalid || !DeviceIoControl(locked,0x90018,IntPtr.Zero,0,IntPtr.Zero,0,out returned,IntPtr.Zero))throw new IOException("Cannot lock source volume; Win32="+Marshal.GetLastWin32Error());
    }
    var handle=CreateFile(source,0x80000000,3,IntPtr.Zero,3,0x08000000,IntPtr.Zero);
    if(handle.IsInvalid)throw new IOException("Cannot open source read-only; Win32="+Marshal.GetLastWin32Error());
    var process=Crypto(exe,key,output,false);
    try {
     using(var input=new FileStream(handle,FileAccess.Read,1,false))
     using(var sha=SHA256.Create()){
      if(offset>0)input.Seek(offset,SeekOrigin.Begin);
      long count=0,last=-30;byte[] buffer=new byte[8*1024*1024];
      using(var zip=new GZipStream(process.StandardInput.BaseStream,CompressionLevel.Fastest,true)){
       while(count<length){
        int n=input.Read(buffer,0,(int)Math.Min(buffer.Length,length-count));
        if(n==0)throw new EndOfStreamException("Source shorter than expected");
        sha.TransformBlock(buffer,0,n,buffer,0);zip.Write(buffer,0,n);count+=n;
        if(clock.Elapsed.TotalSeconds-last>=30){Progress(output+".progress.json","backup",count,length,clock);last=(long)clock.Elapsed.TotalSeconds;}
       }
      }
      sha.TransformFinalBlock(new byte[0],0,0);rawHash=Hex(sha.Hash);
      Progress(output+".progress.json","backup",length,length,clock);
     }
     process.StandardInput.Close();string error=process.StandardError.ReadToEnd();process.WaitForExit();
     if(process.ExitCode!=0)throw new IOException("Encryption failed: "+error);
    } finally {if(!process.HasExited)process.Kill();process.Dispose();}
   } finally {if(locked!=null){DeviceIoControl(locked,0x9001c,IntPtr.Zero,0,IntPtr.Zero,0,out returned,IntPtr.Zero);locked.Dispose();}}
   string cipherHash,macHash;
   using(var input=File.OpenRead(output))using(var sha=SHA256.Create()){cipherHash=Hex(sha.ComputeHash(input));}
   using(var input=File.OpenRead(output))using(var mac=new HMACSHA256(System.Text.Encoding.UTF8.GetBytes(File.ReadAllText(key).Trim()))){macHash=Hex(mac.ComputeHash(input));}
   File.WriteAllText(output+".hmac",macHash+"\n");File.WriteAllText(output+".sha256",cipherHash+"\n");
   var verify=Crypto(exe,key,output,true);long restored=0;string restoredHash;
   try {
    using(var zip=new GZipStream(verify.StandardOutput.BaseStream,CompressionMode.Decompress))using(var sha=SHA256.Create()){
     byte[] buffer=new byte[8*1024*1024];int n;long last=-30;
     while((n=zip.Read(buffer,0,buffer.Length))>0){sha.TransformBlock(buffer,0,n,buffer,0);restored+=n;if(clock.Elapsed.TotalSeconds-last>=30){Progress(output+".progress.json","verify",restored,length,clock);last=(long)clock.Elapsed.TotalSeconds;}}
     sha.TransformFinalBlock(new byte[0],0,0);restoredHash=Hex(sha.Hash);
    }
    string error=verify.StandardError.ReadToEnd();verify.WaitForExit();if(verify.ExitCode!=0)throw new IOException("Decryption failed: "+error);
   } finally {if(!verify.HasExited)verify.Kill();verify.Dispose();}
   if(restored!=length||restoredHash!=rawHash)throw new IOException("Full decrypted image hash/length mismatch");
   Progress(output+".progress.json","verified",restored,length,clock);
   string result="{\"offset\":"+offset+",\"bytes\":"+length+",\"raw_sha256\":\""+rawHash+"\",\"cipher_sha256\":\""+cipherHash+"\",\"decrypt_verified\":true,\"source_opened_read_only\":true}";
   File.WriteAllText(output+".verified.json",result);return result;
 }
}
'@
Add-Type -TypeDefinition $code -ReferencedAssemblies System.IO.Compression
[ReadOnlySdBackup]::Run($source,$volume,$ReadOffset,$length,$OpenSsl,(Resolve-Path -LiteralPath $KeyFile).Path,$OutputFile)
