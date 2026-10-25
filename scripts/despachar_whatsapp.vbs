Option Explicit
Dim fso, shell, scriptDir, batPath
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
batPath = fso.BuildPath(scriptDir, "despachar_whatsapp.bat")
Set shell = CreateObject("WScript.Shell")
shell.Run """" & batPath & """", 0, False
