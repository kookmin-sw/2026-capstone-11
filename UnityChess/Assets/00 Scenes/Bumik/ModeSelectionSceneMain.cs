using System;
using System.Collections;
using System.Net;
using System.Text;
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

public class WaitForCallback : CustomYieldInstruction
{
    bool _done = false;
    public override bool keepWaiting => !_done;
    public void Complete() => _done = true;
}


public class ModeSelectionSceneMain : MonoBehaviour
{


    [Header("Ref to UI Input")]
    [SerializeField] private TMP_InputField IPaddrInputField;
    [SerializeField] private TMP_InputField PortNumInputField;
    [SerializeField] private TMP_InputField DeckInputField;

    [Header("Game Scene Load")]
    [SerializeField] private NetworkManagerUnity netManager;
    [SerializeField] private GameInitParam InitParam;
    [SerializeField] private string gameSceneName;

    private Coroutine _gameLoadCoroutine;
    private Coroutine _gameLoadTimeoutCoroutine;

    public void OnClickStartDedicateMode()
    {
        string IPAddrInput = IPaddrInputField.text;
        string portNumInput = PortNumInputField.text;
        string deckInput = DeckInputField.text;

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
            Debug.Log("No Playfab LogIn.");
            string pcID = SystemInfo.deviceUniqueIdentifier;
            InitParam.Player1Name = "Jimmy, The Mind of PlaceHolder" + pcID;
        }
        else InitParam.Player1Name = PlayFabAccountManager.Instance.InGameDisplayName;

        if (deckInput == "Or") InitParam.Player1Deck = "[\"Or_L\", \"Or_B\", \"Or_R\", \"Or_N\", \"Or_P\", \"Or_P\", \"Or_P\"]";
        else InitParam.Player1Deck = "[\"Cl_L\", \"Cl_B\", \"Cl_R\", \"Cl_N\", \"Cl_P\", \"Cl_P\", \"Cl_P\"]";

        InitParam.IpAddr = ipAddr.ToString();
        InitParam.PortNum = portNum;

        netManager.Init();

        _gameLoadCoroutine = StartCoroutine(GameLoadCoroutine());
        _gameLoadTimeoutCoroutine = StartCoroutine(GameLoadTimeoutCoroutine());
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
        yield return new WaitForSecondsRealtime(30f);
        Debug.Log("GameLoad Timeout: 30초 초과로 로딩 중단");
        StopGameLoad();
    }

    private IEnumerator GameLoadCoroutine()
    {
        yield return ConnectCoroutine();
        yield return SessionEnterCoroutine();

        DontDestroyOnLoad(InitParam);
        DontDestroyOnLoad(netManager);
        SceneManager.LoadScene(gameSceneName);
    }

    private IEnumerator ConnectCoroutine()
    {
        var wait = new WaitForCallback();
        netManager.Session.Events.OnConnectHello = wait.Complete;

        _ = netManager.Net.ConnectTo(InitParam.IpAddr, InitParam.PortNum, 9999);

        yield return wait;

        netManager.Session.Events.OnConnectHello = null;
    }

    private IEnumerator SessionEnterCoroutine()
    {
        var wait = new WaitForCallback();
        netManager.Session.EnterSession(InitParam.Player1Name, (raw) => { wait.Complete(); }, (msg) => { Debug.Log(msg); });

        yield return wait;
        yield return new WaitForSecondsRealtime(1.0f); // 서버 틱 맞추기 위해 대기

        var waitQuery = new WaitForCallback();

        var req = new SimpleReq(InitParam.Player1Deck);

        byte[] buffer = new byte[SimpleReq.Codec.GetSize(req)];
        PacketWriter writer = new(buffer);
        SimpleReq.Codec.Write(ref writer, req);

        netManager.Session.QueryDataRegister(buffer, 5000,
            (result) =>
            {
                if (result.IsResponded)
                {
                    PacketReader reader = new(result.AnswerRaw);
                    var rsp = SimpleRsp.Codec.Read(ref reader);
                    if (rsp.IsAccepted) waitQuery.Complete();
                    else { Debug.Log(rsp.Msg); StopGameLoad(); }
                    return;
                }
                Debug.Log("SessionEnter Req. is Expired");
            });

        yield return waitQuery;
        yield return new WaitForSecondsRealtime(1.0f);
    }

}
