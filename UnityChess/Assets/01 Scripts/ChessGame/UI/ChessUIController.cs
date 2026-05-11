using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using events.client;
using events.ui;
using ui.view.board;
using ui.view.effect;
using ui.view;
using Core;
using Core.StateManagement;
using events.server;
using core.UI;

public enum SelectionState
{
    None,
    SelectingCellTarget,
    SelectingEntityTargets,
    Sumbitting, // 액션 확정 이후 잠시 대기하는 상태, 서버 응답이 오면 다시 None으로 돌아감
    Locked, // 본인 턴이 아닌 경우 선택이 불가능한 상태
}

/// <summary>
/// Selection FSM을 담당하는 UI 컨트롤러
/// </summary>
public class ChessUIController : MonoBehaviour
{
    [SerializeField] private ChessGameManager gameManager;
    [SerializeField] private ChessUIEventBus eventBus;
    [SerializeField] private ViewRegistry viewRegistry;
    [SerializeField] private BoardView boardView;

    private SelectionState state = SelectionState.None;

    // 현재 선택된 액션 source
    private ActionSourceKey selectedSource;

    // source -> cell target
    private HashSet<Vector2Int> validCells = new();

    // source -> entity target groups
    private readonly List<List<EntityID>> validTargetGroups = new();
    private readonly List<EntityID> selectedTargetIds = new();
    private readonly HashSet<string> validTargetCandidateIds = new(StringComparer.Ordinal);

    private bool isInputLocked;
    
    private void Start()
    {
        Init();
    }

    private void OnDestroy()
    {
        Release();
    }


    private void Init()
    {
        if (eventBus == null)
        {
            Debug.LogError("[ChessUIController] eventBus is not assigned.");
            return;
        }

        if (gameManager == null)
        {
            Debug.LogError("[ChessUIController] gameManager is not assigned.");
            return;
        }

        eventBus.Subscribe<IClientEvents.UnitSelectedEvent>(OnUnitSelected);
        eventBus.Subscribe<IClientEvents.CellSelectedEvent>(OnCellSelected);
        eventBus.Subscribe<IClientEvents.CardSelectedEvent>(OnCardSelected);
        eventBus.Subscribe<IClientEvents.EmptySelectedEvent>(OnEmptySelected);

        ResetSelectionAndHighlights();
    }

    // 파괴 되기 전에 구독 해제
    private void Release()
    {
        if (eventBus == null)
            return;

        eventBus.Unsubscribe<IClientEvents.UnitSelectedEvent>(OnUnitSelected);
        eventBus.Unsubscribe<IClientEvents.CellSelectedEvent>(OnCellSelected);
        eventBus.Unsubscribe<IClientEvents.CardSelectedEvent>(OnCardSelected);
        eventBus.Unsubscribe<IClientEvents.EmptySelectedEvent>(OnEmptySelected);
    }

    /// <summary>
    /// Hand 카드 UI에서 직접 호출하기 위한 진입점
    /// </summary>
    public void SelectSourceFromCard(string sourceUid)
    {
        if (string.IsNullOrWhiteSpace(sourceUid))
            return;

        var source = new ActionSourceKey(ViewType.Card, sourceUid);
        TrySelectSource(source);
    }

    // BoardView에서 직접 호출하기 위한 진입점
    private void OnUnitSelected(IClientEvents.UnitSelectedEvent evt)
    {
        if (isInputLocked) return;

        var clickedSource = new ActionSourceKey(ViewType.Unit, evt.UnitUUID);
        
        Debug.Log($"[ChessUIController] Unit selected: {clickedSource.Uid}");

        // source가 이미 선택된 상태에서 entity target을 고르는 단계라면
        // 이번 클릭은 source 재선택이 아니라 target 선택으로 해석한다
        if (state == SelectionState.SelectingEntityTargets)
        {
            TrySelectEntityTarget(evt.UnitUUID);
            return;
        }

        TrySelectSource(clickedSource);
    }

    private void OnCardSelected(IClientEvents.CardSelectedEvent evt)
    {
        if (isInputLocked) return;

        string clickedUid = evt.CardUUID;
        Debug.Log($"[ChessUIController] Card selected: {clickedUid}");
        
        var clickedSource = new ActionSourceKey(ViewType.Card, clickedUid);

        // 카드 선택은 항상 source 선택으로 해석한다
        TrySelectSource(clickedSource);
    }

    // source 선택 시도
    private void TrySelectSource(ActionSourceKey source)
    {
        if (source.IsEmpty)
        {
            ResetSelectionAndHighlights();
            return;
        }

        if (!gameManager.CanSelectSource(source))
        {
            Debug.Log($"[ChessUIController] No available action for source: {source.Uid}");
            ResetSelectionAndHighlights();
            return;
        }
    
        selectedSource = source;

        // 선택된 Source의 하이라이트 적용
        ClearViewHighlights();
        SetSourceHighlight();

        // 1) no-target action이면 즉시 확정
        if (gameManager.TryResolveNoTargetAction(source, out var noTargetAction))
        {
            SubmitAction(noTargetAction.uid);
            ResetSelectionAndHighlights();
            return;
        }

        // 2) cell target이 있으면 셀 선택 단계로 진입
        validCells = gameManager.GetSelectableCells(source);
        if (validCells.Count > 0)
        {
            state = SelectionState.SelectingCellTarget;
            boardView.Clear();
            boardView.Show(validCells, gameManager.State.IsLocalPlayer());
            return;
        }

        // 3) entity target group이 있으면 엔티티 선택 단계로 진입
        BuildEntityTargetSelectionState(source);
        if (validTargetGroups.Count > 0)
        {
            state = SelectionState.SelectingEntityTargets;
            RefreshEntityTargetHighlights();
            return;
        }

        Debug.Log($"[ChessUIController] Source selected but no resolvable target found: {source.Uid}");
        ResetSelectionAndHighlights();
    }

    private void BuildEntityTargetSelectionState(ActionSourceKey source)
    {
        validTargetGroups.Clear();
        selectedTargetIds.Clear();
        validTargetCandidateIds.Clear();

        var groups = gameManager.GetSelectableTargetEntityGroups(source);
        if (groups == null)
            return;

        foreach (var group in groups)
        {
            if (group == null || group.Count == 0)
                continue;

            var copied = group.ToList();
            validTargetGroups.Add(copied);

            foreach (var id in copied)
            {
                if (!id.IsEmpty)
                    validTargetCandidateIds.Add(id.id);
            }
        }
    }

    // 모든 유닛/카드 뷰 하이라이트를 비표시
    private void ClearViewHighlights()
    {
        foreach (var id in viewRegistry.GetAllIds())
        {
            if (id.Type != ViewType.Unit && id.Type != ViewType.Card)
                continue;
            
            (viewRegistry.Get(id) as BaseView).SetHighlight(OutlineType.None);
        }
    }

    // 특정 뷰의 하이라이트를 표시
    private void SetViewHighlight(ViewType type, EntityID id, OutlineType outlineType)
    {
        if (string.IsNullOrWhiteSpace(id.id))
            return;

        (viewRegistry.Get(new ViewID(type, id.id)) as BaseView).SetHighlight(outlineType);
    }

    // 선택한 Action Source의 하이라이트를 표시
    private void SetSourceHighlight()
    {
        if (selectedSource.IsEmpty) 
            return;
        
        SetViewHighlight(selectedSource.Type, selectedSource.Uid, OutlineType.Selected);
    }

    // 현재 선택된 타겟과 양립 가능한 후보 타겟들만 하이라이트
    // TODO: 셀 하이라이트 대신 엔티티(유닛) 하이라이트로 변경
    private void RefreshEntityTargetHighlights()
    {
        boardView.Clear();
        ClearViewHighlights();
        // 선택된 Source는 항상 Selected된 상태
        SetSourceHighlight();

        if (validTargetGroups.Count == 0)
            return;

        int nextIndex = selectedTargetIds.Count;

        // 이미 선택된 Target의 Selected 상태 표시
        foreach (var selectedId in selectedTargetIds)
        {
            SetViewHighlight(ViewType.Unit, selectedId, OutlineType.Selected);
        }

        // 이미 고른 타겟들과 양립 가능한 그룹만 남긴다.
        var compatibleGroups = validTargetGroups
            .Where(IsCompatibleWithCurrentSelection)
            .ToList();

        if (compatibleGroups.Count == 0)
            return;

        // 4. 다음 순서의 후보만 Targetable
        foreach (var group in compatibleGroups)
        {
            if (group.Count <= nextIndex)
                continue;

            var candidate = group[nextIndex];

            if (selectedTargetIds.Contains(candidate))
                continue;

            if (!gameManager.State.TryGetUnit(candidate, out var unit))
                continue;

            if (!unit.isPlaced)
                continue;

            SetViewHighlight(ViewType.Unit, candidate, OutlineType.Targetable);
        }
    }

    // 현재 선택된 타겟들과 양립 가능한 그룹이 하나라도 있으면 true
    private bool IsCompatibleWithCurrentSelection(List<EntityID> group)
    {
        if (group == null || group.Count == 0)
            return false;

        // 이미 선택된 타겟들과 양립 가능한 그룹이 하나라도 있으면 true
        if (selectedTargetIds.Count > group.Count)
            return false;

        for (int i = 0; i < selectedTargetIds.Count; i++)
        {
            if (!group.Contains(selectedTargetIds[i]))
                return false;
        }

        return true;
    }

    // entity target 선택 시도
    private void TrySelectEntityTarget(string clickedUid)
    {
        if (string.IsNullOrWhiteSpace(clickedUid))
            return;

        if (!validTargetCandidateIds.Contains(clickedUid))
        {
            Debug.Log($"[ChessUIController] Invalid entity target: {clickedUid}");
            return;
        }

        var clickedId = new EntityID(clickedUid);

        if (selectedTargetIds.Contains(clickedId))
        {
            Debug.Log($"[ChessUIController] Entity target already selected: {clickedUid}");
            return;
        }

        var proposedTargets = new List<EntityID>(selectedTargetIds) { clickedId };

        // exact match가 되면 즉시 액션 확정
        if (gameManager.TryResolveEntityTargetAction(selectedSource, proposedTargets, out var resolvedAction))
        {
            SubmitAction(resolvedAction.uid);
            ResetSelectionAndHighlights();
            return;
        }

        // 아직 완성되지 않은 부분 선택이면 상태 유지
        if (IsPartialTargetCombinationValid(proposedTargets))
        {
            selectedTargetIds.Add(clickedId);
            RefreshEntityTargetHighlights();
            return;
        }

        Debug.Log($"[ChessUIController] Target combination is not valid yet: {clickedUid}");
    }

    private bool IsPartialTargetCombinationValid(List<EntityID> partialTargets)
    {
        if (partialTargets == null || partialTargets.Count == 0)
            return false;

        foreach (var group in validTargetGroups)
        {
            if (group.Count < partialTargets.Count)
                continue;

            bool isSubset = true;
            foreach (var partial in partialTargets)
            {
                if (!group.Contains(partial))
                {
                    isSubset = false;
                    break;
                }
            }

            if (isSubset)
                return true;
        }

        return false;
    }

    private void OnCellSelected(IClientEvents.CellSelectedEvent evt)
    {
        if (isInputLocked) return;

        Debug.Log($"[ChessUIController] Cell selected at: {evt.Pos}");

        if (state != SelectionState.SelectingCellTarget)
            return;

        if (!validCells.Contains(evt.Pos))
        {
            Debug.Log($"[ChessUIController] Selected cell is not valid: {evt.Pos}");
            return;
        }

        if (gameManager.TryResolveCellAction(selectedSource, evt.Pos, out var action))
        {
            SubmitAction(action.uid);
        }
        else
        {
            Debug.LogWarning($"[ChessUIController] Action not found for source={selectedSource.Uid}, cell={evt.Pos}");
        }

        ResetSelectionAndHighlights();
    }

    private void OnEmptySelected(IClientEvents.EmptySelectedEvent evt)
    {
        if (isInputLocked) return;

        Debug.Log("[ChessUIController] Empty space selected");
        ResetSelectionAndHighlights();
    }

    public void ResetSelectionAndHighlights()
    {
        state = SelectionState.None;
        selectedSource = default;

        validCells.Clear();
        validTargetGroups.Clear();
        selectedTargetIds.Clear();
        validTargetCandidateIds.Clear();

        if (boardView != null)
            boardView.Clear();
        
        ClearViewHighlights();
    }

    public void OnClickTurnEnd()
    {
        var turnEndAction = gameManager.State.GetTurnEndAction();
        SubmitAction(turnEndAction.uid);
        ResetSelectionAndHighlights();
    }

    /// <summary>
    /// 최종 확정된 Action UID 전송
    /// </summary>
    private void SubmitAction(string actionUid)
    {
        Debug.Log($"[ChessUIController] Submit Action UID: {actionUid}");

        NetworkEventBus.Instance.Publish(new IServerEvents.ReplyQueryEvent { actionId = actionUid });
    }

    public void SetInputLocked(bool locked)
    {
        isInputLocked = locked;

        if (locked)
        {
            ResetSelectionAndHighlights();
            state = SelectionState.Locked;
        }
        else 
            state = SelectionState.None;
    }
}
