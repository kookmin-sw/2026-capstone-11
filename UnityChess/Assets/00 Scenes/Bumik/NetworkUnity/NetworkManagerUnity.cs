using System.Collections;
using System.Collections.Generic;
using System.Threading.Tasks;
using Game.Network;
using Game.Network.Protocol;
using Game.Server;
using UnityEngine;
using UnityEngine.Rendering.Universal;

public class NetworkManagerUnity : MonoBehaviour
{
    public static NetworkManagerUnity Instance;
    public INetAPI Net => _network;
    public ServiceContext Context => _context;
    public ServiceHandler Service => _service;
    public PingModule PingPong => _pingPong;
    public bool IsNetworkRunning => _IsNetworkRunning;
    public string GetState() => _network.GetNetState() 
                                + "\n" + _context.GetState();


    private ServiceContext _context;
    private NetworkManager _network;
    private IAuthenticator _authenticator;
    private ServiceHandler _service;
    private PingModule _pingPong;
    

    private bool _IsNetworkRunning;
    private Coroutine NetTickCoroutine;

    public void Init(ConnectionInfo selfInfo, ServiceOption option, IAuthenticator authenticator)
    {        
        if (Instance != null)
        {
            Destroy(gameObject);
            return;
        } 
        else Instance = this;

        Game.Network.Log.SetLogger(Debug.Log);

        _network = NetworkManager.CreateNetworkManager(0, 10);
        _network.Start();

        _authenticator = authenticator;
        _context = new ServiceContext(selfInfo, option);
        _service = new ServiceHandler(_network, _authenticator, _context);
        _pingPong = new PingModule(_network, _context);

        _network.SetControlHandler(_service);
        _network.SetReceiveHandler(ServiceHandler.Id, _service);
        _network.SetReceiveHandler(_pingPong.HandlerId, _pingPong);
        
        _IsNetworkRunning = true;
        NetTickCoroutine = StartCoroutine(TickCoroutine());
    }

    // Update is called once per frame
    private IEnumerator TickCoroutine()
    {
        while (_IsNetworkRunning)
        { 
            _network.Tick();
            _pingPong.Tick((int)(Time.deltaTime * 1000));
            yield return null;
        }
    }


    public async Task OnDestroy()
    {
        await _network.StopAsync();
    }

}
