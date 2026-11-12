param(
    [Parameter(Mandatory=$true)][int]$DiskNumber,
    [Parameter(Mandatory=$true)][char]$DriveLetter,
    [Parameter(Mandatory=$true)][UInt64]$ExpectedBytes,
    [Parameter(Mandatory=$true)][string]$ExpectedModel,
    [Parameter(Mandatory=$true)][string]$ImageFile,
    [Parameter(Mandatory=$true)][string]$CardManifest,
    [Parameter(Mandatory=$true)][string]$CardBackupArchive,
    [Parameter(Mandatory=$true)][string]$KeyFile
)
$ErrorActionPreference='Stop'
$disk=Get-Disk -Number $DiskNumber
$partition=Get-Partition -DriveLetter $DriveLetter
if ($disk.IsBoot -or $disk.IsSystem -or $disk.BusType -ne 'USB' -or $disk.Size -ne $ExpectedBytes -or $disk.FriendlyName -ne $ExpectedModel -or $partition.DiskNumber -ne $DiskNumber) {throw 'Target disk identity mismatch'}
$image=(Resolve-Path -LiteralPath $ImageFile).Path
$proof=Get-Content -LiteralPath ($image+'.ready.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if (!$proof.trial_image_only -or !$proof.isolation_marker_verified -or !$proof.boot_prefix_verified -or $proof.nas_writes_allowed -or $proof.outbound_new_connections_allowed -or !$proof.original_usb_must_be_disconnected) {throw 'Trial isolation proof missing'}
if ((Get-Item -LiteralPath $image).Length -ne $proof.image_bytes -or $proof.image_bytes -gt $ExpectedBytes -or ($proof.image_bytes % 512) -ne 0) {throw 'Image size invalid'}
if ((Get-FileHash -LiteralPath $image -Algorithm SHA256).Hash.ToLowerInvariant() -ne $proof.image_sha256) {throw 'Image hash mismatch'}
$key=[Text.Encoding]::UTF8.GetBytes([IO.File]::ReadAllText($KeyFile).Trim())
$mac=[Security.Cryptography.HMACSHA256]::new($key)
$backupStream=[IO.File]::OpenRead($CardBackupArchive)
try {$actual=[BitConverter]::ToString($mac.ComputeHash($backupStream)).Replace('-','').ToLowerInvariant()} finally {$backupStream.Dispose();$mac.Dispose()}
if($actual -ne [IO.File]::ReadAllText($CardBackupArchive+'.hmac').Trim()){throw 'Original card backup authentication failed'}
$manifest=Get-Content -LiteralPath $CardManifest -Raw -Encoding UTF8 | ConvertFrom-Json
foreach($file in $manifest.files){
    $relative=$file.path.Substring(6)
    $path=Join-Path ($DriveLetter+':\') $relative
    if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256){throw 'Current card content differs from backup'}
}
function CardFiles([string]$folder){
    foreach($entry in Get-ChildItem -LiteralPath $folder -Force){
        if($entry.Name -eq 'System Volume Information'){continue}
        if($entry.PSIsContainer){CardFiles $entry.FullName}else{$entry}
    }
}
if(@(CardFiles ($DriveLetter+':\')).Count -ne @($manifest.files).Count){throw 'Additional unbacked-up card files exist'}
$code=@'
using System;
using System.IO;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class GuardedTrialWriter {
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
 static extern SafeFileHandle CreateFile(string name,uint access,uint share,IntPtr security,uint creation,uint flags,IntPtr template);
 [DllImport("kernel32.dll",SetLastError=true)]
 static extern bool DeviceIoControl(SafeFileHandle h,uint code,IntPtr input,uint inSize,IntPtr output,uint outSize,out uint returned,IntPtr overlap);
 static string Hex(byte[] b){return BitConverter.ToString(b).Replace("-","").ToLowerInvariant();}
 public static string Write(string image,string target,string volume,long length,string expected,string progress){
  uint returned;var locked=CreateFile(volume,0xC0000000,3,IntPtr.Zero,3,0,IntPtr.Zero);
  if(locked.IsInvalid)throw new IOException("Cannot open target volume");
  try {
   if(!DeviceIoControl(locked,0x90018,IntPtr.Zero,0,IntPtr.Zero,0,out returned,IntPtr.Zero))throw new IOException("Target volume is in use; no write performed");
   if(!DeviceIoControl(locked,0x90020,IntPtr.Zero,0,IntPtr.Zero,0,out returned,IntPtr.Zero))throw new IOException("Cannot detach target filesystem; no write performed");
   var handle=CreateFile(target,0xC0000000,3,IntPtr.Zero,3,0x80000000,IntPtr.Zero);
   if(handle.IsInvalid)throw new IOException("Cannot open guarded target disk");
   using(var output=new FileStream(handle,FileAccess.ReadWrite,1,false)){
    var clock=Stopwatch.StartNew();long last=-30,count=0;byte[] b=new byte[8*1024*1024];
    using(var source=File.OpenRead(image)){
     while(count<length){int wanted=(int)Math.Min(b.Length,length-count),got=0;while(got<wanted){int n=source.Read(b,got,wanted-got);if(n==0)throw new EndOfStreamException();got+=n;}output.Write(b,0,got);count+=got;
      if(clock.Elapsed.TotalSeconds-last>=30){Console.WriteLine("TRIAL_SD_WRITE bytes="+count+" total="+length);File.WriteAllText(progress,"{\"phase\":\"write\",\"bytes\":"+count+",\"total\":"+length+"}");last=(long)clock.Elapsed.TotalSeconds;}}
    }
    output.Flush(true);output.Seek(0,SeekOrigin.Begin);count=0;last=-30;string actual;
    using(var sha=SHA256.Create()){
     while(count<length){int n=output.Read(b,0,(int)Math.Min(b.Length,length-count));if(n==0)throw new EndOfStreamException();sha.TransformBlock(b,0,n,b,0);count+=n;
      if(clock.Elapsed.TotalSeconds-last>=30){Console.WriteLine("TRIAL_SD_VERIFY bytes="+count+" total="+length);File.WriteAllText(progress,"{\"phase\":\"readback\",\"bytes\":"+count+",\"total\":"+length+"}");last=(long)clock.Elapsed.TotalSeconds;}}
     sha.TransformFinalBlock(new byte[0],0,0);actual=Hex(sha.Hash);
    }
    if(actual!=expected)throw new IOException("Trial SD readback hash mismatch");
    return actual;
   }
  } finally {DeviceIoControl(locked,0x9001c,IntPtr.Zero,0,IntPtr.Zero,0,out returned,IntPtr.Zero);locked.Dispose();}
 }
}
'@
Add-Type -TypeDefinition $code
$result=[GuardedTrialWriter]::Write($image,('\\.\PhysicalDrive'+$DiskNumber),('\\.\'+$DriveLetter+':'),[long]$proof.image_bytes,$proof.image_sha256,($image+'.write-progress.json'))
[IO.File]::WriteAllText(($image+'.card-verified.json'),(@{disk_number=$DiskNumber;image_bytes=$proof.image_bytes;readback_sha256=$result;verified=$true} | ConvertTo-Json),[Text.UTF8Encoding]::new($false))
Update-HostStorageCache
Write-Output 'TRIAL_SD_CARD_WRITTEN_AND_READBACK_VERIFIED'
