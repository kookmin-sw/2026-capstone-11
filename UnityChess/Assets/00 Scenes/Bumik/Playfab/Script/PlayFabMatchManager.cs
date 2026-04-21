using System.Collections;
using PlayFab;
using PlayFab.MultiplayerModels;
using UnityEngine;

public class PlayFabMatchManager : MonoBehaviour
{
    public static PlayFabMatchManager Instance;
    private const float _LeastPollingTime = 6.0f; 


    [SerializeField] private string _matchQueueName = "TestMatchQueue";
    [SerializeField] private int _giveUpTime = 60;
    [SerializeField][Range(6, 30)] private float _ticketPollingTime;

    private string _ticketId = null;
    private string _matchId = null;
    private bool _isMatchRequested = false;
    private Coroutine _ticketPollingCoroutine = null;

    public bool IsMatchTicketSuccess => _ticketId != null;

    void Awake()
    {
        if (Instance != null)
        {
            Destroy(gameObject);
        }
        else Instance = this;
    }

    public void OnMatchMakingRequest()
    {
        if (!PlayFabAccountManager.Instance.IsLoggedIn)
        {
            Debug.Log("PlayFab Log in 필요");
            return;
        }

        if (_isMatchRequested)
        {
            Debug.Log("이미 매치 요청 중");
            return;
        }

        _isMatchRequested = true;

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
                },
                GiveUpAfterSeconds = _giveUpTime,

                QueueName = _matchQueueName
            },
            (result) =>
            {
                _ticketId = result.TicketId;
                _isMatchRequested = false;
                _ticketPollingCoroutine = StartCoroutine(TicketPolling());

                Debug.Log($"매치 메이킹 티켓 생성 TicketId={_ticketId}");
            },
            (Error) =>
            {
                _ticketId = null;
                _isMatchRequested = false;

                Debug.Log($"매치 메이킹 요청 실패 Error : {Error}");
            }

        );
    }

    public IEnumerator TicketPolling()
    {
        // TODO: 이거 고치기
        while (_ticketId != null && _isMatchRequested != false)
        {

        PlayFabMultiplayerAPI.GetMatchmakingTicket(
            new GetMatchmakingTicketRequest
            {
                TicketId = _ticketId,
                QueueName = _matchQueueName,
            },
            (result) =>
            {
                var status = result.Status;
                if (status != "Matched") return;

                _matchId = result.MatchId;
                if (_ticketPollingCoroutine != null) StopCoroutine(_ticketPollingCoroutine); 
                // StartMatch()!!
            },
            (error) =>
            {
                if (_ticketPollingCoroutine != null) StopCoroutine(_ticketPollingCoroutine); 
            }
        );

            if (_ticketPollingTime < _LeastPollingTime)
                yield return new WaitForSecondsRealtime(_LeastPollingTime);
            else 
                yield return new WaitForSecondsRealtime(_ticketPollingTime);
        }
    }

    public void OnCancelMatchMaking()
    {
        if (!_isMatchRequested || !IsMatchTicketSuccess) return;

        PlayFabMultiplayerAPI.CancelMatchmakingTicket(
            new CancelMatchmakingTicketRequest
            {
                QueueName = _matchQueueName,
                TicketId = _ticketId
            },
            (result) =>
            {
                _ticketId = null;
                _isMatchRequested = false;
                Debug.Log("취소 성공");
            },
            (Error) =>
            {
                Debug.Log($"취소 실패 {Error}");
            }
        );
    }

}
