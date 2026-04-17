using System.Collections.Generic;
using UnityEngine;
using events;
using events.server;
using events.client;
using events.ui;
using Core.StateManagement;
using Core.DTO;
using core.UI;
using System.Linq;

namespace Core
{
    public class ChessGameManager : MonoBehaviour
    {
        [SerializeField] private GameStateStore gameStateStore;
        [SerializeField] private ViewFactory viewFactory;
        [SerializeField] private ChessUIEventBus eventBus;
        
        // View가 생성될 때의 부모 transform
        [SerializeField] private Transform boardParent;
        [SerializeField] private Transform handParent;


        public GameStateStore State => gameStateStore;

        // 스냅샷 수신 시에 StateStore에 적용하기 위해 위임
        public void ApplySnapshotJson(string json)
        {
            gameStateStore.ApplySnapshotJson(json);
            PublishSnapshotRefreshed();
        }

        public void ApplySnapshot(GameSnapshotDTO snapshot)
        {
            gameStateStore.ApplySnapshot(snapshot);
            PublishSnapshotRefreshed();
        }

        public bool CanSelectSource(string sourceUid)
        {
            return gameStateStore.HasAnyActionForSource(sourceUid);
        }

        public HashSet<string> GetSelectableSources()
        {
            return gameStateStore.GetSelectableSources();
        }

        public HashSet<Vector2Int> GetSelectableCells(string sourceUid)
        {
            return gameStateStore.GetSelectableCells(sourceUid);
        }

        public IReadOnlyList<IReadOnlyList<EntityID>> GetSelectableTargetEntityGroups(string sourceUid)
        {
            return gameStateStore.GetSelectableTargetEntityGroups(sourceUid);
        }

        public bool TryResolveCellAction(string sourceUid, Vector2Int pos, out RuntimeAction action)
        {
            return gameStateStore.TryResolveBySourceAndCell(sourceUid, pos, out action);
        }

        public bool TryResolveEntityTargetAction(string sourceUid, IEnumerable<EntityID> targetIds, out RuntimeAction action)
        {
            return gameStateStore.TryResolveBySourceAndTargets(sourceUid, targetIds, out action);
        }

        public bool TryResolveNoTargetAction(string sourceUid, out RuntimeAction action)
        {
            return gameStateStore.TryResolveNoTargetAction(sourceUid, out action);
        }

        public bool TryBuildCellActionRequest(string sourceUid, Vector2Int pos, out string actionUid)
        {
            actionUid = null;

            if (!TryResolveCellAction(sourceUid, pos, out var action))
                return false;

            actionUid = action.uid;
            return true;
        }

        public bool TryBuildEntityTargetActionRequest(string sourceUid, IEnumerable<EntityID> targetIds, out string actionUid)
        {
            actionUid = null;

            if (!TryResolveEntityTargetAction(sourceUid, targetIds, out var action))
                return false;

            actionUid = action.uid;
            return true;
        }

        public bool TryBuildNoTargetActionRequest(string sourceUid, out string actionUid)
        {
            actionUid = null;

            if (!TryResolveNoTargetAction(sourceUid, out var action))
                return false;

            actionUid = action.uid;
            return true;
        }

        public void HandleServerEvent(IServerEvents serverEvent)
        {
            // TODO:
            // 서버 이벤트 타입이 정리되면 snapshot 수신 이벤트에서 ApplySnapshot / ApplySnapshotJson 호출.
        }

        public void HandleClientEvent(IClientEvents clientEvent)
        {
            // TODO:
            // Selection FSM / network sender 와 연결.
        }

        private void PublishSnapshotRefreshed()
        {
            viewFactory.RebuildFromState(
                state: gameStateStore,
                localPlayerId: gameStateStore.Players.Keys.First(), // TODO: 실제 local player ID로 변경 필요
                boardParent: boardParent,
                handParent: handParent, 
                isLocalPlayerP1: true
            );

            //eventBus.Publish(new SnapshotRefreshedEvent());
        }

        private void PublishUIEvent(IBaseEvent uiEvent)
        {
            eventBus.Publish(uiEvent);
        }
    }
}
