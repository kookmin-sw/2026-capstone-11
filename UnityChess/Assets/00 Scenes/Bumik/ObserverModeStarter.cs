using System.Collections;
using System.Net;
using System.Text;
using Game.Network;
using TMPro;
using UnityEngine;
using UnityEngine.SceneManagement;

public class ObserverModeStarter : MonoBehaviour
{


    [Header("Ref to UI Input")]
    [SerializeField] private TMP_InputField IPaddrInputField;
    [SerializeField] private TMP_InputField PortNumInputField;
    [SerializeField] private TMP_InputField ObserverKeyInputField;

    [Header("Game Scene Load")]
    [SerializeField] private NetworkManagerUnity netManager;
    [SerializeField] private GameInitParam InitParam;
    [SerializeField] private string gameSceneName;

    private Coroutine _gameLoadCoroutine;
    private Coroutine _gameLoadTimeoutCoroutine;

    public void OnClickStartObserverMode()
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
        _ = netManager.Net.AsyncRequestQuery(NetEventHandlerId.Constant.ObserverEnter, 
            netManager.Session.Host, 
            Encoding.UTF8.GetBytes(ObserverKeyInputField.text),
            10000,
            (connId, result) =>
            {
                if (result.IsResponded) wait.Complete();
                else
                {
                    Debug.Log("Observer 실패");
                }
            }
            );

        yield return wait;
        yield return new WaitForSecondsRealtime(1.0f); // 서버 틱 맞추기 위해 대기
    }

}

