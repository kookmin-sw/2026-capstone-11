using UnityEngine;
using entity.targetable;
using ui.tooltip;
using events;
using events.server;
using events.client;
using Game.Network;

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
        // 공통 유닛 정의
        public string name;
        public string className;
        public MoveType moveType;

        // 전투 관련 상태
        public int attack;
        public int maxHP;
        public int currentHP;

        public string traitsDesc; // 특성 설명 텍스트
        public int unitID;

        // 보드 위에서의 위치
        public Vector2Int pos;

        public UnitViewData(ViewID id,
                            ViewType type,
                            string name,
                            string className,
                            int attack,
                            int maxHP,
                            int currentHP,
                            string traitsDesc,
                            int unitID,
                            Vector2Int pos,
                            MoveType moveType) : base(id, type)
        {
            this.name = name;
            this.className = className;
            this.attack = attack;
            this.maxHP = maxHP;
            this.currentHP = currentHP;
            this.traitsDesc = traitsDesc;
            this.unitID = unitID;
            this.pos = pos;
            this.moveType = moveType;
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
            return TooltipBuilder.UnitOnboardTooltip(data);
        }

        public void OnSelected()
        {
            Debug.Log("Unit selected: " + data.name + " id: " + data.unitID);
            
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
            
        }
    }
}
