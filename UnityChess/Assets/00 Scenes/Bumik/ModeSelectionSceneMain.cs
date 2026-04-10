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
    [SerializeField] private GameInitializer gameInitializer;

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

        gameInitializer.Data.PlayerName = PlayFabAccountManager.Instance.InGameDisplayName;
        gameInitializer.Data.IpAddr = ipAddr.ToString();
        gameInitializer.Data.PortNum = portNum;
        
        DontDestroyOnLoad(gameInitializer);
        SceneManager.LoadScene("NetworkTestScene");
    }
}
