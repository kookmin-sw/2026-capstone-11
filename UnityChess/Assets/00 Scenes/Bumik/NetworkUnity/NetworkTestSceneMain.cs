using System.Threading.Tasks;
using UnityEngine;

public class NetworkTestSceneMain : MonoBehaviour
{
    async Task Start()
    {
        var manager = FindAnyObjectByType<NetworkManagerUnity>();
        manager.Init();

        await NetworkManagerUnity.Instance.Net.ConnectTo("127.0.0.1", 9000, 10000);
    }

    // Update is called once per frame
    void Update()
    {
        
    }
}
