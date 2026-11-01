Option Explicit

Const FRAME_TIMEOUT = 3000

' Global device info
Dim gDeviceCode
Dim gDeviceRawInfo$
Dim gBuildDate$
Dim gBoardName$
Dim gFwVersion$

' Global self info
Dim gSelfCode
Dim gTypeVal
Dim gTxPowerVal
Dim gMaxTxPowerVal
Dim gFreqVal
Dim gBwVal
Dim gSfVal
Dim gCrVal
Dim gNodeName$

' Global contacts sync state
Dim gContactsSinceVal

' Global app state
Dim gRunning
Dim gLastMenu$

Const MAX_FRAME_LEN = 1024

Const MAX_CONTACTS = 320

Dim contactName$(MAX_CONTACTS)
Dim contactPubKey$(MAX_CONTACTS)
Dim contactType(MAX_CONTACTS)
Dim sendableMap(MAX_CONTACTS)
Dim sendableCount
Dim contactCount
Dim contactsLoaded

Const MAX_CHANNELS = 8

Dim channelName$(MAX_CHANNELS)
Dim channelKey$(MAX_CHANNELS)
Dim channelPrefix$(MAX_CHANNELS)
Dim channelIdx(MAX_CHANNELS)
Dim channelCount

channelCount = 1
channelName$(1) = "#public"
channelIdx(1) = 0

' UART on PicoCalc
SetPin GP9, GP8, COM2
Open "COM2:115200" As #1

gRunning = 1
gLastMenu$ = ""

Print "MeshCore Pico Client"
Print

' Flush any old bytes and allow the radio to finish booting
FlushInput
Pause 500

Print "Boot bytes:"
ReadRawBytes 1000
Print

' Initial startup sequence
DoInitialize

Do While gRunning = 1
  MainMenu
Loop

Print "Done"
End


Sub MainMenu
  Local choice$

  Do
    Print "Main menu"
    Print "---------"
    Print "1 - Messages"
    Print "2 - Contacts"
    Print "3 - Channels"
    Print "4 - Device"
    Print "Q - Exit"
    Print

    Line Input "Select: ", choice$
    Print

    Select Case UCase$(choice$)
      Case "1"
        MessagesMenu
      Case "2"
        ContactsMenu
      Case "3"
        ChannelsMenu
      Case "4"
        DeviceMenu
      Case "Q"
        gRunning = 0
        Exit Do
      Case Else
        Print "Unknown selection"
        Print
    End Select
  Loop
End Sub

Sub ChannelsMenu
  Local choice$

  Do
    Print "Channels"
    Print "--------"
    Print "1 - List channels"
    Print "2 - Add channel"
    Print "3 - Send channel message"
    Print "B - Back"
    Print

    Line Input "Select: ", choice$
    Print

    Select Case UCase$(choice$)
      Case "1"
        ShowChannels
      Case "2"
        DoAddChannel
      Case "3"
        DoSendChannelMessage
      Case "B"
        Exit Do
      Case Else
        Print "Unknown selection"
        Print
    End Select
  Loop
End Sub

Sub DoSendChannelMessage
  Local idxStr$
  Local idxVal
  Local msgText$
  Local payload$
  Local frame$
  Local codeVal
  Local epochVal

  If channelCount = 0 Then
    Print "No channels defined"
    Print
    Exit Sub
  End If

  ShowChannels

  Line Input "Channel number: ", idxStr$
  Print

  idxVal = Val(idxStr$)

  If idxVal < 1 Or idxVal > channelCount Then
    Print "Invalid channel number"
    Print
    Exit Sub
  End If

  Line Input "Message text: ", msgText$
  Print

  If msgText$ = "" Then
    Print "Empty message not sent"
    Print
    Exit Sub
  End If

  epochVal = Int(DateTimeToUnix(Date$, Time$))

  payload$ = ""
  payload$ = payload$ + Chr$(3)
  payload$ = payload$ + Chr$(0)
  payload$ = payload$ + Chr$(channelIdx(idxVal))
  payload$ = payload$ + U32ToLE$(epochVal)
  payload$ = payload$ + msgText$

  Print "Sending to:    "; channelName$(idxVal)
  Print "Time:          "; UnixToDate$(epochVal)

  SendFrame payload$

  frame$ = ReadResponseSkippingAsync$(FRAME_TIMEOUT)

  If frame$ = "" Then
    Print "No response"
    Print
    Exit Sub
  End If

  codeVal = Asc(Mid$(frame$, 1, 1))

  If codeVal = 0 Then
    Print "Channel message sent"
  ElseIf codeVal = 1 Then
    Print "Channel send failed"
    DumpHex frame$
  ElseIf codeVal = 6 Then
    Print "Channel message queued"
    DumpHex frame$
  Else
    Print "Unexpected response code: "; codeVal
    DumpHex frame$
  End If

  Print
End Sub

Sub MessagesMenu
  Local choice$

  Do
    Print "Messages"
    Print "--------"
    Print "1 - Read next message"
    Print "2 - Read all messages"
    Print "3 - Send message"
    Print "B - Back"
    Print

    Line Input "Select: ", choice$
    Print

    Select Case UCase$(choice$)
      Case "1"
        DoReadNextMessage
      Case "2"
        DoReadAllMessages
      Case "3"
        DoSendMessage
      Case "B"
        Exit Do
      Case Else
        Print "Unknown selection"
        Print
    End Select
  Loop
End Sub

Sub DoAddChannel
  Local name$
  Local idxStr$
  Local idxVal

  If channelCount >= MAX_CHANNELS Then
    Print "Channel list full"
    Print
    Exit Sub
  End If

  Line Input "Channel name: ", name$
  Line Input "Channel index: ", idxStr$
  Print

  idxVal = Val(idxStr$)

  If name$ = "" Then
    Print "Name missing"
    Print
    Exit Sub
  End If

  If idxVal < 0 Or idxVal > 255 Then
    Print "Invalid channel index"
    Print
    Exit Sub
  End If

  channelCount = channelCount + 1
  channelName$(channelCount) = name$
  channelIdx(channelCount) = idxVal

  Print "Channel added"
  Print
End Sub

Sub ShowChannels
  Local i

  If channelCount = 0 Then
    Print "No channels"
    Print
    Exit Sub
  End If

  Print "Channels"
  Print "--------"

  For i = 1 To channelCount
    Print i; " - "; channelName$(i)
  Next i

  Print
End Sub

Function FindChannelName$(prefix$)
  Local i

  For i = 1 To channelCount
    If Mid$(channelKey$(i), 1, Len(prefix$)) = prefix$ Then
      FindChannelName$ = channelName$(i)
      Exit Function
    End If
  Next i

  FindChannelName$ = "(unknown channel)"
End Function

Function HexToBin$(hexStr$)
  Local i, b, out1$

  out1$ = ""

  For i = 1 To Len(hexStr$) Step 2
    b = Val("&H" + Mid$(hexStr$, i, 2))
    out1$ = out1$ + Chr$(b)
  Next i

  HexToBin$ = out1$
End Function

Sub DoReadNextMessage
  Local frame$
  Local gotMessage
  Local quietLoops
  Local codeVal

  EnsureContactsLoaded

  Print "Requesting next message..."

  gotMessage = 0
  quietLoops = 0

  ' First, drain any async frames already waiting
  DrainAsyncFrames

  Do While quietLoops < 6
    SendFrame Chr$(10)

    frame$ = ReadFrame$(700)

    If frame$ = "" Then
      quietLoops = quietLoops + 1
      Pause 100

    Else
      codeVal = Asc(Mid$(frame$, 1, 1))

      If codeVal >= 128 Then
        ' Async frame, do not stop yet
        HandleAsyncFrame frame$
        quietLoops = 0
        Pause 80

      ElseIf IsRealMessage(codeVal) Then
        ParseMessageFrame frame$
        Print
        gotMessage = 1
        Exit Do

      ElseIf codeVal = 10 Then
        ' No more messages for now, but keep polling a bit
        quietLoops = quietLoops + 1
        Pause 120

      Else
        Print "Skipping non-message frame, code="; codeVal
        DumpHex frame$
        Print
        quietLoops = quietLoops + 1
        Pause 80
      End If
    End If
  Loop

  If gotMessage = 0 Then
    Print "No new message found"
    Print
  End If
End Sub

Sub AnalyzeMessageFrame(a$)
  Local i, b
  Local ascii$
  Local temp$

  Print "---- MESSAGE FRAME ----"
  Print "Length: "; Len(a$)
  Print "Hex:"
  DumpHex a$

  Print
  Print "Index  Hex  ASCII"
  Print "-----------------"

  For i = 1 To Len(a$)
    b = Asc(Mid$(a$, i, 1))

    If b >= 32 And b <= 126 Then
      ascii$ = Chr$(b)
    Else
      ascii$ = "."
    End If

    Print Pad3$(i); "    "; Right$("0" + Hex$(b), 2); "   "; ascii$
  Next i

  Print
  Print "Byte 1:      "; Right$("0" + Hex$(Asc(Mid$(a$, 1, 1))), 2)
  Print "Byte 2-5 LE: "; Int(U32LEVal(a$, 2))

  If Len(a$) >= 25 Then
    temp$ = "Byte 22-25:  "
    temp$ = temp$ + Right$("0" + Hex$(Asc(Mid$(a$, 22, 1))), 2) + " "
    temp$ = temp$ + Right$("0" + Hex$(Asc(Mid$(a$, 23, 1))), 2) + " "
    temp$ = temp$ + Right$("0" + Hex$(Asc(Mid$(a$, 25, 1))), 2)

    Print temp$;
  End If
End Sub

Sub DoReadAllMessages
  Local frame$
  Local codeVal
  Local count
  Local quietLoops

  Print "Reading all messages..."
  Print

  count = 0
  quietLoops = 0

  DrainAsyncFrames

  Do While quietLoops < 6
    SendFrame Chr$(10)

    frame$ = ReadFrame$(600)

    If frame$ = "" Then
      quietLoops = quietLoops + 1
      Pause 100

    Else
      codeVal = Asc(Mid$(frame$, 1, 1))

      If codeVal >= 128 Then
        HandleAsyncFrame frame$
        quietLoops = 0
        Pause 60

      ElseIf IsRealMessage(codeVal) Then
        ParseMessageFrame frame$
        Print
        count = count + 1
        quietLoops = 0
        Pause 60

      ElseIf codeVal = 10 Then
        quietLoops = quietLoops + 1
        Pause 120

      Else
        Print "Skipping non-message frame, code="; codeVal
        DumpHex frame$
        Print
        quietLoops = quietLoops + 1
        Pause 60
      End If
    End If
  Loop

  Print "Messages read: "; count
  Print
End Sub

Sub DrainAsyncFrames
  Local frame$
  Local codeVal
  Local loops

  loops = 0

  Do While loops < 10
    frame$ = ReadFrame$(120)

    If frame$ = "" Then Exit Do

    codeVal = Asc(Mid$(frame$, 1, 1))

    If codeVal >= 128 Then
      HandleAsyncFrame frame$
    Else
      ' Put non-async frames back is not possible, so stop draining here
      ' Better to show it than lose track completely
      Print "Pending non-async frame while draining:"
      DumpHex frame$
      Print
      Exit Do
    End If

    loops = loops + 1
  Loop
End Sub

Function IsRealMessage(codeVal)
  If codeVal = 7 Then
    IsRealMessage = 1
  ElseIf codeVal = 8 Then
    IsRealMessage = 1
  ElseIf codeVal = 16 Then
    IsRealMessage = 1
  ElseIf codeVal = 17 Then
    IsRealMessage = 1
  Else
    IsRealMessage = 0
  End If
End Function

Sub ParseMessageFrame(a$)
  Local codeVal

  If Len(a$) < 1 Then
    Print "Message frame too short"
    Print
    Exit Sub
  End If

  codeVal = Asc(Mid$(a$, 1, 1))

  Select Case codeVal
    Case 7, 16
      ParseContactMessageFrame a$

    Case 8, 17
      ParseChannelMessageFrame a$

    Case Else
      Print "Unknown message frame type"
      DumpHex a$
      Print
  End Select
End Sub

Sub ParseContactMessageFrame(a$)
  Local codeVal
  Local msgText$
  Local i, b
  Local headerHex$
  Local tsVal
  Local senderKey$
  Local senderName$

  If Len(a$) < 17 Then
    Print "Contact message frame too short"
    Print
    Exit Sub
  End If

  codeVal = Asc(Mid$(a$, 1, 1))

  headerHex$ = ""
  For i = 2 To 16
    b = Asc(Mid$(a$, i, 1))
    headerHex$ = headerHex$ + Right$("0" + Hex$(b), 2)
    If i < 16 Then headerHex$ = headerHex$ + " "
  Next i

  senderKey$ = ""
  For i = 5 To 10
    b = Asc(Mid$(a$, i, 1))
    senderKey$ = senderKey$ + Right$("0" + Hex$(b), 2)
  Next i

  senderName$ = FindContactName$(senderKey$)

  msgText$ = ""
  For i = 17 To Len(a$)
    b = Asc(Mid$(a$, i, 1))
    If b = 0 Then Exit For
    msgText$ = msgText$ + Chr$(b)
  Next i

  Print "---- MESSAGE ----"

  If codeVal = 16 Then
    Print "Kind:         Contact message V3"
  Else
    Print "Kind:         Contact message"
  End If

  Print "Header:       "; headerHex$

  tsVal = U32LEVal(a$, 13)
  If tsVal > 1500000000 And tsVal < 2200000000 Then
    Print "Time guess:   "; UnixToDate$(Int(tsVal))
  End If

  Print "From:         "; senderName$
  Print "Text:         "; msgText$
  Print
End Sub

Sub ParseChannelMessageFrame(a$)
  Local codeVal
  Local msgText$
  Local i, b
  Local headerHex$
  Local tsVal
  Local idxVal
  Local pathLenVal
  Local txtTypeVal
  Local snrVal
  Local channelName$

  If Len(a$) < 12 Then
    Print "Channel message frame too short"
    Print
    Exit Sub
  End If

  codeVal = Asc(Mid$(a$, 1, 1))

  headerHex$ = ""
  For i = 2 To 11
    b = Asc(Mid$(a$, i, 1))
    headerHex$ = headerHex$ + Right$("0" + Hex$(b), 2)
    If i < 11 Then headerHex$ = headerHex$ + " "
  Next i

  If codeVal = 17 Then
    snrVal = Asc(Mid$(a$, 2, 1))
    idxVal = Asc(Mid$(a$, 5, 1))
    pathLenVal = Asc(Mid$(a$, 6, 1))
    txtTypeVal = Asc(Mid$(a$, 7, 1))
    tsVal = U32LEVal(a$, 8)
    msgText$ = ""
    For i = 12 To Len(a$)
      b = Asc(Mid$(a$, i, 1))
      If b = 0 Then Exit For
      msgText$ = msgText$ + Chr$(b)
    Next i
  Else
    idxVal = Asc(Mid$(a$, 2, 1))
    pathLenVal = Asc(Mid$(a$, 3, 1))
    txtTypeVal = Asc(Mid$(a$, 4, 1))
    tsVal = U32LEVal(a$, 5)
    msgText$ = ""
    For i = 9 To Len(a$)
      b = Asc(Mid$(a$, i, 1))
      If b = 0 Then Exit For
      msgText$ = msgText$ + Chr$(b)
    Next i
  End If

  channelName$ = FindChannelNameByIndex$(idxVal)

  Print "---- CHANNEL MESSAGE ----"

  If codeVal = 17 Then
    Print "Kind:         Channel message V3"
    Print "SNR:          "; snrVal
  Else
    Print "Kind:         Channel message"
  End If

  Print "Header:       "; headerHex$
  Print "Channel:      "; channelName$
  Print "Channel idx:  "; idxVal
  Print "Path len:     "; pathLenVal
  Print "Text type:    "; txtTypeVal

  If tsVal > 1500000000 And tsVal < 2200000000 Then
    Print "Time:         "; UnixToDate$(Int(tsVal))
  End If

  Print "Text:         "; msgText$
  Print
End Sub

Function FindChannelNameByIndex$(idxVal)
  Local i

  For i = 1 To channelCount
    If channelIdx(i) = idxVal Then
      FindChannelNameByIndex$ = channelName$(i)
      Exit Function
    End If
  Next i

  FindChannelNameByIndex$ = "(unknown channel)"
End Function

Sub ParseMessage(a$)
  Local i, b
  Local pubKeyHex$
  Local tsVal
  Local msgType
  Local text$
  Local pos

  If Len(a$) < 40 Then
    Print "Message too short"
    Exit Sub
  End If

  pubKeyHex$ = ""
  For i = 2 To 33
    b = Asc(Mid$(a$, i, 1))
    pubKeyHex$ = pubKeyHex$ + Right$("0" + Hex$(b), 2)
  Next i

  tsVal = U32LEVal(a$, 34)
  msgType = Asc(Mid$(a$, 38, 1))

  text$ = ""
  For pos = 39 To Len(a$)
    b = Asc(Mid$(a$, pos, 1))
    If b = 0 Then Exit For
    text$ = text$ + Chr$(b)
  Next pos

  Print "---- MESSAGE ----"
  Print "From:      "; Left$(pubKeyHex$, 16); "..."
  Print "Time:      "; UnixToDate$(Int(tsVal))
  Print "Type:      "; msgType
  Print "Text:      "; text$
  Print
End Sub

Sub ContactsMenu
  Local choice$

  Do
    Print "Contacts"
    Print "--------"
    Print "1 - Refresh contacts"
    Print "2 - Show last sync info"
    Print "3 - List contacts"
    Print "B - Back"
    Print

    Line Input "Select: ", choice$
    Print

    Select Case UCase$(choice$)
      Case "1"
        DoGetContacts
      Case "2"
        ShowContactsStatus
      Case "3"
        ShowContactsList
      Case "B"
        Exit Do
      Case Else
        Print "Unknown selection"
        Print
    End Select
  Loop
End Sub

Sub DeviceMenu
  Local choice$

  Do
    Print "Device"
    Print "------"
    Print "1 - Show status"
    Print "2 - Sync device time"
    Print "3 - Get device time"
    Print "4 - Set node name"
    Print "5 - Advert - Zero Hop"
    Print "6 - Advert - Flood Routing"
    Print "7 - Radio settings"
    Print "8 - Initialize radio"
    Print "9 - Diagnostics"
    Print "B - Back"
    Print

    Line Input "Select: ", choice$
    Print

    Select Case UCase$(choice$)
      Case "1"
        ShowStatus
      Case "2"
        DoSyncDeviceTime
      Case "3"
        DoGetDeviceTime
      Case "4"
        DoSetNodeName
      Case "5"
        DoSendAdvertZeroHop
      Case "6"
        DoSendAdvertFlood
      Case "7"
        RadioMenu
      Case "8"
        DoInitialize
      Case "9"
        DiagnosticsMenu
      Case "B"
        Exit Do
      Case Else
        Print "Unknown selection"
        Print
    End Select
  Loop
End Sub

Sub RadioMenu
  Local choice$

  Do
    Print "Radio settings"
    Print "--------------"
    Print "1 - Show current radio settings"
    Print "2 - Set radio params"
    Print "3 - Set TX power"
    Print "B - Back"
    Print

    Line Input "Select: ", choice$
    Print

    Select Case UCase$(choice$)
      Case "1"
        ShowRadioSettings
      Case "2"
        DoSetRadioParams
      Case "3"
        DoSetTxPower
      Case "B"
        Exit Do
      Case Else
        Print "Unknown selection"
        Print
    End Select
  Loop
End Sub

Sub DiagnosticsMenu
  Local choice$

  Do
    Print "Diagnostics"
    Print "-----------"
    Print "1 - Device query"
    Print "2 - App start"
    Print "3 - Read one frame"
    Print "4 - Flush input"
    Print "B - Back"
    Print

    Line Input "Select: ", choice$
    Print

    Select Case UCase$(choice$)
      Case "1"
        DoDeviceQuery
      Case "2"
        DoAppStart
      Case "3"
        ReadOneFrame
      Case "4"
        FlushInput
        Print "Input buffer flushed"
        Print
      Case "B"
        Exit Do
      Case Else
        Print "Unknown selection"
        Print
    End Select
  Loop
End Sub

Sub DoSendAdvertZeroHop
  Local payload$
  Local frame$
  Local codeVal

  Print "Sending advert (zero hop)..."

  payload$ = Chr$(7)
  SendFrame payload$

  frame$ = ReadResponseSkippingAsync$(FRAME_TIMEOUT)

  If frame$ = "" Then
    Print "No response"
    Print
    Exit Sub
  End If

  codeVal = Asc(Mid$(frame$, 1, 1))

  If codeVal = 0 Then
    Print "Advert sent"
  ElseIf codeVal = 1 Then
    Print "Advert failed"
    DumpHex frame$
  Else
    Print "Unexpected response code: "; codeVal
    DumpHex frame$
  End If

  Print
End Sub

Sub DoSendAdvertFlood
  Local payload$
  Local frame$
  Local codeVal

  Print "Sending advert (flood routing)..."

  payload$ = Chr$(7) + Chr$(1)
  SendFrame payload$

  frame$ = ReadResponseSkippingAsync$(FRAME_TIMEOUT)

  If frame$ = "" Then
    Print "No response"
    Print
    Exit Sub
  End If

  codeVal = Asc(Mid$(frame$, 1, 1))

  If codeVal = 0 Then
    Print "Advert sent"
  ElseIf codeVal = 1 Then
    Print "Advert failed"
    DumpHex frame$
  Else
    Print "Unexpected response code: "; codeVal
    DumpHex frame$
  End If

  Print
End Sub

Sub DoInitialize
  Print "Initializing radio..."
  Print

  DoSyncDeviceTime
  DoDeviceQuery
  DoAppStart

  Print "Initialization complete"
  Print
End Sub

Sub DoSetNodeName
  Local name$
  Local payload$
  Local frame$
  Local codeVal

  Print "Set node name"
  Print "-------------"

  Line Input "New name: ", name$
  Print

  If name$ = "" Then
    Print "Empty name not allowed"
    Print
    Exit Sub
  End If

  ' Limit length to safe value
  If Len(name$) > 32 Then
    Print "Name too long (max 32 chars)"
    Print
    Exit Sub
  End If

  payload$ = Chr$(8) + name$

  Print "Sending name update..."
  SendFrame payload$

  frame$ = ReadResponseSkippingAsync$(FRAME_TIMEOUT)

  If frame$ = "" Then
    Print "No response"
    Print
    Exit Sub
  End If

  codeVal = Asc(Mid$(frame$, 1, 1))

  If codeVal = 0 Then
    Print "Name updated successfully"
    Print

    ' Refresh local device info
    DoAppStart

  ElseIf codeVal = 1 Then
    Print "Name update failed"
    DumpHex frame$
    Print

  Else
    Print "Unexpected response code: "; codeVal
    DumpHex frame$
    Print
  End If
End Sub

Sub DoSetRadioParams
  Local freqStr$, bwStr$, sfStr$, crStr$
  Local freqMHz, bwKHz, sfVal, crVal
  Local freqEnc, bwEnc
  Local payload$, frame$
  Local codeVal

  Print "Set radio params"
  Print "----------------"
  Line Input "Freq MHz: ", freqStr$
  Line Input "BW kHz:   ", bwStr$
  Line Input "SF:       ", sfStr$
  Line Input "CR:       ", crStr$
  Print

  freqMHz = Val(freqStr$)
  bwKHz   = Val(bwStr$)
  sfVal   = Val(sfStr$)
  crVal   = Val(crStr$)

  If freqMHz <= 0 Or bwKHz <= 0 Then
    Print "Invalid frequency or bandwidth"
    Print
    Exit Sub
  End If

  If sfVal < 5 Or sfVal > 12 Then
    Print "Invalid SF"
    Print
    Exit Sub
  End If

  If crVal < 5 Or crVal > 8 Then
    Print "Invalid CR"
    Print
    Exit Sub
  End If

  freqEnc = Int(freqMHz * 1000)
  bwEnc   = Int(bwKHz * 1000)

  payload$ = ""
  payload$ = payload$ + Chr$(11)
  payload$ = payload$ + U32ToLE$(freqEnc)
  payload$ = payload$ + U32ToLE$(bwEnc)
  payload$ = payload$ + Chr$(sfVal)
  payload$ = payload$ + Chr$(crVal)
  payload$ = payload$ + Chr$(0)

  Print "Sending radio params..."
  SendFrame payload$

  frame$ = ReadResponseSkippingAsync$(FRAME_TIMEOUT)

  If frame$ = "" Then
    Print "No response"
    Print
    Exit Sub
  End If

  codeVal = Asc(Mid$(frame$, 1, 1))

  If codeVal = 0 Then
    Print "Radio params saved"
    Print
    DoAppStart
  ElseIf codeVal = 1 Then
    Print "Radio params failed"
    DumpHex frame$
    Print
  Else
    Print "Unexpected response code: "; codeVal
    DumpHex frame$
    Print
  End If
End Sub

Sub DoSetTxPower
  Local pwrStr$
  Local pwrVal
  Local payload$, frame$
  Local codeVal

  Print "Set TX power"
  Print "------------"
  Line Input "TX power dBm: ", pwrStr$
  Print

  pwrVal = Val(pwrStr$)

  If pwrVal < 0 Or pwrVal > 30 Then
    Print "Invalid TX power"
    Print
    Exit Sub
  End If

  payload$ = Chr$(12) + Chr$(pwrVal)

  Print "Sending TX power..."
  SendFrame payload$

  frame$ = ReadResponseSkippingAsync$(FRAME_TIMEOUT)

  If frame$ = "" Then
    Print "No response"
    Print
    Exit Sub
  End If

  codeVal = Asc(Mid$(frame$, 1, 1))

  If codeVal = 0 Then
    Print "TX power saved"
    Print
    DoAppStart
  ElseIf codeVal = 1 Then
    Print "TX power failed"
    DumpHex frame$
    Print
  Else
    Print "Unexpected response code: "; codeVal
    DumpHex frame$
    Print
  End If
End Sub

Sub ShowRadioSettings
  Local freqMHz
  Local bwKHz

  If gFreqVal = 0 Then
    Print "No radio data available"
    Print "Run 'Show status' or 'Initialize radio' first"
    Print
    Exit Sub
  End If

  freqMHz = gFreqVal / 1000
  bwKHz   = gBwVal / 1000

  Print "Current radio settings"
  Print "----------------------"

  Print "Frequency MHz: "; freqMHz
  Print "Bandwidth kHz: "; bwKHz
  Print "Spreading SF:  "; gSfVal
  Print "Coding rate:   "; gCrVal
  Print "TX power dBm:  "; gTxPowerVal

  Print
End Sub

Function ReadResponseSkippingAsync$(timeoutMs)
  Local frame$
  Local codeVal

  Do
    frame$ = ReadFrame$(timeoutMs)

    If frame$ = "" Then
      ReadResponseSkippingAsync$ = ""
      Exit Function
    End If

    codeVal = Asc(Mid$(frame$, 1, 1))

    If codeVal >= 128 Then
      HandleAsyncFrame frame$
    Else
      ReadResponseSkippingAsync$ = frame$
      Exit Function
    End If
  Loop
End Function

Sub DoSyncDeviceTime
  Local payload$, frame$
  Local epochVal
  Local codeVal

  epochVal = DateTimeToUnix(Date$, Time$)

  Print "Syncing device time..."
  Print "Pico date:    "; Date$
  Print "Pico time:    "; Time$
  Print "Epoch:        "; Int(epochVal)

  payload$ = Chr$(6) + U32ToLE$(epochVal)
  SendFrame payload$

  frame$ = ReadFrame$(FRAME_TIMEOUT)
  If frame$ = "" Then
    Print "No SET_DEVICE_TIME response"
  Else
    Print "SET_DEVICE_TIME response:"
    DumpHex frame$

    codeVal = Asc(Mid$(frame$, 1, 1))
    If codeVal = 0 Then
      Print "Time sync OK"
    ElseIf codeVal = 1 Then
      Print "Time sync ERROR"
    Else
      Print "Unexpected response code: "; codeVal
    End If
  End If

  Print
End Sub


Sub DoGetDeviceTime
  Local payload$, frame$
  Local codeVal
  Local epochVal

  Print "Requesting device time..."

  payload$ = Chr$(5)
  SendFrame payload$

  frame$ = ReadFrame$(FRAME_TIMEOUT)
  If frame$ = "" Then
    Print "No GET_DEVICE_TIME response"
    Print
    Exit Sub
  End If

  Print "GET_DEVICE_TIME response:"
  DumpHex frame$

  codeVal = Asc(Mid$(frame$, 1, 1))
  If codeVal <> 9 Then
    Print "Unexpected response code: "; codeVal
    Print
    Exit Sub
  End If

  If Len(frame$) < 5 Then
    Print "CURR_TIME frame too short"
    Print
    Exit Sub
  End If

  epochVal = U32LEVal(frame$, 2)

  Print "Device epoch: "; Int(epochVal)
  Print "Device date:  "; UnixToDate$(Int(epochVal))
  Print
End Sub


Sub DoDeviceQuery
  Local payload$, frame$

  Print "Sending DEVICE_QUERY..."
  payload$ = Chr$(22) + Chr$(10)
  SendFrame payload$

  frame$ = ReadFrame$(FRAME_TIMEOUT)
  If frame$ <> "" Then
    Print "DEVICE_QUERY response:"
    DumpHex frame$
    ParseDeviceInfo frame$
  Else
    Print "No DEVICE_QUERY response"
  End If

  Print
End Sub


Sub DoAppStart
  Local payload$, frame$

  Print "Sending APP_START..."
  payload$ = Chr$(1) + Chr$(10) + String$(6, Chr$(0))
  SendFrame payload$

  frame$ = ReadFrame$(FRAME_TIMEOUT)
  If frame$ <> "" Then
    Print "APP_START response:"
    DumpHex frame$
    ParseSelfInfo frame$
  Else
    Print "No APP_START response"
  End If

  Print
End Sub

Sub EnsureContactsLoaded
  If contactsLoaded = 0 Then
    DoGetContacts
  End If
End Sub

Sub ShowContactsStatus
  Print "Contacts status"
  Print "---------------"
  Print "Next since:    "; Int(gContactsSinceVal)
  If gContactsSinceVal > 0 Then
    Print "Next since dt: "; UnixToDate$(Int(gContactsSinceVal))
  End If
  Print
End Sub

Sub ShowStatus
  Print "=== STATUS ==="
  Print

  Print "Device info"
  Print "-----------"
  Print "Code:        "; gDeviceCode
  Print "Raw info:    "; gDeviceRawInfo$
  Print "Build date:  "; gBuildDate$
  Print "Board:       "; gBoardName$
  Print "FW version:  "; gFwVersion$
  Print

  Print "Self info"
  Print "---------"
  Print "Code:        "; gSelfCode
  Print "Type:        "; gTypeVal
  Print "TX power:    "; gTxPowerVal; " dBm"
  Print "Max TX:      "; gMaxTxPowerVal; " dBm"
  Print "Freq MHz:    "; gFreqVal / 1000
  Print "BW kHz:      "; gBwVal / 1000
  Print "SF:          "; gSfVal
  Print "CR:          "; gCrVal
  Print "Name:        "; gNodeName$
  Print

  Print "Contacts"
  Print "--------"
  Print "Next since:   "; Int(gContactsSinceVal)
  If gContactsSinceVal > 0 Then
    Print "Next since dt:"; UnixToDate$(Int(gContactsSinceVal))
  End If
  Print
End Sub


Sub ReadOneFrame
  Local frame$

  Print "Waiting for one frame..."
  frame$ = ReadFrame$(FRAME_TIMEOUT)

  If frame$ <> "" Then
    Print "Frame received:"
    DumpHex frame$
    Print "Code: "; Asc(Mid$(frame$, 1, 1))
  Else
    Print "No frame received"
  End If

  Print
End Sub


Sub FlushInput
  Local x$
  Do While Loc(#1) > 0
    x$ = Input$(1, #1)
  Loop
End Sub


Sub SendFrame(payload$)
  Local hdr$
  hdr$ = Chr$(60) + Chr$(Len(payload$) And &HFF)
  hdr$ = hdr$ + Chr$((Len(payload$) >> 8) And &HFF)
  Print #1, hdr$ + payload$;
End Sub

Sub HandleAsyncFrame(a$)
  Local codeVal

  If Len(a$) < 1 Then Exit Sub

  codeVal = Asc(Mid$(a$, 1, 1))

  Select Case codeVal
    Case 130
      ' ignore silently
    Case 131
      ' ignore silently
    Case 136
      ' ignore silently
    Case Else
      ' ignore silently
  End Select
End Sub

Function ReadFrame$(timeoutMs)
  Local t0
  Local b$
  Local lenLo
  Local lenHi
  Local payloadLen
  Local payload$

  t0 = Timer

  ' Find frame start byte ">"
  Do
    If Loc(#1) > 0 Then
      b$ = Input$(1, #1)
      If Asc(b$) = 62 Then Exit Do
    End If

    If Timer - t0 > timeoutMs Then
      ReadFrame$ = ""
      Exit Function
    End If
  Loop

  ' Read length low byte
  t0 = Timer
  Do While Loc(#1) < 1
    If Timer - t0 > timeoutMs Then
      ReadFrame$ = ""
      Exit Function
    End If
  Loop
  b$ = Input$(1, #1)
  lenLo = Asc(b$)

  ' Read length high byte
  t0 = Timer
  Do While Loc(#1) < 1
    If Timer - t0 > timeoutMs Then
      ReadFrame$ = ""
      Exit Function
    End If
  Loop
  b$ = Input$(1, #1)
  lenHi = Asc(b$)

  payloadLen = lenLo + 256 * lenHi

  ' Reject invalid lengths
  If payloadLen <= 0 Or payloadLen > MAX_FRAME_LEN Then
    ReadFrame$ = ""
    Exit Function
  End If

  ' Wait until full payload is available
  t0 = Timer
  Do While Loc(#1) < payloadLen
    If Timer - t0 > timeoutMs Then
      ReadFrame$ = ""
      Exit Function
    End If
  Loop

  payload$ = Input$(payloadLen, #1)
  ReadFrame$ = payload$
End Function

Sub ParseContactSilent(a$)
  Local i
  Local b
  Local pubKeyHex$
  Local typeVal
  Local name$

  If Len(a$) < 148 Then Exit Sub
  If Asc(Mid$(a$, 1, 1)) <> 3 Then Exit Sub

  pubKeyHex$ = ""
  For i = 2 To 33
    b = Asc(Mid$(a$, i, 1))
    pubKeyHex$ = pubKeyHex$ + Right$("0" + Hex$(b), 2)
  Next i

  typeVal = Asc(Mid$(a$, 34, 1))
  name$ = ReadCString$(a$, 101)

  If contactCount < MAX_CONTACTS Then
    contactCount = contactCount + 1
    contactName$(contactCount) = name$
    contactPubKey$(contactCount) = pubKeyHex$
    contactType(contactCount) = typeVal
  End If
End Sub

Sub DoGetContacts
  Local payload$
  Local frame$
  Local codeVal
  Local doneFlag
  Local expectedVal
  Local recvCount
  Local quietVal

  Print "Refreshing contacts..."
  Print

  FlushInput
  Pause 100

  contactCount = 0
  sendableCount = 0
  recvCount = 0
  expectedVal = 0
  doneFlag = 0
  quietVal = 0

  payload$ = Chr$(4)
  SendFrame payload$

  Do While doneFlag = 0
    frame$ = ReadFrame$(800)

    If frame$ = "" Then
      quietVal = quietVal + 1

      If quietVal >= 3 Then
        Print "Timeout waiting for contacts frame"
        Print "Expected contacts: "; Int(expectedVal)
        Print "Contacts loaded:   "; recvCount
        Print "Stored contacts:   "; contactCount
        Print
        Exit Do
      End If

      Pause 50

    Else
      quietVal = 0
      codeVal = Asc(Mid$(frame$, 1, 1))

      If codeVal >= 128 Then
        HandleAsyncFrame frame$

      Else
        Select Case codeVal
          Case 2
            If Len(frame$) >= 5 Then
              expectedVal = U32LEVal(frame$, 2)
              Print "Expected contacts: "; Int(expectedVal)
              Print
            End If

          Case 3
            ParseContactSilent frame$
            recvCount = recvCount + 1

          Case 4
            If Len(frame$) >= 5 Then
              gContactsSinceVal = U32LEVal(frame$, 2)
            End If

            Print "Contacts loaded:   "; recvCount
            Print "Stored contacts:   "; contactCount
            If gContactsSinceVal > 0 Then
              Print "Next since:        "; Int(gContactsSinceVal)
              Print "Next since dt:     "; UnixToDate$(Int(gContactsSinceVal))
            End If
            Print

            doneFlag = 1

          Case Else
            ' ignore unexpected non-async frames during sync
        End Select
      End If
    End If
  Loop

  BuildSendableMap
End Sub

Sub ReadRawBytes(timeoutMs)
  Local t0
  Local b$

  t0 = Timer
  Do
    If Loc(#1) > 0 Then
      b$ = Input$(1, #1)
      Print Right$("0" + Hex$(Asc(b$)), 2); " ";
      t0 = Timer
    End If
  Loop Until Timer - t0 > timeoutMs
  Print
End Sub


Sub DumpHex(a$)
  Local i, b
  For i = 1 To Len(a$)
    b = Asc(Mid$(a$, i, 1))
    Print Right$("0" + Hex$(b), 2); " ";
  Next i
  Print
End Sub


Function ReadCString$(a$, startIdx)
  Local i, s$, b
  s$ = ""
  For i = startIdx To Len(a$)
    b = Asc(Mid$(a$, i, 1))
    If b = 0 Then Exit For
    s$ = s$ + Chr$(b)
  Next i
  ReadCString$ = s$
End Function


Function ByteHex$(a$, idx)
  Local b
  b = Asc(Mid$(a$, idx, 1))
  ByteHex$ = Right$("0" + Hex$(b), 2)
End Function


Function U32LEVal(a$, idx)
  Local b0, b1, b2, b3
  Local v

  b0 = Asc(Mid$(a$, idx, 1))
  b1 = Asc(Mid$(a$, idx + 1, 1))
  b2 = Asc(Mid$(a$, idx + 2, 1))
  b3 = Asc(Mid$(a$, idx + 3, 1))

  v = b3
  v = v * 256 + b2
  v = v * 256 + b1
  v = v * 256 + b0

  U32LEVal = v
End Function


Function U32ToLE$(valueVal)
  Local b0, b1, b2, b3
  Local v

  v = Int(valueVal)

  b0 = v Mod 256
  v = Int(v / 256)

  b1 = v Mod 256
  v = Int(v / 256)

  b2 = v Mod 256
  v = Int(v / 256)

  b3 = v Mod 256

  U32ToLE$ = Chr$(b0) + Chr$(b1) + Chr$(b2) + Chr$(b3)
End Function


Function CleanNum$(v)
  Local s$
  s$ = Str$(v)

  If Len(s$) > 0 Then
    If Asc(Mid$(s$, 1, 1)) = 32 Then
      CleanNum$ = Mid$(s$, 2)
    Else
      CleanNum$ = s$
    End If
  Else
    CleanNum$ = ""
  End If
End Function


Function Pad2$(v)
  Local s$
  s$ = CleanNum$(v)

  If Len(s$) < 2 Then
    Pad2$ = "0" + s$
  Else
    Pad2$ = s$
  End If
End Function


Function Pad4$(v)
  Local s$
  s$ = CleanNum$(v)

  If Len(s$) = 1 Then
    Pad4$ = "000" + s$
  ElseIf Len(s$) = 2 Then
    Pad4$ = "00" + s$
  ElseIf Len(s$) = 3 Then
    Pad4$ = "0" + s$
  Else
    Pad4$ = s$
  End If
End Function

Function Pad3$(v)
  Local s$
  s$ = CleanNum$(v)

  If Len(s$) = 1 Then
    Pad3$ = "  " + s$
  ElseIf Len(s$) = 2 Then
    Pad3$ = " " + s$
  Else
    Pad3$ = s$
  End If
End Function


Function DateTimeToUnix(dateStr$, timeStr$)
  Local dayVal, monthVal, yearVal
  Local hourVal, minVal, secVal
  Local daysVal, y, leapVal
  Local mLen(12)
  Local i

  dayVal = Val(Mid$(dateStr$, 1, 2))
  monthVal = Val(Mid$(dateStr$, 4, 2))
  yearVal = Val(Mid$(dateStr$, 7, 4))

  hourVal = Val(Mid$(timeStr$, 1, 2))
  minVal = Val(Mid$(timeStr$, 4, 2))
  secVal = Val(Mid$(timeStr$, 7, 2))

  daysVal = 0

  For y = 1970 To yearVal - 1
    leapVal = 0
    If (y Mod 4 = 0 And y Mod 100 <> 0) Or (y Mod 400 = 0) Then leapVal = 1
    If leapVal Then
      daysVal = daysVal + 366
    Else
      daysVal = daysVal + 365
    End If
  Next y

  mLen(1) = 31
  mLen(2) = 28
  mLen(3) = 31
  mLen(4) = 30
  mLen(5) = 31
  mLen(6) = 30
  mLen(7) = 31
  mLen(8) = 31
  mLen(9) = 30
  mLen(10) = 31
  mLen(11) = 30
  mLen(12) = 31

  leapVal = 0
  If (yearVal Mod 4 = 0 And yearVal Mod 100 <> 0) Or (yearVal Mod 400 = 0) Then leapVal = 1
  If leapVal Then mLen(2) = 29

  For i = 1 To monthVal - 1
    daysVal = daysVal + mLen(i)
  Next i

  daysVal = daysVal + (dayVal - 1)

  DateTimeToUnix = daysVal * 86400 + hourVal * 3600 + minVal * 60 + secVal
End Function


Function UnixToDate$(t)
  Local secondsVal, minutesVal, hoursVal, daysVal
  Local yearVal, monthVal, dayVal
  Local leapVal
  Local mLen(12)
  Local d$, tm$

  secondsVal = t Mod 60
  t = Int(t / 60)

  minutesVal = t Mod 60
  t = Int(t / 60)

  hoursVal = t Mod 24
  daysVal = Int(t / 24)

  yearVal = 1970

  Do
    leapVal = 0
    If (yearVal Mod 4 = 0 And yearVal Mod 100 <> 0) Or (yearVal Mod 400 = 0) Then leapVal = 1

    If leapVal Then
      If daysVal < 366 Then Exit Do
      daysVal = daysVal - 366
    Else
      If daysVal < 365 Then Exit Do
      daysVal = daysVal - 365
    End If

    yearVal = yearVal + 1
  Loop

  mLen(1) = 31
  mLen(2) = 28
  mLen(3) = 31
  mLen(4) = 30
  mLen(5) = 31
  mLen(6) = 30
  mLen(7) = 31
  mLen(8) = 31
  mLen(9) = 30
  mLen(10) = 31
  mLen(11) = 30
  mLen(12) = 31

  If leapVal Then mLen(2) = 29

  monthVal = 1
  Do While daysVal >= mLen(monthVal)
    daysVal = daysVal - mLen(monthVal)
    monthVal = monthVal + 1
  Loop

  dayVal = daysVal + 1

  d$ = Pad4$(yearVal) + "-" + Pad2$(monthVal) + "-" + Pad2$(dayVal)
  tm$ = Pad2$(hoursVal) + ":" + Pad2$(minutesVal) + ":" + Pad2$(secondsVal)

  UnixToDate$ = d$ + " " + tm$
End Function


Sub ParseDeviceInfo(a$)
  Local codeVal
  Local rawInfo$
  Local buildDate$, boardName$, fwVersion$
  Local i, b

  If Len(a$) < 9 Then
    Print "DEVICE_INFO too short"
    Exit Sub
  End If

  codeVal = Asc(Mid$(a$, 1, 1))
  If codeVal <> 13 Then
    Print "Not DEVICE_INFO, code="; codeVal
    Exit Sub
  End If

  rawInfo$ = ""
  For i = 2 To 8
    b = Asc(Mid$(a$, i, 1))
    rawInfo$ = rawInfo$ + Right$("0" + Hex$(b), 2)
    If i < 8 Then rawInfo$ = rawInfo$ + " "
  Next i

  buildDate$ = ReadCString$(a$, 9)
  boardName$ = ReadCString$(a$, 21)
  fwVersion$ = ReadCString$(a$, 61)

  gDeviceCode = codeVal
  gDeviceRawInfo$ = rawInfo$
  gBuildDate$ = buildDate$
  gBoardName$ = boardName$
  gFwVersion$ = fwVersion$

  Print
  Print "=== DEVICE INFO ==="
  Print "Code:        "; gDeviceCode
  Print "Raw info:    "; gDeviceRawInfo$
  Print "Build date:  "; gBuildDate$
  Print "Board:       "; gBoardName$
  Print "FW version:  "; gFwVersion$
End Sub


Sub ParseSelfInfo(a$)
  Local codeVal, typeVal, txPowerVal, maxTxPowerVal
  Local freqVal, bwVal, sfVal, crVal
  Local name$

  If Len(a$) < 59 Then
    Print "SELF_INFO too short"
    Exit Sub
  End If

  codeVal = Asc(Mid$(a$, 1, 1))
  If codeVal <> 5 Then
    Print "Not SELF_INFO, code="; codeVal
    Exit Sub
  End If

  typeVal = Asc(Mid$(a$, 2, 1))
  txPowerVal = Asc(Mid$(a$, 3, 1))
  maxTxPowerVal = Asc(Mid$(a$, 4, 1))

  freqVal = U32LEVal(a$, 49)
  bwVal   = U32LEVal(a$, 53)
  sfVal   = Asc(Mid$(a$, 57, 1))
  crVal   = Asc(Mid$(a$, 58, 1))
  name$   = ReadCString$(a$, 59)

  gSelfCode = codeVal
  gTypeVal = typeVal
  gTxPowerVal = txPowerVal
  gMaxTxPowerVal = maxTxPowerVal
  gFreqVal = freqVal
  gBwVal = bwVal
  gSfVal = sfVal
  gCrVal = crVal
  gNodeName$ = name$

  Print
  Print "=== SELF INFO ==="
  Print "Type:        "; gTypeVal
  Print "TX power:    "; gTxPowerVal; " dBm"
  Print "Max TX:      "; gMaxTxPowerVal; " dBm"
  Print "Freq MHz:    "; gFreqVal / 1000
  Print "BW kHz:      "; gBwVal / 1000
  Print "SF:          "; gSfVal
  Print "CR:          "; gCrVal
  Print "Name:        "; gNodeName$
End Sub

Sub BuildSendableMap
  Local i

  sendableCount = 0

  For i = 1 To contactCount
    If contactType(i) <> 2 Then
      sendableCount = sendableCount + 1
      sendableMap(sendableCount) = i
    End If
  Next i
End Sub

Sub ShowSendableContacts
  Local i
  Local realIdx

  BuildSendableMap

  Print "Sendable contacts"
  Print "-----------------"

  If sendableCount = 0 Then
    Print "No sendable contacts"
    Print
    Exit Sub
  End If

  For i = 1 To sendableCount
    realIdx = sendableMap(i)
    Print i; " - "; contactName$(realIdx)
  Next i

  Print
End Sub

Function GetSendableContactIndex(selVal)
  BuildSendableMap

  If selVal < 1 Or selVal > sendableCount Then
    GetSendableContactIndex = 0
  Else
    GetSendableContactIndex = sendableMap(selVal)
  End If
End Function

Function FindContactName$(pubKeyHex$)
  Local i

  For i = 1 To contactCount
    If Mid$(contactPubKey$(i), 1, Len(pubKeyHex$)) = pubKeyHex$ Then
      FindContactName$ = contactName$(i)
      Exit Function
    End If
  Next i

  FindContactName$ = "(unknown)"
End Function

Function PubKeyPrefix6$(pubKeyHex$)
  Local i
  Local out1$

  out1$ = ""

  For i = 1 To 12 Step 2
    out1$ = out1$ + Chr$(Val("&H" + Mid$(pubKeyHex$, i, 2)))
  Next i

  PubKeyPrefix6$ = out1$
End Function

Sub ShowContactsList
  Local i
  Local linesShown
  Local wait1$
  Local mark$

  If contactCount = 0 Then
    Print "No contacts loaded"
    Print
    Exit Sub
  End If

  Print "Contacts"
  Print "--------"

  linesShown = 0

  For i = 1 To contactCount
    If contactType(i) = 2 Then
      mark$ = "R"
    Else
      mark$ = " "
    End If

    Print Right$("   " + Str$(i), 3); " "; mark$; " "; contactName$(i)

    linesShown = linesShown + 1

    If linesShown >= 20 And i < contactCount Then
      Print
      Line Input "Press Enter for more...", wait1$
      Print
      linesShown = 0
    End If
  Next i

  Print
End Sub

Sub DoSendMessage
  Local idxVal
  Local idxStr$
  Local msgText$
  Local payload$
  Local frame$
  Local codeVal
  Local prefix$
  Local epochVal
  Local txtTypeVal
  Local attemptVal
  Local doneFlag
  Local queuedOk
  Local deliveredOk

  EnsureContactsLoaded

  If contactCount = 0 Then
    Print "No contacts available"
    Print
    Exit Sub
  End If

  ShowSendableContacts

  Line Input "Contact number: ", idxStr$
  Print

  idxVal = GetSendableContactIndex(Val(idxStr$))

  If idxVal = 0 Then
    Print "Invalid contact number"
    Print
    Exit Sub
  End If

  Line Input "Message text: ", msgText$
  Print

  If msgText$ = "" Then
    Print "Empty message not sent"
    Print
    Exit Sub
  End If

  prefix$ = PubKeyPrefix6$(contactPubKey$(idxVal))
  epochVal = Int(DateTimeToUnix(Date$, Time$))

  txtTypeVal = 0
  attemptVal = 0

  payload$ = ""
  payload$ = payload$ + Chr$(2)
  payload$ = payload$ + Chr$(txtTypeVal)
  payload$ = payload$ + Chr$(attemptVal)
  payload$ = payload$ + U32ToLE$(epochVal)
  payload$ = payload$ + prefix$
  payload$ = payload$ + msgText$

  Print "Sending to:    "; contactName$(idxVal)
  Print "Time:          "; UnixToDate$(epochVal)

  SendFrame payload$

  doneFlag = 0
  queuedOk = 0
  deliveredOk = 0

  Do While doneFlag = 0
    frame$ = ReadFrame$(FRAME_TIMEOUT)

    If frame$ = "" Then
      Print "No send response"
      Print
      Exit Sub
    End If

    codeVal = Asc(Mid$(frame$, 1, 1))

    If codeVal >= 128 Then
      HandleAsyncFrame frame$

    ElseIf codeVal = 0 Then
      Print "Send OK"
      DumpHex frame$
      queuedOk = 1
      doneFlag = 1

    ElseIf codeVal = 1 Then
      Print "Send FAILED"
      DumpHex frame$
      Print
      Exit Sub

    ElseIf codeVal = 6 Then
      Print "Send queued OK"
      DumpHex frame$
      queuedOk = 1
      doneFlag = 1

    Else
      Print "Unexpected send response: "; codeVal
      DumpHex frame$
      Print
      Exit Sub
    End If
  Loop

  If queuedOk = 1 Then
    deliveredOk = WaitForSendConfirmation(2000)

    If deliveredOk = 0 Then
      Print "Queued, no delivery confirmation yet"
      Print
    End If
  End If
End Sub

Function WaitForSendConfirmation(timeoutMs)
  Local frame$
  Local codeVal
  Local t0

  t0 = Timer

  Do While Timer - t0 < timeoutMs
    frame$ = ReadFrame$(300)

    If frame$ <> "" Then
      codeVal = Asc(Mid$(frame$, 1, 1))

      If codeVal = 130 Then
        Print "Delivered"
        DumpHex frame$
        WaitForSendConfirmation = 1
        Exit Function

      ElseIf codeVal >= 128 Then
        HandleAsyncFrame frame$

      Else
        Print "Extra non-async frame during send confirm wait:"
        DumpHex frame$
      End If
    End If
  Loop

  WaitForSendConfirmation = 0
End Function
