using System.Collections;
using System.Collections.Generic;
using System.Threading.Tasks;
using Game.Network;
using UnityEngine;
using UnityEngine.Rendering.Universal;

public class NetworkManagerUnity : MonoBehaviour
{
    public static NetworkManagerUnity Instance;
    public INetAPI Net => _network;
    public bool IsNetworkRunning => _IsNetworkRunning;
    public string GetState() => _network.GetNetState();


    
    
    private NetworkManager _network;
    private bool _IsNetworkRunning;
    private Coroutine NetTickCoroutine;

    public void Init()
    {
        Game.Network.Log.SetLogger(Debug.Log);
        
        if (Instance != null)
        {
            Destroy(gameObject);
        } 
        else Instance = this;

        _network = NetworkManager.CreateNetworkManager(0, 10);

        _network.Start();
        _IsNetworkRunning = true;
        NetTickCoroutine = StartCoroutine(TickCoroutine());
    }

    // Update is called once per frame
    private IEnumerator TickCoroutine()
    {
        while (_IsNetworkRunning)
        { 
            _network.Tick();
            yield return null;
        }
    }


    public async Task OnDestroy()
    {
        await _network.StopAsync();
    }

}
