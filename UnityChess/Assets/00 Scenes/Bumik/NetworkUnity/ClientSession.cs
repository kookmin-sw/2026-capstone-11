using System;
using System.Collections.Generic;
using System.Text;
using Game.Network;
using PlayFab.ProfilesModels;
using Unity.VisualScripting;
using UnityEngine;

public class ClientSession : INetEventHandler
{
    public int HandlerId => NetEventHandlerId.Constant.GameMessage;

    private long ConnectionExpireTimeMs = 9999;

    private string _name = "1";


    private ConnId _host = ConnId.Default();
    private SessionEvents _events = new();
    public SessionEvents Events => _events;

    public ClientSession()
    {
        NetworkManagerUnity.Instance.Net.SetControlHandler(this);
        NetworkManagerUnity.Instance.Net.SetReceiveHandler(this);
    }

    public void SetName(string name) {if (String.IsNullOrEmpty(name)) _name = name;}

    public void StartSession(string ipAddr, int portNum)
    {
        _ = NetworkManagerUnity.Instance.Net.ConnectTo(ipAddr, portNum, ConnectionExpireTimeMs);
    }

    public void OnReceive(ConnId connId, byte[] raw)
    {
        _events.OnMessageReceive?.Invoke(raw);
    }

    public void Answer(int queryNum, byte[] raw)
    {
        NetworkManagerUnity.Instance.Net.Send(NetEventHandlerId.Constant.GameMessage, queryNum, _host, raw);
    }

    public void OnQuery(ConnId connId, int queryNum, byte[] raw)
    {
        _events.OnGetQuery?.Invoke(queryNum, raw);
    }
    public void OnException(ConnId connId, byte[] raw, string msg)
    {
        if (_host == ConnId.Default()) return;
        _host = ConnId.Default();
        _events.OnDisconnectUnsafe?.Invoke();
    }

    public void OnHello(ConnId connId, byte[] raw)
    {
        _host = connId;
        NetworkManagerUnity.Instance.Net.Send(NetEventHandlerId.Constant.PeerEntrance, 0, connId, Encoding.UTF8.GetBytes(_name));
        _events.OnConnectHello?.Invoke();

    }

    public void OnDisconnect(ConnId connId, byte[] raw)
    {
        if (_host == ConnId.Default()) return;
        _host = ConnId.Default();
        _events.OnDisconnectUnsafe?.Invoke();
    }

}
