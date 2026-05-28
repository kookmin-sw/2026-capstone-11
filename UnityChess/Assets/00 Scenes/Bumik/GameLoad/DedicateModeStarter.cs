using System;
using System.Collections;
using System.Collections.Generic;
using System.Net;
using System.Text;
using core.data;
using Game.Network;
using Game.Network.Protocol;
using Game.Network.Service;
using PlayFab;
using PlayFab.ClientModels;
using TMPro;
using Unity.VisualScripting;
using UnityEngine;
using UnityEngine.Purchasing;
using UnityEngine.SceneManagement;


public class DedicateModeStarter : MonoBehaviour
{
    [Header("Ref to UI Input")]
    [SerializeField] private TMP_InputField IPaddrInputField;
    [SerializeField] private TMP_InputField PortNumInputField;
    [SerializeField] private TMP_InputField DeckInputField;

    [Header("Connectino Opt")]
    [SerializeField] private float gameLoadTimeoutSec;
    [SerializeField] private int connectionTimeOutMs;

    [Header("Game Scene Load")]
    [SerializeField] private string gameSceneName;

    [Header("Fast Start Test")]
    [SerializeField] private string ip;
    [SerializeField] private string port;
    [SerializeField] private string deck;
    [SerializeField] private List<DeckDB> decks;

    private Coroutine _gameLoadCoroutine;
    private Coroutine _gameLoadTimeoutCoroutine;

    public void OnClickStartDedicateMode()
    {
        string hostInput = IPaddrInputField.text.Trim();
        string portNumInput = PortNumInputField.text.Trim();
        string deckInput = DeckInputField.text.Trim();

        if (!IsValidHost(hostInput))
        {
            Debug.Log("Wrong IPAddress / Host Input!");
            return;
        }

        if (!TryParsePort(portNumInput, out int portNum))
        {
            Debug.Log("Wrong PortNum Input!");
            return;
        }

        StartDedicateMode(hostInput, portNum, deckInput);
    }

    /// <summary>
    /// PlayFab MPS 매칭 성공 후 호출하는 진입점.
    /// UI의 IP/Port 입력값을 쓰지 않고, MPS에서 받은 주소와 포트를 사용한다.
    /// </summary>
    public void StartDedicateModeFromMatchmaking(string serverAddress, int serverPort)
    {
        if (string.IsNullOrWhiteSpace(serverAddress))
        {
            Debug.LogError("MPS ServerAddress is empty.");
            return;
        }

        if (serverPort <= 0 || serverPort > 65535)
        {
            Debug.LogError($"Wrong MPS ServerPort: {serverPort}");
            return;
        }

        // string deckInput = DeckInputField != null ? DeckInputField.text.Trim() : string.Empty;
        
        deck = decks[PlayerPrefs.GetInt("SelectedDeckIndex", 0)].deckId;

        StartDedicateMode(serverAddress, serverPort, deck);
    }

    private void StartDedicateMode(string hostAddress, int portNum, string deckInput)
    {
        StopGameLoad();

        SetupPlayerName();
        SetupPlayerDeck(deckInput);

        GameInitParam.Instance.IpAddr = hostAddress;
        GameInitParam.Instance.PortNum = portNum;

        Debug.Log($"Start Dedicated Mode. Address={hostAddress}, Port={portNum}");

        NetworkManagerUnity.Instance.Init();

        _gameLoadCoroutine = StartCoroutine(GameLoadCoroutine());
        _gameLoadTimeoutCoroutine = StartCoroutine(GameLoadTimeoutCoroutine());
    }

    private void SetupPlayerName()
    {
        if (!PlayFabAccountManager.Instance.IsLoggedIn)
        {
            Debug.Log("No Playfab LogIn.");
            string pcID = SystemInfo.deviceUniqueIdentifier;
            GameInitParam.Instance.Player1Name = "Jimmy, The Mind of PlaceHolder" + pcID;
        }
        else
        {
            GameInitParam.Instance.Player1Name = PlayFabAccountManager.Instance.InGameDisplayName;
        }
    }

    private void SetupPlayerDeck(string deckInput) {
        GameInitParam.Instance.Player1Deck = deckInput switch
        {
            "Or" => "[\"Or_L\", \"Or_B\", \"Or_R\", \"Or_N\", \"Or_P\", \"Or_P\", \"Or_P\"]",
            "Me" => "[\"Me_L\", \"Me_B\", \"Me_R\", \"Me_N\", \"Me_P\", \"Me_P\", \"Me_P\"]",
            "Tr" => "[\"Tr_L\", \"Tr_B\", \"Tr_R\", \"Tr_N\", \"Tr_P\", \"Tr_P\", \"Tr_P\"]",
            _ => "[\"Cl_L\", \"Cl_B\", \"Cl_R\", \"Cl_N\", \"Cl_P\", \"Cl_P\", \"Cl_P\"]",
        };
    }

    private bool IsValidHost(string host)
    {
        if (string.IsNullOrWhiteSpace(host))
            return false;

        // IP 직접 입력 허용
        if (IPAddress.TryParse(host, out _))
            return true;

        // PlayFab MPS GetMatch 결과는 Fqdn이 올 수 있으므로 도메인도 허용
        return Uri.CheckHostName(host) == UriHostNameType.Dns;
    }

    private bool TryParsePort(string portText, out int port)
    {
        if (!int.TryParse(portText, out port))
            return false;

        return port > 0 && port <= 65535;
    }

    private void StopGameLoad()
    {
        if (_gameLoadCoroutine != null)
        {
            StopCoroutine(_gameLoadCoroutine);
            _gameLoadCoroutine = null;
        }

        if (_gameLoadTimeoutCoroutine != null)
        {
            StopCoroutine(_gameLoadTimeoutCoroutine);
            _gameLoadTimeoutCoroutine = null;
        }
    }

    private IEnumerator GameLoadTimeoutCoroutine()
    {
        yield return new WaitForSecondsRealtime(gameLoadTimeoutSec);

        Debug.Log("GameLoad Timeout: 30초 초과로 로딩 중단");
        StopGameLoad();
    }

    private IEnumerator GameLoadCoroutine()
    {
        yield return ConnectCoroutine();
        yield return SessionEnterCoroutine();

        if (_gameLoadTimeoutCoroutine != null)
        {
            StopCoroutine(_gameLoadTimeoutCoroutine);
            _gameLoadTimeoutCoroutine = null;
        }

        DontDestroyOnLoad(GameInitParam.Instance);
        DontDestroyOnLoad(NetworkManagerUnity.Instance);

        SceneManager.LoadScene(gameSceneName);

        _gameLoadCoroutine = null;
    }

    private IEnumerator ConnectCoroutine()
    {
        var wait = new WaitForCallback();

        NetworkManagerUnity.Instance.Session.Events.OnConnectHello = wait.Complete;

        _ = NetworkManagerUnity.Instance.Net.ConnectTo(
            GameInitParam.Instance.IpAddr,
            GameInitParam.Instance.PortNum,
            connectionTimeOutMs
        );

        yield return wait;

        NetworkManagerUnity.Instance.Session.Events.OnConnectHello = null;
    }

    private IEnumerator SessionEnterCoroutine()
    {
        var wait = new WaitForCallback();

        NetworkManagerUnity.Instance.Session.EnterSession(
            GameInitParam.Instance.Player1Name,
            raw =>
            {
                wait.Complete();
            },
            msg =>
            {
                Debug.Log(msg);
            }
        );

        yield return wait;

        // 서버 틱 맞추기 위해 대기
        yield return new WaitForSecondsRealtime(1.0f);

        var waitQuery = new WaitForCallback();

        var req = new SimpleReq(GameInitParam.Instance.Player1Deck);

        byte[] buffer = new byte[SimpleReq.Codec.GetSize(req)];
        PacketWriter writer = new(buffer);
        SimpleReq.Codec.Write(ref writer, req);

        NetworkManagerUnity.Instance.Session.QueryDataRegister(
            buffer,
            5000,
            result =>
            {
                if (result.IsResponded)
                {
                    PacketReader reader = new(result.AnswerRaw);
                    var rsp = SimpleRsp.Codec.Read(ref reader);

                    if (rsp.IsAccepted)
                    {
                        waitQuery.Complete();
                    }
                    else
                    {
                        Debug.Log(rsp.Msg);
                        StopGameLoad();
                    }

                    return;
                }

                Debug.Log("SessionEnter Req. is Expired");
                StopGameLoad();
            }
        );

        yield return waitQuery;
        yield return new WaitForSecondsRealtime(1.0f);
    }
    
    /*  =================== for test ===================== */
    
    public void OnClickStartDedicateFast()
    {
        if (!IPAddress.TryParse(ip, out var ipAddr))
        {
            Debug.Log("Wrong IPAddress Input!");
            return;
        }

        if (!int.TryParse(port, out var portNum) || portNum < 0)
        {
            Debug.Log("Wrong PortNum Input!");
            return;
        }

        if (!PlayFabAccountManager.Instance.IsLoggedIn)
        {
            Debug.Log("No Playfab LogIn.");
            string pcID = SystemInfo.deviceUniqueIdentifier;
            GameInitParam.Instance.Player1Name = "Jimmy, The Mind of PlaceHolder" + pcID;
        }
        else GameInitParam.Instance.Player1Name = PlayFabAccountManager.Instance.InGameDisplayName;

        deck = decks[PlayerPrefs.GetInt("SelectedDeckIndex", 0)].deckId;

        SetupPlayerDeck(deck);

        GameInitParam.Instance.IpAddr = ipAddr.ToString();
        GameInitParam.Instance.PortNum = portNum;

        NetworkManagerUnity.Instance.Init();

        _gameLoadCoroutine = StartCoroutine(GameLoadCoroutine());
        _gameLoadTimeoutCoroutine = StartCoroutine(GameLoadTimeoutCoroutine());
    }

    public void SetDeck(string deckId)
    {
        deck = deckId;
    }
}



