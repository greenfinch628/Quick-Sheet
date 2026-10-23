Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
shell.CurrentDirectory = fs.GetParentFolderName(WScript.ScriptFullName)
shell.Run "pythonw.exe """ & fs.BuildPath(shell.CurrentDirectory, "main.py") & """", 0, False
