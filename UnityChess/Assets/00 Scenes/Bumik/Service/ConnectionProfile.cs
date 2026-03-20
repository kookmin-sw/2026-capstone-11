using Game.Network.Protocol;
using UnityEngine;

public class ConnectionProfile : MonoBehaviour
{
    [Header("Initialize Profile")]
    public NetworkType networkType;
    public ConnectionType connectionType;
    public int sessionId;
    public int accountId;
    public string accountName;
    public string appVersion;
    public string token;

    private ConnectionInfo _info;
    public ConnectionInfo Info => _info;

    void Init()
    {
        if (accountName == null) accountName = "Empty";
        if (appVersion == null) appVersion = "Empty";
        if (token == null) token = "Empty";

        _info = new ConnectionInfo(
            networkType,
            connectionType,
            sessionId,
            accountId,
            accountName,
            appVersion,
            token
        );
    }
}
