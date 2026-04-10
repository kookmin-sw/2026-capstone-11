using System;
using System.Collections.Generic;
using System.Text;
using Game.Network;
using Unity.VisualScripting;
using UnityEngine;

public class Session : MonoBehaviour, INetEventHandler
{
    public int HandlerId => NetEventHandlerId.Constant.GameMessage;

    [SerializeField] private long ConnectionExpireTimeMs;
    
    private string _name;
    private string _ipAddr;
    private int _portNum;

    private ConnId _host = ConnId.Default();
    private SessionEvents _events = new();
    public SessionEvents Events => _events;

    public void Init(string ipAddr, int portNum, string name)
    {
        _ipAddr = ipAddr;
        _portNum = portNum;
        _name = name;
        NetworkManagerUnity.Instance.Net.SetControlHandler(this);
    }

    public void StartSession()
    {
        _ = NetworkManagerUnity.Instance.Net.ConnectTo(_ipAddr, _portNum, ConnectionExpireTimeMs);
    }

    public void OnReceive(ConnId connId, byte[] raw)
    {
        _events.OnMessageReceive?.Invoke(raw);
    }

    public void Answer(int queryNum, byte[] raw)
    {
        NetworkManagerUnity.Instance.Net.Send(NetEventHandlerId.Constant.GameMessage,  queryNum, _host, raw);
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