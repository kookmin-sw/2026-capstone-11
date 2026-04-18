using System;
using UnityEngine;

public class SessionEvents
{
    public Action? OnConnectHello = null;
    public Action? OnDisconnectUnsafe = null;
    public Action<byte[]>? OnMessageReceive = null;
    public Action<int, byte[]>? OnGetQuery = null;
    

}
