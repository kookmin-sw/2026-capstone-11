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
using Unity.VisualScripting;
using core.data;

namespace Animations
{
    public class AnimationHandler : MonoBehaviour
    {
        [Header("References")]
        [SerializeField] private ViewRegistry viewRegistry;
        [SerializeField] private ChessHUDController HUDController;
        [SerializeField] private VFXHandler vfxHandler;
        
        [SerializeField] private BuffDB buffDB;

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
            AnimationEventBus.Instance.Subscribe<UnitAttackEvent>(OnUnitAttack);
            AnimationEventBus.Instance.Subscribe<UnitDamageEvent>(OnUnitDamage);
            AnimationEventBus.Instance.Subscribe<UnitHealEvent>(OnUnitHeal);
            AnimationEventBus.Instance.Subscribe<UnitSwapEvent>(OnSwapUnit);

            AnimationEventBus.Instance.Subscribe<ApplyBuffEvent>(OnAddBuff);
            AnimationEventBus.Instance.Subscribe<RemoveBuffEvent>(OnRemoveBuff);

            AnimationEventBus.Instance.Subscribe<CardDrawEvent>(OnCardDraw);
            AnimationEventBus.Instance.Subscribe<CardUseEvent>(OnCardUse);
        }

        private void OnDisable()
        {
            AnimationEventBus.Instance.Unsubscribe<UnitMoveEvent>(OnUnitMove);
            AnimationEventBus.Instance.Unsubscribe<UnitDeployEvent>(OnUnitDeploy);
            AnimationEventBus.Instance.Unsubscribe<UnitDestroyEvent>(OnUnitDestroy);
            AnimationEventBus.Instance.Unsubscribe<UnitAttackEvent>(OnUnitAttack);
            AnimationEventBus.Instance.Unsubscribe<UnitDamageEvent>(OnUnitDamage);
            AnimationEventBus.Instance.Unsubscribe<UnitHealEvent>(OnUnitHeal);
            AnimationEventBus.Instance.Unsubscribe<UnitSwapEvent>(OnSwapUnit);

            AnimationEventBus.Instance.Unsubscribe<ApplyBuffEvent>(OnAddBuff);
            AnimationEventBus.Instance.Unsubscribe<RemoveBuffEvent>(OnRemoveBuff);

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
            
            vfxHandler.PlayMove(view.transform.position + Vector3.down * 0.2f);
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

            StartCoroutine(DeployUnit(view, cmd.duration));
        }

        private IEnumerator DeployUnit(UnitView view, float interval)
        {
            view.unitSprite.enabled = false;
            vfxHandler.PlayDeploy(view.gameObject.transform.position);

            yield return new WaitForSeconds(interval);

            view.unitSprite.enabled = true;
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

            view.unitAnimator.PlayDestroy(evt.cmd.duration);
            StartCoroutine(InvokeUnregister(view, cmd.duration + 0.1f));
        }       

        // 애니메이션 재생 시간동안 안전하도록 Unregister 유예
        private IEnumerator InvokeUnregister(BaseView view, float interval)
        {
            yield return new WaitForSeconds(interval);
            viewRegistry.Unregister(view.Id);
        }

        private void OnUnitAttack(UnitAttackEvent evt)
        {
            var cmd = evt.cmd;

            if (cmd == null)
                return;
            
            UnitView source = viewRegistry.Get(new ViewID(ViewType.Unit, cmd.source.id)) as UnitView;
            UnitView target = viewRegistry.Get(new ViewID(ViewType.Unit, cmd.target.id)) as UnitView;

            Vector3 targetPos = target != null ? target.transform.position : Vector3.zero;

            StartCoroutine(AttackEffects(source.gameObject.transform.position, targetPos, cmd.duration / 2));
        }

        private IEnumerator AttackEffects(Vector3 source, Vector3 target, float interval)
        {
            vfxHandler.PlayEyeLight(source);

            yield return new WaitForSeconds(interval);

            if (target != Vector3.zero)
                vfxHandler.PlayHit(target);
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
            view.SetCurHp(cmd.value);
        }

        private void OnUnitHeal(UnitHealEvent evt)
        {
            var cmd = evt.cmd;

            if (cmd == null)
                return;
            
            UnitView view = viewRegistry.Get(new ViewID(ViewType.Unit, cmd.target.id)) as UnitView;

            if (view == null)
                return;

            vfxHandler.PlayHeal(view.transform.position);
            view.SetCurHp(cmd.value);
        }

        private void OnSwapUnit(UnitSwapEvent evt)
        {
            var cmd = evt.cmd;

            if (cmd == null)
                return;

            UnitView view1 = viewRegistry.Get(new ViewID(ViewType.Unit,cmd.source.id)) as UnitView;
            UnitView view2 = viewRegistry.Get(new ViewID(ViewType.Unit,cmd.target.id)) as UnitView;

            var tmp = view1.transform.position;

            view1.transform.position = view2.transform.position;
            view2.transform.position = tmp; 
            
            vfxHandler.PlayMove(view2.transform.position + Vector3.down * 0.2f);
            vfxHandler.PlayMove(view1.transform.position + Vector3.down * 0.2f);
        }

        private void OnAddBuff(ApplyBuffEvent evt)
        {
            var cmd = evt.cmd;

            if (cmd == null)
                return;

            UnitView view = viewRegistry.Get(new ViewID(ViewType.Unit, cmd.target.id)) as UnitView;
            var buff = factory.ResolveBuff(cmd.extra, cmd.value);

            view.AddBuff(buff);
        }

        private void OnRemoveBuff(RemoveBuffEvent evt)
        {
            var cmd = evt.cmd;

            if (cmd == null)
                return;

            UnitView view = viewRegistry.Get(new ViewID(ViewType.Unit, cmd.target.id)) as UnitView;

            view.RemoveBuff(cmd.extra);
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