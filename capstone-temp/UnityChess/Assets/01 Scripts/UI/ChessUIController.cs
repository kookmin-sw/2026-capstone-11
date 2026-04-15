using UnityEngine;
using events.client;
using events.ui;
using System.Collections.Generic;
using ui.view.board;
using ui.view.unit;
using ui.view.card;
using core.actions;

public enum SelectionState
{
    None,
    SourceSelected
}

public class ChessUIController : MonoBehaviour
{
    public CardView cardView;
    public BoardView boardView;

    private SelectionState state = SelectionState.None;

    // 현재 선택된 source (유닛 UID 또는 카드 UID)
    private string selectedSourceUID;

    // 현재 선택 source로 가능한 위치 타겟들
    private HashSet<Vector2Int> validCells = new();

    [SerializeField] private ChessUIEventBus eventBus;

    // 서버에서 받은 현재 턴 액션 목록 인덱스
    private readonly ActionIndex actionIndex = new();

    void Start()
    {
        Init();
    }

    void Init()
    {
        eventBus.Subscribe<IClientEvents.UnitSelectedEvent>(OnUnitSelected);
        //eventBus.Subscribe<IClientEvents.CardSelectedEvent>(OnCardSelected);
        eventBus.Subscribe<IClientEvents.CellSelectedEvent>(OnCellSelected);
        eventBus.Subscribe<IClientEvents.EmptySelectedEvent>(OnEmptySelected);

        validCells = new HashSet<Vector2Int>();
    }

    /// <summary>
    /// 서버에서 가능한 액션 목록을 받았을 때 호출
    /// ChessGameManager 등에서 연결해주면 됨
    /// </summary>
    public void SetAvailableActions(List<ActionDTO> actionDTOs)
    {
        var parsed = new List<ParsedAction>(actionDTOs.Count);

        foreach (var dto in actionDTOs)
        {
            parsed.Add(ActionParser.Parse(dto));
        }

        actionIndex.SetActions(parsed);

        ResetSelectionAndHighlights();

        Debug.Log($"Available actions updated: {parsed.Count}");
    }

    private void OnUnitSelected(IClientEvents.UnitSelectedEvent evt)
    {
        string sourceUid = evt.UnitUUID;

        Debug.Log($"Unit selected: {sourceUid}");

        if (!actionIndex.HasAnyActionForSource(sourceUid))
        {
            Debug.Log($"No available action for source: {sourceUid}");
            ResetSelectionAndHighlights();
            return;
        }

        evt.Unit.OnSelected();

        SelectSource(sourceUid);
    }

    // private void OnCardSelected(IClientEvents.CardSelectedEvent evt)
    // {
    //     string sourceUid = evt.CardUUID;

    //     Debug.Log($"Card selected: {sourceUid}");

    //     if (!actionIndex.HasAnyActionForSource(sourceUid))
    //     {
    //         Debug.Log($"No available action for source: {sourceUid}");
    //         ResetSelectionAndHighlights();
    //         return;
    //     }

    //     // 카드 뷰 하이라이트가 있다면 여기서 호출
    //     // evt.Card.OnSelected();

    //     SelectSource(sourceUid);
    // }

    private void SelectSource(string sourceUid)
    {
        selectedSourceUID = sourceUid;
        state = SelectionState.SourceSelected;

        // target 없는 단일 액션이면 바로 확정 가능
        if (actionIndex.TryResolveNoTargetAction(sourceUid, out var noTargetAction))
        {
            SubmitAction(noTargetAction.UID);
            ResetSelectionAndHighlights();
            return;
        }

        validCells = actionIndex.GetSelectableCells(sourceUid);

        if (validCells.Count > 0)
        {
            boardView.Show(validCells);
            return;
        }

        // 나중에 엔티티 타겟 카드도 여기서 확장 가능
        Debug.Log($"Source selected but no cell targets found: {sourceUid}");
    }

    private void OnCellSelected(IClientEvents.CellSelectedEvent evt)
    {
        Debug.Log($"Cell selected at: {evt.Pos}");

        if (state != SelectionState.SourceSelected)
            return;

        if (!validCells.Contains(evt.Pos))
        {
            Debug.Log($"Selected cell is not valid: {evt.Pos}");
            return;
        }

        if (actionIndex.TryResolveBySourceAndCell(selectedSourceUID, evt.Pos, out var action))
        {
            SubmitAction(action.UID);
        }
        else
        {
            Debug.LogWarning($"Action not found for source={selectedSourceUID}, cell={evt.Pos}");
        }

        ResetSelectionAndHighlights();
    }

    private void OnEmptySelected(IClientEvents.EmptySelectedEvent evt)
    {
        Debug.Log("Empty space selected");
        ResetSelectionAndHighlights();
    }

    private void ResetSelectionAndHighlights()
    {
        state = SelectionState.None;
        selectedSourceUID = null;
        validCells.Clear();
        boardView.Clear();
    }

    /// <summary>
    /// 최종 확정된 Action UID 전송
    /// TODO: 실제 프로젝트의 client event / network 전송 구조에 맞게 교체 필요
    /// </summary>
    private void SubmitAction(string actionUid)
    {
        Debug.Log($"Submit Action UID: {actionUid}");

        // TODO:
        // 여기서 실제 클라이언트 명령 이벤트 또는 네트워크 전송 호출
        //
        // 예시:
        // eventBus.Publish(new IClientEvents.ActionConfirmedEvent(actionUid));
    }

    /// <summary>
    /// 턴 종료 버튼에서 호출 가능
    /// </summary>
    public void OnClickTurnEnd()
    {
        if (actionIndex.TryGetTurnEndAction(out var action))
        {
            SubmitAction(action.UID);
            ResetSelectionAndHighlights();
        }
        else
        {
            Debug.Log("TurnEnd action is not available.");
        }
    }
}