using System.Threading.Tasks;
using Game.Network.Protocol;
using Game.Server;
using PlayFab.EconomyModels;
using UnityEngine;

public class NetworkTestSceneMain : MonoBehaviour
{
    public string IPAddr;
    public int portNum;

    private SessionHandler sessionh;
    async Task Start()
    {
        var manager = FindAnyObjectByType<NetworkManagerUnity>();
        manager.Init();

        var info = new ConnectionInfo(
            NetworkType.Dedicated,
            ConnectionType.Client,
            1,
            333,
            "TestClient:333",
            "Develop-0.0.0",
            "Dummy"
        );


        sessionh = new SessionHandler(NetworkManagerUnity.Instance.Net, info, 2, 5000);
        NetworkManagerUnity.Instance.Net.SetReceiveHandler(SessionHandler.Id, sessionh);
        NetworkManagerUnity.Instance.Net.SetControlHandler(sessionh);

        await NetworkManagerUnity.Instance.Net.ConnectTo(IPAddr, portNum, 10000);
    }

    // Update is called once per frame
    void Update()
    {
        sessionh.Tick((int)(Time.deltaTime * 1000));
    }
}
