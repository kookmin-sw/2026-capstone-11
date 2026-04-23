using System;
using entity.targetable;
using events;
using events.client;
using ui.tooltip;
using UnityEngine;

namespace ui.view.card
{
    public enum VisualType
    {
        MyCard, // 정보를 볼 수 있는 자신의 카드
        OpponentCard, // 정보를 볼 수 없는 상대의 카드
    }

    /// <summary>
    /// 카드 뷰에 필요한 데이터 클래스
    /// </summary>
    public class CardViewData : BaseViewData
    {
        public VisualType visualType;

        public CardViewData(ViewID id,
                            ViewType type,
                            string cardId,
                            VisualType visualType) : base(id, type)
        {
            this.cardId = cardId;
            this.visualType = visualType;
        }
    }

    /// <summary>
    /// 카드 뷰의 공통 클래스
    /// </summary>
    public class CardView : BaseView, IHoverable
    {
        public CardViewData data;

        public override void Init(BaseViewData baseData, IEventBus eventBus)
        {
            base.Init(baseData, eventBus);
            data = (CardViewData)baseData;
        }

        public TooltipData GetTooltipData()
        {
            // 시점에 따라 유닛 카드 또는 스펠 카드 툴팁을 반환
            if (data.visualType == VisualType.MyCard)
            {
                return TooltipBuilder.CardTooltip(definition);
            }
            else // VisualType.OpponentCard
            {
                return TooltipBuilder.OpponentCardTooltip();
            }
        }

        public void OnSelected()
        {
            Debug.Log("Card selected: " + data.cardId);
        }

        public override void Subscribe()
        {
            eventBus.Subscribe<IClientEvents.CardSelectedEvent>(OnSelected);
        }

        private void OnSelected(IClientEvents.CardSelectedEvent @event)
        {
            throw new NotImplementedException();
        }

        public override void UnSubscribe()
        {
            eventBus.Unsubscribe<IClientEvents.CardSelectedEvent>(OnSelected);
        }
    }
}