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



    private ConnId _host = ConnId.Default();
    private SessionEvents _events = new();
    public SessionEvents Events => _events;

    public ClientSession()
    {
        NetworkManagerUnity.Instance.Net.SetControlHandler(this);
        NetworkManagerUnity.Instance.Net.SetReceiveHandler(this);
    }


    public void EnterSession(string name, Action<byte[]> succ, Action<string> fail)
    {
        _ = NetworkManagerUnity.Instance.Net.AsyncRequestQuery(
            NetEventHandlerId.Constant.PeerEntrance,
            _host,
            Encoding.UTF8.GetBytes(name),
            10000,
            (connId, result) => { if (result.IsResponded) succ.Invoke(result.AnswerRaw); else fail.Invoke("failed"); }
            );
    }

    public void Query(byte[] raw, long expireMs, Action<QueryTaskResult> callback)
    {
        _ = NetworkManagerUnity.Instance.Net.AsyncRequestQuery(
            NetEventHandlerId.Constant.GameMessage,
            _host,
            raw, 
            expireMs,
            (connId, result) => { callback.Invoke(result); }
            );
    }
    public void QueryDataRegister(byte[] raw, long expireMs, Action<QueryTaskResult> callback)
    {
        _ = NetworkManagerUnity.Instance.Net.AsyncRequestQuery(
            NetEventHandlerId.Constant.GameDataRegister,
            _host,
            raw, 
            expireMs,
            (connId, result) => { callback.Invoke(result); }
            );
    }
    public void QueryReady(byte[] raw, long expireMs, Action<QueryTaskResult> callback)
    {
        _ = NetworkManagerUnity.Instance.Net.AsyncRequestQuery(
            NetEventHandlerId.Constant.GameReady,
            _host,
            raw, 
            expireMs,
            (connId, result) => { callback.Invoke(result); }
            );
    }

    public void Answer(int queryNum, byte[] raw)
    {
        NetworkManagerUnity.Instance.Net.Send(NetEventHandlerId.Constant.GameMessage, queryNum, _host, raw);
    }

    public void Send(int queryNum, byte[] raw)
    {
        NetworkManagerUnity.Instance.Net.Send(NetEventHandlerId.Constant.GameMessage, 0, _host, raw);
    }

    public void OnReceive(ConnId connId, byte[] raw)
    {
        _events.OnMessageReceive?.Invoke(raw);
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
        _events.OnConnectHello?.Invoke();

    }

    public void OnDisconnect(ConnId connId, byte[] raw)
    {
        if (_host == ConnId.Default()) return;
        _host = ConnId.Default();
        _events.OnDisconnectUnsafe?.Invoke();
    }

}
