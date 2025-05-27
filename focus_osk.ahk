SetTitleMatchMode, 2
DetectHiddenWindows, On

if WinExist("On-Screen Keyboard") {
	Run, osk.exe
    WinShow
    WinRestore
    WinActivate
} else {
    MsgBox, On-Screen Keyboard not found.
}
