#NoEnv
#SingleInstance Force

; zoom_control.ahk — v1 syntax
; Usage: zoom_control.exe <WindowID> <LoopCount>

if %0% < 2
{
    MsgBox, 48, Error, Usage:`n`%A_ScriptName`% <WindowID> <LoopCount>
    ExitApp
}

windowID  = %1%
loopCount = %2%

WinActivate, ahk_id %windowID%
WinWaitActive, ahk_id %windowID%, , 2
if ErrorLevel
{
    MsgBox, 48, Error, Failed to activate window with ID %windowID%
    ExitApp
}
Sleep, 100

Send, ^0
Sleep, 50

if loopCount = 2
{
    ExitApp   ; quit immediately when loopCount is 2
}

Loop, %loopCount%
{
    Send, ^{NumpadAdd}
    Sleep, 50
}

ExitApp
