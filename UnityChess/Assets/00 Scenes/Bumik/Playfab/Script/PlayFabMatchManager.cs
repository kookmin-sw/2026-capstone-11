using System.Collections;
using System.Linq;
using PlayFab;
using PlayFab.MultiplayerModels;
using UnityEngine;

public class PlayFabMatchManager : MonoBehaviour
{
    public static PlayFabMatchManager Instance;

    private const float _LeastPollingTime = 6.0f;

    [Header("Matchmaking")]
    [SerializeField] private string _matchQueueName = "TestMatchQueue";
    [SerializeField] private int _giveUpTime = 60;
    [SerializeField][Range(6, 30)] private float _ticketPollingTime = 6.0f;

    [Header("MPS")]
    [SerializeField] private string _gamePortName = "game_port";

    [Header("Region Selection Rule")]
    [SerializeField] private string _regionName = "KoreaCentral";
    [SerializeField] private int _dummyLatencyMs = 50;

    [Header("Game Start")]
    [SerializeField] private DedicateModeStarter _dedicateModeStarter;

    private string _ticketId = null;
    private string _matchId = null;

    private bool _isCreateTicketRequested = false;
    private bool _isTicketPolling = false;

    private Coroutine _ticketPollingCoroutine = null;

    public bool IsMatchTicketSuccess => !string.IsNullOrEmpty(_ticketId);
    public bool IsMatching => IsMatchTicketSuccess && _isTicketPolling;

    public string ServerAddress { get; private set; }
    public int ServerPort { get; private set; }

    private void Awake()
    {
        if (Instance != null)
        {
            Destroy(gameObject);
            return;
        }

        Instance = this;
    }

    public void OnMatchMakingRequest()
    {
        if (!PlayFabAccountManager.Instance.IsLoggedIn)
        {
            Debug.Log("PlayFab Log in 필요");
            return;
        }

        if (_isCreateTicketRequested || _isTicketPolling)
        {
            Debug.Log("이미 매치 요청 중");
            return;
        }

        _isCreateTicketRequested = true;

        PlayFabMultiplayerAPI.CreateMatchmakingTicket(
            new CreateMatchmakingTicketRequest
            {
                Creator = new MatchmakingPlayer
                {
                    Entity = new EntityKey
                    {
                        Id = PlayFabAccountManager.Instance.EntityId,
                        Type = PlayFabAccountManager.Instance.EntityType,
                    },

                    Attributes = new MatchmakingPlayerAttributes
                    {
                        DataObject = new
                        {
                            Latencies = new object[]
                            {
                                new
                                {
                                    region = _regionName,
                                    latency = _dummyLatencyMs
                                }
                            }
                        }
                    }
                },

                GiveUpAfterSeconds = _giveUpTime,
                QueueName = _matchQueueName
            },
            result =>
            {
                _ticketId = result.TicketId;
                _matchId = null;

                _isCreateTicketRequested = false;
                _isTicketPolling = true;

                if (_ticketPollingCoroutine != null)
                    StopCoroutine(_ticketPollingCoroutine);

                _ticketPollingCoroutine = StartCoroutine(TicketPolling());

                Debug.Log($"매치 메이킹 티켓 생성 TicketId={_ticketId}");
            },
            error =>
            {
                _ticketId = null;
                _matchId = null;

                _isCreateTicketRequested = false;
                _isTicketPolling = false;

                Debug.LogError($"매치 메이킹 요청 실패: {error.GenerateErrorReport()}");
            }
        );
    }

    private IEnumerator TicketPolling()
    {
        while (!string.IsNullOrEmpty(_ticketId) && _isTicketPolling)
        {
            bool requestDone = false;

            PlayFabMultiplayerAPI.GetMatchmakingTicket(
                new GetMatchmakingTicketRequest
                {
                    TicketId = _ticketId,
                    QueueName = _matchQueueName,
                },
                result =>
                {
                    requestDone = true;

                    string status = result.Status;
                    Debug.Log($"Matchmaking Status: {status}");

                    if (status == "Matched")
                    {
                        _matchId = result.MatchId;
                        _isTicketPolling = false;

                        Debug.Log($"매치 성공 MatchId={_matchId}");

                        RequestMatchDetails();
                        return;
                    }

                    if (status == "Canceled" || status == "Failed")
                    {
                        Debug.LogWarning($"매치메이킹 종료 Status={status}");

                        _ticketId = null;
                        _matchId = null;
                        _isTicketPolling = false;
                    }
                },
                error =>
                {
                    requestDone = true;

                    Debug.LogError($"티켓 폴링 실패: {error.GenerateErrorReport()}");

                    _ticketId = null;
                    _matchId = null;
                    _isTicketPolling = false;
                }
            );

            yield return new WaitUntil(() => requestDone || !_isTicketPolling);

            if (!_isTicketPolling)
                break;

            float waitTime = Mathf.Max(_LeastPollingTime, _ticketPollingTime);
            yield return new WaitForSecondsRealtime(waitTime);
        }

        _ticketPollingCoroutine = null;
    }

    private void RequestMatchDetails()
    {
        if (string.IsNullOrEmpty(_matchId))
        {
            Debug.LogError("MatchId가 없어서 GetMatch 요청 불가");
            return;
        }

        PlayFabMultiplayerAPI.GetMatch(
            new GetMatchRequest
            {
                MatchId = _matchId,
                QueueName = _matchQueueName,
                ReturnMemberAttributes = false,
                EscapeObject = false
            },
            result =>
            {
                if (result.ServerDetails == null)
                {
                    Debug.LogError(
                        "GetMatch 성공했지만 ServerDetails가 없음. " +
                        "Queue의 Server Allocation, BuildId/BuildAlias, RegionSelectionRule 설정 확인 필요"
                    );
                    return;
                }

                var server = result.ServerDetails;

                string address = !string.IsNullOrEmpty(server.Fqdn)
                    ? server.Fqdn
                    : server.IPV4Address;

                if (string.IsNullOrEmpty(address))
                {
                    Debug.LogError("ServerDetails에 Fqdn/IPV4Address가 없음");
                    return;
                }

                var selectedPort =
                    server.Ports?.FirstOrDefault(p => p.Name == _gamePortName)
                    ?? server.Ports?.FirstOrDefault();

                if (selectedPort == null)
                {
                    Debug.LogError("ServerDetails에 Port 정보가 없음");
                    return;
                }

                ServerAddress = address;
                ServerPort = selectedPort.Num;

                Debug.Log(
                    $"MPS 서버 할당 성공\n" +
                    $"Address={ServerAddress}\n" +
                    $"PortName={selectedPort.Name}\n" +
                    $"Port={ServerPort}\n" +
                    $"Region={server.Region}\n" +
                    $"ServerId={server.ServerId}"
                );

                StartGameWithAllocatedServer();
            },
            error =>
            {
                Debug.LogError($"GetMatch 실패: {error.GenerateErrorReport()}");
            }
        );
    }

    private void StartGameWithAllocatedServer()
    {
        if (_dedicateModeStarter == null)
        {
            Debug.LogError("DedicateModeStarter 참조가 없음. Inspector에 연결 필요");
            return;
        }

        _dedicateModeStarter.StartDedicateModeFromMatchmaking(ServerAddress, ServerPort);
    }

    public void OnCancelMatchMaking()
    {
        if (string.IsNullOrEmpty(_ticketId))
        {
            Debug.Log("취소할 매치 티켓이 없음");
            return;
        }

        PlayFabMultiplayerAPI.CancelMatchmakingTicket(
            new CancelMatchmakingTicketRequest
            {
                QueueName = _matchQueueName,
                TicketId = _ticketId
            },
            result =>
            {
                _ticketId = null;
                _matchId = null;

                _isCreateTicketRequested = false;
                _isTicketPolling = false;

                if (_ticketPollingCoroutine != null)
                {
                    StopCoroutine(_ticketPollingCoroutine);
                    _ticketPollingCoroutine = null;
                }

                Debug.Log("매치메이킹 취소 성공");
            },
            error =>
            {
                Debug.LogError($"매치메이킹 취소 실패: {error.GenerateErrorReport()}");
            }
        );
    }
}