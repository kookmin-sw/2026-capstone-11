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
using ui.view;
using UI.HUD;

namespace Core
{
    public class ChessGameManager : MonoBehaviour
    {
        [SerializeField] private GameStateStore gameStateStore;
        [SerializeField] private ViewFactory viewFactory;
        [SerializeField] private ChessHUDController hudController;
        [SerializeField] private ChessResultController resultController;
        [SerializeField] private ChessUIEventBus eventBus;
        [SerializeField] private WorldInputHandler inputHandler;
        
        // View가 생성될 때의 부모 transform
        [SerializeField] private Transform boardParent;
        [SerializeField] private Transform handParent;

        public GameStateStore State => gameStateStore;

        // 스냅샷 수신 시에 StateStore에 적용하기 위해 위임
        public void InitSnapshotJson(string json, string localPlayerId)
        {
            gameStateStore.LocalPlayerId = localPlayerId;

            gameStateStore.ApplySnapshotJson(json);
            inputHandler.Init(gameStateStore.IsLocalPlayer());

            PublishSnapshotRefreshed();

            // 게임 종료 여부 체크
            if (gameStateStore.WinnerId != null && gameStateStore.WinnerId != string.Empty)
            {
                PublishGameEnd();
            }
        }
        
        public void ApplySnapshotJson(string json)
        {
            gameStateStore.ApplySnapshotJson(json);
            PublishSnapshotRefreshed();

            // 게임 종료 여부 체크
            if (gameStateStore.WinnerId != null && gameStateStore.WinnerId != string.Empty)
            {
                PublishGameEnd();
            }
        }

        public void ApplySnapshot(GameSnapshotDTO snapshot)
        {
            gameStateStore.ApplySnapshot(snapshot);
            PublishSnapshotRefreshed();
        }

        public bool CanSelectSource(ActionSourceKey source)
        {
            return gameStateStore.HasAnyActionForSource(source);
        }

        public HashSet<string> GetSelectableSources()
        {
            return gameStateStore.GetSelectableSources();
        }

        public HashSet<Vector2Int> GetSelectableCells(ActionSourceKey source)
        {
            return gameStateStore.GetSelectableCells(source);
        }

        public IReadOnlyList<IReadOnlyList<EntityID>> GetSelectableTargetEntityGroups(ActionSourceKey source)
        {
            return gameStateStore.GetSelectableTargetEntityGroups(source);
        }

        public bool TryResolveCellAction(ActionSourceKey source, Vector2Int pos, out RuntimeAction action)
        {
            return gameStateStore.TryResolveBySourceAndCell(source, pos, out action);
        }

        public bool TryResolveEntityTargetAction(ActionSourceKey source, IEnumerable<EntityID> targetIds, out RuntimeAction action)
        {
            return gameStateStore.TryResolveBySourceAndTargets(source, targetIds, out action);
        }

        public bool TryResolveNoTargetAction(ActionSourceKey source, out RuntimeAction action)
        {
            return gameStateStore.TryResolveNoTargetAction(source, out action);
        }

        public bool TryBuildCellActionRequest(ActionSourceKey source, Vector2Int pos, out string actionUid)
        {
            actionUid = null;

            if (!TryResolveCellAction(source, pos, out var action))
                return false;

            actionUid = action.uid;
            return true;
        }

        public bool TryBuildEntityTargetActionRequest(ActionSourceKey source, IEnumerable<EntityID> targetIds, out string actionUid)
        {
            actionUid = null;

            if (!TryResolveEntityTargetAction(source, targetIds, out var action))
                return false;

            actionUid = action.uid;
            return true;
        }

        public bool TryBuildNoTargetActionRequest(ActionSourceKey source, out string actionUid)
        {
            actionUid = null;

            if (!TryResolveNoTargetAction(source, out var action))
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
                localPlayerId: gameStateStore.LocalPlayerId,
                opponentPlayerId: gameStateStore.Players.Keys.First(id => id != gameStateStore.LocalPlayerId),
                boardParent: boardParent,
                handParent: handParent, 
                isLocalPlayerP1: gameStateStore.IsLocalPlayer()
            );

            hudController.RefreshHUD(
                state: gameStateStore,
                playerNames: gameStateStore.Players.Values.Select(p => p.playerId).ToArray(),
                isLocalPlayerP1: gameStateStore.IsLocalPlayer()
            );
            //eventBus.Publish(new SnapshotRefreshedEvent());
        }

        private void PublishGameEnd()
        {
            resultController.gameObject.SetActive(true);
            
            resultController.ShowResult(
                state: gameStateStore,
                winner: gameStateStore.WinnerId,
                playerNames: gameStateStore.Players.Values.Select(p => p.playerId).ToArray()
            );
        }

        private void PublishUIEvent(IBaseEvent uiEvent)
        {
            eventBus.Publish(uiEvent);
        }
    }
}
