using UnityEngine;
using events.Animation;
using ui.view.board;
using ui.view;
using ui.view.unit;
using ui.view.card;
using Core.StateManagement;
using Core.Delta;
using core.UI;
using static evets.Animation.IAnimationEvents;
using UI.HUD;
using System.Collections;

namespace Animations
{
    public class AnimationHandler : MonoBehaviour
    {
        [Header("References")]
        [SerializeField] private ViewRegistry viewRegistry;
        [SerializeField] private ChessHUDController HUDController;

        private GameStateStore state;
        private ViewFactory factory;

        private Transform boardParent;
        private Transform handParent;

        public void Init(
            GameStateStore state,
            ViewFactory factory,
            Transform boardParent,
            Transform handParent)
        {
            this.state = state;
            this.factory = factory;

            this.boardParent = boardParent;
            this.handParent = handParent;
        }

        private void OnEnable()
        {
            AnimationEventBus.Instance.Subscribe<UnitMoveEvent>(OnUnitMove);
            AnimationEventBus.Instance.Subscribe<UnitDeployEvent>(OnUnitDeploy);
            AnimationEventBus.Instance.Subscribe<UnitDestroyEvent>(OnUnitDestroy);
            AnimationEventBus.Instance.Subscribe<UnitDamageEvent>(OnUnitDamage);

            AnimationEventBus.Instance.Subscribe<CardDrawEvent>(OnCardDraw);
            AnimationEventBus.Instance.Subscribe<CardUseEvent>(OnCardUse);
        }

        private void OnDisable()
        {
            AnimationEventBus.Instance.Unsubscribe<UnitMoveEvent>(OnUnitMove);
            AnimationEventBus.Instance.Unsubscribe<UnitDeployEvent>(OnUnitDeploy);
            AnimationEventBus.Instance.Unsubscribe<UnitDestroyEvent>(OnUnitDestroy);

            AnimationEventBus.Instance.Unsubscribe<CardDrawEvent>(OnCardDraw);
            AnimationEventBus.Instance.Unsubscribe<CardUseEvent>(OnCardUse);
        }

        private void OnUnitMove(UnitMoveEvent evt)
        {
            var cmd = evt.cmd;

            if (cmd == null)
                return;

            UnitView view = viewRegistry.Get(new ViewID(ViewType.Unit,cmd.target.id)) as UnitView;

            var cell = BoardView.BoardToCell(cmd.position, state.IsLocalPlayer());
            view.transform.position = boardParent.gameObject.GetComponent<BoardView>().tilemap.GetCellCenterWorld(cell);
            // view.Animator.Move(cmd.To);
        }

        private void OnUnitDeploy(UnitDeployEvent evt)
        {
            var cmd = evt.cmd;

            if (cmd == null)
                return;

            if (!state.TryGetUnit(cmd.target.id, out var entity))
                return;

            bool isLocalPlayerP1 = state.IsLocalPlayer();

            var view = factory.CreateUnitView(
                state,
                entity.owner,
                boardParent,
                isLocalPlayerP1,
                entity.id
            );

            //view.Animator.Spawn();
        }

        private void OnUnitDestroy(UnitDestroyEvent evt)
        {
            var cmd = evt.cmd;

            if (cmd == null)
                return;

            var viewId = new ViewID(ViewType.Unit, cmd.target.id);

            UnitView view = viewRegistry.Get(viewId) as UnitView;
                
            if (view == null)
                return;

            viewRegistry.Unregister(viewId);
            view.unitAnimator.PlayDestroy(evt.cmd.duration);
        }

        private void OnUnitDamage(UnitDamageEvent evt)
        {
            var cmd = evt.cmd;

            if (cmd == null)
                return;

            UnitView view = viewRegistry.Get(new ViewID(ViewType.Unit, cmd.target.id)) as UnitView;

            if (view == null)
                return;

            view.unitAnimator.PlayDamage();
            view.data.curHP -= cmd.value;
        }

        private void OnCardDraw(CardDrawEvent evt)
        {
            var cmd = evt.cmd;

            if (cmd == null)
                return;

            // 자신의 카드 드로우에 대해서만 애니메이션 재생
            if (cmd.playerId != state.LocalPlayerId)
                return;
            
            foreach (var card in state.Handdiff)
            {
                StartCoroutine(CardDraw(card, cmd.duration / cmd.value));
            }
        }

        private IEnumerator CardDraw(EntityID cardId, float interval)
        {
            var view = factory.CreateCardView(
                    state,
                    handParent,
                    cardId
                );

            view.cardAnimator.PlayDraw();

            yield return new WaitForSeconds(interval);    
        }

        private void OnCardUse(CardUseEvent evt)
        {
            var cmd = evt.cmd;

            if (cmd == null)
                return;

            var viewId = new ViewID(ViewType.Card, cmd.target.id);

            CardView view = viewRegistry.Get(viewId) as CardView;

            if (view == null)
                return;

            // TODO: Destroy 애니메이션 재생 후 뷰 제거하도록 수정
            // 자신의 카드 사용에 대해서만 애니메이션 재생
            if (state.IsMyTurn)
            {
                viewRegistry.Unregister(viewId);

                view.cardAnimator.PlayUse(evt.cmd.duration);
            }
            else
            {
                HUDController.UpdateOppoCardCountText(state.GetHand(state.OpponentPlayerId).Count);

                Debug.Log("Opponent Uses Card");
            }
        }
    }
}