Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
shell.CurrentDirectory = fs.GetParentFolderName(WScript.ScriptFullName)
pythonExe = fs.BuildPath(shell.CurrentDirectory, ".venv\Scripts\pythonw.exe")
If Not fs.FileExists(pythonExe) Then pythonExe = "pythonw.exe"
shell.Run """" & pythonExe & """ """ & fs.BuildPath(shell.CurrentDirectory, "main.py") & """", 0, False
