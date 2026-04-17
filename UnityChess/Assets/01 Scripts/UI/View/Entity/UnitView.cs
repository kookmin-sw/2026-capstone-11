using UnityEngine;
using entity.targetable;
using ui.tooltip;
using events;
using events.server;
using events.client;
using Game.Network;
using core.data;

namespace ui.view.unit
{
    public enum MoveType
    {
        Pawn,
        Rook,
        Knight,
        Bishop,
        Queen,
        King
    }

    /// <summary>
    /// 유닛의 런타임 상태를 다루는 뷰 데이터
    /// </summary>
    public class UnitViewData : BaseViewData
    {
        

        // 동적 상태
        public int curAttack;
        public int curHP;

        // 보드 위에서의 위치
        public Vector2Int pos;

        public UnitViewData(ViewID id,
                            ViewType type,
                            string cardId,
                            int curAttack,
                            int curHP,
                            Vector2Int pos
                            ) : base(id, type)
        {
            this.cardId = cardId;

            this.curAttack = curAttack;
            this.curHP = curHP;

            this.pos = pos;
        }
    }

    public class UnitView : BaseView, IHoverable, ISelectable
    {
        public UnitViewData data;

        public override void Init(BaseViewData baseData, IEventBus eventBus)
        {
            base.Init(baseData, eventBus);
            data = (UnitViewData)baseData;

            // 유닛 뷰에게 필요한 이벤트 구독
            Subscribe();
        }

        // ITargetable 인터페이스 구현
        public TooltipData GetTooltipData()
        {
            return TooltipBuilder.UnitOnboardTooltip(definition, data);
        }

        public void OnSelected()
        {
            Debug.Log("Unit selected: " + data.cardId);
            
        }

        public void OnDisable()
        {
            // 유닛 뷰가 구독한 이벤트 해제
            UnSubscribe();
        }

        public override void Subscribe()
        {
            eventBus.Subscribe<IServerEvents.UnitMoveEvent>(OnUnitMove);
        }
    
        public override void UnSubscribe()
        {
            eventBus.Unsubscribe<IServerEvents.UnitMoveEvent>(OnUnitMove);
        }

        private void OnUnitMove(IServerEvents.UnitMoveEvent evt)
        {
            // TODO: evt에서 이동한 유닛의 ID와 위치를 받아서 해당 유닛 뷰의 위치를 업데이트
        }
    }
}
