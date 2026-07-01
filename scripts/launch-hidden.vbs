Option Explicit

Dim fso, shell, scriptDir, root, launcher, powershell, command

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
root = fso.GetParentFolderName(scriptDir)
launcher = fso.BuildPath(scriptDir, "launch.ps1")
powershell = shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\WindowsPowerShell\v1.0\powershell.exe"

command = """" & powershell & """ -NoProfile -ExecutionPolicy Bypass -File """ & launcher & """"
shell.CurrentDirectory = root
shell.Run command, 0, False
