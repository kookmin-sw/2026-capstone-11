using System;
using System.Net;
using Game.Network;
using Game.Network.Protocol;
using PlayFab;
using TMPro;
using Unity.VisualScripting;
using UnityEngine;
using UnityEngine.SceneManagement;

public class ModeSelectionSceneMain : MonoBehaviour
{
    [SerializeField] private TMP_InputField IPaddrInputField;
    [SerializeField] private TMP_InputField PortNumInputField;
    [SerializeField] private NetworkManagerUnity networkManager;



    public void OnClickStartDedicateMode()
    {
        string IPAddrInput = IPaddrInputField.text;
        string portNumInput = PortNumInputField.text;

        if (!IPAddress.TryParse(IPAddrInput, out var ipAddr))
        {
            Debug.Log("Wrong IPAddress Input!");
            return;
        }

        if (!int.TryParse(portNumInput, out var portNum) || portNum < 0)
        {
            Debug.Log("Wrong PortNum Input!");
            return;
        }

        if (!PlayFabAccountManager.Instance.IsLoggedIn)
        {
            Debug.Log("Need Playfab LogIn First");
            return;
        }


        ConnectionInfo selfInfo = new ConnectionInfo(
            netType: NetworkType.Dedicated, 
            connType: ConnectionType.Client, 
            seesion_id: 0, 
            account_id: 0, 
            account_name: PlayFabAccountManager.Instance.InGameDisplayName, 
            app_version: "DevelopVersion", 
            Token: PlayFabAccountManager.Instance.SessionTicket
        );

        ServiceOption option = new ServiceOption(
            MaxConnPerService: 2,
            HelloTimeOutMs: 10000,
            PingIntervalMs: 5000,
            PingTimeOutMs: 4500,
            PingFailCountToDisconnect: 3       
            );

        BypassAuthenticator auth = new();


        networkManager.Init(selfInfo, option, auth);
        _ = networkManager.Net.ConnectTo(ipAddr.ToString(), portNum, 20000);
        DontDestroyOnLoad(networkManager);
        SceneManager.LoadScene("NetworkTestScene");
    }
}
