using UnityEngine;
using Core;
using Core.StateManagement;
using ui.view.board;
using System.Text;
using System.Collections;
using Game.Network.Service;
using Game.Network;
using events.ui;
using UnityEngine.SceneManagement;
using Unity.VisualScripting;


public class GameInit : MonoBehaviour
{

    [Header("Runtime References")]
    [SerializeField] private ChessGameManager gameManager;
    [SerializeField] private GameStateStore stateStore;
    [SerializeField] private BoardView boardView;
    [SerializeField] private Transform handParent;

    [Header("Game Close Scene")] 
    [SerializeField] private string CloseScene;
    private Coroutine _closeCoroutine = null;
    private string prevJson = string.Empty;

    void Start()
    {
        if (NetworkManagerUnity.Instance == null) Debug.LogError("Network is not Instanciated");
        if (GameInitParam.Instance == null) Debug.LogError("InitParam is not Instanciated");

        NetworkManagerUnity.Instance.Session.Events.OnDisconnectUnsafe = () => {if (_closeCoroutine == null) _closeCoroutine = StartCoroutine(SceneCloseCoroutine());};

        // NetworkManagerUnity.Instance.Session.Events.OnGetQuery = (queryNum, raw) => { };
        NetworkManagerUnity.Instance.Session.Events.OnMessageReceive = (raw) => 
        { 
            var json = Encoding.UTF8.GetString(raw);    
            
            // 새로 받은 스냅샷에 diff가 없으면 무시
            if (prevJson != json)
            {
                prevJson = json;
                gameManager.InitSnapshotJson(json, GameInitParam.Instance.Player1Name);
            }

            
        };

        NetworkManagerUnity.Instance.Session.SubscribeEventBus();

        // 이 코루틴을 실행하기 이전에 게임 씬 로드 및 Bootstrap이 완료되어야 함
        StartCoroutine(ReadyCoroutine());
    }

    private IEnumerator SceneCloseCoroutine()
    {
        yield return new WaitForSecondsRealtime(1.0f);
        
        GameInitParam.Instance.Clear();
        NetworkManagerUnity.Instance.Session.Clear();

        DontDestroyOnLoad(GameInitParam.Instance);
        DontDestroyOnLoad(NetworkManagerUnity.Instance);
        
        SceneManager.LoadScene(CloseScene);
    }

    private IEnumerator ReadyCoroutine()
    {

        var wait = new WaitForCallback();

        var req = new SimpleReq("Ready");

        byte[] buffer = new byte[SimpleReq.Codec.GetSize(req)];
        PacketWriter writer = new(buffer);
        SimpleReq.Codec.Write(ref writer, req);

        NetworkManagerUnity.Instance.Session.QueryReady(buffer, 5000,
            (result) =>
            {
                if (result.IsResponded)
                {
                    PacketReader reader = new(result.AnswerRaw);
                    var rsp = SimpleRsp.Codec.Read(ref reader);
                    if (rsp.IsAccepted) wait.Complete();
                    else { Debug.Log(rsp.Msg);  }
                    return;
                }
                Debug.Log("SessionEnter Req. is Expired");
            });

        yield return wait;
    
    }
}
